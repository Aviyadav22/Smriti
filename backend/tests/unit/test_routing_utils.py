"""Tests for shared routing utilities."""
from __future__ import annotations

import pytest

from langgraph.graph import END

from app.core.agents.routing_utils import (
    is_proceed,
    make_feedback_router,
)


# ---------------------------------------------------------------------------
# is_proceed
# ---------------------------------------------------------------------------


class TestIsProceed:
    def test_proceed_phrases(self) -> None:
        assert is_proceed("proceed") is True
        assert is_proceed("Proceed") is True
        assert is_proceed("looks good") is True
        assert is_proceed("LGTM") is True
        assert is_proceed("ok") is True
        assert is_proceed("yes") is True
        assert is_proceed("go ahead") is True
        assert is_proceed("fine.") is True
        assert is_proceed("  continue  ") is True

    def test_non_proceed_phrases(self) -> None:
        assert is_proceed("add more citations") is False
        assert is_proceed("revise section 3") is False
        assert is_proceed("") is False
        assert is_proceed("focus on contract law") is False


# ---------------------------------------------------------------------------
# make_feedback_router
# ---------------------------------------------------------------------------


class TestMakeFeedbackRouter:
    def test_no_feedback_proceeds(self) -> None:
        router = make_feedback_router("plan", "decompose", "search")
        state = {"messages": [], "iteration": 0}
        assert router(state) == "search"

    def test_proceed_feedback_proceeds(self) -> None:
        router = make_feedback_router("plan", "decompose", "search")
        state = {
            "messages": [
                {"type": "user_feedback", "step": "plan", "content": "looks good"},
            ],
            "iteration": 0,
        }
        assert router(state) == "search"

    def test_substantive_feedback_loops(self) -> None:
        router = make_feedback_router("plan", "decompose", "search")
        state = {
            "messages": [
                {"type": "user_feedback", "step": "plan", "content": "add more queries"},
            ],
            "iteration": 0,
        }
        assert router(state) == "decompose"

    def test_max_iterations_stops_loop(self) -> None:
        router = make_feedback_router("plan", "decompose", "search", max_iterations=3)
        state = {
            "messages": [
                {"type": "user_feedback", "step": "plan", "content": "keep revising"},
                {"type": "user_feedback", "step": "plan", "content": "more changes"},
                {"type": "user_feedback", "step": "plan", "content": "still not right"},
            ],
            "iteration": 3,
        }
        assert router(state) == "search"

    def test_proceed_none_returns_end(self) -> None:
        router = make_feedback_router("memo", "synthesize")
        state = {"messages": [], "iteration": 0}
        assert router(state) == END

    def test_check_error_routes_to_end(self) -> None:
        router = make_feedback_router("analysis", "analyze", "search", check_error=True)
        state = {"messages": [], "iteration": 0, "error": "something went wrong"}
        assert router(state) == END

    def test_check_error_no_error_proceeds(self) -> None:
        router = make_feedback_router("analysis", "analyze", "search", check_error=True)
        state = {"messages": [], "iteration": 0, "error": ""}
        assert router(state) == "search"

    def test_ignores_feedback_for_other_steps(self) -> None:
        router = make_feedback_router("plan", "decompose", "search")
        state = {
            "messages": [
                {"type": "user_feedback", "step": "memo", "content": "revise this"},
            ],
            "iteration": 0,
        }
        assert router(state) == "search"

    def test_router_function_name(self) -> None:
        router = make_feedback_router("plan", "decompose", "search")
        assert router.__name__ == "route_after_plan"
