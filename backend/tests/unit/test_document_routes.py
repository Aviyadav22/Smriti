"""Tests for document API routes."""

import pytest

from app.api.routes.documents import router


class TestDocumentRoutes:
    def test_routes_registered(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/upload" in paths
        assert "" in paths
        assert "/{document_id}" in paths
        assert "/{document_id}/memo" in paths

    def test_upload_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/upload":
                assert "POST" in route.methods

    def test_delete_exists(self) -> None:
        found = False
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/{document_id}"
                and hasattr(route, "methods")
            ) and "DELETE" in route.methods:
                found = True
        assert found, "DELETE route not found for /{document_id}"

    def test_list_is_get(self) -> None:
        for route in router.routes:
            if (
                hasattr(route, "path") and route.path == "" and hasattr(route, "methods")
            ) and "GET" in route.methods:
                return
        pytest.fail("GET route not found for list documents")
