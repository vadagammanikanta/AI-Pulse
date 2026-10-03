"""
Shared pytest fixtures.

All tests use an isolated SQLite temp-file database.
The FastAPI app's get_db dependency is overridden to use the same connection,
so the app and test share state without conflicts.
"""
from __future__ import annotations

import os
from pathlib import Path

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

# Set env before any app imports so pydantic-settings picks them up
os.environ.setdefault("API_SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("GROQ_API_KEY", "")   # not set → provider skipped
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("LLM_PROVIDER_ORDER", '["ollama"]')  # valid JSON array for pydantic-settings


@pytest.fixture
async def db(tmp_path: Path):
    """Isolated in-file SQLite database per test."""
    from app.database import init_db

    db_path = str(tmp_path / "test.db")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    # Re-import settings after env change
    import importlib
    import app.config as cfg_mod
    importlib.reload(cfg_mod)

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await init_db(conn)
        yield conn


@pytest.fixture
async def seeded_db(db: aiosqlite.Connection):
    """Database with 3 test sources seeded."""
    await db.execute(
        """
        INSERT INTO sources (name, type, url, feed_url, source_weight)
        VALUES
          ('OpenAI Blog',      'rss', 'https://openai.com/blog',           'https://openai.com/blog/rss.xml',       30),
          ('Anthropic News',   'rss', 'https://www.anthropic.com/news',    'https://www.anthropic.com/rss.xml',     30),
          ('HuggingFace Blog', 'rss', 'https://huggingface.co/blog',       'https://huggingface.co/blog/feed.xml',  25)
        """
    )
    await db.commit()
    yield db


@pytest.fixture
async def client(seeded_db: aiosqlite.Connection):
    """Async HTTP client for the FastAPI app, connected to the test database."""
    from app.main import app
    from app.database import get_db

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-secret-key-for-pytest"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def unauthed_client(seeded_db: aiosqlite.Connection):
    """Client without API key — for testing 403 responses."""
    from app.main import app
    from app.database import get_db

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
