"""Test that bulk_upsert_cases executes in batches, not row-by-row."""

from unittest.mock import AsyncMock

import pytest


class TestBulkUpsertBatching:
    """Verify bulk_upsert_cases uses batch execution."""

    @pytest.mark.asyncio
    async def test_batch_executes_once_per_batch_not_per_row(self):
        """With 5 rows and batch_size=250, should be 1 db.execute call, not 5."""
        from app.core.ingestion.pipeline import bulk_upsert_cases

        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        cases = [
            {"id": f"id-{i}", "title": f"Case {i}", "court": "SC", "citation": f"cite-{i}"}
            for i in range(5)
        ]

        ids = await bulk_upsert_cases(cases, mock_db)
        assert len(ids) == 5
        # Key assertion: should be 1 execute call (batch), not 5 (per-row)
        assert mock_db.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_returns_pre_generated_ids(self):
        """IDs should come from the input data, not from RETURNING."""
        from app.core.ingestion.pipeline import bulk_upsert_cases

        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        cases = [
            {"id": "my-id-1", "title": "Case 1", "court": "SC", "citation": "cite-1"},
            {"id": "my-id-2", "title": "Case 2", "court": "SC", "citation": "cite-2"},
        ]

        ids = await bulk_upsert_cases(cases, mock_db)
        assert ids == ["my-id-1", "my-id-2"]
