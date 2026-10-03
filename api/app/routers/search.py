"""
Search router — GET /search.

Combines SQLite FTS5 (full text) and ONNX vector cosine similarity (hybrid search).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
import re
from fastapi import APIRouter, Depends, Query
import aiosqlite

from app.ai.embedder import embed_text, rank_by_similarity
from app.config import settings
from app.database import get_db
from app.dependencies import verify_api_key
from app.pipeline.ranker import compute_feed_score
from app.schemas.item import FeedItem

router = APIRouter(prefix="/search", dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)


def _sanitize_fts_query(query: str) -> str:
    """Sanitize raw search string into safe FTS5 match expression."""
    words = re.findall(r"\w+", query)
    if not words:
        return ""
    # Join with AND, wildcarding each word
    return " AND ".join(f'"{w}"*' for w in words)


@router.get("", response_model=list[FeedItem])
async def search_items(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(default=20, ge=1, le=100),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[FeedItem]:
    """
    Hybrid search combining FTS5 keyword matching and ONNX vector cosine similarity.
    """
    q_clean = q.strip()
    if not q_clean:
        return []

    # 1. FTS5 Search
    fts_scores: dict[int, float] = {}
    fts_q = _sanitize_fts_query(q_clean)
    if fts_q:
        try:
            async with db.execute(
                """
                SELECT rowid, rank
                FROM items_fts
                WHERE items_fts MATCH ?
                ORDER BY rank
                LIMIT 50
                """,
                (fts_q,),
            ) as cur:
                fts_rows = await cur.fetchall()
                for r in fts_rows:
                    item_id = r["rowid"]
                    rank_val = abs(float(r["rank"]))
                    # BM25 rank in SQLite FTS5 is negative; lower magnitude is better
                    fts_scores[item_id] = 1.0 / (1.0 + rank_val)
        except Exception as exc:
            logger.warning("fts_search_error query=%r err=%s", fts_q, exc)

    # 2. Vector Cosine Search with Configurable Min Cosine Threshold
    vector_scores: dict[int, float] = {}
    min_cosine = settings.search_min_cosine_threshold
    try:
        q_embed = await embed_text(q_clean)
        async with db.execute("SELECT id, embedding FROM items WHERE embedding IS NOT NULL") as cur:
            emb_rows = await cur.fetchall()
            candidates = [(r["id"], r["embedding"]) for r in emb_rows if r["embedding"]]

        if candidates:
            ranked = rank_by_similarity(q_embed, candidates, top_k=50)
            for item_id, sim_score in ranked:
                if sim_score >= min_cosine:
                    vector_scores[item_id] = float(sim_score)
    except Exception as exc:
        logger.warning("vector_search_error query=%r err=%s", q_clean, exc)

    # 3. Combine scores (hybrid RRF / weighted average)
    all_item_ids = set(fts_scores.keys()) | set(vector_scores.keys())
    if not all_item_ids:
        return []

    combined_scores: dict[int, float] = {}
    for item_id in all_item_ids:
        f_score = fts_scores.get(item_id, 0.0)
        v_score = vector_scores.get(item_id, 0.0)
        combined_scores[item_id] = 0.5 * f_score + 0.5 * v_score

    # Sort item IDs by combined search score
    sorted_ids = sorted(combined_scores.keys(), key=lambda i: combined_scores[i], reverse=True)[:limit]

    # 4. Fetch full item details from DB
    placeholders = ",".join("?" * len(sorted_ids))
    query = f"""
        SELECT i.*, s.name AS source_name
        FROM items i
        JOIN sources s ON i.source_id = s.id
        WHERE i.id IN ({placeholders})
    """
    async with db.execute(query, sorted_ids) as cur:
        item_rows = await cur.fetchall()

    row_map = {r["id"]: r for r in item_rows}
    now_dt = datetime.now(timezone.utc)
    result_items: list[FeedItem] = []

    for item_id in sorted_ids:
        if item_id not in row_map:
            continue
        r = row_map[item_id]
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

        # Determine match_type indicator
        in_fts = item_id in fts_scores and fts_scores[item_id] > 0
        in_vec = item_id in vector_scores and vector_scores[item_id] >= min_cosine
        if in_fts and in_vec:
            item.match_type = "hybrid"
        elif in_fts:
            item.match_type = "keyword"
        else:
            item.match_type = "semantic"

        result_items.append(item)

    return result_items
