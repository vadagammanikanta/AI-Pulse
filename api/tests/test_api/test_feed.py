"""API-level tests for /feed and /items endpoints."""
from __future__ import annotations

import json
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _insert_item(db, source_id: int = 1, importance_score: int = 80) -> int:
    """Insert a minimal item row and return its id."""
    async with db.execute(
        """
        INSERT INTO items (
            source_id, title, url, category, importance_score,
            what_is_new, why_it_matters, who_should_care_json, learning_module_json
        ) VALUES (?, ?, ?, 'news', ?, 'What is new', 'Why it matters', '["developers"]', '{}')
        """,
        (source_id, f"Test Item {importance_score}", f"https://example.com/{importance_score}",
         importance_score),
    ) as cur:
        await db.commit()
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

class TestAuth:
    async def test_feed_requires_key(self, unauthed_client):
        resp = await unauthed_client.get("/feed")
        assert resp.status_code == 403

    async def test_items_requires_key(self, unauthed_client):
        resp = await unauthed_client.get("/items/1")
        assert resp.status_code == 403

    async def test_admin_requires_key(self, unauthed_client):
        resp = await unauthed_client.get("/admin/stats")
        assert resp.status_code == 403

    async def test_health_no_key_needed(self, unauthed_client):
        resp = await unauthed_client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Feed tests
# ---------------------------------------------------------------------------

class TestFeed:
    async def test_empty_feed(self, client):
        resp = await client.get("/feed")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_feed_returns_items(self, client, seeded_db):
        await _insert_item(seeded_db, source_id=1, importance_score=75)
        await _insert_item(seeded_db, source_id=1, importance_score=60)

        resp = await client.get("/feed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_feed_ordered_by_importance(self, client, seeded_db):
        await _insert_item(seeded_db, source_id=1, importance_score=50)
        await _insert_item(seeded_db, source_id=1, importance_score=90)
        await _insert_item(seeded_db, source_id=1, importance_score=70)

        resp = await client.get("/feed")
        scores = [item["importance_score"] for item in resp.json()]
        assert scores == sorted(scores, reverse=True)

    async def test_feed_category_filter(self, client, seeded_db):
        await seeded_db.execute(
            """INSERT INTO items (source_id, title, url, category, importance_score,
               who_should_care_json, learning_module_json)
               VALUES (1, 'Model Item', 'https://example.com/model', 'model', 80, '[]', '{}')"""
        )
        await seeded_db.execute(
            """INSERT INTO items (source_id, title, url, category, importance_score,
               who_should_care_json, learning_module_json)
               VALUES (1, 'News Item', 'https://example.com/news', 'news', 80, '[]', '{}')"""
        )
        await seeded_db.commit()

        resp = await client.get("/feed?category=model")
        data = resp.json()
        assert all(item["category"] == "model" for item in data)

    async def test_feed_min_score_filter(self, client, seeded_db):
        await _insert_item(seeded_db, source_id=1, importance_score=30)
        await _insert_item(seeded_db, source_id=1, importance_score=80)

        resp = await client.get("/feed?min_score=50")
        data = resp.json()
        assert all(item["importance_score"] >= 50 for item in data)

    async def test_feed_pagination(self, client, seeded_db):
        for i in range(5):
            await _insert_item(seeded_db, source_id=1, importance_score=50 + i)

        resp = await client.get("/feed?limit=2&offset=0")
        assert len(resp.json()) == 2

        resp2 = await client.get("/feed?limit=2&offset=2")
        ids_page1 = {item["id"] for item in resp.json()}
        ids_page2 = {item["id"] for item in resp2.json()}
        assert ids_page1.isdisjoint(ids_page2)


# ---------------------------------------------------------------------------
# Item detail tests
# ---------------------------------------------------------------------------

class TestItemDetail:
    async def test_get_item_returns_detail(self, client, seeded_db):
        item_id = await _insert_item(seeded_db, source_id=1)
        resp = await client.get(f"/items/{item_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == item_id
        assert "learning_module" in data

    async def test_get_item_404(self, client):
        resp = await client.get("/items/999999")
        assert resp.status_code == 404

    async def test_save_item(self, client, seeded_db):
        item_id = await _insert_item(seeded_db, source_id=1)
        resp = await client.post(f"/items/{item_id}/save")
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

        # Verify in DB
        async with seeded_db.execute(
            "SELECT saved FROM items WHERE id = ?", (item_id,)
        ) as cur:
            row = await cur.fetchone()
        assert row[0] == 1

    async def test_unsave_item(self, client, seeded_db):
        item_id = await _insert_item(seeded_db, source_id=1)
        await client.post(f"/items/{item_id}/save")
        resp = await client.delete(f"/items/{item_id}/save")
        assert resp.status_code == 200
        assert resp.json()["saved"] is False


# ---------------------------------------------------------------------------
# Admin tests
# ---------------------------------------------------------------------------

class TestAdmin:
    async def test_stats_returns_structure(self, client):
        resp = await client.get("/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "items_total" in data
        assert "sources_active" in data
        assert "llm_usage_today" in data

    async def test_pipeline_trigger(self, client):
        """Pipeline trigger should return 200 (it runs in background)."""
        # We only check it doesn't crash the endpoint — not the full run
        resp = await client.post("/admin/pipeline/run")
        assert resp.status_code == 200
        assert "Pipeline" in resp.json()["message"]
