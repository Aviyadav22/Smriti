"""Tests for procedural timeline and citation evolution endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.cases import router as cases_router
from app.api.routes.graph import router as graph_router
from app.core.dependencies import get_graph_store
from app.db.postgres import get_db


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CASE_ID = str(uuid.uuid4())
_CITING_CASE_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_db_execute(rows: list[dict], *, scalar: object | None = None):
    """Build an AsyncMock for db.execute that returns mapping rows."""
    mock_result = MagicMock()

    mock_mappings = MagicMock()
    if rows:
        mock_mappings.one_or_none.return_value = rows[0]
        mock_mappings.all.return_value = rows
    else:
        mock_mappings.one_or_none.return_value = None
        mock_mappings.all.return_value = []
    mock_result.mappings.return_value = mock_mappings

    mock_result.scalar_one_or_none.return_value = scalar

    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


def _mock_graph_store() -> AsyncMock:
    """Create a mock GraphStore with common defaults."""
    mock = AsyncMock()
    mock.query = AsyncMock(return_value=[])
    mock.get_node = AsyncMock(return_value=None)
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cases_app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(cases_router, prefix="/api/v1/cases")
    return test_app


@pytest.fixture
def cases_client(cases_app: FastAPI) -> TestClient:
    return TestClient(cases_app, raise_server_exceptions=False)


@pytest.fixture
def graph_app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(graph_router, prefix="/api/v1/graph")
    return test_app


@pytest.fixture
def graph_client(graph_app: FastAPI) -> TestClient:
    return TestClient(graph_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/timeline — Procedural timeline
# ---------------------------------------------------------------------------


class TestCaseTimeline:
    def test_timeline_returns_events_with_procedural_history(
        self, cases_app: FastAPI, cases_client: TestClient
    ) -> None:
        """Timeline endpoint returns chronological events from procedural history."""
        case_row = {
            "title": "State v. Accused",
            "filing_date": date(2020, 1, 15),
            "decision_date": date(2023, 3, 10),
            "procedural_history": [
                {"date": "2021-06-01", "type": "hearing", "court": "High Court", "detail": "Arguments heard"},
                {"date": "2022-02-15", "type": "judgment", "court": "High Court", "detail": "Appeal dismissed"},
            ],
            "interim_orders": [
                {"date": "2020-05-01", "type": "stay", "court": "Trial Court", "detail": "Stay granted"},
                "Bail granted to accused",
            ],
            "lower_court": "Trial Court",
            "appeal_from": "High Court",
            "disposal_nature": "Dismissed",
            "court": "Supreme Court of India",
        }
        db = _mock_db_execute([case_row])

        async def _override_db():
            yield db

        cases_app.dependency_overrides[get_db] = _override_db

        resp = cases_client.get(f"/api/v1/cases/{_CASE_ID}/timeline")
        assert resp.status_code == 200

        body = resp.json()
        assert body["case_title"] == "State v. Accused"
        events = body["events"]
        assert len(events) >= 4  # filing + 2 procedural + 1 interim dict + 1 interim str + decision

        # Events with dates should be sorted chronologically
        dated_events = [e for e in events if e["date"]]
        dates = [e["date"] for e in dated_events]
        assert dates == sorted(dates)

        # Check filing event present
        filing = [e for e in events if e["type"] == "filing"]
        assert len(filing) == 1
        assert filing[0]["court"] == "Trial Court"

        # Check judgment (decision) event present
        judgments = [e for e in events if e["type"] == "judgment"]
        assert any(j["detail"] == "Dismissed" for j in judgments)

        # String interim order should be at the end (no date)
        undated = [e for e in events if not e["date"]]
        assert any("Bail granted" in e["detail"] for e in undated)

        cases_app.dependency_overrides.clear()

    def test_timeline_not_found_returns_404(
        self, cases_app: FastAPI, cases_client: TestClient
    ) -> None:
        """Timeline for nonexistent case returns 404."""
        db = _mock_db_execute([])

        async def _override_db():
            yield db

        cases_app.dependency_overrides[get_db] = _override_db

        fake_id = str(uuid.uuid4())
        resp = cases_client.get(f"/api/v1/cases/{fake_id}/timeline")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Case not found"

        cases_app.dependency_overrides.clear()

    def test_timeline_handles_no_procedural_history(
        self, cases_app: FastAPI, cases_client: TestClient
    ) -> None:
        """Case with no procedural history returns minimal events."""
        case_row = {
            "title": "Simple Case",
            "filing_date": None,
            "decision_date": date(2023, 5, 20),
            "procedural_history": None,
            "interim_orders": None,
            "lower_court": None,
            "appeal_from": None,
            "disposal_nature": "Allowed",
            "court": "Supreme Court of India",
        }
        db = _mock_db_execute([case_row])

        async def _override_db():
            yield db

        cases_app.dependency_overrides[get_db] = _override_db

        resp = cases_client.get(f"/api/v1/cases/{_CASE_ID}/timeline")
        assert resp.status_code == 200

        body = resp.json()
        assert body["case_title"] == "Simple Case"
        # Only the decision event should be present
        assert len(body["events"]) == 1
        assert body["events"][0]["type"] == "judgment"
        assert body["events"][0]["detail"] == "Allowed"

        cases_app.dependency_overrides.clear()

    def test_timeline_invalid_uuid_returns_422(
        self, cases_client: TestClient
    ) -> None:
        """Invalid case_id format returns 422."""
        resp = cases_client.get("/api/v1/cases/not-a-uuid/timeline")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /graph/{case_id}/evolution — Citation evolution
# ---------------------------------------------------------------------------


class TestCitationEvolution:
    def test_evolution_returns_root_case_info(
        self, graph_app: FastAPI, graph_client: TestClient
    ) -> None:
        """Evolution endpoint returns root case and evolution list."""
        root_row = {
            "id": _CASE_ID,
            "title": "Landmark Case",
            "year": 2020,
            "citation": "(2020) 5 SCC 100",
            "court": "Supreme Court of India",
        }
        db = _mock_db_execute([root_row])

        async def _override_db():
            yield db

        mock_graph = _mock_graph_store()
        mock_graph.query.return_value = [
            {
                "id": _CITING_CASE_ID,
                "title": "Citing Case",
                "year": 2022,
                "citation": "(2022) 3 SCC 200",
                "court": "Supreme Court of India",
                "treatment": "followed",
                "ratio": "The principle established in the landmark case was upheld.",
            }
        ]

        graph_app.dependency_overrides[get_db] = _override_db
        graph_app.dependency_overrides[get_graph_store] = lambda: mock_graph

        resp = graph_client.get(f"/api/v1/graph/{_CASE_ID}/evolution")
        assert resp.status_code == 200

        body = resp.json()
        assert body["root_case"]["id"] == _CASE_ID
        assert body["root_case"]["title"] == "Landmark Case"
        assert body["direction"] == "forward"
        assert len(body["evolution"]) == 1
        assert body["evolution"][0]["case_id"] == _CITING_CASE_ID
        assert body["evolution"][0]["treatment"] == "followed"

        graph_app.dependency_overrides.clear()

    def test_evolution_not_found_returns_404(
        self, graph_app: FastAPI, graph_client: TestClient
    ) -> None:
        """Evolution for nonexistent case returns 404."""
        db = _mock_db_execute([])

        async def _override_db():
            yield db

        mock_graph = _mock_graph_store()

        graph_app.dependency_overrides[get_db] = _override_db
        graph_app.dependency_overrides[get_graph_store] = lambda: mock_graph

        fake_id = str(uuid.uuid4())
        resp = graph_client.get(f"/api/v1/graph/{fake_id}/evolution")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Case not found"

        graph_app.dependency_overrides.clear()

    def test_evolution_graph_error_returns_empty_list(
        self, graph_app: FastAPI, graph_client: TestClient
    ) -> None:
        """Neo4j failure returns empty evolution list (does not 502)."""
        root_row = {
            "id": _CASE_ID,
            "title": "Some Case",
            "year": 2021,
            "citation": "(2021) 1 SCC 50",
            "court": "Supreme Court of India",
        }
        db = _mock_db_execute([root_row])

        async def _override_db():
            yield db

        mock_graph = _mock_graph_store()
        mock_graph.query.side_effect = ConnectionError("Neo4j down")

        graph_app.dependency_overrides[get_db] = _override_db
        graph_app.dependency_overrides[get_graph_store] = lambda: mock_graph

        resp = graph_client.get(f"/api/v1/graph/{_CASE_ID}/evolution")
        assert resp.status_code == 200

        body = resp.json()
        assert body["root_case"]["id"] == _CASE_ID
        assert body["evolution"] == []

        graph_app.dependency_overrides.clear()

    def test_evolution_backward_direction(
        self, graph_app: FastAPI, graph_client: TestClient
    ) -> None:
        """Evolution with direction=backward queries outgoing CITES."""
        root_row = {
            "id": _CASE_ID,
            "title": "A Case",
            "year": 2023,
            "citation": "(2023) 2 SCC 300",
            "court": "Supreme Court of India",
        }
        db = _mock_db_execute([root_row])

        async def _override_db():
            yield db

        mock_graph = _mock_graph_store()
        mock_graph.query.return_value = []

        graph_app.dependency_overrides[get_db] = _override_db
        graph_app.dependency_overrides[get_graph_store] = lambda: mock_graph

        resp = graph_client.get(f"/api/v1/graph/{_CASE_ID}/evolution?direction=backward")
        assert resp.status_code == 200

        body = resp.json()
        assert body["direction"] == "backward"

        # Verify the cypher query uses outgoing direction
        mock_graph.query.assert_awaited_once()
        call_kwargs = mock_graph.query.call_args
        assert "-[r:CITES]->(cited:Case)" in call_kwargs.kwargs["cypher"]

        graph_app.dependency_overrides.clear()

    def test_evolution_invalid_direction_returns_422(
        self, graph_client: TestClient
    ) -> None:
        """Invalid direction parameter returns 422."""
        resp = graph_client.get(f"/api/v1/graph/{_CASE_ID}/evolution?direction=sideways")
        assert resp.status_code == 422
