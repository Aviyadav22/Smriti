"""Tests for judge analytics route registration."""

from __future__ import annotations


def test_judges_routes_registered() -> None:
    """Verify judge and court routes are registered on the app."""
    from app.main import app

    paths = [r.path for r in app.routes]
    assert any("/judges" in p for p in paths), f"No /judges route found in {paths}"
    assert any("/courts" in p for p in paths), f"No /courts route found in {paths}"


def test_judge_route_ordering() -> None:
    """Verify /judges/compare comes before /judges/{judge_name} to avoid path conflicts."""
    from app.main import app

    judge_paths = [r.path for r in app.routes if "/judges" in r.path]
    compare_idx = None
    profile_idx = None
    for i, p in enumerate(judge_paths):
        if p.endswith("/judges/compare"):
            compare_idx = i
        if "{judge_name}" in p and not p.endswith("/cases"):
            profile_idx = i

    assert compare_idx is not None, "compare route not found"
    assert profile_idx is not None, "profile route not found"
    assert compare_idx < profile_idx, (
        f"/judges/compare (idx={compare_idx}) must come before "
        f"/judges/{{judge_name}} (idx={profile_idx})"
    )


def test_all_judge_endpoints_present() -> None:
    """Verify all expected judge analytics endpoints exist."""
    from app.main import app

    paths = [r.path for r in app.routes]

    expected = [
        "/api/v1/judges",
        "/api/v1/judges/compare",
        "/api/v1/judges/{judge_name}",
        "/api/v1/judges/{judge_name}/cases",
        "/api/v1/courts/{court_name}/stats",
    ]

    for ep in expected:
        assert ep in paths, f"Missing endpoint: {ep}. Available: {paths}"
