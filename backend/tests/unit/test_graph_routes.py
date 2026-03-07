"""Tests for citation graph API routes."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.graph import router


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CASE_ID = str(uuid.uuid4())
_NEIGHBOR_ID = str(uuid.uuid4())
_CITED_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/graph")
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_graph_store() -> AsyncMock:
    """Create a mock GraphStore with common defaults."""
    mock = AsyncMock()
    mock.query = AsyncMock(return_value=[])
    mock.get_node = AsyncMock(return_value=None)
    return mock


# ---------------------------------------------------------------------------
# GET /graph/{case_id}/neighborhood
# ---------------------------------------------------------------------------


class TestNeighborhood:
    @patch("app.api.routes.graph.get_graph_store")
    def test_neighborhood_returns_nodes_and_edges(
        self, mock_get_graph: MagicMock, client: TestClient
    ) -> None:
        """GET /{case_id}/neighborhood returns nodes and edges."""
        mock_graph = _mock_graph_store()

        # get_node returns center node info
        mock_graph.get_node.return_value = {
            "id": _CASE_ID,
            "title": "Center Case",
            "citation": "(2023) 5 SCC 100",
            "court": "Supreme Court of India",
            "year": 2023,
            "cited_by_count": 10,
        }

        # query returns neighbor records
        mock_graph.query.return_value = [
            {
                "id": _NEIGHBOR_ID,
                "title": "Neighbor Case",
                "citation": "(2022) 3 SCC 50",
                "court": "Supreme Court of India",
                "year": 2022,
                "cited_by_count": 5,
                "edges": [
                    {
                        "from": _CASE_ID,
                        "to": _NEIGHBOR_ID,
                        "type": "CITES",
                        "context": "Section 14",
                    }
                ],
            }
        ]
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/graph/{_CASE_ID}/neighborhood")
        assert resp.status_code == 200

        body = resp.json()
        assert "nodes" in body
        assert "edges" in body
        assert len(body["nodes"]) == 2  # center + neighbor
        assert len(body["edges"]) == 1

        node_ids = {n["id"] for n in body["nodes"]}
        assert _CASE_ID in node_ids
        assert _NEIGHBOR_ID in node_ids

        edge = body["edges"][0]
        assert edge["from"] == _CASE_ID
        assert edge["to"] == _NEIGHBOR_ID
        assert edge["type"] == "CITES"
        assert edge["context"] == "Section 14"

    @patch("app.api.routes.graph.get_graph_store")
    def test_neighborhood_with_depth_param(
        self, mock_get_graph: MagicMock, client: TestClient
    ) -> None:
        """Depth query parameter is passed through."""
        mock_graph = _mock_graph_store()
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/graph/{_CASE_ID}/neighborhood?depth=2")
        assert resp.status_code == 200

        # Verify query was called with depth=2
        mock_graph.query.assert_awaited_once()
        call_kwargs = mock_graph.query.call_args
        assert call_kwargs.kwargs["params"]["depth"] == 2

    @patch("app.api.routes.graph.get_graph_store")
    def test_neighborhood_graph_error_returns_empty(
        self, mock_get_graph: MagicMock, client: TestClient
    ) -> None:
        """Graph connection error returns empty nodes/edges."""
        mock_graph = _mock_graph_store()
        mock_graph.query.side_effect = ConnectionError("Neo4j down")
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/graph/{_CASE_ID}/neighborhood")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []


# ---------------------------------------------------------------------------
# GET /graph/{case_id}/chain
# ---------------------------------------------------------------------------


class TestChain:
    @patch("app.api.routes.graph.get_graph_store")
    def test_chain_returns_forward_citations(
        self, mock_get_graph: MagicMock, client: TestClient
    ) -> None:
        """GET /{case_id}/chain returns citation chain nodes and edges."""
        mock_graph = _mock_graph_store()
        mock_graph.query.return_value = [
            {
                "id": _CITED_ID,
                "title": "Cited Authority",
                "citation": "(2020) 1 SCC 200",
                "court": "Supreme Court of India",
                "year": 2020,
                "cited_by_count": 30,
                "edges": [
                    {
                        "from": _CASE_ID,
                        "to": _CITED_ID,
                        "type": "CITES",
                    }
                ],
            }
        ]
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/graph/{_CASE_ID}/chain")
        assert resp.status_code == 200

        body = resp.json()
        assert "nodes" in body
        assert "edges" in body
        assert len(body["nodes"]) == 2  # start + cited
        assert len(body["edges"]) == 1

        node_ids = {n["id"] for n in body["nodes"]}
        assert _CASE_ID in node_ids
        assert _CITED_ID in node_ids

        edge = body["edges"][0]
        assert edge["from"] == _CASE_ID
        assert edge["to"] == _CITED_ID
        assert edge["type"] == "CITES"

    @patch("app.api.routes.graph.get_graph_store")
    def test_chain_with_max_depth(
        self, mock_get_graph: MagicMock, client: TestClient
    ) -> None:
        """max_depth query parameter is passed through."""
        mock_graph = _mock_graph_store()
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/graph/{_CASE_ID}/chain?max_depth=5")
        assert resp.status_code == 200

        mock_graph.query.assert_awaited_once()
        call_kwargs = mock_graph.query.call_args
        assert call_kwargs.kwargs["params"]["depth"] == 5

    @patch("app.api.routes.graph.get_graph_store")
    def test_chain_graph_error_returns_empty(
        self, mock_get_graph: MagicMock, client: TestClient
    ) -> None:
        """Graph connection error returns empty chain."""
        mock_graph = _mock_graph_store()
        mock_graph.query.side_effect = RuntimeError("connection lost")
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/graph/{_CASE_ID}/chain")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []


# ---------------------------------------------------------------------------
# GET /graph/{case_id}/authorities
# ---------------------------------------------------------------------------


class TestAuthorities:
    @patch("app.api.routes.graph.get_graph_store")
    def test_authorities_returns_most_cited(
        self, mock_get_graph: MagicMock, client: TestClient
    ) -> None:
        """GET /{case_id}/authorities returns top-cited cases."""
        authority_id = str(uuid.uuid4())
        mock_graph = _mock_graph_store()
        mock_graph.query.return_value = [
            {
                "id": authority_id,
                "title": "Landmark Authority",
                "citation": "(1973) 4 SCC 225",
                "court": "Supreme Court of India",
                "year": 1973,
                "cited_by_count": 150,
            }
        ]
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/graph/{_CASE_ID}/authorities")
        assert resp.status_code == 200

        body = resp.json()
        assert body["case_id"] == _CASE_ID
        assert body["total"] == 1
        assert len(body["authorities"]) == 1

        auth = body["authorities"][0]
        assert auth["id"] == authority_id
        assert auth["title"] == "Landmark Authority"
        assert auth["cited_by_count"] == 150

    @patch("app.api.routes.graph.get_graph_store")
    def test_authorities_respects_limit(
        self, mock_get_graph: MagicMock, client: TestClient
    ) -> None:
        """Limit parameter is forwarded to graph query."""
        mock_graph = _mock_graph_store()
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/graph/{_CASE_ID}/authorities?limit=5")
        assert resp.status_code == 200

        mock_graph.query.assert_awaited_once()
        call_kwargs = mock_graph.query.call_args
        assert call_kwargs.kwargs["params"]["limit"] == 5

    @patch("app.api.routes.graph.get_graph_store")
    def test_authorities_graph_error_returns_empty(
        self, mock_get_graph: MagicMock, client: TestClient
    ) -> None:
        """Graph error returns empty authorities."""
        mock_graph = _mock_graph_store()
        mock_graph.query.side_effect = ConnectionError("unavailable")
        mock_get_graph.return_value = mock_graph

        resp = client.get(f"/api/v1/graph/{_CASE_ID}/authorities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["authorities"] == []
        assert body["total"] == 0


# ---------------------------------------------------------------------------
# GET /graph/stats
# ---------------------------------------------------------------------------


class TestStats:
    @patch("app.api.routes.graph.get_redis")
    @patch("app.api.routes.graph.get_graph_store")
    def test_stats_returns_global_stats(
        self, mock_get_graph: MagicMock, mock_get_redis: MagicMock, client: TestClient
    ) -> None:
        """GET /stats returns graph statistics."""
        mock_graph = _mock_graph_store()
        top_case_id = str(uuid.uuid4())
        mock_graph.query.side_effect = [
            # count query
            [{"total_judgments": 35000}],
            # edge count query
            [{"total_edges": 120000}],
            # top cited query
            [
                {
                    "id": top_case_id,
                    "title": "Kesavananda Bharati v. State of Kerala",
                    "citation": "(1973) 4 SCC 225",
                    "cited_by_count": 500,
                }
            ],
        ]
        mock_get_graph.return_value = mock_graph

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # no cache
        mock_get_redis.return_value = mock_redis

        resp = client.get("/api/v1/graph/stats")
        assert resp.status_code == 200

        body = resp.json()
        assert body["total_judgments"] == 35000
        assert body["total_edges"] == 120000
        assert len(body["most_cited"]) == 1
        assert body["most_cited"][0]["id"] == top_case_id
        assert body["most_cited"][0]["cited_by_count"] == 500

    @patch("app.api.routes.graph.get_redis")
    @patch("app.api.routes.graph.get_graph_store")
    def test_stats_uses_cache(
        self, mock_get_graph: MagicMock, mock_get_redis: MagicMock, client: TestClient
    ) -> None:
        """Stats returns cached result when available."""
        import json

        cached_stats = {
            "total_judgments": 10000,
            "total_edges": 50000,
            "most_cited": [],
        }

        mock_graph = _mock_graph_store()
        mock_get_graph.return_value = mock_graph

        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps(cached_stats)
        mock_get_redis.return_value = mock_redis

        resp = client.get("/api/v1/graph/stats")
        assert resp.status_code == 200

        body = resp.json()
        assert body["total_judgments"] == 10000
        assert body["total_edges"] == 50000

        # Graph should NOT have been queried
        mock_graph.query.assert_not_awaited()

    @patch("app.api.routes.graph.get_redis")
    @patch("app.api.routes.graph.get_graph_store")
    def test_stats_graph_error_returns_zeros(
        self, mock_get_graph: MagicMock, mock_get_redis: MagicMock, client: TestClient
    ) -> None:
        """Graph error returns zeroed stats."""
        mock_graph = _mock_graph_store()
        mock_graph.query.side_effect = ConnectionError("unavailable")
        mock_get_graph.return_value = mock_graph

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        resp = client.get("/api/v1/graph/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_judgments"] == 0
        assert body["total_edges"] == 0
        assert body["most_cited"] == []


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    def test_depth_parameter_rejects_zero(self, client: TestClient) -> None:
        """depth=0 is rejected by ge=1 constraint."""
        resp = client.get(f"/api/v1/graph/{_CASE_ID}/neighborhood?depth=0")
        assert resp.status_code == 422

    def test_depth_parameter_rejects_above_max(self, client: TestClient) -> None:
        """depth=4 is rejected by le=3 constraint."""
        resp = client.get(f"/api/v1/graph/{_CASE_ID}/neighborhood?depth=4")
        assert resp.status_code == 422

    def test_chain_max_depth_rejects_zero(self, client: TestClient) -> None:
        """max_depth=0 is rejected by ge=1 constraint."""
        resp = client.get(f"/api/v1/graph/{_CASE_ID}/chain?max_depth=0")
        assert resp.status_code == 422

    def test_chain_max_depth_rejects_above_max(self, client: TestClient) -> None:
        """max_depth=6 is rejected by le=5 constraint."""
        resp = client.get(f"/api/v1/graph/{_CASE_ID}/chain?max_depth=6")
        assert resp.status_code == 422

    def test_authorities_limit_rejects_zero(self, client: TestClient) -> None:
        """limit=0 is rejected by ge=1 constraint."""
        resp = client.get(f"/api/v1/graph/{_CASE_ID}/authorities?limit=0")
        assert resp.status_code == 422

    def test_authorities_limit_rejects_above_max(self, client: TestClient) -> None:
        """limit=51 is rejected by le=50 constraint."""
        resp = client.get(f"/api/v1/graph/{_CASE_ID}/authorities?limit=51")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    def test_all_graph_endpoints_present(self) -> None:
        """All expected graph routes are registered."""
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/{case_id}/neighborhood" in paths
        assert "/{case_id}/chain" in paths
        assert "/{case_id}/authorities" in paths
        assert "/stats" in paths

    def test_all_endpoints_are_get(self) -> None:
        """All graph endpoints use GET method."""
        for route in router.routes:
            if hasattr(route, "methods"):
                assert "GET" in route.methods
