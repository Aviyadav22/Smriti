"""Tests for case detail API routes."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.cases import router
from app.db.postgres import get_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CASE_ID = str(uuid.uuid4())
_CITED_CASE_ID = str(uuid.uuid4())
_CITING_CASE_ID = str(uuid.uuid4())
_SIMILAR_CASE_ID = str(uuid.uuid4())


def _make_case_row(case_id: str = _CASE_ID) -> dict:
    """Return a dict mimicking a full case row from PostgreSQL."""
    return {
        "id": case_id,
        "title": "State of Maharashtra v. Rajesh Kumar",
        "citation": "(2023) 7 SCC 456",
        "case_id": "CA-5678-2023",
        "cnr": "SCCA12345678902023",
        "court": "Supreme Court of India",
        "year": 2023,
        "case_type": "Civil Appeal",
        "jurisdiction": "Civil",
        "bench_type": "Division Bench",
        "judge": ["A.B. Sharma", "C.D. Patel"],
        "author_judge": "A.B. Sharma",
        "petitioner": "State of Maharashtra",
        "respondent": "Rajesh Kumar & Ors.",
        "decision_date": date(2023, 3, 15),
        "disposal_nature": "Dismissed",
        "description": "Land acquisition compensation dispute",
        "keywords": ["land acquisition", "compensation"],
        "acts_cited": ["Land Acquisition Act, 2013"],
        "cases_cited": ["(2019) 5 SCC 234"],
        "ratio_decidendi": "Personal hearing under Section 26 is mandatory.",
        "full_text": "JUDGMENT\nThis is the judgment text.",
        "pdf_storage_path": f"pdfs/{case_id}.pdf",
        "source": "indian-supreme-court-judgments",
        "language": "english",
        "chunk_count": 3,
        "available_languages": "english,hindi",
        "created_at": datetime(2023, 6, 1, tzinfo=UTC),
        "updated_at": datetime(2023, 6, 2, tzinfo=UTC),
    }


def _make_summary_row(case_id: str, title: str = "Some Case") -> dict:
    """Return a dict mimicking a summary row for enrichment queries."""
    return {
        "id": case_id,
        "title": title,
        "citation": "(2022) 3 SCC 100",
        "court": "Supreme Court of India",
        "year": 2022,
        "decision_date": date(2022, 1, 10),
    }


def _mock_db_execute(rows: list[dict], *, scalar: object | None = None):
    """Build an AsyncMock for db.execute that returns mapping rows."""
    mock_result = MagicMock()

    # Support .mappings().one_or_none()
    mock_mappings = MagicMock()
    if rows:
        mock_mappings.one_or_none.return_value = rows[0]
        mock_mappings.all.return_value = rows
    else:
        mock_mappings.one_or_none.return_value = None
        mock_mappings.all.return_value = []
    mock_result.mappings.return_value = mock_mappings

    # Support .scalar_one_or_none() for existence checks
    mock_result.scalar_one_or_none.return_value = scalar

    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


def _mock_db_multi_execute(results: list):
    """Build an AsyncMock for db.execute that returns different results per call."""
    db = AsyncMock()
    side_effects = []
    for spec in results:
        mock_result = MagicMock()
        if isinstance(spec, dict) and "scalar" in spec:
            mock_result.scalar_one_or_none.return_value = spec["scalar"]
            mock_mappings = MagicMock()
            mock_mappings.one_or_none.return_value = spec.get("row")
            mock_mappings.all.return_value = spec.get("rows", [])
            mock_result.mappings.return_value = mock_mappings
        elif isinstance(spec, list):
            mock_mappings = MagicMock()
            mock_mappings.one_or_none.return_value = spec[0] if spec else None
            mock_mappings.all.return_value = spec
            mock_result.mappings.return_value = mock_mappings
            mock_result.scalar_one_or_none.return_value = 1 if spec else None
        else:
            mock_mappings = MagicMock()
            mock_mappings.one_or_none.return_value = None
            mock_mappings.all.return_value = []
            mock_result.mappings.return_value = mock_mappings
            mock_result.scalar_one_or_none.return_value = None
        side_effects.append(mock_result)
    db.execute.side_effect = side_effects
    return db


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/cases")
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Route registration tests
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    def test_all_case_endpoints_present(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/{case_id}" in paths
        assert "/{case_id}/pdf" in paths
        assert "/{case_id}/citations" in paths
        assert "/{case_id}/cited-by" in paths
        assert "/{case_id}/similar" in paths

    def test_all_endpoints_are_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "methods"):
                assert "GET" in route.methods


# ---------------------------------------------------------------------------
# GET /cases/{case_id} — Full case detail
# ---------------------------------------------------------------------------


class TestGetCase:
    def test_get_case_returns_full_detail(self, app: FastAPI, client: TestClient) -> None:
        """GET case by ID returns all fields."""
        case_row = _make_case_row()
        db = _mock_db_execute([case_row])

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        resp = client.get(f"/api/v1/cases/{_CASE_ID}")
        assert resp.status_code == 200

        body = resp.json()
        assert body["id"] == _CASE_ID
        assert body["title"] == "State of Maharashtra v. Rajesh Kumar"
        assert body["citation"] == "(2023) 7 SCC 456"
        assert body["court"] == "Supreme Court of India"
        assert body["year"] == 2023
        assert body["case_type"] == "Civil Appeal"
        assert body["petitioner"] == "State of Maharashtra"
        assert body["respondent"] == "Rajesh Kumar & Ors."
        assert body["disposal_nature"] == "Dismissed"
        assert body["ratio_decidendi"] == "Personal hearing under Section 26 is mandatory."
        # Sections should be built from full_text
        assert "sections" in body
        # full_text should be removed (popped) from the response
        assert "full_text" not in body
        # Datetime fields should be serialized as strings
        assert isinstance(body["decision_date"], str)
        assert isinstance(body["created_at"], str)
        assert isinstance(body["updated_at"], str)

        app.dependency_overrides.clear()

    def test_get_case_not_found_returns_404(self, app: FastAPI, client: TestClient) -> None:
        """Nonexistent case ID returns 404."""
        db = _mock_db_execute([])

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/cases/{fake_id}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Case not found"

        app.dependency_overrides.clear()

    def test_get_case_empty_full_text_returns_empty_sections(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """Case with no full_text returns empty sections dict."""
        case_row = _make_case_row()
        case_row["full_text"] = ""
        db = _mock_db_execute([case_row])

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        resp = client.get(f"/api/v1/cases/{_CASE_ID}")
        assert resp.status_code == 200
        assert resp.json()["sections"] == {}

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/citations
# ---------------------------------------------------------------------------


class TestGetCitations:
    @patch("app.api.routes.cases.get_graph_store")
    def test_get_citations_returns_cited_cases(
        self, mock_get_graph: MagicMock, app: FastAPI, client: TestClient
    ) -> None:
        """Citations endpoint returns outgoing CITES neighbors."""
        # First call: existence check (scalar), second call: enrichment query
        db = _mock_db_multi_execute(
            [
                {"scalar": 1},  # existence check
                [_make_summary_row(_CITED_CASE_ID, "Cited Case Title")],  # enrichment
            ]
        )

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        mock_graph = AsyncMock()
        mock_graph.get_neighbors.return_value = {
            "neighbors": [
                {
                    "node": {"id": _CITED_CASE_ID, "title": "Cited Case Title"},
                    "relationship": "CITES",
                }
            ]
        }
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/cases/{_CASE_ID}/citations")
        assert resp.status_code == 200

        body = resp.json()
        assert body["case_id"] == _CASE_ID
        assert body["total"] == 1
        assert len(body["citations"]) == 1
        assert body["citations"][0]["case_id"] == _CITED_CASE_ID
        assert body["citations"][0]["relationship"] == "CITES"

        mock_graph.get_neighbors.assert_awaited_once_with(
            _CASE_ID, relationship="CITES", direction="outgoing", depth=1
        )

        app.dependency_overrides.clear()

    def test_get_citations_case_not_found(self, app: FastAPI, client: TestClient) -> None:
        """Citations on nonexistent case returns 404."""
        db = _mock_db_multi_execute([{"scalar": None}])

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/cases/{fake_id}/citations")
        assert resp.status_code == 404

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/cited-by
# ---------------------------------------------------------------------------


class TestGetCitedBy:
    @patch("app.api.routes.cases.get_graph_store")
    def test_get_cited_by_returns_citing_cases(
        self, mock_get_graph: MagicMock, app: FastAPI, client: TestClient
    ) -> None:
        """Cited-by endpoint returns incoming CITES neighbors."""
        db = _mock_db_multi_execute(
            [
                {"scalar": 1},
                [_make_summary_row(_CITING_CASE_ID, "Citing Case Title")],
            ]
        )

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        mock_graph = AsyncMock()
        mock_graph.get_neighbors.return_value = {
            "neighbors": [
                {
                    "node": {"id": _CITING_CASE_ID, "title": "Citing Case Title"},
                    "relationship": "CITES",
                }
            ]
        }
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/cases/{_CASE_ID}/cited-by")
        assert resp.status_code == 200

        body = resp.json()
        assert body["case_id"] == _CASE_ID
        assert body["total"] == 1
        assert len(body["cited_by"]) == 1
        assert body["cited_by"][0]["case_id"] == _CITING_CASE_ID

        mock_graph.get_neighbors.assert_awaited_once_with(
            _CASE_ID, relationship="CITES", direction="incoming", depth=1
        )

        app.dependency_overrides.clear()

    def test_get_cited_by_case_not_found(self, app: FastAPI, client: TestClient) -> None:
        """Cited-by on nonexistent case returns 404."""
        db = _mock_db_multi_execute([{"scalar": None}])

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/cases/{fake_id}/cited-by")
        assert resp.status_code == 404

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/similar
# ---------------------------------------------------------------------------


class TestGetSimilar:
    @patch("app.api.routes.cases.get_vector_store")
    @patch("app.api.routes.cases.get_embedder")
    def test_get_similar_cases(
        self,
        mock_get_embedder: MagicMock,
        mock_get_vector: MagicMock,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """Similar endpoint returns semantically similar cases."""
        # First call: fetch ratio_decidendi, second call: enrichment
        similar_row = _make_summary_row(_SIMILAR_CASE_ID, "Similar Case")
        similar_row["ratio_decidendi"] = "Similar ratio text."
        db = _mock_db_multi_execute(
            [
                [{"ratio_decidendi": "Personal hearing is mandatory.", "title": "Test Case"}],
                [similar_row],
            ]
        )

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        # Mock embedder
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 1536
        mock_get_embedder.return_value = mock_embedder

        # Mock vector store
        mock_vector = AsyncMock()
        mock_result = MagicMock()
        mock_result.id = _SIMILAR_CASE_ID
        mock_result.score = 0.92
        mock_result.metadata = {"case_id": _SIMILAR_CASE_ID}
        mock_vector.search.return_value = [mock_result]
        mock_get_vector.return_value = mock_vector

        resp = client.get(f"/api/v1/cases/{_CASE_ID}/similar?limit=5")
        assert resp.status_code == 200

        body = resp.json()
        assert body["case_id"] == _CASE_ID
        assert body["total"] == 1
        assert len(body["similar"]) == 1
        assert body["similar"][0]["case_id"] == _SIMILAR_CASE_ID
        assert body["similar"][0]["similarity_score"] == 0.92

        mock_embedder.embed_text.assert_awaited_once()
        mock_vector.search.assert_awaited_once()

        app.dependency_overrides.clear()

    def test_get_similar_case_not_found(self, app: FastAPI, client: TestClient) -> None:
        """Similar on nonexistent case returns 404."""
        db = _mock_db_execute([], scalar=None)

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/cases/{fake_id}/similar")
        assert resp.status_code == 404

        app.dependency_overrides.clear()

    @patch("app.api.routes.cases.get_vector_store")
    @patch("app.api.routes.cases.get_embedder")
    def test_get_similar_no_ratio_returns_empty(
        self,
        mock_get_embedder: MagicMock,
        mock_get_vector: MagicMock,
        app: FastAPI,
        client: TestClient,
    ) -> None:
        """Case with no ratio_decidendi and no title returns empty similar list."""
        db = _mock_db_execute([{"ratio_decidendi": None, "title": None}])

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        resp = client.get(f"/api/v1/cases/{_CASE_ID}/similar")
        assert resp.status_code == 200
        body = resp.json()
        assert body["similar"] == []
        assert body["total"] == 0

        # Should not call embedder or vector store
        mock_get_embedder.assert_not_called()
        mock_get_vector.assert_not_called()

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/pdf
# ---------------------------------------------------------------------------


class TestGetPdf:
    @patch("app.api.routes.cases.get_storage")
    def test_get_pdf_returns_file(
        self, mock_get_storage: MagicMock, app: FastAPI, client: TestClient
    ) -> None:
        """PDF endpoint returns PDF content with correct headers."""
        db = _mock_db_execute(
            [
                {
                    "pdf_storage_path": f"pdfs/{_CASE_ID}.pdf",
                    "title": "Test Case Title",
                }
            ]
        )

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        mock_storage = AsyncMock()
        mock_storage.retrieve.return_value = b"%PDF-1.4 fake pdf content"
        mock_get_storage.return_value = mock_storage

        resp = client.get(f"/api/v1/cases/{_CASE_ID}/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "Content-Disposition" in resp.headers
        assert "Test Case Title.pdf" in resp.headers["Content-Disposition"]
        assert resp.content == b"%PDF-1.4 fake pdf content"

        mock_storage.retrieve.assert_awaited_once_with(f"pdfs/{_CASE_ID}.pdf")

        app.dependency_overrides.clear()

    def test_get_pdf_case_not_found(self, app: FastAPI, client: TestClient) -> None:
        """PDF on nonexistent case returns 404."""
        db = _mock_db_execute([])

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/cases/{fake_id}/pdf")
        assert resp.status_code == 404

        app.dependency_overrides.clear()

    def test_get_pdf_no_pdf_path_returns_404(self, app: FastAPI, client: TestClient) -> None:
        """Case with no pdf_storage_path returns 404."""
        db = _mock_db_execute(
            [
                {
                    "pdf_storage_path": None,
                    "title": "Test Case",
                }
            ]
        )

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        resp = client.get(f"/api/v1/cases/{_CASE_ID}/pdf")
        assert resp.status_code == 404
        assert "No PDF available" in resp.json()["detail"]

        app.dependency_overrides.clear()

    @patch("app.api.routes.cases.get_storage")
    def test_get_pdf_storage_error_returns_404(
        self, mock_get_storage: MagicMock, app: FastAPI, client: TestClient
    ) -> None:
        """PDF storage download failure returns 404."""
        db = _mock_db_execute(
            [
                {
                    "pdf_storage_path": f"pdfs/{_CASE_ID}.pdf",
                    "title": "Test Case",
                }
            ]
        )

        async def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db

        mock_storage = AsyncMock()
        mock_storage.retrieve.side_effect = FileNotFoundError("not found")
        mock_get_storage.return_value = mock_storage

        resp = client.get(f"/api/v1/cases/{_CASE_ID}/pdf")
        assert resp.status_code == 404
        assert "PDF file not found" in resp.json()["detail"]

        app.dependency_overrides.clear()
