"""Shared routing utilities for agent graphs."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from langgraph.graph import END
from langgraph.types import interrupt

logger = logging.getLogger(__name__)

_PROCEED_PHRASES = frozenset({
    "looks good", "looks good, proceed", "proceed", "continue",
    "ok", "okay", "yes", "go ahead", "lgtm", "good", "fine",
    "no changes", "no change", "looks great", "approve", "approved",
    # Chip suggestions from frontend checkpoints
    "looks good, proceed to synthesis",
    "looks good, finalize",
})


def is_proceed(content: str | dict | None) -> bool:
    """Return True if user feedback means 'proceed without changes'.

    Accepts plain strings (``"proceed"``), dicts from structured
    HITL responses (``{"action": "proceed"}``), and JSON-encoded
    strings from the frontend (``'{"action": "approve", ...}'``).
    """
    if content is None:
        return True  # No feedback = proceed
    if isinstance(content, dict):
        # Structured response — check "action" key
        action = content.get("action", "")
        if isinstance(action, str):
            action_lower = action.strip().lower().rstrip(".!")
            # Explicit approve/proceed action
            if action_lower in ("approve", "approved", "proceed"):
                return True
            return action_lower in _PROCEED_PHRASES
        return False
    if not isinstance(content, str):
        logger.warning("is_proceed: unexpected content type %s: %r", type(content).__name__, content)
        return True  # Unknown types = don't loop
    # Try parsing JSON strings from frontend (e.g. '{"action": "approve", ...}')
    if content.strip().startswith("{"):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return is_proceed(parsed)
        except (json.JSONDecodeError, TypeError):
            pass
    return content.strip().lower().rstrip(".!") in _PROCEED_PHRASES


def make_feedback_router(
    step: str,
    loop_back: str,
    proceed: str | None = None,
    max_iterations: int = 3,
    check_error: bool = False,
) -> Callable[[dict], str]:
    """Factory for HITL feedback routing functions.

    Parameters
    ----------
    step:
        The checkpoint step name to match in user_feedback messages.
    loop_back:
        Node name to route to when user provides substantive feedback.
    proceed:
        Node name to route to when user approves. None means END.
    max_iterations:
        Maximum number of loop-back iterations before forcing proceed.
    check_error:
        If True, route to END when state contains an error.
    """
    def route(state: dict) -> str:
        if check_error and state.get("error"):
            return END
        messages = state.get("messages", [])
        # Find the most recent feedback for this step
        content = None
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("type") == "user_feedback" and m.get("step") == step:
                content = m.get("content", "")
                break
        # Count feedback messages for THIS specific step only to avoid
        # iteration counts from one checkpoint blocking a different checkpoint.
        step_feedback_count = sum(
            1 for m in messages
            if isinstance(m, dict) and m.get("type") == "user_feedback" and m.get("step") == step
        )

        proceed_check = is_proceed(content)
        logger.warning(
            "ROUTE_DEBUG route_after_%s: content=%r type=%s is_proceed=%s feedback_count=%d",
            step, str(content)[:200], type(content).__name__, proceed_check, step_feedback_count,
        )

        if content and not proceed_check and step_feedback_count < max_iterations:
            return loop_back
        return proceed if proceed is not None else END

    route.__name__ = f"route_after_{step}"
    route.__qualname__ = f"route_after_{step}"
    return route


def make_checkpoint_node(
    step: str,
    question: str,
    state_fields: dict[str, tuple[str, Any]],
    extra_return: Callable[[str], dict] | None = None,
) -> Callable:
    """Factory for HITL checkpoint nodes using interrupt().

    Parameters
    ----------
    step:
        The step name for user_feedback messages.
    question:
        The question displayed to the user at the checkpoint.
    state_fields:
        Maps interrupt payload key -> (state key, default value).
        These fields are extracted from state and included in the interrupt payload.
    extra_return:
        Optional callback that receives the user response and returns additional
        fields to include in the node's return dict (beyond messages).
    """
    async def checkpoint(state: dict) -> dict:
        payload: dict[str, Any] = {"question": question}
        for key, (state_key, default) in state_fields.items():
            payload[key] = state.get(state_key, default)
        response = interrupt(payload)
        # Parse JSON strings from frontend into dicts
        parsed = response
        if isinstance(response, str) and response.strip().startswith("{"):
            try:
                parsed = json.loads(response)
            except (json.JSONDecodeError, TypeError):
                pass
        result: dict[str, Any] = {
            "messages": [
                {"type": "user_feedback", "step": step, "content": parsed}
            ],
        }
        if extra_return is not None:
            result.update(extra_return(parsed))
        return result

    checkpoint.__name__ = f"checkpoint_{step}"
    checkpoint.__qualname__ = f"checkpoint_{step}"
    return checkpoint


def compile_graph(graph: Any, checkpointer: Any | None = None) -> Any:
    """Compile a LangGraph StateGraph with an optional checkpointer."""
    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    return graph.compile(**compile_kwargs)
