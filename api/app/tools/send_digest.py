"""
CLI tool to trigger Telegram daily digest manually.

Usage:
  python -m app.tools.send_digest
"""
from __future__ import annotations

import asyncio
import logging
import sys

import aiosqlite

from app.config import settings
from app.database import init_db
from app.notifications.telegram import send_telegram_digest

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    db_path = settings.db_path
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await init_db(db)
        
        logger.info("Executing Telegram digest dispatch...")
        sent = await send_telegram_digest(db)
        if sent:
            logger.info("Telegram digest successfully sent!")
        else:
            logger.info("Telegram digest skipped (credentials unset or no items).")


def cli_entry() -> None:
    asyncio.run(main())
    sys.exit(0)


if __name__ == "__main__":
    cli_entry()
