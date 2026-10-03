"""Top-N selector — picks the highest pre-scored items for LLM processing."""
from __future__ import annotations

from app.config import settings
from app.models.item import RawItem


def select_top_n(
    scored: list[tuple[RawItem, int]],
    n: int | None = None,
) -> list[tuple[RawItem, int]]:
    """
    Sort by pre-score descending and return at most n items.
    n defaults to settings.top_n_per_run.
    """
    limit = n if n is not None else settings.top_n_per_run
    return sorted(scored, key=lambda t: t[1], reverse=True)[:limit]
