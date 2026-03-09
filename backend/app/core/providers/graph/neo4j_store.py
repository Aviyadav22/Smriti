"""Neo4j graph store provider implementation."""

from __future__ import annotations

import logging

from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

_neo4j_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ServiceUnavailable, OSError, ConnectionError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

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
        if not settings.neo4j_uri or not settings.neo4j_uri.strip():
            raise ValueError(
                "Neo4j URI is required. Set NEO4J_URI environment variable."
            )
        if not settings.neo4j_password or not settings.neo4j_password.strip():
            raise ValueError(
                "Neo4j password is required. Set NEO4J_PASSWORD environment variable."
            )
        try:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        except (ServiceUnavailable, Exception) as exc:
            logger.error("Failed to create Neo4j driver (uri=%s): %s", settings.neo4j_uri, exc)
            raise RuntimeError(f"Neo4j connection failed: {exc}") from exc
        self._database = settings.neo4j_database

    @_neo4j_retry
    async def create_node(self, label: str, properties: dict) -> str:
        _validate_label(label)
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(
                    f"CREATE (n:{label} $props) RETURN n.id AS id",
                    props=properties,
                )
                record = await result.single()
                return str(record["id"]) if record else ""
        except Neo4jError as exc:
            logger.error("Neo4j create_node failed (label=%s): %s", label, exc)
            raise RuntimeError(f"Neo4j create_node failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in create_node: %s", exc)
            raise RuntimeError(f"Neo4j create_node failed unexpectedly: {exc}") from exc

    @_neo4j_retry
    async def get_node(self, node_id: str) -> dict | None:
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(
                    "MATCH (n {id: $id}) RETURN n",
                    id=node_id,
                )
                record = await result.single()
                return dict(record["n"]) if record else None
        except Neo4jError as exc:
            logger.error("Neo4j get_node failed (id=%s): %s", node_id, exc)
            raise RuntimeError(f"Neo4j get_node failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in get_node (id=%s): %s", node_id, exc)
            raise RuntimeError(f"Neo4j get_node failed unexpectedly: {exc}") from exc

    @_neo4j_retry
    async def query(
        self,
        cypher: str,
        *,
        params: dict | None = None,
    ) -> list[dict]:
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(cypher, **(params or {}))
                return [dict(record) async for record in result]
        except Neo4jError as exc:
            logger.error("Neo4j query failed: %s (cypher: %.200s)", exc, cypher)
            raise RuntimeError(f"Neo4j query failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in Neo4j query: %s", exc)
            raise RuntimeError(f"Neo4j query failed unexpectedly: {exc}") from exc

    @_neo4j_retry
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

        cypher = (
            f"MATCH (n {{id: $id}}){pattern}(m) "
            "RETURN DISTINCT m, type(r[-1]) AS rel_type"
        )
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(cypher, id=node_id)
                nodes: list[dict] = []
                async for record in result:
                    nodes.append({
                        "node": dict(record["m"]),
                        "relationship": record["rel_type"],
                    })
                return {"center": node_id, "neighbors": nodes}
        except Neo4jError as exc:
            logger.error("Neo4j get_neighbors failed (id=%s): %s", node_id, exc)
            raise RuntimeError(f"Neo4j get_neighbors failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in get_neighbors (id=%s): %s", node_id, exc)
            raise RuntimeError(f"Neo4j get_neighbors failed unexpectedly: {exc}") from exc

    async def close(self) -> None:
        """Close the Neo4j driver connection."""
        await self._driver.close()
