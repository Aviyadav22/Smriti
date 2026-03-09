"""Graph store interface for knowledge graph operations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class GraphStore(Protocol):
    """Contract for graph database providers."""

    async def create_node(self, label: str, properties: dict) -> str:
        """Create a node and return its ID."""
        ...

    async def get_node(self, node_id: str) -> dict | None: ...

    async def query(
        self,
        cypher: str,
        *,
        params: dict | None = None,
    ) -> list[dict]: ...

    async def get_neighbors(
        self,
        node_id: str,
        *,
        relationship: str | None = None,
        direction: str = "both",
        depth: int = 1,
    ) -> dict: ...

    async def ensure_constraints(self) -> None: ...

    async def batch_create_nodes(
        self,
        nodes: list[dict],
        *,
        batch_size: int = 500,
    ) -> int: ...

    async def batch_create_citation_edges(
        self,
        edges: list[dict],
        *,
        batch_size: int = 500,
    ) -> int: ...
