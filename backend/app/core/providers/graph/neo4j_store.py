"""Neo4j graph store provider implementation."""

from __future__ import annotations

from neo4j import AsyncGraphDatabase

from app.core.config import settings

# ---------------------------------------------------------------------------
# Input validation allowlists
# ---------------------------------------------------------------------------

_VALID_LABELS = frozenset({"Case", "Statute", "Section", "Judge", "Court", "Act"})
_VALID_RELATIONSHIPS = frozenset({
    "CITES", "CITED_BY", "OVERRULES", "OVERRULED_BY",
    "DISTINGUISHES", "FOLLOWS", "REFERS_TO", "APPLIES",
    "DECIDED_BY", "HEARD_IN",
})


def _validate_label(label: str) -> str:
    if label not in _VALID_LABELS:
        raise ValueError(f"Invalid node label: '{label}'. Allowed: {sorted(_VALID_LABELS)}")
    return label


def _validate_relationship(rel_type: str) -> str:
    if rel_type not in _VALID_RELATIONSHIPS:
        raise ValueError(f"Invalid relationship: '{rel_type}'. Allowed: {sorted(_VALID_RELATIONSHIPS)}")
    return rel_type


class Neo4jGraph:
    """Neo4j graph database implementing GraphStore protocol."""

    def __init__(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        self._database = settings.neo4j_database

    async def create_node(self, label: str, properties: dict) -> str:
        _validate_label(label)
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                f"CREATE (n:{label} $props) RETURN n.id AS id",
                props=properties,
            )
            record = await result.single()
            return str(record["id"]) if record else ""

    async def get_node(self, node_id: str) -> dict | None:
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                "MATCH (n {id: $id}) RETURN n",
                id=node_id,
            )
            record = await result.single()
            return dict(record["n"]) if record else None

    async def query(
        self,
        cypher: str,
        *,
        params: dict | None = None,
    ) -> list[dict]:
        async with self._driver.session(database=self._database) as session:
            result = await session.run(cypher, **(params or {}))
            return [dict(record) async for record in result]

    async def get_neighbors(
        self,
        node_id: str,
        *,
        relationship: str | None = None,
        direction: str = "both",
        depth: int = 1,
    ) -> dict:
        if relationship is not None:
            _validate_relationship(relationship)
        # Clamp depth to 1-5 to prevent expensive traversals
        depth = max(1, min(depth, 5))

        rel_filter = f":{relationship}" if relationship else ""

        if direction == "outgoing":
            pattern = f"-[r{rel_filter}*1..{depth}]->"
        elif direction == "incoming":
            pattern = f"<-[r{rel_filter}*1..{depth}]-"
        else:
            pattern = f"-[r{rel_filter}*1..{depth}]-"

        query = (
            f"MATCH (n {{id: $id}}){pattern}(m) "
            "RETURN DISTINCT m, type(r[-1]) AS rel_type"
        )
        async with self._driver.session(database=self._database) as session:
            result = await session.run(query, id=node_id)
            nodes: list[dict] = []
            async for record in result:
                nodes.append({
                    "node": dict(record["m"]),
                    "relationship": record["rel_type"],
                })
            return {"center": node_id, "neighbors": nodes}

    async def close(self) -> None:
        """Close the Neo4j driver connection."""
        await self._driver.close()
