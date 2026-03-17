"""Tests for pipeline transaction handling.

Verifies that the initial ingestion_status = 'processing' UPDATE is wrapped
in an explicit transaction (async with db.begin()) so it commits atomically
and independently from the bulk pipeline commit.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.ingestion.pipeline import ingest_judgment


@asynccontextmanager
async def _fake_begin():
    """Simulate async with db.begin(): context manager."""
    yield


def _make_db_mock() -> AsyncMock:
    """Build a mock AsyncSession with begin() returning an async CM."""
    db = AsyncMock()
    db.begin = MagicMock(side_effect=lambda: _fake_begin())
    # execute returns an awaitable; fetchone() on the result returns None
    # (no duplicate hash row).
    exec_result = MagicMock()
    exec_result.fetchone.return_value = None
    db.execute = AsyncMock(return_value=exec_result)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _make_metadata_mock():
    """Build a mock CaseMetadata with all required attributes."""
    return MagicMock(
        citation="2024 INSC 1",
        case_name="Test v State",
        date_of_judgment=None,
        petitioner="Test",
        respondent="State",
        bench=["Justice A"],
        court="Supreme Court of India",
        case_number=None,
        is_reportable=None,
        headnotes=None,
        outcome_summary=None,
        case_type=None,
        acts_cited=[],
        cases_cited=[],
    )


def _make_quality_mock():
    """Build a mock TextQuality object."""
    return MagicMock(
        text="Full text of the judgment for testing purposes " * 20,
        char_count=1000,
        tier="high",
        legal_keyword_count=10,
    )


def _common_patches(fake_case_id: str):
    """Return a tuple of patch context managers for the pipeline.

    Patches everything before detect_judgment_sections, which raises
    RuntimeError to halt the pipeline right after the status UPDATE.
    """
    meta = _make_metadata_mock()
    quality = _make_quality_mock()
    return (
        patch(
            "app.core.ingestion.pipeline.extract_and_score",
            new_callable=AsyncMock,
            return_value=quality,
        ),
        patch(
            "app.core.ingestion.pipeline.extract_metadata_llm",
            new_callable=AsyncMock,
            return_value=meta,
        ),
        patch(
            "app.core.ingestion.pipeline.validate_parquet_data",
            return_value={"title": "Test case"},
        ),
        patch(
            "app.core.ingestion.pipeline.merge_metadata",
            return_value=(meta, {"citation": "llm"}),
        ),
        patch(
            "app.core.ingestion.pipeline.validate_with_regex",
            return_value=meta,
        ),
        patch("app.core.ingestion.pipeline.validate_cross_fields", return_value=meta),
        patch(
            "app.core.ingestion.pipeline.extract_acts_cited",
            return_value=[],
        ),
        patch(
            "app.core.ingestion.pipeline.extract_citations",
            return_value=[],
        ),
        patch(
            "app.core.ingestion.pipeline.compute_extraction_confidence",
            return_value=0.85,
        ),
        patch(
            "app.core.ingestion.pipeline._insert_case",
            new_callable=AsyncMock,
            return_value=(fake_case_id, False),
        ),
        patch(
            "app.core.ingestion.pipeline.detect_judgment_sections",
            side_effect=RuntimeError("stop-after-status-update"),
        ),
        patch(
            "app.core.ingestion.pipeline._record_ingestion_failure",
            new_callable=AsyncMock,
        ),
    )


async def _run_pipeline(db: AsyncMock) -> None:
    """Invoke ingest_judgment with mocked deps, expecting RuntimeError."""
    await ingest_judgment(
        pdf_path="/tmp/test.pdf",
        parquet_metadata={"title": "Test case"},
        db=db,
        llm=AsyncMock(),
        embedder=AsyncMock(),
        vector_store=AsyncMock(),
        graph_store=AsyncMock(),
        storage=AsyncMock(),
    )


class TestIngestionStatusTransaction:
    """Verify the 'processing' status update uses an explicit transaction."""

    @pytest.mark.asyncio
    async def test_begin_called_for_status_update(self):
        """db.begin() must be called for the processing status UPDATE.

        The pipeline is halted at detect_judgment_sections (step 6), right
        after the status UPDATE.  The assertion checks db.begin() was called.
        """
        db = _make_db_mock()
        fake_case_id = "case-tx-test"

        p = _common_patches(fake_case_id)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11]:
            with pytest.raises(RuntimeError, match="stop-after-status-update"):
                await _run_pipeline(db)

        # The key assertion: db.begin() was called (for the status update)
        db.begin.assert_called()

    @pytest.mark.asyncio
    async def test_status_update_inside_begin_block(self):
        """The UPDATE ... ingestion_status = 'processing' must execute
        inside the begin() context manager (between __aenter__ and __aexit__).
        """
        db = _make_db_mock()
        call_order: list[str] = []

        # Track call ordering via a custom begin() CM
        @asynccontextmanager
        async def tracking_begin():
            call_order.append("begin_enter")
            yield
            call_order.append("begin_exit")

        db.begin = MagicMock(side_effect=lambda: tracking_begin())

        # Wrap execute to detect the status update query
        base_exec_result = MagicMock()
        base_exec_result.fetchone.return_value = None

        async def tracking_execute(*args, **kwargs):
            stmt = str(args[0]) if args else ""
            if "ingestion_status" in stmt and "processing" in stmt:
                call_order.append("status_update")
            return base_exec_result

        db.execute = AsyncMock(side_effect=tracking_execute)

        fake_case_id = "case-tx-order"

        p = _common_patches(fake_case_id)
        with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11]:
            with pytest.raises(RuntimeError, match="stop-after-status-update"):
                await _run_pipeline(db)

        # Verify ordering: begin_enter -> status_update -> begin_exit
        assert "begin_enter" in call_order, f"begin() not entered; call_order={call_order}"
        assert "status_update" in call_order, f"status UPDATE not executed; call_order={call_order}"
        begin_idx = call_order.index("begin_enter")
        update_idx = call_order.index("status_update")
        exit_idx = call_order.index("begin_exit")
        assert begin_idx < update_idx < exit_idx, (
            f"Status update must be inside begin() block; call_order={call_order}"
        )
