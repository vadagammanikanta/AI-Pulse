"""Tests for the deduplicator."""
from __future__ import annotations

import pytest

from app.pipeline.deduplicator import normalize_url, is_duplicate


class TestNormalizeUrl:
    def test_strips_utm_params(self):
        url = "https://example.com/post?utm_source=twitter&utm_medium=social"
        assert normalize_url(url) == "https://example.com/post"

    def test_strips_fbclid(self):
        url = "https://example.com/post?fbclid=abc123"
        assert normalize_url(url) == "https://example.com/post"

    def test_preserves_semantic_params(self):
        url = "https://example.com/search?q=llm&page=2"
        norm = normalize_url(url)
        assert "q=llm" in norm
        assert "page=2" in norm

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/post/") == "https://example.com/post"

    def test_lowercases_domain(self):
        assert normalize_url("HTTPS://EXAMPLE.COM/Post") == "https://example.com/Post"

    def test_strips_fragment(self):
        url = "https://example.com/post#section"
        assert "#section" not in normalize_url(url)

    def test_handles_malformed_url(self):
        result = normalize_url("not a url")
        assert isinstance(result, str)


class TestIsDeuplicate:
    @pytest.mark.asyncio
    async def test_new_item_not_duplicate(self, seeded_db):
        result = await is_duplicate(
            "https://openai.com/new-article",
            "Brand New Article About AI",
            source_id=1,
            db=seeded_db,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_exact_url_match_is_duplicate(self, seeded_db):
        # Insert a raw_item with source_id=2 (different source)
        await seeded_db.execute(
            "INSERT INTO raw_items (source_id, external_id, title, url) VALUES (2, 'ext1', 'Existing', 'https://example.com/existing')"
        )
        await seeded_db.commit()

        result = await is_duplicate(
            "https://example.com/existing",
            "Different Title Same URL",
            source_id=1,  # different source_id
            db=seeded_db,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_fuzzy_title_match_is_duplicate(self, seeded_db):
        await seeded_db.execute(
            "INSERT INTO raw_items (source_id, external_id, title, url) VALUES (1, 'ext2', 'GPT-5 Released by OpenAI Today', 'https://openai.com/gpt5')"
        )
        await seeded_db.commit()

        result = await is_duplicate(
            "https://example.com/different-url",
            "GPT-5 Released by OpenAI Today",  # identical title
            source_id=2,
            db=seeded_db,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_similar_but_distinct_titles_not_duplicate(self, seeded_db):
        await seeded_db.execute(
            "INSERT INTO raw_items (source_id, external_id, title, url) VALUES (1, 'ext3', 'GPT-4 Released', 'https://openai.com/gpt4')"
        )
        await seeded_db.commit()

        result = await is_duplicate(
            "https://anthropic.com/claude3",
            "Claude 3 Released by Anthropic",
            source_id=2,
            db=seeded_db,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_utm_urls_deduplicated(self, seeded_db):
        await seeded_db.execute(
            "INSERT INTO raw_items (source_id, external_id, title, url) VALUES (1, 'ext4', 'Some Article', 'https://example.com/post')"
        )
        await seeded_db.commit()

        # Same URL with UTM params should be detected as duplicate
        result = await is_duplicate(
            "https://example.com/post?utm_source=twitter",
            "Some Article",
            source_id=2,
            db=seeded_db,
        )
        assert result is True
