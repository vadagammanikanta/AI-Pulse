# AI Pulse — Phase 1A Backend

## Quick start

```bash
cd api
cp .env.example .env          # fill GROQ_API_KEY / GEMINI_API_KEY + API_SECRET_KEY

pip install -e ".[dev]"       # installs all deps incl. sentence-transformers

python -m app.tools.seed_sources   # insert 3 RSS sources into DB
python -m app.pipeline.run         # run pipeline once (ingests + summarises)
uvicorn app.main:app --reload      # starts API on :8000
```

## Pipeline

```
3 RSS sources
  → ingest (title + url + excerpt ≤500 chars only)
  → dedup (URL norm + RapidFuzz)
  → pre-score (heuristic, 0-100, no LLM cost)
  → top-20 filter
  → LLM summarize (Groq→Gemini→Ollama fallback, cache, per-item retry)
  → embed (sentence-transformers, local)
  → SQLite
```

## API Key security

- `API_SECRET_KEY` lives only in `api/.env` (server-side)
- Next.js frontend calls its own Route Handlers, which attach the key
- Admin routes (`/admin/*`) are **not** proxied via Next.js

## Run tests

```bash
pytest tests/ -v
```

## Manually trigger pipeline

```bash
curl -X POST http://localhost:8000/admin/pipeline/run \
     -H "X-API-Key: $API_SECRET_KEY"
```

## Check stats

```bash
curl http://localhost:8000/admin/stats \
     -H "X-API-Key: $API_SECRET_KEY"
```

## Tune pre-score threshold

Items filtered out are logged with full breakdown:
```json
{"raw_item_id": 42, "title": "...", "pre_score": 27,
 "breakdown": {"source_weight": 10, "keyword_score": 7, "recency_score": 5, "length_score": 5}}
```
Adjust `PRE_SCORE_THRESHOLD` in `.env` (default: 40).
