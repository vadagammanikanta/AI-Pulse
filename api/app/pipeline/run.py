"""
Pipeline orchestrator.

Steps:
  1.  Create pipeline_run row (status=running).
  2.  Ingest from all active sources.
  3.  Upsert raw_items (idempotent: UNIQUE on source_id+external_id).
  4.  Dedup newly ingested items.
  5.  Pre-score: ALL pending + previously-failed items.
      – Log each filtered item (score, breakdown) via structlog + store in run.
      – Cap filtered_items_log at FILTERED_LOG_MAX_ENTRIES.
  6.  Select top-N by pre-score.
  7.  Summarize via LLM (Groq→Gemini→Ollama fallback, with cache).
  8.  Embed successful summaries (sentence-transformers, local).
  9.  Insert into items table; update raw_item status.
  10. Finalize pipeline_run row.

Retry semantics:
  – Items whose LLM call fails (all providers exhausted) stay status='failed'.
  – Next pipeline run picks them up again in step 5.
  – 429/timeouts never mark an item failed — they fall through to the next provider.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.ai.embedder import embed_text
from app.ai.llm_router import summarize_items
from app.config import settings
from app.database import init_db
from app.ingestion.base import IngestedItem
from app.ingestion.rss import RSSIngester
from app.models.item import RawItem, Source
from app.pipeline.deduplicator import is_duplicate, normalize_url
from app.pipeline.prescorer import compute_pre_score
from app.pipeline.selector import select_top_n
from app.schemas.item import ItemAIOutput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ingester factory
# ---------------------------------------------------------------------------

def _get_ingester(source: Source):
    if source.type == "rss":
        return RSSIngester(source)
    raise NotImplementedError(f"Ingester not implemented for type: {source.type!r}")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _get_active_sources(db: aiosqlite.Connection) -> list[Source]:
    async with db.execute(
        "SELECT * FROM sources WHERE active = 1"
    ) as cur:
        rows = await cur.fetchall()
    return [Source.from_row(r) for r in rows]


async def _upsert_raw_item(
    item: IngestedItem,
    source: Source,
    db: aiosqlite.Connection,
) -> int | None:
    """
    Insert raw_item.  Returns the new row id, or None if already existed.
    Excerpt is hard-capped at 500 chars here as a safety net.
    """
    norm_url = normalize_url(item.url)
    excerpt = (item.excerpt or "")[:500] or None

    try:
        async with db.execute(
            """
            INSERT INTO raw_items
                (source_id, external_id, title, url, excerpt, author, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.id,
                item.external_id,
                item.title,
                norm_url,
                excerpt,
                item.author,
                item.published_at,
            ),
        ) as cur:
            await db.commit()
            return cur.lastrowid
    except aiosqlite.IntegrityError:
        # Already exists (UNIQUE constraint on source_id + external_id)
        return None


async def _get_scoreable_items(db: aiosqlite.Connection) -> list[RawItem]:
    """
    Return all items that should go through pre-scoring:
      – status = 'pending'   (freshly ingested / not yet scored)
      – status = 'failed'    (LLM failed previously — retry ONLY if prompt version changed AND within last 14 days)
    Joined with sources to get source_name and source_weight.
    """
    from app.ai.prompts import PROMPT_VERSION
    days = settings.prompt_reprocess_window_days
    cutoff = f"-{days} days"
    async with db.execute(
        """
        SELECT ri.*, s.name, s.source_weight
        FROM raw_items ri
        JOIN sources s ON ri.source_id = s.id
        WHERE ri.status = 'pending'
           OR (
               ri.status = 'failed'
               AND (ri.failed_prompt_version IS NULL OR ri.failed_prompt_version != ?)
               AND ri.ingested_at >= datetime('now', ?)
           )
        ORDER BY ri.ingested_at DESC
        """,
        (PROMPT_VERSION, cutoff),
    ) as cur:
        rows = await cur.fetchall()
    return [RawItem.from_row(r) for r in rows]


async def _mark_raw_item(
    item_id: int,
    status: str,
    db: aiosqlite.Connection,
    error: str | None = None,
) -> None:
    await db.execute(
        """
        UPDATE raw_items
        SET status = ?, error_message = ?
        WHERE id = ?
        """,
        (status, error, item_id),
    )
    await db.commit()


async def _mark_provider_exhausted(
    item_id: int,
    db: aiosqlite.Connection,
    error: str | None = None,
) -> None:
    """
    Provider exhaustion (429/timeouts/all providers down):
    Increments attempts counter. If attempts < 5, leaves item 'pending'.
    If attempts >= 5, sets status 'failed' (without failed_prompt_version).
    """
    async with db.execute("SELECT attempts FROM raw_items WHERE id = ?", (item_id,)) as cur:
        row = await cur.fetchone()
    current_attempts = (row[0] if row else 0) + 1
    new_status = "pending" if current_attempts < 5 else "failed"
    err_msg = error or f"Provider exhaustion (attempt {current_attempts})"
    await db.execute(
        """
        UPDATE raw_items
        SET status = ?, attempts = ?, error_message = ?
        WHERE id = ?
        """,
        (new_status, current_attempts, err_msg, item_id),
    )
    await db.commit()


