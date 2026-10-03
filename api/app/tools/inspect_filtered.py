"""Inspect filtered items log from pipeline_runs."""
import asyncio
import json
import aiosqlite
from app.config import settings

async def main():
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, started_at, items_skipped, filtered_items_log FROM pipeline_runs WHERE status = 'completed' ORDER BY id DESC"
        ) as cur:
            rows = await cur.fetchall()

        for r in rows:
            log = json.loads(r["filtered_items_log"])
            print(f"Run #{r['id']} ({r['started_at']}) — Skipped: {r['items_skipped']}, Logged: {len(log)}")
            if log:
                print("  Sample filtered items:")
                for item in log[:10]:
                    safe_title = item['title'].encode('ascii', 'ignore').decode('ascii')
                    print(f"    - Score: {item['pre_score']} | Title: {safe_title[:65]}")
                    print(f"      Breakdown: {item['breakdown']}")
            print("-" * 70)

if __name__ == "__main__":
    asyncio.run(main())
