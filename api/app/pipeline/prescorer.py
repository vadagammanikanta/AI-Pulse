"""
Heuristic pre-scorer (0-100).

Runs BEFORE any LLM call.  Items that score below PRE_SCORE_THRESHOLD
are filtered out, logged individually, and marked 'skipped'.

Score breakdown (each component is independent and additive):
  source_weight  : 0-30  (set per source in DB)
  keyword_score  : 0-40  (keyword matches in title + excerpt)
  recency_score  : 0-20  (how recent is the published_at date)
  length_score   : 0-10  (excerpt present = 10, title-only = 0)
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from app.models.item import RawItem

logger = logging.getLogger(__name__)

# Keywords that signal AI-relevant content
_HIGH_KEYWORDS = [
    "gpt", "claude", "gemini", "llama", "mistral", "falcon", "phi",
    "release", "released", "launched", "announce", "api", "model",
    "benchmark", "paper", "breakthrough", "sota", "open-source", "open source",
    "fine-tun", "rag", "embedding", "multimodal", "agent", "reasoning",
    "diffusion", "image generation", "code model",
]
_MED_KEYWORDS = [
    "ai", "ml", "machine learning", "deep learning", "neural", "transformer",
    "update", "new", "feature", "integration", "tool", "framework",
]


def _keyword_score(title: str, excerpt: str | None) -> int:
    text = f"{title} {excerpt or ''}".lower()
    high = sum(1 for kw in _HIGH_KEYWORDS if kw in text)
    med = sum(1 for kw in _MED_KEYWORDS if kw in text)
    # Cap: high keywords give 8 pts each up to 32, med give 2 pts up to 8
    raw = min(high * 8, 32) + min(med * 2, 8)
    return min(raw, 40)


def _recency_score(published_at: str | None) -> int:
    if not published_at:
        return 5  # unknown — give partial credit

    try:
        pub = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_hours = (now - pub).total_seconds() / 3600

        if age_hours <= 24:
            return 20
        elif age_hours <= 48:
            return 15
        elif age_hours <= 96:
            return 10
        elif age_hours <= 168:  # 7 days
            return 5
        else:
            return 0
    except (ValueError, TypeError):
        return 5


def _length_score(excerpt: str | None) -> int:
    if not excerpt:
        return 0
    return 10 if len(excerpt.strip()) > 20 else 5


def compute_pre_score(
    item: RawItem,
) -> tuple[int, dict[str, int]]:
    """
    Returns (total_score, breakdown_dict).
    breakdown_dict is logged for every filtered item.
    """
    source_w = item.source_weight or 20
    keyword_s = _keyword_score(item.title, item.excerpt)
    recency_s = _recency_score(item.published_at)
    length_s = _length_score(item.excerpt)

    total = source_w + keyword_s + recency_s + length_s

    breakdown = {
        "source_weight": source_w,
        "keyword_score": keyword_s,
        "recency_score": recency_s,
        "length_score": length_s,
    }
    return total, breakdown
