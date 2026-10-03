"""Tests for the arXiv category rule."""
from app.pipeline.ranker import apply_arxiv_rule


def test_arxiv_url_forces_category_paper_and_caps_importance_without_keywords():
    cat, score = apply_arxiv_rule(
        url="https://arxiv.org/abs/2609.12345",
        source_name="arXiv cs.AI",
        title="A General Survey of Methods",
        excerpt="We survey general methods without specific interest terms.",
        category="tool",
        importance_score=95,
    )
    assert cat == "paper"
    assert score == 60  # Capped at 60 because no interest keywords matched


def test_arxiv_url_preserves_high_score_when_matching_interest_keywords():
    cat, score = apply_arxiv_rule(
        url="https://arxiv.org/abs/2609.12345",
        source_name="arXiv cs.AI",
        title="DeepSeek-R1: GRPO Fine-Tuning for Reasoning",
        excerpt="We present GRPO fine-tuning for DeepSeek models.",
        category="news",
        importance_score=95,
    )
    assert cat == "paper"
    assert score == 95  # Not capped because 'deepseek' and 'grpo' match interest keywords


def test_non_arxiv_item_keeps_original_category_and_score():
    cat, score = apply_arxiv_rule(
        url="https://github.com/vllm-project/vllm",
        source_name="GitHub Trending",
        title="vLLM v0.7 Released",
        excerpt="Fast LLM serving engine.",
        category="tool",
        importance_score=85,
    )
    assert cat == "tool"
    assert score == 85
