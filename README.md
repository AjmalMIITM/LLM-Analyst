# LLM Analysis - Autonomous Quiz Solver Agent

An intelligent, autonomous agent built with LangGraph and LangChain that solves data-related quizzes involving web scraping, data processing, analysis, and visualization tasks. The system uses Google's Gemini 2.5 Flash model to orchestrate tool usage and make decisions.

##  Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Tools &amp; Capabilities](#tools--capabilities)
- [Docker Deployment](#docker-deployment)
- [How It Works](#how-it-works)
- [License](#license)

##  Overview

This project was developed for the TDS (Tools in Data Science) course project, where the objective is to build an application that can autonomously solve multi-step quiz tasks involving:

- **Data sourcing**: Scraping websites, calling APIs, downloading files
- **Data preparation**: Cleaning text, PDFs, and various data formats
- **Data analysis**: Filtering, aggregating, statistical analysis, ML models
- **Data visualization**: Generating charts, narratives, and presentations

The system receives quiz URLs via a REST API, navigates through multiple quiz pages, solves each task using LLM-powered reasoning and specialized tools, and submits answers back to the evaluation server.

##  Architecture

The project uses a **LangGraph state machine** architecture with the following components:

```
┌─────────────┐
│   FastAPI   │  ← Receives POST requests with quiz URLs
│   Server    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Agent     │  ← LangGraph orchestrator with Gemini 2.5 Flash
│   (LLM)     │
└──────┬──────┘
       │
       ├────────────┬────────────┬─────────────┬──────────────┐
       ▼            ▼            ▼             ▼              ▼
   [Scraper]   [Downloader]  [Code Exec]  [POST Req]  [Add Deps]
```

### Key Components:

1. **FastAPI Server** (`main.py`): Handles incoming POST requests, validates secrets, and triggers the agent
2. **LangGraph Agent** (`agent.py`): State machine that coordinates tool usage and decision-making
3. **Tools Package** (`tools/`): Modular tools for different capabilities
4. **LLM**: Google Gemini 2.5 Flash with rate limiting (9 requests per minute)

##  Features

-  **Autonomous multi-step problem solving**: Chains together multiple quiz pages
-  **Dynamic JavaScript rendering**: Uses Playwright for client-side rendered pages
-  **Code generation & execution**: Writes and runs Python code for data tasks
-  **Flexible data handling**: Downloads files, processes PDFs, CSVs, images, etc.
-  **Self-installing dependencies**: Automatically adds required Python packages
-  **Robust error handling**: Retries failed attempts within time limits
-  **Docker containerization**: Ready for deployment on HuggingFace Spaces or cloud platforms
-  **Rate limiting**: Respects API quotas with exponential backoff

##  Project Structure

```
LLM-Analysis-TDS-Project-2/
├── agent.py                    # LangGraph state machine & orchestration
├── main.py                     # FastAPI server with /solve endpoint
├── pyproject.toml              # Project dependencies & configuration
├── Dockerfile                  # Container image with Playwright
├── .env                        # Environment variables (not in repo)
├── tools/
│   ├── __init__.py
│   ├── web_scraper.py          # Playwright-based HTML renderer
│   ├── code_generate_and_run.py # Python code executor
│   ├── download_file.py        # File downloader
│   ├── send_request.py         # HTTP POST tool
│   └── add_dependencies.py     # Package installer
└── README.md
```
