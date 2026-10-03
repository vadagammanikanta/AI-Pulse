"""Clean sources table to exactly 3 unique active sources."""
import asyncio
import aiosqlite
from app.config import settings

async def main():
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("DELETE FROM sources")
        await db.execute(
            """
            INSERT INTO sources (id, name, type, url, feed_url, source_weight) VALUES
            (1, 'OpenAI Blog', 'rss', 'https://openai.com/blog', 'https://openai.com/blog/rss.xml', 30),
            (2, 'arXiv cs.AI', 'rss', 'https://arxiv.org/list/cs.AI/recent', 'https://rss.arxiv.org/rss/cs.AI', 25),
            (3, 'Hugging Face Blog', 'rss', 'https://huggingface.co/blog', 'https://huggingface.co/blog/feed.xml', 25)
            """
        )
        # Update raw_items that pointed to old source_ids
        await db.execute("UPDATE raw_items SET source_id = 1 WHERE source_id IN (4)")
        await db.execute("UPDATE raw_items SET source_id = 3 WHERE source_id IN (6)")
        await db.commit()
        print("Sources cleaned!")

if __name__ == "__main__":
    asyncio.run(main())
