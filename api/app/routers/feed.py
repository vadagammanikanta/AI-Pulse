"""Feed router — GET /feed with dynamic 3-factor feed ranking."""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
import aiosqlite

from app.database import get_db
from app.dependencies import verify_api_key
from app.pipeline.ranker import compute_feed_score
from app.schemas.item import FeedItem

router = APIRouter(prefix="/feed", dependencies=[Depends(verify_api_key)])


@router.get("", response_model=list[FeedItem])
async def get_feed(
    category: str | None = Query(
        default=None,
        description="Filter by category: news|model|tool|api|paper|company",
    ),
    min_score: int = Query(default=0, ge=0, le=100),
    saved: bool | None = Query(default=None, description="Filter by saved status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[FeedItem]:
    """
    Personalised feed, ranked by dynamic feed_score DESC then published_at DESC.
    Formula: 0.6*importance_norm + 0.3*interest_match + 0.1*recency_score
    """
    # 1. Query items matching filters
    conditions = ["1=1"]
    params: list = []

    if category:
        conditions.append("i.category = ?")
        params.append(category)
    if min_score:
        conditions.append("i.importance_score >= ?")
        params.append(min_score)
    if saved is not None:
        conditions.append("i.saved = ?")
        params.append(1 if saved else 0)

    where = " AND ".join(conditions)

    query = f"""
        SELECT i.*, s.name AS source_name
        FROM items i
        JOIN sources s ON i.source_id = s.id
        WHERE {where}
    """

    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()

    # 2. Compute feed score & matched keywords for each item
    items_with_score: list[tuple[FeedItem, float]] = []
    now_dt = datetime.now(timezone.utc)

    for r in rows:
        item = FeedItem.from_row(r)
        text_for_kws = f"{item.title} {item.what_is_new or ''} {item.why_it_matters or ''}"
        
        feed_score, matched_kws = compute_feed_score(
            importance_score=item.importance_score,
            category=item.category,
            text_for_keywords=text_for_kws,
            published_at_str=item.published_at,
            now_dt=now_dt,
        )
        item.feed_score = feed_score
        item.matched_keywords = matched_kws
        items_with_score.append((item, feed_score))

    # 4. Sort by feed_score DESC, published_at DESC
    items_with_score.sort(
        key=lambda x: (x[1], x[0].published_at or ""),
        reverse=True,
    )

    # 5. Apply offset & limit
    paged_items = [item for item, _ in items_with_score[offset : offset + limit]]
    return paged_items
