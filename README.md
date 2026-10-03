# AI Pulse — Intelligence & Personal Learning Platform

AI Pulse is a single-user, ₹0-cost personal AI intelligence platform that ingests, scores, de-duplicates, summarizes, and generates 5-minute interactive skill lessons for AI releases, papers, tools, and company announcements.

---

## 🚀 Key Features

- **Multi-Source Ingestion**: Ingests RSS feeds, arXiv papers, GitHub releases, and tech blogs.
- **Pre-Scoring & Top-N Selection**: Lowers API costs by filtering low-signal items before calling LLMs.
- **Provider Fallback Chain**: Tiered LLM router (Groq → Gemini → Ollama) with daily rate limiting & prompt version hashing.
- **Local ONNX Sentence Embeddings**: 384-dimensional `all-MiniLM-L6-v2` embeddings via ONNX Runtime & Hugging Face Tokenizers (no PyTorch overhead).
- **Hybrid Search**: Combines SQLite FTS5 keyword search and vector cosine similarity.
- **Dynamic 3-Factor Feed Ranking**: Ranks items using `0.6 * (importance/100) + 0.3 * interest_match + 0.1 * recency_decay`.
- **Telegram Daily Digest**: Delivers the top 5 updates directly to your Telegram chat.
- **PWA Web App**: Built with Next.js App Router, Tailwind CSS, dark mode, and Edge-signed HMAC cookie authentication.

---

## ⏰ Automated Scheduling & Windows Task Scheduler Setup

AI Pulse supports both **in-process scheduling** (via APScheduler) and **external OS scheduling** (via Windows Task Scheduler or cron).

### 1. In-Process APScheduler (Default)
In `api/.env`:
```env
ENABLE_IN_PROCESS_SCHEDULER=true
PIPELINE_INTERVAL_HOURS=6
TELEGRAM_DIGEST_TIME="08:00"
TELEGRAM_DIGEST_TIMEZONE="Asia/Kolkata"
```

### 2. Windows Task Scheduler Setup (Optional External Scheduling)
If you prefer running pipeline cycles and Telegram digests independently of the FastAPI server:

1. Set `ENABLE_IN_PROCESS_SCHEDULER=false` in `api/.env`.
2. Open **Task Scheduler** in Windows (`taskschd.msc`).
3. Click **Create Basic Task...**:

#### A. Pipeline Execution Task (Every 6 Hours)
- **Name**: `AI Pulse Pipeline Run`
- **Trigger**: Daily, repeat task every **6 hours** for a duration of 1 day (indefinitely).
- **Action**: Start a program
- **Program/script**: `python.exe` (or path to your Python executable)
- **Add arguments**: `-m app.pipeline.run`
- **Start in**: `D:\PROJECTS\AI\ai-pulse\api`

#### B. Daily Telegram Digest Task (Every Day at 08:00 AM IST)
- **Name**: `AI Pulse Telegram Digest`
- **Trigger**: Daily at **08:00 AM** (`Asia/Kolkata` / Local System Time).
- **Action**: Start a program
- **Program/script**: `python.exe`
- **Add arguments**: `-m app.tools.send_digest`
- **Start in**: `D:\PROJECTS\AI\ai-pulse\api`

---

## 🛠️ Manual CLI Commands

Run pipeline on demand:
```bash
cd api
python -m app.pipeline.run
```

Send Telegram digest manually:
```bash
cd api
python -m app.tools.send_digest
```

Run test suite:
```bash
cd api
pytest
```
