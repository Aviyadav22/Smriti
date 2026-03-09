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


_DEFAULT_BATCH_SIZE = 500


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

    @_neo4j_retry
    async def ensure_constraints(self) -> None:
        """Create unique constraints on Case nodes.

        Safe to call multiple times — uses IF NOT EXISTS.
        """
        constraints = [
            (
                "constraint_case_id_unique",
                "CREATE CONSTRAINT constraint_case_id_unique IF NOT EXISTS "
                "FOR (c:Case) REQUIRE c.id IS UNIQUE",
            ),
            (
                "constraint_case_citation_unique",
                "CREATE CONSTRAINT constraint_case_citation_unique IF NOT EXISTS "
                "FOR (c:Case) REQUIRE c.citation IS UNIQUE",
            ),
        ]
        try:
            async with self._driver.session(database=self._database) as session:
                for name, cypher in constraints:
                    await session.run(cypher)
                    logger.info("Ensured Neo4j constraint: %s", name)
        except Neo4jError as exc:
            logger.error("Failed to create Neo4j constraints: %s", exc)
            raise RuntimeError(f"Neo4j ensure_constraints failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in ensure_constraints: %s", exc)
            raise RuntimeError(
                f"Neo4j ensure_constraints failed unexpectedly: {exc}"
            ) from exc

    @_neo4j_retry
    async def batch_create_nodes(
        self,
        nodes: list[dict],
        *,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> int:
        """Batch-create Case nodes using UNWIND MERGE.

        Args:
            nodes: List of dicts, each must contain at least ``id``.
            batch_size: Number of nodes per transaction (default 500).

        Returns:
            Total number of nodes merged.
        """
        if not nodes:
            return 0

        cypher = (
            "UNWIND $batch AS node "
            "MERGE (c:Case {id: node.id}) "
            "SET c += node "
            "RETURN count(*) AS cnt"
        )
        total = 0
        try:
            async with self._driver.session(database=self._database) as session:
                for i in range(0, len(nodes), batch_size):
                    batch = nodes[i : i + batch_size]
                    result = await session.run(cypher, batch=batch)
                    record = await result.single()
                    total += record["cnt"] if record else 0
            logger.info(
                "batch_create_nodes: merged %d nodes in %d batches",
                total,
                (len(nodes) + batch_size - 1) // batch_size,
            )
            return total
        except Neo4jError as exc:
            logger.error("Neo4j batch_create_nodes failed: %s", exc)
            raise RuntimeError(f"Neo4j batch_create_nodes failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in batch_create_nodes: %s", exc)
            raise RuntimeError(
                f"Neo4j batch_create_nodes failed unexpectedly: {exc}"
            ) from exc

    @_neo4j_retry
    async def batch_create_citation_edges(
        self,
        edges: list[dict],
        *,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> int:
        """Batch-create CITES edges between Case nodes using UNWIND MERGE.

        Args:
            edges: List of dicts with keys ``source_id``, ``target_citation``,
                and optionally ``source_citation``, ``treatment``.
            batch_size: Number of edges per transaction (default 500).

        Returns:
            Total number of edges merged.
        """
        if not edges:
            return 0

        cypher = (
            "UNWIND $batch AS edge "
            "MERGE (source:Case {id: edge.source_id}) "
            "MERGE (target:Case {citation: edge.target_citation}) "
            "MERGE (source)-[r:CITES]->(target) "
            "SET r.treatment = edge.treatment "
            "RETURN count(*) AS cnt"
        )
        total = 0
        try:
            async with self._driver.session(database=self._database) as session:
                for i in range(0, len(edges), batch_size):
                    batch = edges[i : i + batch_size]
                    result = await session.run(cypher, batch=batch)
                    record = await result.single()
                    total += record["cnt"] if record else 0
            logger.info(
                "batch_create_citation_edges: merged %d edges in %d batches",
                total,
                (len(edges) + batch_size - 1) // batch_size,
            )
            return total
        except Neo4jError as exc:
            logger.error("Neo4j batch_create_citation_edges failed: %s", exc)
            raise RuntimeError(
                f"Neo4j batch_create_citation_edges failed: {exc}"
            ) from exc
        except Exception as exc:
            logger.error("Unexpected error in batch_create_citation_edges: %s", exc)
            raise RuntimeError(
                f"Neo4j batch_create_citation_edges failed unexpectedly: {exc}"
            ) from exc

    async def close(self) -> None:
        """Close the Neo4j driver connection."""
        await self._driver.close()
