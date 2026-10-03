"""Tests for item failure and retry logic."""
import pytest
import aiosqlite
from app.database import init_db
from app.pipeline.run import _mark_provider_exhausted, _mark_validation_failed
from app.models.item import RawItem, Source

@pytest.mark.asyncio
async def test_provider_exhaustion_leaves_pending_under_max_attempts(tmp_path):
    db_file = str(tmp_path / "test.db")
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        await init_db(db)

        # Create source
        async with db.execute("INSERT INTO sources (name, url) VALUES ('test', 'http://test.com')") as cur:
            source_id = cur.lastrowid
        await db.commit()

        # Insert raw item
        async with db.execute(
            """
            INSERT INTO raw_items (source_id, external_id, title, url, status, pre_score, attempts)
            VALUES (?, 'ext1', 'Test Item', 'http://test.com/1', 'pending', 50, 0)
            """,
            (source_id,),
        ) as cur:
            raw_id = cur.lastrowid
        await db.commit()

        # First provider failure -> attempts=1, status=pending, no failed_prompt_version
        await _mark_provider_exhausted(raw_id, db, "429 Rate Limit")
        async with db.execute("SELECT status, attempts, failed_prompt_version FROM raw_items WHERE id = ?", (raw_id,)) as cur:
            row = await cur.fetchone()
            assert row["status"] == "pending"
            assert row["attempts"] == 1
            assert row["failed_prompt_version"] is None

        # Repeat up to 5 attempts -> attempt 5 sets status=failed
        for _ in range(3):
            await _mark_provider_exhausted(raw_id, db, "429 Rate Limit")

        async with db.execute("SELECT status, attempts FROM raw_items WHERE id = ?", (raw_id,)) as cur:
            row = await cur.fetchone()
            assert row["status"] == "pending"
            assert row["attempts"] == 4

        # 5th attempt -> status=failed
        await _mark_provider_exhausted(raw_id, db, "429 Rate Limit")
        async with db.execute("SELECT status, attempts, failed_prompt_version FROM raw_items WHERE id = ?", (raw_id,)) as cur:
            row = await cur.fetchone()
            assert row["status"] == "failed"
            assert row["attempts"] == 5
            assert row["failed_prompt_version"] is None


@pytest.mark.asyncio
async def test_validation_failure_sets_failed_prompt_version_after_3_attempts(tmp_path):
    db_file = str(tmp_path / "test.db")
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        await init_db(db)

        async with db.execute("INSERT INTO sources (name, url) VALUES ('test', 'http://test.com')") as cur:
            source_id = cur.lastrowid
        await db.commit()

        async with db.execute(
            """
            INSERT INTO raw_items (source_id, external_id, title, url, status, pre_score, attempts)
            VALUES (?, 'ext2', 'Test Item 2', 'http://test.com/2', 'pending', 50, 0)
            """,
            (source_id,),
        ) as cur:
            raw_id = cur.lastrowid
        await db.commit()

        # 1st validation failure -> pending
        await _mark_validation_failed(raw_id, db, "Invalid JSON")
        async with db.execute("SELECT status, attempts, failed_prompt_version FROM raw_items WHERE id = ?", (raw_id,)) as cur:
            row = await cur.fetchone()
            assert row["status"] == "pending"
            assert row["attempts"] == 1
            assert row["failed_prompt_version"] is None

        # 2nd validation failure -> pending
        await _mark_validation_failed(raw_id, db, "Invalid JSON")

        # 3rd validation failure -> failed with failed_prompt_version set
        await _mark_validation_failed(raw_id, db, "Invalid JSON")
        async with db.execute("SELECT status, attempts, failed_prompt_version FROM raw_items WHERE id = ?", (raw_id,)) as cur:
            row = await cur.fetchone()
            assert row["status"] == "failed"
            assert row["attempts"] == 3
            assert row["failed_prompt_version"] == "v2.2"
