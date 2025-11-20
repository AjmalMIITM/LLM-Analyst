# main.py
import os
import sys
import json
import subprocess
import re
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from playwright.async_api import async_playwright
from openai import OpenAI

app = FastAPI()

# --- CONFIGURATION ---
# These will come from Render's Environment Variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MY_EMAIL = "24f2004489@ds.study.iitm.ac.in" 
MY_SECRET = "D2bUfDeHviRVcz6z6bUqTReloZ0R+7ggRlkuV/6/ea4="    

client = OpenAI(api_key=OPENAI_API_KEY)

class QuizTask(BaseModel):
    email: str
    secret: str
    url: str

def extract_python_code(llm_text):
    """Extracts code from markdown blocks in LLM response"""
    match = re.search(r"```python\n(.*?)```", llm_text, re.DOTALL)
    if match:
        return match.group(1)
    return llm_text # Fallback: assume the whole text is code if no blocks

def execute_python_code(code):
    """Runs the extracted code and captures output"""
    try:
        # Write code to a temporary file
        with open("solver.py", "w") as f:
            f.write(code)
        
        # Run it
        result = subprocess.run(
            [sys.executable, "solver.py"], 
            capture_output=True, 
            text=True, 
            timeout=60 # 1 minute timeout for the script
        )
        return result.stdout + "\n" + result.stderr
    except Exception as e:
        return str(e)

async def solve_quiz_loop(start_url: str):
    current_url = start_url
    
    # Limit recursion to 3 steps to avoid infinite loops
    for i in range(3): 
        print(f"--- Step {i+1}: Processing {current_url} ---")
        
        # 1. SCRAPE THE PAGE
        task_text = ""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(current_url)
                # Wait for body to ensure JS runs
                await page.wait_for_selector("body", timeout=10000)
                task_text = await page.inner_text("body")
            except Exception as e:
                print(f"Scraping failed: {e}")
                break
            finally:
                await browser.close()

        print(f"Scraped Instructions: {task_text[:100]}...")

        # 2. ASK LLM TO WRITE CODE
        prompt = f"""
        You are a Python Data Analyst. Here is a task description scraped from a website:
        
        "{task_text}"
        
        Your Goal:
        1. Identify the Question and the Data Source (URL).
        2. Identify the Submission URL (it is mentioned in the text).
        3. Write a COMPLETE Python script to:
           - Download the data (using requests, pandas, etc).
           - Perform the analysis.
           - PRINT the answer to stdout.
           - If the answer is JSON, print valid JSON.
        
        CRITICAL:
        - Do not use input().
        - Do not use browser automation (selenium/playwright) inside your script; use requests/pandas.
        - Output ONLY the python code inside ```python ``` blocks.
        """

        completion = client.chat.completions.create(
            model="gpt-4o-mini", # Use gpt-4o if you have budget, mini is cheaper
            messages=[{"role": "system", "content": "You are a helpful coder."},
                      {"role": "user", "content": prompt}]
        )
        
        generated_code = completion.choices[0].message.content
        clean_code = extract_python_code(generated_code)
        
        print("Executing Generated Code...")
        
        # 3. EXECUTE THE CODE
        execution_output = execute_python_code(clean_code)
        print(f"Code Output: {execution_output}")

        # 4. SUBMIT ANSWER (The Agentic Part)
        # We now ask the LLM to look at the Output and Submit it.
        # This is a "Reflection" step.
        
        submission_prompt = f"""
        I have executed the analysis code.
        
        Original Task: {task_text}
        Code Execution Output: {execution_output}
        
        Your Goal:
        Construct the JSON payload to submit.
        The format usually requires: "email", "secret", "url", "answer".
        
        Return ONLY the JSON object.
        """
        
        submission_completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": submission_prompt}]
        )
        
        try:
            # Extract JSON from LLM response
            json_str = submission_completion.choices[0].message.content
            # Cleanup markdown if present
            json_str = json_str.replace("```json", "").replace("```", "").strip()
            payload = json.loads(json_str)
            
            # Ensure email/secret are correct
            payload["email"] = MY_EMAIL
            payload["secret"] = MY_SECRET
            
            # Find the submit URL from the text (using Regex for safety)
            # The text usually says "Post your answer to https://..."
            submit_url_match = re.search(r"https?://[^\s]+submit", task_text)
            if submit_url_match:
                submit_url = submit_url_match.group(0)
                
                # POST THE SUBMISSION
                response = requests.post(submit_url, json=payload)
                print(f"Submission Response: {response.text}")
                
                response_data = response.json()
                if response_data.get("correct") is True:
                    next_url = response_data.get("url")
                    if next_url:
                        current_url = next_url # RECURSION: Go to next level
                    else:
                        print("Quiz Completed Successfully!")
                        break
                else:
                    print("Answer incorrect, retrying not implemented yet.")
                    break
            else:
                print("Could not find submission URL in text.")
                break
                
        except Exception as e:
            print(f"Error during submission parsing: {e}")
            break

@app.post("/analyze")
async def analyze(task: QuizTask, background_tasks: BackgroundTasks):
    if task.secret != MY_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    # Run the heavy lifting in background so we respond 200 OK instantly
    background_tasks.add_task(solve_quiz_loop, task.url)
    
    return {"message": "Agent activated", "status": "ok"}
