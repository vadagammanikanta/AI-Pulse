"""
APScheduler integration — in-process pipeline scheduler.

Runs pipeline every 6 hours (configurable via settings.pipeline_interval_hours),
with concurrency lock against overlapping runs and daily LLM budget check.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.ai.rate_limiter import get_rate_limiter
from app.pipeline.run import run_pipeline

if TYPE_CHECKING:
    import aiosqlite

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_pipeline_lock = asyncio.Lock()


async def check_daily_budget_available(db: "aiosqlite.Connection") -> bool:
    """Return True if at least one active LLM provider has daily budget remaining."""
    limiter = get_rate_limiter()
    active_providers = settings.active_providers()
    if not active_providers:
        logger.warning("scheduler_no_active_providers")
        return False

    for provider in active_providers:
        rpm = getattr(settings, f"{provider}_rpm", 30)
        daily_limit = getattr(settings, f"{provider}_daily_limit", 1000)
        allowed = await limiter.is_allowed(provider, rpm, daily_limit, db)
        if allowed:
            return True
    return False


async def scheduled_pipeline_job() -> None:
    """Scheduled job runner executing every 6 hours."""
    if _pipeline_lock.locked():
        logger.info("scheduler_skip_overlapping_run — previous run still active")
        return

    async with _pipeline_lock:
        logger.info("scheduler_job_start")
        try:
            import aiosqlite
            from app.database import get_db_path

            async with aiosqlite.connect(get_db_path()) as db:
                db.row_factory = aiosqlite.Row
                budget_ok = await check_daily_budget_available(db)
                if not budget_ok:
                    logger.warning("scheduler_skip_budget_exhausted — all providers reached daily limit")
                    return

            stats = await run_pipeline()
            logger.info("scheduler_job_completed stats=%s", stats)

            # Trigger Telegram daily digest if configured
            from app.notifications.telegram import send_telegram_digest
            async with aiosqlite.connect(get_db_path()) as db:
                db.row_factory = aiosqlite.Row
                await send_telegram_digest(db)

        except Exception as exc:
            logger.exception("scheduler_job_failed err=%s", exc)


async def scheduled_telegram_digest_job() -> None:
    """Scheduled Telegram daily digest job runner."""
    from app.notifications.telegram import send_telegram_digest
    import aiosqlite

    logger.info("telegram_scheduled_digest_start")
    try:
        async with aiosqlite.connect(settings.db_path) as db:
            db.row_factory = aiosqlite.Row
            sent = await send_telegram_digest(db)
            logger.info("telegram_scheduled_digest_result sent=%s", sent)
    except Exception as exc:
        logger.exception("telegram_scheduled_digest_failed err=%s", exc)


def start_scheduler() -> AsyncIOScheduler | None:
    """Initialize and start APScheduler if enabled in config."""
    global _scheduler
    if not settings.enable_in_process_scheduler:
        logger.info("apscheduler_disabled_by_config — use external Task Scheduler / cron for pipeline")
        return None

    if _scheduler is not None and _scheduler.running:
        return _scheduler

    from apscheduler.triggers.cron import CronTrigger

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        scheduled_pipeline_job,
        trigger="interval",
        hours=settings.pipeline_interval_hours,
        id="pipeline_job",
        replace_existing=True,
    )

    # Parse HH:MM format for daily Telegram digest
    digest_hour, digest_minute = 8, 0
    try:
        parts = settings.telegram_digest_time.split(":")
        digest_hour, digest_minute = int(parts[0]), int(parts[1])
    except Exception:
        pass

    _scheduler.add_job(
        scheduled_telegram_digest_job,
        trigger=CronTrigger(
            hour=digest_hour,
            minute=digest_minute,
            timezone=settings.telegram_digest_timezone,
        ),
        id="telegram_digest_job",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "apscheduler_started interval_hours=%d digest_cron='%02d:%02d' tz=%s",
        settings.pipeline_interval_hours,
        digest_hour,
        digest_minute,
        settings.telegram_digest_timezone,
    )
    return _scheduler


def stop_scheduler() -> None:
    """Stop APScheduler if running."""
    global _scheduler
    if _scheduler is not None:
        if _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("apscheduler_stopped")
        _scheduler = None
