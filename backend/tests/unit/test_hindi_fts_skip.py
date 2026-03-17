"""Tests for Hindi FTS skip behavior in search layer."""

import pytest

from app.core.search.fulltext import search_fulltext


class TestHindiFTSSkip:
    """When language='hi', FTS should return empty immediately."""

    @pytest.mark.asyncio
    async def test_hindi_fts_returns_empty(self):
        """Hindi queries should skip FTS entirely without touching DB."""
        result = await search_fulltext(
            "धारा 302 भारतीय दंड संहिता",
            language="hi",
            db=None,  # type: ignore[arg-type]  # Should never touch DB
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_english_fts_requires_db(self):
        """English queries should NOT skip FTS (will fail without DB)."""
        with pytest.raises(Exception):
            await search_fulltext(
                "Section 302 IPC",
                language="en",
                db=None,  # type: ignore[arg-type]
            )

    @pytest.mark.asyncio
    async def test_default_language_is_english(self):
        """Default language should be 'en' (backward compatible)."""
        with pytest.raises(Exception):
            await search_fulltext(
                "murder conviction",
                db=None,  # type: ignore[arg-type]
            )
