# YouTube AI Summarizer

A Flask and JavaScript web application that extracts YouTube transcripts and generates AI-powered summaries with key takeaways.

## Features

- Extracts transcripts from YouTube videos
- Generates summaries with Gemini AI
- Supports short, medium, and detailed summary lengths
- Caches summaries by video and length to avoid repeated AI usage
- Stores summary history in PostgreSQL or local SQLite
- Provides a simple browser-based frontend

## Project Structure

```text
backend/       Flask API and services
 database/      PostgreSQL schema and local SQLite data
frontend/      Static browser interface
```

## Requirements

- Python 3.10 or newer
- A Gemini API key for AI-generated summaries
- Optional Neon/PostgreSQL connection string

## Configuration

Create `backend/.env` using `backend/.env.example` as a template:

```env
PORT=5000
FLASK_ENV=development
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
```

Keep `backend/.env` private. It is excluded from Git.

## Run Locally

From the project directory in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Start the backend in one terminal:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe app.py
```

Start the frontend in another terminal:

```powershell
Set-Location frontend
..\.venv\Scripts\python.exe -m http.server 8080
```

Open the application at:

<http://127.0.0.1:8080>

Backend health check:

<http://127.0.0.1:5000/api/health>

## GitHub

Repository: <https://github.com/ShrujanaVangari/Youtube-Summarizer>
