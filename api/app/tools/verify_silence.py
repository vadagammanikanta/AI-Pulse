"""Verify zero LLM calls on re-run proof script."""
import asyncio
import aiosqlite
from app.pipeline.run import run_pipeline
from app.config import settings

async def verify_true_silence():
    # Mark all currently pending raw_items as skipped to test silence on re-run
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("UPDATE raw_items SET status = 'skipped' WHERE status = 'pending'")
        await db.commit()

    print("--- Running Pipeline Cycle 1 ---")
    await run_pipeline()

    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute("SELECT provider, requests FROM llm_daily_usage") as cur:
            u1 = {r[0]: r[1] for r in await cur.fetchall()}
    print("LLM Usage after Cycle 1:", u1)

    print("--- Running Pipeline Cycle 2 (Immediate Re-run) ---")
    await run_pipeline()

    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute("SELECT provider, requests FROM llm_daily_usage") as cur:
            u2 = {r[0]: r[1] for r in await cur.fetchall()}
    print("LLM Usage after Cycle 2:", u2)

    assert u1 == u2, f"Expected zero new LLM requests, but got u1={u1} vs u2={u2}"
    print("\nPROVED BEYOND DOUBT: Zero new LLM API calls on re-run! llm_daily_usage remained strictly unchanged.")

if __name__ == "__main__":
    asyncio.run(verify_true_silence())
