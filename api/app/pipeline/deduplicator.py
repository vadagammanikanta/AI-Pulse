"""
Deduplicator — two-stage:
  1. Exact: URL normalization + lookup in raw_items and items tables.
  2. Fuzzy: RapidFuzz title similarity ≥ 0.85 against items from the last 30 days.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

if TYPE_CHECKING:
    import aiosqlite

logger = logging.getLogger(__name__)

# Query-string parameters that carry no semantic meaning (tracking pixels, etc.)
_JUNK_PARAMS = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
        "utm_id", "fbclid", "gclid", "ref", "source", "mc_cid", "mc_eid",
        "cmpid", "via",
    }
)

_FUZZY_THRESHOLD = 85  # RapidFuzz returns 0-100


def normalize_url(url: str) -> str:
    """
    Lowercase domain, strip tracking params, remove fragment and trailing slash.
    This is the canonical URL used for exact-match dedup.
    """
    try:
        parsed = urlparse(url.strip())
        clean_qs = urlencode(
            [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in _JUNK_PARAMS],
            doseq=True,
        )
        path = parsed.path.rstrip("/") or "/"
        cleaned = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=path,
            query=clean_qs,
            fragment="",
        )
        return urlunparse(cleaned)
    except Exception:
        return url.strip().lower()


async def is_duplicate(
    url: str,
    title: str,
    source_id: int,
    db: "aiosqlite.Connection",
) -> bool:
    """
    Return True if this item is a duplicate.
    Stage 1: exact normalized URL check.
    Stage 2: fuzzy title match against last 30 days.
    """
    norm = normalize_url(url)

    # Stage 1 — exact URL (both tables)
    async with db.execute(
        "SELECT 1 FROM raw_items WHERE url = ? AND source_id != ? LIMIT 1",
        (norm, source_id),
    ) as cur:
        if await cur.fetchone():
            logger.debug("dedup_exact url=%r", norm[:60])
            return True

    async with db.execute(
        "SELECT 1 FROM items WHERE url = ? LIMIT 1",
        (norm,),
    ) as cur:
        if await cur.fetchone():
            logger.debug("dedup_exact_items url=%r", norm[:60])
            return True

    # Stage 2 — fuzzy title against last 30 days
    async with db.execute(
        """
        SELECT title FROM raw_items
        WHERE ingested_at >= datetime('now', '-30 days')
          AND url != ?
        LIMIT 2000
        """,
        (norm,),
    ) as cur:
        rows = await cur.fetchall()

    title_lower = title.strip().lower()
    for (existing_title,) in rows:
        score = fuzz.token_sort_ratio(title_lower, existing_title.strip().lower())
        if score >= _FUZZY_THRESHOLD:
            logger.debug(
                "dedup_fuzzy score=%d title=%r vs %r",
                score, title[:60], existing_title[:60],
            )
            return True

    return False
