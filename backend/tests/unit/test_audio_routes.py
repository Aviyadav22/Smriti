"""Tests for audio digest API routes."""

from app.api.routes.audio import router


class TestAudioRoutes:
    def test_routes_registered(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/{case_id}/audio/generate" in paths
        assert "/{case_id}/audio/status" in paths
        assert "/{case_id}/audio" in paths

    def test_generate_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{case_id}/audio/generate":
                assert "POST" in route.methods

    def test_status_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{case_id}/audio/status":
                assert "GET" in route.methods

    def test_stream_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{case_id}/audio":
                assert "GET" in route.methods
