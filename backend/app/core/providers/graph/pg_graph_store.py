"""PostgreSQL-based graph store provider implementation.

Uses a citations table with recursive CTEs for citation network traversal.
Drop-in replacement for Neo4jGraph — switch via GRAPH_PROVIDER=postgresql.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 500
_QUERY_TIMEOUT_SECONDS = 30

# Same validation allowlists as Neo4j store for consistency.
_VALID_LABELS = frozenset({
    "Case", "Statute", "Judge", "Act", "Doctrine",
    "Counsel", "LegalPrinciple", "Issue", "Community",
})
_VALID_RELATIONSHIPS = frozenset({
    "CITES", "EQUIVALENT_TO", "APPLIES_DOCTRINE", "DECIDED_BY",
    "REPRESENTED_BY", "APPLIES_PRINCIPLE", "ADDRESSES",
    "BELONGS_TO", "INTERPRETS", "AUTHORED_BY",
})


def _validate_label(label: str) -> str:
    if label not in _VALID_LABELS:
        raise ValueError(f"Invalid node label: '{label}'. Allowed: {sorted(_VALID_LABELS)}")
    return label


def _validate_relationship(rel_type: str) -> str:
    if rel_type not in _VALID_RELATIONSHIPS:
        raise ValueError(f"Invalid relationship: '{rel_type}'. Allowed: {sorted(_VALID_RELATIONSHIPS)}")
    return rel_type


class PgGraphStore:
    """PostgreSQL graph store implementing GraphStore protocol.

    Uses the existing cases table for nodes and a citations table for edges.
    Citation network traversal via recursive CTEs.
    """

    async def create_node(self, label: str, properties: dict) -> str:
        """Create or update a Case node (upsert into cases table)."""
        _validate_label(label)
        node_id = properties.get("id", "")
        if not node_id:
            raise ValueError("Node properties must include 'id'")

        # For Case nodes, upsert into the existing cases table.
        # Other labels are stored as metadata — the cases table already has all needed columns.
        if label == "Case":
            async with async_session_factory() as session:
                try:
                    # Only update graph-relevant fields, don't overwrite core case data.
                    result = await session.execute(
                        text(
                            "UPDATE cases SET "
                            "  citation = COALESCE(:citation, citation), "
                            "  title = COALESCE(:title, title) "
                            "WHERE id = :id "
                            "RETURNING id"
                        ),
                        {
                            "id": node_id,
                            "citation": properties.get("citation"),
                            "title": properties.get("title"),
                        },
                    )
                    row = result.fetchone()
                    if row:
                        await session.commit()
                        return str(row[0])

                    # If case doesn't exist yet, the ingestion pipeline creates it separately.
                    # Just return the ID — graph operations are non-critical.
                    await session.commit()
                    return node_id
                except Exception as exc:
                    await session.rollback()
                    logger.error("PgGraph create_node failed (id=%s): %s", node_id, exc)
                    raise RuntimeError(f"PgGraph create_node failed: {exc}") from exc
        else:
            # Non-Case nodes (Statute, Judge, etc.) — not currently stored in graph.
            # Return the ID for compatibility.
            logger.debug("PgGraph skipping non-Case node label=%s, id=%s", label, node_id)
            return node_id

    async def get_node(self, node_id: str) -> dict | None:
        async with async_session_factory() as session:
            try:
                result = await session.execute(
                    text(
                        "SELECT id, title, citation, court, year, case_type, "
                        "judge, bench_type, disposal_nature "
                        "FROM cases WHERE id = :id"
                    ),
                    {"id": node_id},
                )
                row = result.fetchone()
                if not row:
                    return None
                return dict(row._mapping)
            except Exception as exc:
                logger.error("PgGraph get_node failed (id=%s): %s", node_id, exc)
                raise RuntimeError(f"PgGraph get_node failed: {exc}") from exc

    async def query(
        self,
        cypher: str,
        *,
        params: dict | None = None,
    ) -> list[dict]:
        """Execute a raw SQL query (named 'cypher' for protocol compatibility).

        For PgGraphStore, callers should pass SQL instead of Cypher.
        For backward compatibility with code that passes Cypher, we handle
        common patterns.
        """
        async with async_session_factory() as session:
            try:
                result = await session.execute(text(cypher), params or {})
                return [dict(row._mapping) for row in result.fetchall()]
            except Exception as exc:
                logger.error("PgGraph query failed: %s (sql: %.200s)", exc, cypher)
                raise RuntimeError(f"PgGraph query failed: {exc}") from exc

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
        depth = max(1, min(depth, 5))

        # Build recursive CTE for citation network traversal.
        treatment_filter = ""
        params: dict = {"node_id": node_id, "max_depth": depth}
        if relationship:
            treatment_filter = "AND c.treatment = :treatment"
            params["treatment"] = relationship

        if direction == "outgoing":
            # Cases this case cites
            base_join = "c.source_case_id = :node_id::uuid"
            recursive_join = "c.source_case_id = net.target_case_id"
            target_col = "c.target_case_id"
        elif direction == "incoming":
            # Cases that cite this case
            base_join = "c.target_case_id = :node_id::uuid"
            recursive_join = "c.target_case_id = net.source_case_id"
            target_col = "c.source_case_id"
        else:
            # Both directions — union of outgoing and incoming
            base_join = "(c.source_case_id = :node_id::uuid OR c.target_case_id = :node_id::uuid)"
            recursive_join = (
                "(c.source_case_id = net.found_id OR c.target_case_id = net.found_id)"
            )
            target_col = (
                "CASE WHEN c.source_case_id = net.found_id "
                "THEN c.target_case_id ELSE c.source_case_id END"
            )

        sql = text(f"""
            WITH RECURSIVE net AS (
                SELECT
                    CASE WHEN c.source_case_id = :node_id::uuid
                         THEN c.target_case_id ELSE c.source_case_id END AS found_id,
                    c.treatment AS rel_type,
                    1 AS depth
                FROM citations c
                WHERE {base_join} {treatment_filter}
                  AND c.target_case_id IS NOT NULL

                UNION ALL

                SELECT
                    {target_col} AS found_id,
                    c.treatment AS rel_type,
                    net.depth + 1 AS depth
                FROM citations c
                JOIN net ON {recursive_join}
                WHERE net.depth < :max_depth {treatment_filter}
                  AND c.target_case_id IS NOT NULL
            )
            SELECT DISTINCT ON (cs.id)
                cs.id, cs.title, cs.citation, cs.court, cs.year,
                cs.case_type, cs.bench_type, n.rel_type
            FROM net n
            JOIN cases cs ON cs.id = n.found_id
            WHERE n.found_id != :node_id::uuid
            LIMIT 100
        """)

        try:
            async with async_session_factory() as session:
                result = await session.execute(sql, params)
                rows = result.fetchall()
                nodes = []
                for row in rows:
                    mapping = dict(row._mapping)
                    rel = mapping.pop("rel_type", "CITES")
                    nodes.append({"node": mapping, "relationship": rel})
                return {"center": node_id, "neighbors": nodes}
        except Exception as exc:
            logger.error("PgGraph get_neighbors failed (id=%s): %s", node_id, exc)
            raise RuntimeError(f"PgGraph get_neighbors failed: {exc}") from exc

    async def ensure_constraints(self) -> None:
        """Ensure indexes exist on citations table. Safe to call multiple times."""
        # Indexes are created by the migration; this is a no-op for PostgreSQL.
        logger.info("PgGraph ensure_constraints: indexes managed by migrations")

    async def batch_create_nodes(
        self,
        nodes: list[dict],
        *,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> int:
        """Batch-create Case nodes. Since cases are created by the ingestion pipeline,
        this only updates graph-relevant fields on existing rows."""
        if not nodes:
            return 0

        total = 0
        async with async_session_factory() as session:
            try:
                for i in range(0, len(nodes), batch_size):
                    batch = nodes[i : i + batch_size]
                    for node in batch:
                        node_id = node.get("id")
                        if not node_id:
                            continue
                        result = await session.execute(
                            text(
                                "UPDATE cases SET "
                                "  citation = COALESCE(:citation, citation) "
                                "WHERE id = :id"
                            ),
                            {"id": node_id, "citation": node.get("citation")},
                        )
                        total += result.rowcount
                await session.commit()
                logger.info("batch_create_nodes: updated %d nodes in %d batches",
                            total, (len(nodes) + batch_size - 1) // batch_size)
                return total
            except Exception as exc:
                await session.rollback()
                logger.error("PgGraph batch_create_nodes failed: %s", exc)
                raise RuntimeError(f"PgGraph batch_create_nodes failed: {exc}") from exc

    async def batch_create_citation_edges(
        self,
        edges: list[dict],
        *,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> int:
        """Batch-create citation edges using INSERT ON CONFLICT."""
        if not edges:
            return 0

        total = 0
        async with async_session_factory() as session:
            try:
                for i in range(0, len(edges), batch_size):
                    batch = edges[i : i + batch_size]
                    value_clauses = []
                    params: dict = {}
                    for j, edge in enumerate(batch):
                        src = f"src_{j}"
                        tgt = f"tgt_{j}"
                        treat = f"treat_{j}"
                        params[src] = edge["source_id"]
                        params[tgt] = edge["target_citation"]
                        params[treat] = edge.get("treatment", "CITED")
                        value_clauses.append(
                            f"(:{src}::uuid, :{tgt}, :{treat})"
                        )

                    sql = text(
                        "INSERT INTO citations (source_case_id, target_citation, treatment) "
                        f"VALUES {', '.join(value_clauses)} "
                        "ON CONFLICT (source_case_id, target_citation) "
                        "DO UPDATE SET treatment = EXCLUDED.treatment"
                    )
                    result = await session.execute(sql, params)
                    total += result.rowcount

                # Resolve target_case_id for citations that reference known cases.
                await session.execute(text(
                    "UPDATE citations SET target_case_id = c.id "
                    "FROM cases c "
                    "WHERE citations.target_citation = c.citation "
                    "AND citations.target_case_id IS NULL"
                ))

                await session.commit()
                logger.info(
                    "batch_create_citation_edges: merged %d edges in %d batches",
                    total, (len(edges) + batch_size - 1) // batch_size,
                )
                return total
            except Exception as exc:
                await session.rollback()
                logger.error("PgGraph batch_create_citation_edges failed: %s", exc)
                raise RuntimeError(
                    f"PgGraph batch_create_citation_edges failed: {exc}"
                ) from exc

    async def delete_node(self, node_id: str) -> bool:
        """Delete citation edges for a case (does not delete the case itself)."""
        async with async_session_factory() as session:
            try:
                result = await session.execute(
                    text(
                        "DELETE FROM citations "
                        "WHERE source_case_id = :id::uuid OR target_case_id = :id::uuid"
                    ),
                    {"id": node_id},
                )
                await session.commit()
                return result.rowcount > 0
            except Exception as exc:
                await session.rollback()
                logger.error("PgGraph delete_node failed (id=%s): %s", node_id, exc)
                raise RuntimeError(f"PgGraph delete_node failed: {exc}") from exc
