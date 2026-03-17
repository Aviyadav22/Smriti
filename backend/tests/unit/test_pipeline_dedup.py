"""Tests for text-hash dedup early-exit logic in ingest_single_case."""

import inspect
import pytest


class TestTextHashDedupRaceSafety:
    """Verify the dedup query uses row-level locking for race safety."""

    def test_dedup_check_uses_for_update_skip_locked(self):
        """The advisory SELECT should use FOR UPDATE SKIP LOCKED to prevent races."""
        from app.core.ingestion import pipeline
        source = inspect.getsource(pipeline.ingest_judgment)
        assert "FOR UPDATE SKIP LOCKED" in source, (
            "Dedup SELECT must use FOR UPDATE SKIP LOCKED to prevent "
            "race conditions during concurrent ingestion"
        )
