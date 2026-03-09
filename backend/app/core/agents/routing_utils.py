"""Shared routing utilities for agent graphs."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END
from langgraph.types import interrupt

_PROCEED_PHRASES = frozenset({
    "looks good", "looks good, proceed", "proceed", "continue",
    "ok", "okay", "yes", "go ahead", "lgtm", "good", "fine",
    "no changes", "no change", "looks great",
})


def is_proceed(content: str) -> bool:
    """Return True if user feedback means 'proceed without changes'."""
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
        content = ""
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
        if content and not is_proceed(content) and step_feedback_count < max_iterations:
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
        result: dict[str, Any] = {
            "messages": [
                {"type": "user_feedback", "step": step, "content": response}
            ],
        }
        if extra_return is not None:
            result.update(extra_return(response))
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
