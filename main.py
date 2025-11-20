# main.py
import os
import sys
import json
import subprocess
import re
import asyncio
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
    """Extracts code from markdown blocks"""
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1)
    return text

def extract_json(text):
    """Extracts JSON object from text, ignoring chatty intros"""
    # Finds the first { and the last }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
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
        
        # 1. SCRAPE (Updated to wait for Network Idle)
        task_text = ""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                # wait_until='networkidle' ensures JS has finished loading content
                await page.goto(current_url, wait_until="networkidle", timeout=15000)
                
                # Fallback: sometimes networkidle is too slow, wait for body
                await page.wait_for_selector("body", timeout=5000)
                
                task_text = await page.inner_text("body")
            except Exception as e:
                print(f"Scraping failed: {e}")
                break
            finally:
                await browser.close()

        print(f"Scraped Instructions: {task_text[:100]}...")

        # 2. ASK LLM TO WRITE CODE
        prompt = f"""
        You are an Expert Python Data Analyst. 
        
        CONTEXT:
        - I am currently visiting this URL: {current_url}
        - The page content is below.
        
        PAGE CONTENT:
        "{task_text}"
        
        YOUR GOAL:
        Write a Python script to solve the user's question.
        
        REQUIREMENTS:
        1. Identify the Data Source. If the link is relative (e.g. '/data.csv'), construct the full URL using the base URL: {current_url}
        2. Download the data (using requests) and process it (pandas, etc).
        3. Calculate the final answer.
        4. PRINT the answer to stdout. 
        
        CONSTRAINTS:
        - Do not use input().
        - Do not use browser automation (selenium/playwright) inside the script.
        - Output ONLY executable Python code inside ```python ``` blocks.
        """

        completion = client.chat.completions.create(
            model=MODEL_NAME, 
            messages=[{"role": "system", "content": "You are a helpful coder."},
                      {"role": "user", "content": prompt}]
        )
        
        generated_code = completion.choices[0].message.content
        clean_code = extract_python_code(generated_code)
        
        print("Executing Generated Code...")
        
        # 3. EXECUTE CODE
        execution_output = execute_python_code(clean_code)
        print(f"Code Output: {execution_output}")

        # 4. SUBMIT ANSWER (Robust JSON Parsing)
        submission_prompt = f"""
        You are the Agent Controller. You must format the final submission.
        
        CONTEXT:
        - Current Page URL: {current_url}
        - Original Task Instructions: "{task_text}"
        - Result from Code Execution: "{execution_output}"
        - My Email: {MY_EMAIL}
        - My Secret: {MY_SECRET}
        
        YOUR JOB:
        1. **Find the Submission URL**: 
           - If the URL is relative (e.g. '/submit'), resolve it to an absolute URL based on Current Page URL.
           
        2. **Construct the JSON Payload**:
           - Standard keys: "email", "secret", "url" (the task url), "answer".
           - Use the "Result from Code Execution" as the "answer".
        
        OUTPUT FORMAT:
        Return PURE JSON with exactly two top-level keys: "post_url" and "payload".
        
        Example:
        {{
            "post_url": "https://example.com/submit",
            "payload": {{ "email": "...", "answer": ... }}
        }}
        """
        
        submission_completion = client.chat.completions.create(
            model=MODEL_NAME, 
            messages=[{"role": "user", "content": submission_prompt}]
        )
        
        try:
            # ROBUST JSON EXTRACTION
            raw_response = submission_completion.choices[0].message.content
            json_str = extract_json(raw_response) # Uses Regex to find { }
            
            decision_data = json.loads(json_str)
            
            submit_url = decision_data.get("post_url")
            payload = decision_data.get("payload")
            
            print(f"Agent decided to submit to: {submit_url}")
            
            if submit_url and payload:
                response = requests.post(submit_url, json=payload)
                print(f"Submission Response: {response.text}")
                
                try:
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
                except:
                    print("Response was not JSON.")
                    break
            else:
                print("LLM failed to determine submission URL or payload.")
                break
                
        except Exception as e:
            print(f"Error parsing Agent decision: {e}")
            print(f"Raw LLM Output: {raw_response}")
            break

@app.post("/analyze")
async def analyze(task: QuizTask, background_tasks: BackgroundTasks):
    if task.secret != MY_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    background_tasks.add_task(solve_quiz_loop, task.url)
    return {"message": "Agent activated", "status": "ok"}
