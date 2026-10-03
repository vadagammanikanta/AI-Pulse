"""
AI Pulse — FastAPI application factory.

Security note: The X-API-Key is handled server-side by FastAPI's
verify_api_key dependency.  The Next.js frontend must call its own
Route Handlers (/api/*), which attach the key before forwarding to this
API.  The key must NEVER appear in NEXT_PUBLIC_* env vars.

Admin routes (/admin/*) are excluded from the Next.js proxy entirely —
they are only accessible with the key directly from trusted contexts.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routers.admin import router as admin_router
from app.routers.feed import router as feed_router
from app.routers.items import router as items_router
from app.routers.items import saved_router
from app.routers.search import router as search_router
from app.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    # Register all secrets with the masking filter FIRST, before anything logs.
    from app.logging_config import configure_logging, register_secret
    configure_logging(settings.log_level)
    register_secret(settings.api_secret_key)
    register_secret(settings.groq_api_key)
    register_secret(settings.gemini_api_key)
    register_secret(settings.telegram_bot_token)

    db_path = settings.db_path
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA foreign_keys = ON")
        await init_db(conn)

    start_scheduler()
    logger.info("startup db=%s scheduler=running", db_path)
    yield
    # ── Shutdown ──
    stop_scheduler()
    logger.info("shutdown scheduler=stopped")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Pulse personal intelligence platform — API",
    lifespan=lifespan,
    # Docs are useful locally; disable in prod if desired
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    # Only allow localhost in dev; Next.js server-side proxy never uses CORS
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "PATCH"],
    allow_headers=["X-API-Key", "Content-Type"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(feed_router)
app.include_router(items_router)
app.include_router(saved_router)
app.include_router(search_router)
app.include_router(admin_router)

# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/health/ready", tags=["ops"])
async def health_ready():
    try:
        async with aiosqlite.connect(settings.db_path) as conn:
            await conn.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(exc)},
        )
