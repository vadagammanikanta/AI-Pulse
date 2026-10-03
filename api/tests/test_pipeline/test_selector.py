"""Tests for the top-N selector."""
from __future__ import annotations

from datetime import datetime, timezone
from app.models.item import RawItem
from app.pipeline.selector import select_top_n


def _item(id: int, score: int, status: str = "pending") -> RawItem:
    now = datetime.now(timezone.utc).isoformat()
    return RawItem(
        id=id, source_id=1, external_id=f"ext{id}",
        title=f"Item {id}", url=f"https://example.com/{id}",
        excerpt="excerpt", author=None, published_at=now,
        ingested_at=now, status=status, pre_score=score,
        error_message=None, source_name="Test", source_weight=20,
    )


class TestSelectTopN:
    def test_returns_n_items(self):
        scored = [(_item(i, i * 10), i * 10) for i in range(1, 11)]
        result = select_top_n(scored, n=5)
        assert len(result) == 5

    def test_returns_highest_scored_first(self):
        scored = [
            (_item(1, 40), 40),
            (_item(2, 90), 90),
            (_item(3, 60), 60),
        ]
        result = select_top_n(scored, n=3)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)

    def test_returns_all_when_fewer_than_n(self):
        scored = [(_item(i, i * 10), i * 10) for i in range(1, 4)]
        result = select_top_n(scored, n=10)
        assert len(result) == 3

    def test_empty_input(self):
        assert select_top_n([], n=20) == []

    def test_top_item_has_highest_score(self):
        scored = [(_item(i, i), i) for i in range(1, 50)]
        result = select_top_n(scored, n=10)
        assert result[0][1] == 49  # highest score item is first

    def test_uses_settings_default_when_n_is_none(self):
        """select_top_n with n=None should use settings.top_n_per_run."""
        from app.config import settings
        scored = [(_item(i, i), i) for i in range(1, 100)]
        result = select_top_n(scored, n=None)
        assert len(result) == settings.top_n_per_run
