FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for Playwright/Chrome
RUN apt-get update && apt-get install -y \
    wget gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the browsers
RUN playwright install --with-deps chromium

COPY . .

# Run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
