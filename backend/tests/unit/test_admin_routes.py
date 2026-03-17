"""Tests for admin review, corrections, and data quality routes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.admin_review import router as review_router
from app.api.routes.admin_corrections import router as corrections_router
from app.api.routes.data_quality import router as quality_router
from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ADMIN_PAYLOAD = TokenPayload(
    sub="admin-user-id",
    role="admin",
    exp=datetime(2099, 1, 1, tzinfo=timezone.utc),
    iat=datetime(2024, 1, 1, tzinfo=timezone.utc),
    jti=str(uuid.uuid4()),
)

_CASE_ID = str(uuid.uuid4())


def _make_app(*routers_and_prefixes):
    """Build a test FastAPI app with given routers."""
    app = FastAPI()
    for router, prefix in routers_and_prefixes:
        app.include_router(router, prefix=prefix)
    # Override get_current_user so the role checker receives admin payload
    app.dependency_overrides[get_current_user] = lambda: _ADMIN_PAYLOAD
    return app


def _mock_db_for_mappings(rows: list[dict]):
    """Create an AsyncMock DB where execute returns rows as mappings."""
    mock_result = MagicMock()
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = rows
    mock_mappings.first.return_value = rows[0] if rows else None
    mock_result.mappings.return_value = mock_mappings
    mock_result.scalar.return_value = len(rows)
    mock_result.fetchone.return_value = (rows[0]["id"],) if rows else None

    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


# ---------------------------------------------------------------------------
# Admin review queue tests
# ---------------------------------------------------------------------------

class TestAdminReviewRoutes:

    def _make_client(self, db):
        app = _make_app((review_router, "/review"))
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app)

    def test_list_review_queue_returns_items(self):
        row = {
            "id": _CASE_ID,
            "title": "Test Case",
            "citation": "(2023) 1 SCC 1",
            "court": "Supreme Court of India",
            "year": 2023,
            "ingestion_status": "needs_review",
            "extraction_confidence": 0.35,
            "metadata_provenance": {"title": "llm"},
            "created_at": datetime(2023, 6, 1, tzinfo=timezone.utc),
        }
        db = _mock_db_for_mappings([row])
        client = self._make_client(db)

        resp = client.get("/review?status=needs_review")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == _CASE_ID

    def test_list_review_queue_empty(self):
        db = _mock_db_for_mappings([])
        # Override scalar for count
        db.execute.return_value.scalar.return_value = 0
        client = self._make_client(db)

        resp = client.get("/review?status=needs_review")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_approve_case(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (_CASE_ID,)
        db.execute.return_value = mock_result

        client = self._make_client(db)
        resp = client.post(f"/review/{_CASE_ID}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"

    def test_approve_nonexistent_case(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        db.execute.return_value = mock_result

        client = self._make_client(db)
        resp = client.post(f"/review/{_CASE_ID}/approve")
        assert resp.status_code == 404

    def test_reject_case(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (_CASE_ID,)
        db.execute.return_value = mock_result

        client = self._make_client(db)
        resp = client.post(f"/review/{_CASE_ID}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


# ---------------------------------------------------------------------------
# Admin corrections tests
# ---------------------------------------------------------------------------

class TestAdminCorrectionRoutes:

    def _make_client(self, db):
        app = _make_app((corrections_router, "/corrections"))
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app)

    def test_correct_scalar_field(self):
        db = AsyncMock()
        # First call: SELECT existing value
        mock_select = MagicMock()
        mock_select_map = MagicMock()
        mock_select_map.first.return_value = {
            "title": "Old Title",
            "metadata_provenance": json.dumps({"title": "llm"}),
        }
        mock_select.mappings.return_value = mock_select_map

        # Subsequent calls: UPDATE, UPDATE provenance, INSERT audit_log
        mock_update = MagicMock()
        mock_update.fetchone.return_value = None

        db.execute.side_effect = [mock_select, mock_update, mock_update, mock_update]

        client = self._make_client(db)
        resp = client.post(
            f"/corrections/{_CASE_ID}/correct",
            json={
                "field": "title",
                "new_value": "Corrected Title",
                "reason": "Typo in original extraction",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["field"] == "title"
        assert data["old_value"] == "Old Title"
        assert data["new_value"] == "Corrected Title"
        assert data["status"] == "corrected"

    def test_correct_invalid_field_rejected(self):
        db = AsyncMock()
        client = self._make_client(db)
        resp = client.post(
            f"/corrections/{_CASE_ID}/correct",
            json={
                "field": "full_text",
                "new_value": "should not be allowed",
                "reason": "trying to change full_text",
            },
        )
        assert resp.status_code == 400
        assert "not correctable" in resp.json()["detail"]

    def test_correct_nonexistent_case(self):
        db = AsyncMock()
        mock_select = MagicMock()
        mock_select_map = MagicMock()
        mock_select_map.first.return_value = None
        mock_select.mappings.return_value = mock_select_map
        db.execute.return_value = mock_select

        client = self._make_client(db)
        resp = client.post(
            f"/corrections/{_CASE_ID}/correct",
            json={
                "field": "title",
                "new_value": "New Title",
                "reason": "Fix title",
            },
        )
        assert resp.status_code == 404

    def test_correction_history(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = [
            {
                "metadata": json.dumps({
                    "field": "title",
                    "old_value": "Old",
                    "new_value": "New",
                    "reason": "Fix",
                    "corrected_by": "admin-user-id",
                }),
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
        ]
        mock_result.mappings.return_value = mock_mappings
        db.execute.return_value = mock_result

        client = self._make_client(db)
        resp = client.get(f"/corrections/{_CASE_ID}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["corrections"]) == 1
        assert data["corrections"][0]["field"] == "title"

    def test_array_field_requires_list(self):
        db = AsyncMock()
        client = self._make_client(db)
        resp = client.post(
            f"/corrections/{_CASE_ID}/correct",
            json={
                "field": "judge",
                "new_value": "not a list",
                "reason": "Testing validation",
            },
        )
        assert resp.status_code == 400
        assert "list" in resp.json()["detail"]

    @pytest.mark.parametrize("malicious_field", [
        "title; DROP TABLE cases--",
        "title, password FROM users--",
        "1=1; UPDATE cases SET title='hacked' WHERE 1=1--",
        "title FROM cases UNION SELECT secret FROM credentials--",
    ])
    def test_sql_injection_in_field_name_rejected(self, malicious_field):
        """Fields containing SQL metacharacters must be rejected."""
        db = AsyncMock()
        client = self._make_client(db)
        resp = client.post(
            f"/corrections/{_CASE_ID}/correct",
            json={
                "field": malicious_field,
                "new_value": "anything",
                "reason": "Testing SQL injection defence",
            },
        )
        assert resp.status_code == 400
        assert "not correctable" in resp.json()["detail"]
        # Verify no SQL was executed
        db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Data quality dashboard tests
# ---------------------------------------------------------------------------

class TestDataQualityRoutes:

    def _make_client(self, db):
        app = _make_app((quality_router, "/data-quality"))
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app)

    def test_dashboard_with_data(self):
        db = AsyncMock()

        # Call 1: status breakdown
        mock_status = MagicMock()
        mock_status_map = MagicMock()
        mock_status_map.all.return_value = [
            {"ingestion_status": "complete", "cnt": 100},
            {"ingestion_status": "needs_review", "cnt": 5},
        ]
        mock_status.mappings.return_value = mock_status_map

        # Call 2: field population counts
        mock_pop = MagicMock()
        pop_row = {f"{f}_count": 80 for f in [
            "title", "citation", "court", "year", "decision_date",
            "case_type", "jurisdiction", "bench_type", "petitioner",
            "respondent", "author_judge", "disposal_nature", "ratio_decidendi",
            "case_number", "headnotes", "outcome_summary", "coram_size",
            "lower_court", "opinion_type", "split_ratio",
            "petitioner_type", "respondent_type", "is_pil",
            "extraction_confidence", "text_hash",
            "judge", "acts_cited", "cases_cited", "keywords",
            "dissenting_judges", "concurring_judges", "companion_cases",
        ]}
        mock_pop_map = MagicMock()
        mock_pop_map.first.return_value = pop_row
        mock_pop.mappings.return_value = mock_pop_map

        # Call 3: avg fields
        mock_avg = MagicMock()
        mock_avg_map = MagicMock()
        mock_avg_map.first.return_value = {"avg_fields": 18.5}
        mock_avg.mappings.return_value = mock_avg_map

        # Call 4: citation stats
        mock_cit = MagicMock()
        mock_cit_map = MagicMock()
        mock_cit_map.first.return_value = {
            "cases_with_citations": 90,
            "known_citations": 1500,
        }
        mock_cit.mappings.return_value = mock_cit_map

        db.execute.side_effect = [mock_status, mock_pop, mock_avg, mock_cit]

        client = self._make_client(db)
        resp = client.get("/data-quality")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cases"] == 105
        assert "complete" in data["status_breakdown"]
        assert "title" in data["field_population"]
        assert data["average_fields_per_case"] == 18.5

    def test_dashboard_empty_database(self):
        db = AsyncMock()

        mock_status = MagicMock()
        mock_status_map = MagicMock()
        mock_status_map.all.return_value = []
        mock_status.mappings.return_value = mock_status_map

        db.execute.return_value = mock_status

        client = self._make_client(db)
        resp = client.get("/data-quality")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cases"] == 0


# ---------------------------------------------------------------------------
# Benchmark extraction tests
# ---------------------------------------------------------------------------

class TestBenchmarkExtraction:
    """Test the benchmark evaluation logic (no LLM calls)."""

    def test_compare_scalar_match(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
        from benchmark_extraction import _compare_scalar

        has_gold, matches = _compare_scalar("Supreme Court of India", "supreme court of india")
        assert has_gold is True
        assert matches is True

    def test_compare_scalar_mismatch(self):
        from benchmark_extraction import _compare_scalar

        has_gold, matches = _compare_scalar(2023, 2024)
        assert has_gold is True
        assert matches is False

    def test_compare_scalar_none_gold(self):
        from benchmark_extraction import _compare_scalar

        has_gold, matches = _compare_scalar(None, "something")
        assert has_gold is False

    def test_compare_list_overlap(self):
        from benchmark_extraction import _compare_list

        tp, fp, fn = _compare_list(
            ["Section 302 IPC", "Section 34 IPC"],
            ["section 302 ipc", "Section 307 IPC"],
        )
        assert tp == 1  # 302 IPC matches
        assert fp == 1  # 307 IPC is false positive
        assert fn == 1  # 34 IPC is false negative

    def test_evaluate_case_tracks_metrics(self):
        from benchmark_extraction import evaluate_case, BenchmarkResults
        from app.core.ingestion.metadata import CaseMetadata

        results = BenchmarkResults()
        gold = {"title": "State v. X", "year": 2023, "court": "Supreme Court of India"}
        predicted = CaseMetadata(
            title="State v. X",
            year=2023,
            court="High Court of Delhi",
        )
        evaluate_case(gold, predicted, results, {"title", "year", "court"})

        assert results.field_metrics["title"].true_positive == 1
        assert results.field_metrics["year"].true_positive == 1
        assert results.field_metrics["court"].false_negative == 1  # mismatch
