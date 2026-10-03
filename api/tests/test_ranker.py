"""Tests for feed ranking and interest keyword extraction."""
from datetime import datetime, timezone, timedelta
from app.pipeline.ranker import compute_feed_score, extract_matched_keywords, parse_published_datetime


def test_extract_matched_keywords():
    text = "Announcing new FastAPI integration with vLLM and RAG speculative decoding."
    matched = extract_matched_keywords(text)
    assert "fastapi" in matched
    assert "vllm" in matched
    assert "rag" in matched
    assert "speculative decoding" in matched


def test_compute_feed_score_recency_decay():
    now_dt = datetime.now(timezone.utc)
    recent_pub = (now_dt - timedelta(hours=2)).isoformat()
    old_pub = (now_dt - timedelta(hours=48)).isoformat()

    text_recent = "New release of vLLM"
    text_plain = "Generic update"

    score_recent, kws_recent = compute_feed_score(
        importance_score=90,
        category="tool",
        category_max_score=100,
        text_for_keywords=text_recent,
        published_at_str=recent_pub,
        now_dt=now_dt,
    )

    score_old, kws_old = compute_feed_score(
        importance_score=90,
        category="tool",
        category_max_score=100,
        text_for_keywords=text_plain,
        published_at_str=old_pub,
        now_dt=now_dt,
    )

    assert "vllm" in kws_recent
    assert len(kws_old) == 0
    # Recent item with keyword match must rank higher than old item without keyword match
    assert score_recent > score_old
