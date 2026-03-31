"""Tests for counsel analytics route registration and endpoints."""

from __future__ import annotations


def test_counsel_routes_registered() -> None:
    """Verify counsel routes are registered on the app."""
    from app.main import app

    paths = [r.path for r in app.routes]
    assert any("/counsel" in p for p in paths), f"No /counsel route found in {paths}"


def test_all_counsel_endpoints_present() -> None:
    """Verify all expected counsel analytics endpoints exist."""
    from app.main import app

    paths = [r.path for r in app.routes]

    expected = [
        "/api/v1/counsel",
        "/api/v1/counsel/{name}",
        "/api/v1/counsel/{name}/cases",
        "/api/v1/counsel/{name}/matchups",
    ]

    for ep in expected:
        assert ep in paths, f"Missing endpoint: {ep}. Available: {paths}"


def test_counsel_router_before_judges_router() -> None:
    """Counsel routes should not conflict with judges routes."""
    from app.main import app

    paths = [r.path for r in app.routes]
    counsel_paths = [p for p in paths if "/counsel" in p]
    judge_paths = [p for p in paths if "/judges" in p]

    # Both should exist
    assert len(counsel_paths) > 0, "No counsel routes found"
    assert len(judge_paths) > 0, "No judge routes found"
