"""Graph store interface for knowledge graph operations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class GraphStore(Protocol):
    """Contract for graph database providers."""

    async def create_node(self, label: str, properties: dict) -> str:
        """Create a node and return its ID."""
        ...

    async def create_edge(
        self,
        from_id: str,
        to_id: str,
        relationship: str,
        *,
        properties: dict | None = None,
    ) -> None: ...

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
