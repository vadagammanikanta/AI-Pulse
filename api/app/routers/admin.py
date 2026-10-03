"""
Admin router — pipeline trigger and stats.

IMPORTANT: Admin routes require the X-API-Key header and must NOT be
proxied through the Next.js frontend.  They are intended for direct
server-to-server or CLI access only.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
import aiosqlite

from app.database import get_db
from app.dependencies import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PipelineRunResponse(BaseModel):
    message: str
    run_id: int | None = None


class StatsResponse(BaseModel):
    items_total: int
    items_today: int
    sources_active: int
    llm_usage_today: dict[str, int]
    last_run: dict | None
    cache_size: int


# ---------------------------------------------------------------------------
# Background pipeline trigger
# ---------------------------------------------------------------------------

_pipeline_lock = asyncio.Lock()


async def _run_pipeline_bg() -> None:
    """Run the pipeline in the background, guarded by a lock (no concurrency)."""
    from app.pipeline.run import run_pipeline

    if _pipeline_lock.locked():
        logger.warning("admin_pipeline_skipped — already running")
        return

    async with _pipeline_lock:
        try:
            stats = await run_pipeline()
            logger.info("admin_pipeline_done stats=%s", stats)
        except Exception as exc:
            logger.error("admin_pipeline_error err=%s", exc)


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
) -> PipelineRunResponse:
    """
    Manually trigger a pipeline run.  Returns immediately; runs in background.
    Call GET /admin/stats to check progress.
    """
    if _pipeline_lock.locked():
        raise HTTPException(status_code=409, detail="Pipeline already running")

    background_tasks.add_task(_run_pipeline_bg)
    return PipelineRunResponse(message="Pipeline started in background")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: aiosqlite.Connection = Depends(get_db),
) -> StatsResponse:
    today = date.today().isoformat()

    async with db.execute("SELECT COUNT(*) FROM items") as cur:
        items_total = (await cur.fetchone())[0]

    async with db.execute(
        "SELECT COUNT(*) FROM items WHERE DATE(processed_at) = ?", (today,)
    ) as cur:
        items_today = (await cur.fetchone())[0]

    async with db.execute("SELECT COUNT(*) FROM sources WHERE active = 1") as cur:
        sources_active = (await cur.fetchone())[0]

    async with db.execute(
        "SELECT provider, requests FROM llm_daily_usage WHERE date = ?", (today,)
    ) as cur:
        usage_rows = await cur.fetchall()
    llm_usage_today = {r[0]: r[1] for r in usage_rows}

    async with db.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ) as cur:
        run_row = await cur.fetchone()

    last_run = None
    if run_row:
        last_run = {
            "id": run_row["id"],
            "started_at": run_row["started_at"],
            "finished_at": run_row["finished_at"],
            "status": run_row["status"],
            "items_ingested": run_row["items_ingested"],
            "items_llm_processed": run_row["items_llm_processed"],
            "items_skipped": run_row["items_skipped"],
            "items_retried": run_row["items_retried"],
            "error_message": run_row["error_message"],
        }

    async with db.execute("SELECT COUNT(*) FROM llm_cache") as cur:
        cache_size = (await cur.fetchone())[0]

    return StatsResponse(
        items_total=items_total,
        items_today=items_today,
        sources_active=sources_active,
        llm_usage_today=llm_usage_today,
        last_run=last_run,
        cache_size=cache_size,
    )
