"""Tests for Telegram digest module."""
import pytest
import aiosqlite
from app.notifications.telegram import send_telegram_digest, escape_markdown


def test_escape_markdown():
    raw = "Release of *vLLM_v2* [Link]"
    escaped = escape_markdown(raw)
    assert "\\*" in escaped
    assert "\\_" in escaped
    assert "\\[" in escaped


@pytest.mark.asyncio
async def test_telegram_digest_skips_when_unset():
    async with aiosqlite.connect(":memory:") as db:
        # Credentials unset by default in test env -> returns False silently
        sent = await send_telegram_digest(db)
        assert sent is False
