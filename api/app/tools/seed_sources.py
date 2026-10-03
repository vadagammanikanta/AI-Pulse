"""
Seed the sources table with 3 bootstrap RSS feeds.

Run once:
    python -m app.tools.seed_sources
or:
    seed   (if installed via pyproject.toml [scripts])
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import aiosqlite

from app.config import settings
from app.database import init_db

logger = logging.getLogger(__name__)

SOURCES = [
    {
        "name": "OpenAI Blog",
        "type": "rss",
        "url": "https://openai.com/blog",
        "feed_url": "https://openai.com/blog/rss.xml",
        "source_weight": 30,
    },
    {
        "name": "arXiv cs.AI",
        "type": "rss",
        "url": "https://arxiv.org/list/cs.AI/recent",
        "feed_url": "https://rss.arxiv.org/rss/cs.AI",
        "source_weight": 25,
    },
    {
        "name": "Hugging Face Blog",
        "type": "rss",
        "url": "https://huggingface.co/blog",
        "feed_url": "https://huggingface.co/blog/feed.xml",
        "source_weight": 25,
    },
]


async def seed(db: aiosqlite.Connection | None = None) -> None:
    own = db is None
    if own:
        db_path = settings.db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await init_db(db)

    try:
        for src in SOURCES:
            await db.execute(
                """
                INSERT OR IGNORE INTO sources
                    (name, type, url, feed_url, source_weight)
                VALUES (?, ?, ?, ?, ?)
                """,
                (src["name"], src["type"], src["url"], src["feed_url"], src["source_weight"]),
            )
        await db.commit()
        logger.info("sources_seeded count=%d", len(SOURCES))
        print(f"Seeded {len(SOURCES)} sources.")
    finally:
        if own and db:
            await db.close()


def cli_seed() -> None:
    logging.basicConfig(level="INFO")
    asyncio.run(seed())


if __name__ == "__main__":
    cli_seed()
