"""Neo4j graph store provider implementation."""

from __future__ import annotations

import asyncio
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
from app.core.providers.circuit_breaker import CircuitBreakerOpen

logger = logging.getLogger(__name__)

_neo4j_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((ServiceUnavailable, OSError, ConnectionError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

# ---------------------------------------------------------------------------
# Input validation allowlists
# ---------------------------------------------------------------------------

_VALID_LABELS = frozenset({
    "Case", "Statute", "Judge", "Act", "Doctrine",
    "Counsel", "LegalPrinciple", "Issue", "Community",
    "IssueTopic", "StatuteSection",
})
_VALID_RELATIONSHIPS = frozenset({
    "CITES", "EQUIVALENT_TO", "APPLIES_DOCTRINE", "DECIDED_BY",
    "REPRESENTED_BY", "APPLIES_PRINCIPLE", "ADDRESSES",
    "BELONGS_TO", "INTERPRETS", "AUTHORED_BY",
    "CLASSIFIED_AS",
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
_QUERY_TIMEOUT_SECONDS = 30


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
                max_connection_pool_size=50,
                connection_acquisition_timeout=60.0,
            )
        except (ServiceUnavailable, Exception) as exc:
            logger.error("Failed to create Neo4j driver (uri=%s): %s", settings.neo4j_uri, exc)
            raise RuntimeError(f"Neo4j connection failed: {exc}") from exc
        self._database = settings.neo4j_database

        # Lazy import to avoid circular deps at module level
        from app.core.dependencies import neo4j_breaker

        self._breaker = neo4j_breaker

    async def create_node(self, label: str, properties: dict) -> str:
        """Create or merge a node. Uses MERGE for idempotency (safe to call multiple times)."""
        if not await self._breaker.check():
            raise CircuitBreakerOpen(0, service="neo4j")
        try:
            result = await self._create_node_inner(label, properties)
            await self._breaker.record_success()
            return result
        except CircuitBreakerOpen:
            raise
        except Exception:
            await self._breaker.record_failure()
            raise

    @_neo4j_retry
    async def _create_node_inner(self, label: str, properties: dict) -> str:
        _validate_label(label)
        node_id = properties.get("id", "")
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(
                    f"MERGE (n:{label} {{id: $id}}) SET n += $props RETURN n.id AS id",
                    id=node_id,
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

    async def get_node(self, node_id: str) -> dict | None:
        if not await self._breaker.check():
            raise CircuitBreakerOpen(0, service="neo4j")
        try:
            result = await self._get_node_inner(node_id)
            await self._breaker.record_success()
            return result
        except CircuitBreakerOpen:
            raise
        except Exception:
            await self._breaker.record_failure()
            raise

    @_neo4j_retry
    async def _get_node_inner(self, node_id: str) -> dict | None:
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

    async def query(
        self,
        cypher: str,
        *,
        params: dict | None = None,
    ) -> list[dict]:
        if not await self._breaker.check():
            raise CircuitBreakerOpen(0, service="neo4j")
        try:
            result = await self._query_inner(cypher, params=params)
            await self._breaker.record_success()
            return result
        except CircuitBreakerOpen:
            raise
        except Exception:
            await self._breaker.record_failure()
            raise

    @_neo4j_retry
    async def _query_inner(
        self,
        cypher: str,
        *,
        params: dict | None = None,
    ) -> list[dict]:
        try:

            async def _run() -> list[dict]:
                async with self._driver.session(database=self._database) as session:
                    result = await session.run(cypher, parameters=(params or {}))
                    return [dict(record) async for record in result]

            return await asyncio.wait_for(_run(), timeout=_QUERY_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.error("Neo4j query timed out after %ds (cypher: %.200s)", _QUERY_TIMEOUT_SECONDS, cypher)
            raise RuntimeError(f"Neo4j query timed out after {_QUERY_TIMEOUT_SECONDS}s")
        except Neo4jError as exc:
            logger.error("Neo4j query failed: %s (cypher: %.200s)", exc, cypher)
            raise RuntimeError(f"Neo4j query failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in Neo4j query: %s", exc)
            raise RuntimeError(f"Neo4j query failed unexpectedly: {exc}") from exc

    async def get_neighbors(
        self,
        node_id: str,
        *,
        relationship: str | None = None,
        direction: str = "both",
        depth: int = 1,
    ) -> dict:
        if not await self._breaker.check():
            raise CircuitBreakerOpen(0, service="neo4j")
        try:
            result = await self._get_neighbors_inner(
                node_id, relationship=relationship, direction=direction, depth=depth
            )
            await self._breaker.record_success()
            return result
        except CircuitBreakerOpen:
            raise
        except Exception:
            await self._breaker.record_failure()
            raise

    @_neo4j_retry
    async def _get_neighbors_inner(
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

            async def _run() -> dict:
                async with self._driver.session(database=self._database) as session:
                    result = await session.run(cypher, id=node_id)
                    nodes: list[dict] = []
                    async for record in result:
                        nodes.append({
                            "node": dict(record["m"]),
                            "relationship": record["rel_type"],
                        })
                    return {"center": node_id, "neighbors": nodes}

            return await asyncio.wait_for(_run(), timeout=_QUERY_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.error("Neo4j get_neighbors timed out after %ds (id=%s)", _QUERY_TIMEOUT_SECONDS, node_id)
            raise RuntimeError(f"Neo4j get_neighbors timed out after {_QUERY_TIMEOUT_SECONDS}s")
        except Neo4jError as exc:
            logger.error("Neo4j get_neighbors failed (id=%s): %s", node_id, exc)
            raise RuntimeError(f"Neo4j get_neighbors failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in get_neighbors (id=%s): %s", node_id, exc)
            raise RuntimeError(f"Neo4j get_neighbors failed unexpectedly: {exc}") from exc

    @_neo4j_retry
    async def ensure_constraints(self) -> None:
        """Create unique constraints and indexes on Case/Statute nodes.

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
            (
                "constraint_statute_id_unique",
                "CREATE CONSTRAINT constraint_statute_id_unique IF NOT EXISTS "
                "FOR (s:Statute) REQUIRE s.id IS UNIQUE",
            ),
            (
                "constraint_doctrine_id_unique",
                "CREATE CONSTRAINT constraint_doctrine_id_unique IF NOT EXISTS "
                "FOR (d:Doctrine) REQUIRE d.id IS UNIQUE",
            ),
            (
                "constraint_counsel_name_unique",
                "CREATE CONSTRAINT constraint_counsel_name_unique IF NOT EXISTS "
                "FOR (c:Counsel) REQUIRE c.name IS UNIQUE",
            ),
            (
                "constraint_principle_name_unique",
                "CREATE CONSTRAINT constraint_principle_name_unique IF NOT EXISTS "
                "FOR (p:LegalPrinciple) REQUIRE p.name IS UNIQUE",
            ),
            (
                "constraint_issue_tag_unique",
                "CREATE CONSTRAINT constraint_issue_tag_unique IF NOT EXISTS "
                "FOR (i:Issue) REQUIRE i.tag IS UNIQUE",
            ),
        ]
        # [B15] Expanded fulltext index — drop old narrow index first, recreate with more fields
        fulltext_upgrade = [
            (
                "drop_old_case_search",
                "DROP INDEX case_search IF EXISTS",
            ),
            (
                "fulltext_case_search_v2",
                "CREATE FULLTEXT INDEX case_search IF NOT EXISTS "
                "FOR (c:Case) ON EACH [c.title, c.citation, c.keywords, c.acts_cited, c.ratio]",
            ),
            (
                "fulltext_principle_text",
                "CREATE FULLTEXT INDEX principle_text IF NOT EXISTS "
                "FOR (n:LegalPrinciple) ON EACH [n.name]",
            ),
        ]
        async with self._driver.session(database=self._database) as session:
            for name, cypher in constraints:
                try:
                    await session.run(cypher)
                    logger.info("Ensured Neo4j constraint: %s", name)
                except Exception as exc:
                    logger.warning("Skipped Neo4j constraint %s: %s", name, exc)
            for name, cypher in fulltext_upgrade:
                try:
                    await session.run(cypher)
                    logger.info("Ensured Neo4j fulltext: %s", name)
                except Exception as exc:
                    logger.warning("Skipped Neo4j fulltext %s: %s", name, exc)

            # [E1] Seed doctrine nodes
            await self._seed_doctrines(session)

    async def _seed_doctrines(self, session) -> None:
        """Seed 12 foundational Indian constitutional/legal doctrines."""
        doctrines = [
            {"id": "doctrine:basic_structure", "name": "Basic Structure Doctrine",
             "description": "Parliament cannot amend the Constitution to destroy its basic structure",
             "origin_case": "Kesavananda Bharati v. State of Kerala (1973) 4 SCC 225",
             "category": "constitutional"},
            {"id": "doctrine:eclipse", "name": "Doctrine of Eclipse",
             "description": "Pre-constitutional laws inconsistent with fundamental rights are eclipsed but not dead",
             "origin_case": "Bhikaji Narain Dhakras v. State of MP AIR 1955 SC 781",
             "category": "constitutional"},
            {"id": "doctrine:pith_and_substance", "name": "Doctrine of Pith and Substance",
             "description": "Legislation is valid if its true nature falls within the competence of the legislature",
             "origin_case": "State of Bombay v. FN Balsara AIR 1951 SC 318",
             "category": "constitutional"},
            {"id": "doctrine:colourable_legislation", "name": "Doctrine of Colourable Legislation",
             "description": "Legislature cannot do indirectly what it cannot do directly",
             "origin_case": "K.C. Gajapati Narayan Deo v. State of Orissa AIR 1953 SC 375",
             "category": "constitutional"},
            {"id": "doctrine:severability", "name": "Doctrine of Severability",
             "description": "Only offending parts of a statute are void; rest survives if separable",
             "origin_case": "A.K. Gopalan v. State of Madras AIR 1950 SC 27",
             "category": "constitutional"},
            {"id": "doctrine:prospective_overruling", "name": "Doctrine of Prospective Overruling",
             "description": "Supreme Court may limit the effect of overruling to future cases only",
             "origin_case": "I.C. Golaknath v. State of Punjab AIR 1967 SC 1643",
             "category": "constitutional"},
            {"id": "doctrine:legitimate_expectation", "name": "Doctrine of Legitimate Expectation",
             "description": "A person may have a legitimate expectation of being treated in a certain way by a public authority",
             "origin_case": "Food Corporation of India v. Kamdhenu Cattle Feed Industries (1993) 1 SCC 71",
             "category": "administrative"},
            {"id": "doctrine:proportionality", "name": "Doctrine of Proportionality",
             "description": "State action must be proportionate to the objective pursued",
             "origin_case": "K.S. Puttaswamy v. Union of India (2017) 10 SCC 1",
             "category": "constitutional"},
            {"id": "doctrine:res_judicata", "name": "Doctrine of Res Judicata",
             "description": "A matter once finally decided cannot be re-litigated between the same parties",
             "origin_case": "Section 11, Code of Civil Procedure 1908",
             "category": "procedural"},
            {"id": "doctrine:lifting_corporate_veil", "name": "Doctrine of Lifting the Corporate Veil",
             "description": "Courts may look behind the corporate entity to the persons controlling it",
             "origin_case": "LIC of India v. Escorts Ltd (1986) 1 SCC 264",
             "category": "corporate"},
            {"id": "doctrine:last_seen_together", "name": "Doctrine of Last Seen Together",
             "description": "If accused was last seen with deceased, burden shifts to explain circumstances",
             "origin_case": "Trimukh Maroti Kirkan v. State of Maharashtra (2006) 10 SCC 681",
             "category": "criminal"},
            {"id": "doctrine:double_jeopardy", "name": "Doctrine of Double Jeopardy",
             "description": "No person shall be prosecuted and punished for the same offence more than once",
             "origin_case": "Article 20(2), Constitution of India",
             "category": "criminal"},
        ]
        for d in doctrines:
            try:
                await session.run(
                    "MERGE (doc:Doctrine {id: $id}) "
                    "SET doc.name = $name, doc.description = $description, "
                    "doc.origin_case = $origin_case, doc.category = $category",
                    d,
                )
            except Exception:
                pass  # Best-effort seeding

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
                    async with await session.begin_transaction() as tx:
                        result = await tx.run(cypher, batch=batch)
                        record = await result.single()
                        total += record["cnt"] if record else 0
                        await tx.commit()
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
                    async with await session.begin_transaction() as tx:
                        result = await tx.run(cypher, batch=batch)
                        record = await result.single()
                        total += record["cnt"] if record else 0
                        await tx.commit()
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

    @_neo4j_retry
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its relationships."""
        query = "MATCH (n:Case {id: $id}) DETACH DELETE n RETURN count(n) AS deleted"
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(query, id=node_id)
                record = await result.single()
                return bool(record and record.get("deleted", 0) > 0)
        except Neo4jError as exc:
            logger.error("Neo4j delete_node failed (id=%s): %s", node_id, exc)
            raise RuntimeError(f"Neo4j delete_node failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in delete_node (id=%s): %s", node_id, exc)
            raise RuntimeError(f"Neo4j delete_node failed unexpectedly: {exc}") from exc

    async def close(self) -> None:
        """Close the Neo4j driver connection."""
        await self._driver.close()
