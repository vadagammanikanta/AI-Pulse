"""
Feed ranker — calculates personalized feed scores and matches interest keywords.

Formula:
  feed_score = w_importance * importance_norm + w_interest * interest_match + w_recency * recency_score
Where:
  - importance_norm: importance_score normalized against category max score
  - interest_match: 1.0 if matched interest keywords present, else 0.0
  - recency_score: exponential decay with 48h half-life: exp(-ln(2)/48 * hours_old)
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from app.config import settings


_COMPILED_KEYWORDS: list[tuple[str, re.Pattern]] = []

def extract_matched_keywords(text: str) -> list[str]:
    """
    Find interest keywords present in text using normalized word boundaries.
    Uses lazily compiled and cached regex patterns to avoid ~2.6x overhead
    from dynamically recompiling patterns inside loops during feed ranking.
    """
    if not text:
        return []

    global _COMPILED_KEYWORDS
    if not _COMPILED_KEYWORDS:
        compiled = []
        for kw in settings.interest_keywords:
            kw_clean = re.sub(r"[-_,\.:;/\\]", " ", kw.lower())
            pattern = r"\b" + re.escape(kw_clean) + r"\b"
            compiled.append((kw, re.compile(pattern)))
        # Atomic assignment to prevent race conditions in multithreaded environments
        _COMPILED_KEYWORDS = compiled

    text_clean = re.sub(r"[-_,\.:;/\\]", " ", text.lower())
    matched: list[str] = []
    for kw, regex in _COMPILED_KEYWORDS:
        if regex.search(text_clean):
            matched.append(kw)
    return matched


def parse_published_datetime(published_at_str: str | None) -> datetime:
    """Parse ISO published_at string to UTC datetime. Defaults to now if invalid/missing."""
    if not published_at_str:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def compute_feed_score(
    importance_score: int,
    category: str,
    text_for_keywords: str,
    published_at_str: str | None,
    now_dt: datetime | None = None,
    category_max_score: int = 100,
) -> tuple[float, list[str]]:
    """
    Calculate feed score and return (score, matched_keywords).
    Importance is normalized strictly against 100.0 (never all-time maxima).
    """
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)

    # 1. Importance (normalized against 100)
    importance_norm = min(importance_score / 100.0, 1.0)

    # 2. Interest match
    matched_kws = extract_matched_keywords(text_for_keywords)
    interest_match = 1.0 if matched_kws else 0.0

    # 3. Recency (exponential decay)
    pub_dt = parse_published_datetime(published_at_str)
    hours_old = max(0.0, (now_dt - pub_dt).total_seconds() / 3600.0)
    decay_constant = math.log(2.0) / settings.recency_half_life_hours
    recency_score = math.exp(-decay_constant * hours_old)

    # Weighted sum
    w_imp = settings.feed_score_weight_importance
    w_int = settings.feed_score_weight_interest
    w_rec = settings.feed_score_weight_recency

    raw_score = w_imp * importance_norm + w_int * interest_match + w_rec * recency_score
    return round(raw_score, 4), matched_kws


def apply_arxiv_rule(
    url: str | None,
    source_name: str | None,
    title: str,
    excerpt: str | None,
    category: str,
    importance_score: int,
) -> tuple[str, int]:
    """
    arXiv rule: arXiv items ALWAYS get category 'paper' and their importance score
    is capped at 60 unless their title/excerpt matches interest keywords.
    """
    is_arxiv = "arxiv" in (url or "").lower() or "arxiv" in (source_name or "").lower()
    if is_arxiv:
        category = "paper"
        text = f"{title} {excerpt or ''}"
        matched = extract_matched_keywords(text)
        if not matched:
            importance_score = min(importance_score, 60)
    return category, importance_score

