"""
Telegram daily digest notification module.

Sends top 5 items by feed_score to Telegram channel/chat.
Skips silently if telegram_bot_token or telegram_chat_id are unset.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx

from app.config import settings
from app.pipeline.ranker import compute_feed_score

if TYPE_CHECKING:
    import aiosqlite

logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown format."""
    if not text:
        return ""
    chars = ["_", "*", "`", "["]
    for c in chars:
        text = text.replace(c, f"\\{c}")
    return text


async def send_telegram_digest(db: "aiosqlite.Connection") -> bool:
    """
    Fetch top 5 items by feed score and send digest to Telegram.
    Returns True if sent, False if skipped or failed.
    Protected by cross-process ProcessFileLock.
    """
    from app.locks import ProcessFileLock
    file_lock = ProcessFileLock("data/digest.lock")
    if not file_lock.acquire():
        logger.warning("telegram_digest_skip_locked — another process is sending the digest")
        return False

    try:
        token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id

        if not token or not chat_id:
            logger.debug("telegram_digest_skipped — telegram_bot_token or telegram_chat_id unset")
            return False

        # Fetch active items
        query = """
            SELECT i.*, s.name AS source_name
            FROM items i
            JOIN sources s ON i.source_id = s.id
            ORDER BY i.published_at DESC
            LIMIT 100
        """
        async with db.execute(query) as cur:
            rows = await cur.fetchall()

        if not rows:
            logger.info("telegram_digest_skipped — no items in database")
            return False

        now_dt = datetime.now(timezone.utc)
        scored_items = []

        for r in rows:
            text_for_kws = f"{r['title']} {r['what_is_new'] or ''} {r['why_it_matters'] or ''}"
            score, _ = compute_feed_score(
                importance_score=r["importance_score"],
                category=r["category"],
                text_for_keywords=text_for_kws,
                published_at_str=r["published_at"],
                now_dt=now_dt,
            )
            scored_items.append((score, r))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        top_5 = scored_items[:5]

        # Build digest text
        lines = ["🤖 *AI Pulse Daily Digest*", ""]
        for idx, (score, r) in enumerate(top_5, 1):
            title = escape_markdown(r["title"].strip())
            why = escape_markdown((r["why_it_matters"] or r["what_is_new"] or "").strip())
            url = r["url"].strip()
            lines.append(f"{idx}\\. [{title}]({url})")
            lines.append(f"💡 *Why it matters:* {why}")
            lines.append("")

        message_text = "\n".join(lines)
        telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                telegram_url,
                json={
                    "chat_id": chat_id,
                    "text": message_text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False,
                },
            )
            if resp.status_code == 200:
                logger.info("telegram_digest_sent items_count=%d", len(top_5))
                return True
            else:
                logger.warning(
                    "telegram_digest_failed status=%d body=%s",
                    resp.status_code,
                    resp.text,
                )
                return False
    except Exception as exc:
        logger.warning("telegram_digest_error err=%s", exc)
        return False
    finally:
        file_lock.release()
