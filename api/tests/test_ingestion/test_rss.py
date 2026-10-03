"""Tests for the RSS ingester."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.ingestion.rss import RSSIngester, _clean_html, _extract_excerpt, _parse_date
from app.models.item import Source


def _make_source(**kwargs) -> Source:
    defaults = dict(
        id=1, name="Test Feed", type="rss",
        url="https://example.com", feed_url="https://example.com/rss.xml",
        active=True, fetch_interval_minutes=360,
        config_json="{}", source_weight=25,
        last_fetched_at=None, created_at="2026-01-01T00:00:00Z",
    )
    defaults.update(kwargs)
    return Source(**defaults)


class TestCleanHtml:
    def test_strips_tags(self):
        assert _clean_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_collapses_whitespace(self):
        assert _clean_html("<p>  foo   bar  </p>") == "foo bar"

    def test_plain_text_unchanged(self):
        assert _clean_html("plain text") == "plain text"


class TestExtractExcerpt:
    def _make_entry(self, summary=None, content=None):
        entry = MagicMock()
        entry.summary = summary
        if content:
            entry.content = content
        else:
            del entry.content  # ensure AttributeError → hasattr returns False
        return entry

    def test_uses_summary(self):
        entry = self._make_entry(summary="<p>Short excerpt</p>")
        result = _extract_excerpt(entry)
        assert result == "Short excerpt"

    def test_caps_at_500_chars(self):
        entry = self._make_entry(summary="x" * 1000)
        result = _extract_excerpt(entry)
        assert result is not None
        assert len(result) <= 500

    def test_no_content_returns_none(self):
        entry = self._make_entry(summary=None)
        result = _extract_excerpt(entry)
        assert result is None


class TestRSSIngester:
    def _make_feed(self, entries):
        feed = MagicMock()
        feed.bozo = False
        feed.entries = entries
        return feed

    def _make_entry(self, title, link, summary="excerpt", published_parsed=None):
        e = MagicMock()
        e.title = title
        e.link = link
        e.id = link
        e.summary = summary
        e.published_parsed = published_parsed
        e.updated_parsed = None
        e.created_parsed = None
        e.author = "Test Author"
        e.get = lambda k, default=None: {
            "title": title, "link": link, "author": "Test Author"
        }.get(k, default)
        return e

    @pytest.mark.asyncio
    async def test_fetch_returns_items(self):
        source = _make_source()
        ingester = RSSIngester(source)

        entry = self._make_entry("GPT-5 Released", "https://openai.com/gpt5")
        feed = self._make_feed([entry])

        with patch("app.ingestion.rss.feedparser.parse", return_value=feed):
            items = await ingester.fetch()

        assert len(items) == 1
        assert items[0].title == "GPT-5 Released"
        assert items[0].url == "https://openai.com/gpt5"

    @pytest.mark.asyncio
    async def test_skips_entry_without_link(self):
        source = _make_source()
        ingester = RSSIngester(source)

        entry = self._make_entry("No Link", "")
        entry.link = ""
        feed = self._make_feed([entry])

        with patch("app.ingestion.rss.feedparser.parse", return_value=feed):
            items = await ingester.fetch()

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_excerpt_never_exceeds_500(self):
        source = _make_source()
        ingester = RSSIngester(source)

        entry = self._make_entry(
            "Long Article", "https://example.com/long",
            summary="<p>" + "A" * 2000 + "</p>",
        )
        feed = self._make_feed([entry])

        with patch("app.ingestion.rss.feedparser.parse", return_value=feed):
            items = await ingester.fetch()

        assert items[0].excerpt is not None
        assert len(items[0].excerpt) <= 500

    @pytest.mark.asyncio
    async def test_handles_parse_error_gracefully(self):
        source = _make_source()
        ingester = RSSIngester(source)

        with patch("app.ingestion.rss.feedparser.parse", side_effect=Exception("network error")):
            items = await ingester.fetch()

        assert items == []
