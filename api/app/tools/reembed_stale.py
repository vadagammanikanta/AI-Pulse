"""
One-time re-embedding tool.

Finds all rows in `items` where `embedding_model` is null or does not match
the current `settings.embedding_model` (e.g. created during fallback mode),
re-embeds the item using the ONNX neural model, and updates SQLite.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import aiosqlite

from app.ai.embedder import embed_text
from app.config import settings
from app.database import init_db

logger = logging.getLogger(__name__)


async def reembed_all(db: aiosqlite.Connection | None = None) -> int:
    own = db is None
    if own:
        db_path = settings.db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        await conn_init(db)

    try:
        async with db.execute(
            """
            SELECT id, title, what_is_new, embedding_model
            FROM items
            WHERE embedding_model IS NULL OR embedding_model != ?
            """,
            (settings.embedding_model,),
        ) as cur:
            stale_rows = await cur.fetchall()

        if not stale_rows:
            logger.info("reembed_stale: All items already up to date with model %s", settings.embedding_model)
            print(f"Re-embedding: All items already up to date with model {settings.embedding_model}.")
            return 0

        logger.info("reembed_stale: Found %d stale rows to re-embed", len(stale_rows))
        print(f"Found {len(stale_rows)} items with stale/fallback embeddings. Re-embedding with ONNX {settings.embedding_model}...")

        updated_count = 0
        for row in stale_rows:
            text = f"{row['title']}. {row['what_is_new'] or ''}"
            new_embedding = await embed_text(text)
            await db.execute(
                """
                UPDATE items
                SET embedding = ?, embedding_model = ?
                WHERE id = ?
                """,
                (new_embedding, settings.embedding_model, row["id"]),
            )
            updated_count += 1

        await db.commit()
        logger.info("reembed_stale: Successfully re-embedded %d items", updated_count)
        print(f"Successfully re-embedded {updated_count} items with ONNX {settings.embedding_model}.")
        return updated_count

    finally:
        if own and db:
            await db.close()


async def conn_init(db: aiosqlite.Connection):
    await db.execute("PRAGMA foreign_keys = ON")
    await init_db(db)


def cli_reembed() -> None:
    logging.basicConfig(level="INFO")
    asyncio.run(reembed_all())


if __name__ == "__main__":
    cli_reembed()
