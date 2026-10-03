"""Quick DB stats checker script."""
import asyncio
import aiosqlite
from app.config import settings

async def main():
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sources") as cur:
            sources = await cur.fetchall()
            print("--- SOURCES ---")
            for s in sources:
                print(dict(s))

        async with db.execute("SELECT source_id, COUNT(*) as cnt FROM raw_items GROUP BY source_id") as cur:
            counts = await cur.fetchall()
            print("\n--- RAW ITEMS BY SOURCE ---")
            for c in counts:
                print(dict(c))

if __name__ == "__main__":
    asyncio.run(main())
