"""
Database initialisation and dependency helpers.

Uses raw aiosqlite — no ORM.  All tables are created by init_db().
The get_db() FastAPI dependency yields a single connection per request
with WAL mode and foreign-key enforcement enabled.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA cache_size = -32000;

-- ── App config ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS app_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ── Sources ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sources (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT    NOT NULL,
    type                   TEXT    NOT NULL DEFAULT 'rss'
                               CHECK (type IN ('rss','github','arxiv','huggingface','blog','api')),
    url                    TEXT    NOT NULL,
    feed_url               TEXT,
    active                 INTEGER NOT NULL DEFAULT 1,
    fetch_interval_minutes INTEGER NOT NULL DEFAULT 360,
    config_json            TEXT    NOT NULL DEFAULT '{}',
    source_weight          INTEGER NOT NULL DEFAULT 20
                               CHECK (source_weight BETWEEN 0 AND 30),
    last_fetched_at        TEXT,
    created_at             TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ── Raw items (immutable after insert; excerpt ≤ 500 chars) ────────────────
CREATE TABLE IF NOT EXISTS raw_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id   TEXT    NOT NULL,
    title         TEXT    NOT NULL,
    url           TEXT    NOT NULL,
    excerpt       TEXT,
    author        TEXT,
    published_at  TEXT,
    ingested_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    status        TEXT    NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','processing','processed',
                                        'duplicate','skipped','failed')),
    pre_score             INTEGER,
    failed_prompt_version TEXT,
    error_message         TEXT,
    attempts              INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_status      ON raw_items(status);
CREATE INDEX IF NOT EXISTS idx_raw_ingested    ON raw_items(ingested_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_source      ON raw_items(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_url         ON raw_items(url);

-- ── Items (processed; summaries + metadata only, no full text) ─────────────
CREATE TABLE IF NOT EXISTS items (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_item_id          INTEGER UNIQUE REFERENCES raw_items(id) ON DELETE SET NULL,
    source_id            INTEGER NOT NULL REFERENCES sources(id),
    title                TEXT    NOT NULL,
    url                  TEXT    NOT NULL,
    author               TEXT,
    published_at         TEXT,
    category             TEXT    NOT NULL DEFAULT 'news'
                             CHECK (category IN ('news','model','tool','api','paper','company')),
    importance_score     INTEGER NOT NULL DEFAULT 50
                             CHECK (importance_score BETWEEN 0 AND 100),
    importance_reason    TEXT,
    what_is_new          TEXT,
    why_it_matters       TEXT,
    who_should_care_json TEXT    NOT NULL DEFAULT '[]',
    how_to_use           TEXT,
    pro_tip              TEXT,
    learning_module_json TEXT    NOT NULL DEFAULT '{}',
    embedding            BLOB,
    embedding_model      TEXT,
    saved                INTEGER NOT NULL DEFAULT 0,
    validator_result     TEXT,
    processed_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_items_category  ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_score     ON items(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_saved     ON items(saved) WHERE saved = 1;
CREATE INDEX IF NOT EXISTS idx_items_url       ON items(url);

-- ── LLM cache (keyed by sha256 of "title|url") ────────────────────────────
CREATE TABLE IF NOT EXISTS llm_cache (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash      TEXT    NOT NULL UNIQUE,
    provider          TEXT    NOT NULL,
    model             TEXT    NOT NULL,
    output_json       TEXT    NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ── LLM daily usage (persisted; all calls including retries/fallbacks) ─────
CREATE TABLE IF NOT EXISTS llm_daily_usage (
    date     TEXT    NOT NULL,
    provider TEXT    NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date, provider)
);

-- ── Learning progress ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS learning_progress (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id      INTEGER NOT NULL UNIQUE REFERENCES items(id) ON DELETE CASCADE,
    status       TEXT    NOT NULL DEFAULT 'not_started'
                     CHECK (status IN ('not_started','in_progress','completed')),
    score        INTEGER CHECK (score BETWEEN 0 AND 100),
    started_at   TEXT,
    completed_at TEXT
);

-- ── Chat ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role           TEXT    NOT NULL CHECK (role IN ('user','assistant','system')),
    content        TEXT    NOT NULL,
    citations_json TEXT    NOT NULL DEFAULT '[]',
    created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_chat_msg_session ON chat_messages(session_id);

-- ── Saved prompts ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saved_prompts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    prompt_text  TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT 'general',
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ── Pipeline runs ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    finished_at         TEXT,
    items_ingested      INTEGER NOT NULL DEFAULT 0,
    items_deduped       INTEGER NOT NULL DEFAULT 0,
    items_skipped       INTEGER NOT NULL DEFAULT 0,
    items_llm_processed INTEGER NOT NULL DEFAULT 0,
    items_retried       INTEGER NOT NULL DEFAULT 0,
    filtered_items_log  TEXT    NOT NULL DEFAULT '[]',
    status              TEXT    NOT NULL DEFAULT 'running'
                            CHECK (status IN ('running','completed','failed')),
    error_message       TEXT
);

-- ── Items Full Text Search (FTS5) ──────────────────────────────────────────
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    title,
    what_is_new,
    why_it_matters,
    how_to_use,
    content='items',
    content_rowid='id'
);
"""

_SEED_CONFIG = """
INSERT OR IGNORE INTO app_config (key, value) VALUES
    ('embedding_model', :embedding_model),
    ('embedding_dims',  :embedding_dims),
    ('llm_provider',    :llm_provider),
    ('schema_version',  '1');
"""


async def init_db(conn: aiosqlite.Connection) -> None:
    """Create all tables and seed app_config. Idempotent."""
    await conn.executescript(_DDL)

    # Migration: Add failed_prompt_version column to raw_items if missing
    try:
        await conn.execute("ALTER TABLE raw_items ADD COLUMN failed_prompt_version TEXT")
    except aiosqlite.OperationalError:
        pass  # Column already exists

    # Migration: Add attempts column to raw_items if missing
    try:
        await conn.execute("ALTER TABLE raw_items ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
    except aiosqlite.OperationalError:
        pass  # Column already exists

    # Migration: Add validator_result column to items if missing
    try:
        await conn.execute("ALTER TABLE items ADD COLUMN validator_result TEXT")
    except aiosqlite.OperationalError:
        pass  # Column already exists

    # Migration: Populate FTS5 table for items missing from index
    try:
        await conn.execute("""
            INSERT INTO items_fts(rowid, title, what_is_new, why_it_matters, how_to_use)
            SELECT id, title, COALESCE(what_is_new, ''), COALESCE(why_it_matters, ''), COALESCE(how_to_use, '')
            FROM items
            WHERE id NOT IN (SELECT rowid FROM items_fts)
        """)
    except Exception as exc:
        logger.debug("fts_populate_skipped err=%s", exc)

    await conn.execute(
        _SEED_CONFIG,
        {
            "embedding_model": settings.embedding_model,
            "embedding_dims": str(settings.embedding_dims),
            "llm_provider": settings.llm_provider_order[0] if settings.llm_provider_order else "none",
        },
    )
    await conn.commit()
    logger.info("Database initialised at %s", settings.db_path)


async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """FastAPI dependency — yields a per-request aiosqlite connection."""
    db_path = settings.db_path
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA foreign_keys = ON")
        yield conn
