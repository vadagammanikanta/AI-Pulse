"""Tests for the heuristic pre-scorer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from app.models.item import RawItem
from app.pipeline.prescorer import compute_pre_score


def _make_item(**kwargs) -> RawItem:
    now = datetime.now(timezone.utc).isoformat()
    defaults = dict(
        id=1, source_id=1, external_id="ext1",
        title="Some AI News",
        url="https://example.com/post",
        excerpt="A short excerpt about AI.",
        author="Author",
        published_at=now,
        ingested_at=now,
        status="pending",
        pre_score=None,
        error_message=None,
        source_name="OpenAI Blog",
        source_weight=30,
    )
    defaults.update(kwargs)
    return RawItem(**defaults)


class TestComputePreScore:
    def test_returns_score_and_breakdown(self):
        item = _make_item()
        score, breakdown = compute_pre_score(item)
        assert isinstance(score, int)
        assert isinstance(breakdown, dict)
        assert "source_weight" in breakdown
        assert "keyword_score" in breakdown
        assert "recency_score" in breakdown
        assert "length_score" in breakdown

    def test_score_within_range(self):
        item = _make_item()
        score, _ = compute_pre_score(item)
        assert 0 <= score <= 100

    def test_high_source_weight_increases_score(self):
        low = _make_item(source_weight=10)
        high = _make_item(source_weight=30)
        score_low, _ = compute_pre_score(low)
        score_high, _ = compute_pre_score(high)
        assert score_high > score_low

    def test_keyword_match_increases_score(self):
        no_kw = _make_item(title="Random blog post", excerpt="Nothing relevant")
        kw = _make_item(title="GPT-5 model released via API", excerpt="major breakthrough")
        score_no, _ = compute_pre_score(no_kw)
        score_kw, _ = compute_pre_score(kw)
        assert score_kw > score_no

    def test_old_item_gets_zero_recency(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        item = _make_item(published_at=old_date)
        _, breakdown = compute_pre_score(item)
        assert breakdown["recency_score"] == 0

    def test_today_item_gets_max_recency(self):
        item = _make_item(published_at=datetime.now(timezone.utc).isoformat())
        _, breakdown = compute_pre_score(item)
        assert breakdown["recency_score"] == 20

    def test_no_excerpt_reduces_length_score(self):
        with_exc = _make_item(excerpt="This is a good excerpt with details.")
        no_exc = _make_item(excerpt=None)
        _, bd_with = compute_pre_score(with_exc)
        _, bd_no = compute_pre_score(no_exc)
        assert bd_with["length_score"] > bd_no["length_score"]

    def test_breakdown_sums_to_total(self):
        item = _make_item()
        score, breakdown = compute_pre_score(item)
        assert score == sum(breakdown.values())
