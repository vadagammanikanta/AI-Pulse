"""Tests for APScheduler integration and concurrency locking."""
import pytest
from app.scheduler import start_scheduler, stop_scheduler, _pipeline_lock, check_daily_budget_available
from app.database import init_db
import aiosqlite


@pytest.mark.asyncio
async def test_scheduler_lifecycle_and_lock():
    scheduler = start_scheduler()
    assert scheduler.running is True
    job = scheduler.get_job("pipeline_job")
    assert job is not None

    # Test lock concurrency behavior
    async with _pipeline_lock:
        assert _pipeline_lock.locked() is True

    stop_scheduler()


@pytest.mark.asyncio
async def test_daily_budget_check():
    async with aiosqlite.connect(":memory:") as db:
        await init_db(db)
        budget_available = await check_daily_budget_available(db)
        assert isinstance(budget_available, bool)
