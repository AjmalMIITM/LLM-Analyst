import os
import json
import asyncio
import subprocess
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from playwright.async_api import async_playwright

app = FastAPI()

# --- CONFIGURATION ---
# You will set these in your deployment environment variables later
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MY_EMAIL = "24f2004489@ds.study.iitm.ac.in" 
MY_SECRET = "D2bUfDeHviRVcz6z6bUqTReloZ0R+7ggRlkuV/6/ea4="   

class QuizTask(BaseModel):
    email: str
    secret: str
    url: str

async def solve_quiz_loop(start_url: str):
    """
    The main loop:
    1. Scrape URL
    2. LLM writes code
    3. Execute code
    4. Submit
    5. If new URL, repeat
    """
    current_url = start_url
    
    # Limit recursion to avoid infinite loops
    for _ in range(5): 
        print(f"Processing URL: {current_url}")
        
        # 1. SCRAPE
        task_text = await scrape_page(current_url)
        print(f"Scraped task: {task_text[:100]}...")

        # 2. THINK (LLM) & 3. EXECUTE
        # We will implement this in the next step.
        # For now, let's just print.
        
        # 4. SUBMIT (Placeholder)
        # result = submit_answer(...)
        
        # 5. CHECK FOR NEXT URL
        # if 'url' in result: current_url = result['url']
        # else: break
        
        break # Stop after one loop for now

async def scrape_page(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        # Wait for the Javascript to decode the text
        try:
            # The prompt says content is often in body or #result
            await page.wait_for_selector("body", timeout=5000)
            content = await page.inner_text("body")
            return content
        except Exception as e:
            return f"Error scraping: {e}"
        finally:
            await browser.close()

@app.post("/analyze")
async def analyze(task: QuizTask, background_tasks: BackgroundTasks):
    # 1. Verify Secret
    if task.secret != MY_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    # 2. Start the solver in the background (so we can return 200 OK immediately)
    background_tasks.add_task(solve_quiz_loop, task.url)
    
    return {"message": "Quiz processing started", "status": "ok"}
