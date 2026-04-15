"""Tests for worker_nodes module constants and configuration."""

from __future__ import annotations


class TestWorkerVectorTypes:
    def test_agent_vector_types_includes_summary(self) -> None:
        from app.core.agents.nodes.worker_nodes import _AGENT_VECTOR_TYPES

        assert "summary" in _AGENT_VECTOR_TYPES
        assert "proposition" in _AGENT_VECTOR_TYPES
        assert "ratio" in _AGENT_VECTOR_TYPES
        assert "headnote" in _AGENT_VECTOR_TYPES
