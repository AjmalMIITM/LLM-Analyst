# main.py
import os
import sys
import json
import subprocess
import re
import asyncio
import base64
import requests 
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from playwright.async_api import async_playwright
from openai import OpenAI

app = FastAPI()

# --- CONFIGURATION ---
AIPIPE_TOKEN = os.environ.get("AIPIPE_TOKEN") or os.environ.get("OPENAI_API_KEY")

MY_EMAIL = "24f2004489@ds.study.iitm.ac.in" 
MY_SECRET = "D2bUfDeHviRVcz6z6bUqTReloZ0R+7ggRlkuV/6/ea4="    

client = OpenAI(
    api_key=AIPIPE_TOKEN,
    base_url="https://aipipe.org/openrouter/v1"
)

MODEL_NAME = "anthropic/claude-3.7-sonnet"

class QuizTask(BaseModel):
    email: str
    secret: str
    url: str

def extract_python_code(text):
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if match: return match.group(1)
    return text

def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match: return match.group(0)
    return text

def execute_python_code(code):
    try:
        with open("solver.py", "w") as f:
            f.write(code)
        result = subprocess.run(
            [sys.executable, "solver.py"], 
            capture_output=True, 
            text=True, 
            timeout=60 
        )
        return result.stdout + "\n" + result.stderr
    except Exception as e:
        return str(e)

async def solve_quiz_loop(start_url: str):
    current_url = start_url
    
    for i in range(5): 
        print(f"--- Step {i+1}: Processing {current_url} ---")
        
        # 1. SCRAPE & SCREENSHOT
        task_text = ""
        screenshot_b64 = ""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(current_url, wait_until="networkidle", timeout=15000)
                await page.wait_for_timeout(4000) # Wait for JS/Images
                await page.wait_for_selector("body", timeout=5000)
                
                # Get Text
                task_text = await page.inner_text("body")
                
                # Get Screenshot (Vision)
                screenshot_bytes = await page.screenshot(format="jpeg", quality=50)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                
            except Exception as e:
                print(f"Scraping failed: {e}")
                break
            finally:
                await browser.close()

        print(f"Scraped Instructions (Text): {task_text[:100]}...")

        # 2. ASK LLM (WITH VISION)
        # We construct a message with both Text and Image
        messages = [
            {"role": "system", "content": "You are an Expert Python Data Analyst. Use the attached Screenshot and Text to solve the task."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
                        CONTEXT:
                        - URL: {current_url}
                        - Email: "{MY_EMAIL}"
                        - Page Text: "{task_text}"
                        
                        YOUR GOAL:
                        1. Look at the SCREENSHOT to understand the question (especially if text is empty).
                        2. If the page asks to download data, write Python requests code to download it.
                        3. Calculate the answer.
                        4. PRINT the answer to stdout.
                        
                        CRITICAL:
                        - Resolve relative links using base URL: {current_url}
                        - Use variable `email = "{MY_EMAIL}"`
                        - Output ONLY executable Python code inside ```python``` blocks.
                        """
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{screenshot_b64}"
                        }
                    }
                ]
            }
        ]

        completion = client.chat.completions.create(
            model=MODEL_NAME, 
            messages=messages
        )
        
        clean_code = extract_python_code(completion.choices[0].message.content)
        print("Executing Generated Code...")
        
        # 3. EXECUTE CODE
        execution_output = execute_python_code(clean_code)
        print(f"Code Output: {execution_output}")

        # Short Circuit
        if '"correct": true' in execution_output or '"correct":true' in execution_output:
            print("Internal script solved it. Jumping to next URL...")
            try:
                output_json = extract_json(execution_output)
                response_data = json.loads(output_json)
                next_url = response_data.get("url")
                if next_url:
                    current_url = next_url
                    continue 
                else:
                    print("Quiz Completed Successfully!")
                    break
            except:
                pass
        
        # 4. SUBMIT ANSWER
        submission_prompt = f"""
        You are the Agent Controller.
        
        CONTEXT:
        - URL: {current_url}
        - Code Result: "{execution_output}"
        - Email: {MY_EMAIL}
        - Secret: {MY_SECRET}
        
        YOUR JOB:
        1. Find Submission URL.
        2. Construct Payload: {{"email": "{MY_EMAIL}", "secret": "{MY_SECRET}", "url": "...", "answer": ...}}
           - Use the content of the Result as the answer.
        
        OUTPUT: PURE JSON with keys "post_url" and "payload".
        """
        
        submission_completion = client.chat.completions.create(
            model=MODEL_NAME, 
            messages=[{"role": "user", "content": submission_prompt}]
        )
        
        try:
            raw_response = submission_completion.choices[0].message.content
            json_str = extract_json(raw_response)
            decision_data = json.loads(json_str)
            
            submit_url = decision_data.get("post_url")
            payload = decision_data.get("payload")
            
            print(f"Agent decided to submit to: {submit_url}")
            print(f"Payload: {json.dumps(payload)}") # Log payload for debugging
            
            if submit_url and payload:
                response = requests.post(submit_url, json=payload)
                print(f"Submission Response: {response.text}")
                
                response_data = response.json()
                if response_data.get("correct") is True:
                    next_url = response_data.get("url")
                    if next_url:
                        current_url = next_url 
                    else:
                        print("Quiz Completed Successfully!")
                        break
                else:
                    print("Answer incorrect. Retrying not implemented.")
                    break
            else:
                print("LLM failed to determine submission URL or payload.")
                break
        except Exception as e:
            print(f"Error parsing Agent decision: {e}")
            break

@app.post("/analyze")
async def analyze(task: QuizTask, background_tasks: BackgroundTasks):
    if task.secret != MY_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    background_tasks.add_task(solve_quiz_loop, task.url)
    return {"message": "Agent activated", "status": "ok"}