async def _mark_validation_failed(
    item_id: int,
    db: aiosqlite.Connection,
    error: str | None = None,
) -> None:
    """
    Validation / JSON parse failure:
    Increments attempts counter. If attempts < 3, leaves item 'pending'.
    If attempts >= 3, sets status 'failed' AND sets failed_prompt_version = PROMPT_VERSION.
    """
    from app.ai.prompts import PROMPT_VERSION
    async with db.execute("SELECT attempts FROM raw_items WHERE id = ?", (item_id,)) as cur:
        row = await cur.fetchone()
    current_attempts = (row[0] if row else 0) + 1
    if current_attempts >= 3:
        new_status = "failed"
        failed_ver = PROMPT_VERSION
    else:
        new_status = "pending"
        failed_ver = None

    err_msg = error or f"Validation failure (attempt {current_attempts})"
    await db.execute(
        """
        UPDATE raw_items
        SET status = ?, attempts = ?, error_message = ?, failed_prompt_version = COALESCE(?, failed_prompt_version)
        WHERE id = ?
        """,
        (new_status, current_attempts, err_msg, failed_ver, item_id),
    )
    await db.commit()


async def _insert_item(
    raw: RawItem,
    output: ItemAIOutput,
    embedding: bytes,
    db: aiosqlite.Connection,
    validator_result: str = "skipped",
) -> int:
    from app.pipeline.ranker import apply_arxiv_rule
    category, importance_score = apply_arxiv_rule(
        raw.url, raw.source_name, raw.title, raw.excerpt, output.category, output.importance_score
    )

    async with db.execute(
        """
        INSERT INTO items (
            raw_item_id, source_id, title, url, author, published_at,
            category, importance_score, importance_reason,
            what_is_new, why_it_matters, who_should_care_json,
            how_to_use, pro_tip, learning_module_json,
            embedding, embedding_model, validator_result
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(raw_item_id) DO UPDATE SET
            category = excluded.category,
            importance_score = excluded.importance_score,
            importance_reason = excluded.importance_reason,
            what_is_new = excluded.what_is_new,
            why_it_matters = excluded.why_it_matters,
            who_should_care_json = excluded.who_should_care_json,
            how_to_use = excluded.how_to_use,
            pro_tip = excluded.pro_tip,
            learning_module_json = excluded.learning_module_json,
            embedding = excluded.embedding,
            embedding_model = excluded.embedding_model,
            validator_result = excluded.validator_result,
            processed_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        """,
        (
            raw.id,
            raw.source_id,
            raw.title,
            raw.url,
            raw.author,
            raw.published_at,
            category,
            importance_score,
            output.importance_reason,
            output.what_is_new,
            output.why_it_matters,
            json.dumps(output.who_should_care),
            output.how_to_use,
            output.pro_tip,
            output.learning_module.model_dump_json() if output.learning_module else "{}",
            embedding,
            settings.embedding_model,
            validator_result,
        ),
    ) as cur:
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def _start_run(db: aiosqlite.Connection) -> int:
    async with db.execute(
        "INSERT INTO pipeline_runs (status) VALUES ('running')"
    ) as cur:
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def _finish_run(
    run_id: int,
    stats: dict,
    filtered_log: list[dict],
    status: str,
    error: str | None,
    db: aiosqlite.Connection,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    capped_log = filtered_log[: settings.filtered_log_max_entries]
    await db.execute(
        """
        UPDATE pipeline_runs
        SET finished_at         = ?,
            items_ingested      = ?,
            items_deduped       = ?,
            items_skipped       = ?,
            items_llm_processed = ?,
            items_retried       = ?,
            filtered_items_log  = ?,
            status              = ?,
            error_message       = ?
        WHERE id = ?
        """,
        (
            now,
            stats["ingested"],
            stats["deduped"],
            stats["skipped"],
            stats["processed"],
            stats["retried"],
            json.dumps(capped_log),
            status,
            error,
            run_id,
        ),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Main pipeline function
# ---------------------------------------------------------------------------

async def run_pipeline(db: aiosqlite.Connection | None = None) -> dict:
    """
    Run the full pipeline.  Returns a stats dict.
    If db is None, opens its own connection (for CLI / APScheduler usage).
    Protected by cross-process ProcessFileLock.
    """
    from app.locks import ProcessFileLock
    file_lock = ProcessFileLock("data/pipeline.lock")
    if not file_lock.acquire():
        logger.warning("pipeline_skip_process_locked — another process is running the pipeline")
        return {"ingested": 0, "deduped": 0, "skipped": 0, "processed": 0, "retried": 0, "locked": True}

    own_conn = db is None
    if own_conn:
        db_path = settings.db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("PRAGMA foreign_keys = ON")
        await init_db(db)

    stats = {
        "ingested": 0,
        "deduped": 0,
        "skipped": 0,
        "processed": 0,
        "retried": 0,
    }
    filtered_log: list[dict] = []
    run_id = await _start_run(db)
    logger.info("pipeline_start run_id=%d", run_id)

    try:
        # ── Step 1-3: Ingest ──────────────────────────────────────────────────
        sources = await _get_active_sources(db)
        if not sources:
            logger.warning("pipeline_no_sources — add sources via seed_sources")

        for source in sources:
            try:
                ingester = _get_ingester(source)
                raw_items = await ingester.fetch()
            except Exception as exc:
                logger.error("ingest_error source=%r err=%s", source.name, exc)
                continue

            # ── Step 4: Dedup new items immediately after fetch ───────────────
            for ri in raw_items:
                row_id = await _upsert_raw_item(ri, source, db)
                if row_id is None:
                    continue  # already existed (exact id match)

                stats["ingested"] += 1

                dup = await is_duplicate(ri.url, ri.title, source.id, db)
                if dup:
                    await _mark_raw_item(row_id, "duplicate", db)
                    stats["deduped"] += 1

            await db.execute(
                "UPDATE sources SET last_fetched_at = datetime('now') WHERE id = ?",
                (source.id,),
            )
            await db.commit()

        # ── Step 5: Pre-score (pending + failed from previous runs) ───────────
        scoreable = await _get_scoreable_items(db)
        logger.info("pipeline_prescoring count=%d", len(scoreable))

        passed: list[tuple[RawItem, int]] = []

        for item in scoreable:
            score, breakdown = compute_pre_score(item)
            await db.execute(
                "UPDATE raw_items SET pre_score = ? WHERE id = ?",
                (score, item.id),
            )
            await db.commit()

            if score < settings.pre_score_threshold:
                # Log every filtered item with full breakdown
                entry = {
                    "raw_item_id": item.id,
                    "title": item.title,
                    "url": item.url,
                    "pre_score": score,
                    "breakdown": breakdown,
                }
                filtered_log.append(entry)

                logger.info(
                    "item_filtered raw_item_id=%d pre_score=%d title=%r source_weight=%d keyword_score=%d recency_score=%d length_score=%d",
                    item.id,
                    score,
                    item.title,
                    breakdown["source_weight"],
                    breakdown["keyword_score"],
                    breakdown["recency_score"],
                    breakdown["length_score"],
                )
                # Only mark skipped if it was 'pending'; preserve 'failed' status
                # until it's eventually retried and either passes or fails again.
                if item.status == "pending":
                    await _mark_raw_item(item.id, "skipped", db)
                stats["skipped"] += 1
            else:
                passed.append((item, score))
                if item.status == "failed":
                    stats["retried"] += 1

        # Cap log entries
        filtered_log = filtered_log[: settings.filtered_log_max_entries]

        # ── Step 6: Top-N selection ───────────────────────────────────────────
        top_n = select_top_n(passed)
        logger.info(
            "pipeline_top_n selected=%d from_passed=%d",
            len(top_n), len(passed),
        )

        if not top_n:
            logger.info("pipeline_no_items_to_process run_id=%d", run_id)
            await _finish_run(run_id, stats, filtered_log, "completed", None, db)
            return stats

        # ── Step 7: LLM summarization ─────────────────────────────────────────
        items_to_summarize = [item for item, _ in top_n]

        # Mark as 'processing' so a crashed run doesn't leave them as 'failed'
        for item in items_to_summarize:
            await _mark_raw_item(item.id, "processing", db)

        ai_results = await summarize_items(items_to_summarize, db)

        # ── Step 8-9: Embed + store ───────────────────────────────────────────
        for item in items_to_summarize:
            if item.id not in ai_results:
                await _mark_provider_exhausted(item.id, db, "Provider exhaustion")
                logger.warning("item_provider_exhausted item_id=%d title=%r", item.id, item.title)
                continue

            output = ai_results[item.id]
            from app.ai.validator import sanitize_item_output
            output, vr = sanitize_item_output(output, item.title, item.excerpt)

            embed_text_input = f"{item.title}. {output.what_is_new}"
            try:
                embedding = await embed_text(embed_text_input)
            except Exception as exc:
                logger.error("embed_error item_id=%d err=%s", item.id, exc)
                await _mark_raw_item(item.id, "failed", db)
                continue

            await _insert_item(item, output, embedding, db, validator_result=vr)
            await _mark_raw_item(item.id, "processed", db)
            stats["processed"] += 1
            logger.info(
                "item_processed item_id=%d score=%d category=%s validator=%s title=%r",
                item.id, output.importance_score, output.category, vr, item.title,
            )

        # ── Finalize ──────────────────────────────────────────────────────────
        await _finish_run(run_id, stats, filtered_log, "completed", None, db)
        logger.info("pipeline_complete run_id=%d stats=%s", run_id, stats)

    except Exception as exc:
        logger.exception("pipeline_error run_id=%d err=%s", run_id, exc)
        await _finish_run(run_id, stats, filtered_log, "failed", str(exc), db)
        raise

    finally:
        if own_conn and db:
            await db.close()
        file_lock.release()

    return stats


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cli_run() -> None:
    """Entry point for `pipeline` script (pyproject.toml [scripts])."""
    import sys

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stats = asyncio.run(run_pipeline())
    print(json.dumps(stats, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    cli_run()
