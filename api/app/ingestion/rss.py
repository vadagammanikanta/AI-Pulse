"""
RSS ingester — uses feedparser.

Only title, URL, excerpt (≤ 500 chars), author, and published_at are stored.
Full article HTML is never fetched or persisted.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from app.ingestion.base import BaseIngester, IngestedItem
from app.models.item import Source

logger = logging.getLogger(__name__)

_EXCERPT_MAX = 500


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_date(entry: feedparser.FeedParserDict) -> str | None:
    """Try multiple feedparser date fields; return ISO-8601 string or None."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                dt = datetime(*val[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
    # Try raw string fallback
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw).isoformat()
            except Exception:
                pass
    return None


def _extract_excerpt(entry: feedparser.FeedParserDict) -> str | None:
    """
    Extract a short excerpt from summary or content.
    Hard-capped at _EXCERPT_MAX characters.
    Full article text is NEVER stored.
    """
    candidates = []

    # Prefer summary over content (shorter by design)
    if hasattr(entry, "summary") and entry.summary:
        candidates.append(entry.summary)

    # content[] is often full article — skip if > 2000 chars after cleaning
    if hasattr(entry, "content"):
        for c in entry.content:
            raw = c.get("value", "")
            if raw and len(raw) < 2000:
                candidates.append(raw)
                break

    for candidate in candidates:
        cleaned = _clean_html(candidate)
        if cleaned:
            return cleaned[:_EXCERPT_MAX]

    return None


def _get_external_id(entry: feedparser.FeedParserDict) -> str:
    """Stable unique ID for an entry."""
    return entry.get("id") or entry.get("link") or entry.get("title", "unknown")


class RSSIngester(BaseIngester):
    async def fetch(self) -> list[IngestedItem]:
        feed_url = self.source.feed_url or self.source.url
        logger.info("rss_fetch source=%r url=%r", self.source.name, feed_url)

        try:
            feed = await asyncio.to_thread(feedparser.parse, feed_url)
        except Exception as exc:
            logger.error("rss_parse_error source=%r err=%s", self.source.name, exc)
            return []

        if feed.bozo and not feed.entries:
            logger.warning(
                "rss_bozo source=%r reason=%s",
                self.source.name,
                feed.bozo_exception,
            )

        items: list[IngestedItem] = []
        for entry in feed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            title = entry.get("title", "").strip()
            if not title:
                continue

            items.append(
                IngestedItem(
                    external_id=_get_external_id(entry),
                    title=title,
                    url=url,
                    excerpt=_extract_excerpt(entry),
                    author=entry.get("author") or None,
                    published_at=_parse_date(entry),
                )
            )

        logger.info("rss_fetched source=%r count=%d", self.source.name, len(items))
        return items
