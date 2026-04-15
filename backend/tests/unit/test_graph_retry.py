"""Tests for the graph build retry queue module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ingestion.graph_retry import (
    get_pending_retries,
    increment_retry_count,
    mark_retry_success,
    record_graph_failure,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> AsyncMock:
    """Create a mock AsyncSession."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# record_graph_failure
# ---------------------------------------------------------------------------

class TestRecordGraphFailure:
    @pytest.mark.asyncio
    async def test_inserts_row_with_correct_params(self):
        db = _make_db()

        await record_graph_failure(db, "case-123", "Neo4j timeout")

        db.execute.assert_called_once()
        args, kwargs = db.execute.call_args
        sql_text = str(args[0].text)
        params = args[1]

        assert "INSERT INTO graph_build_queue" in sql_text
        assert "ON CONFLICT (case_id) DO UPDATE" in sql_text
        assert params["case_id"] == "case-123"
        assert params["error"] == "Neo4j timeout"
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_truncates_error_to_500_chars(self):
        db = _make_db()
        long_error = "x" * 1000

        await record_graph_failure(db, "case-456", long_error)

        args, _ = db.execute.call_args
        params = args[1]
        assert len(params["error"]) == 500

    @pytest.mark.asyncio
    async def test_short_error_not_truncated(self):
        db = _make_db()
        short_error = "Connection refused"

        await record_graph_failure(db, "case-789", short_error)

        args, _ = db.execute.call_args
        params = args[1]
        assert params["error"] == "Connection refused"


# ---------------------------------------------------------------------------
# get_pending_retries
# ---------------------------------------------------------------------------

class TestGetPendingRetries:
    @pytest.mark.asyncio
    async def test_returns_cases_under_max_retries(self):
        db = _make_db()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("case-1", 0),
            ("case-2", 1),
        ]
        db.execute.return_value = mock_result

        result = await get_pending_retries(db, max_retries=3)

        assert result == [("case-1", 0), ("case-2", 1)]
        db.execute.assert_called_once()
        args, _ = db.execute.call_args
        sql_text = str(args[0].text)
        params = args[1]
        assert "retry_count < :max_retries" in sql_text
        assert params["max_retries"] == 3

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_pending(self):
        db = _make_db()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result

        result = await get_pending_retries(db)

        assert result == []

    @pytest.mark.asyncio
    async def test_default_max_retries_is_3(self):
        db = _make_db()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db.execute.return_value = mock_result

        await get_pending_retries(db)

        args, _ = db.execute.call_args
        params = args[1]
        assert params["max_retries"] == 3


# ---------------------------------------------------------------------------
# mark_retry_success
# ---------------------------------------------------------------------------

class TestMarkRetrySuccess:
    @pytest.mark.asyncio
    async def test_deletes_row_for_case(self):
        db = _make_db()

        await mark_retry_success(db, "case-done")

        db.execute.assert_called_once()
        args, _ = db.execute.call_args
        sql_text = str(args[0].text)
        params = args[1]
        assert "DELETE FROM graph_build_queue" in sql_text
        assert params["case_id"] == "case-done"
        db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# increment_retry_count
# ---------------------------------------------------------------------------

class TestIncrementRetryCount:
    @pytest.mark.asyncio
    async def test_updates_retry_count(self):
        db = _make_db()

        await increment_retry_count(db, "case-retry")

        db.execute.assert_called_once()
        args, _ = db.execute.call_args
        sql_text = str(args[0].text)
        params = args[1]
        assert "retry_count = retry_count + 1" in sql_text
        assert "updated_at = NOW()" in sql_text
        assert params["case_id"] == "case-retry"
        db.commit.assert_awaited_once()
