"""pgvector-based vector store provider implementation.

Uses PostgreSQL with the pgvector extension for similarity search.
Drop-in replacement for PineconeStore — switch via VECTOR_PROVIDER=pgvector.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.core.interfaces.vector_store import SearchResult
from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)

# Maximum vectors per upsert batch (PostgreSQL parameter limit / columns per row).
_UPSERT_BATCH_SIZE = 100

# Allowlist of valid metadata filter keys to prevent SQL injection via dict keys.
_ALLOWED_FILTER_KEYS = frozenset(
    {
        "case_id",
        "chunk_index",
        "section_type",
        "court",
        "year",
        "case_type",
        "jurisdiction",
        "bench_type",
        "disposal_nature",
        "title",
        "citation",
        "author_judge",
        "judge",
        "acts_cited",
        "opinion_author",
        "para_start",
        "para_end",
        "language",
        "is_reportable",
        "user_id",
    }
)


def _build_filter_clause(
    filters: dict[str, Any],
    params: dict[str, Any],
    *,
    prefix: str = "f",
) -> str:
    """Translate Pinecone-style filter dict to SQL WHERE clauses on JSONB metadata.

    Supports operators: $eq, $in, $gte, $lte, $ne, and bare-value shorthand.
    """
    clauses: list[str] = []
    idx = 0

    for key, value in filters.items():
        if key not in _ALLOWED_FILTER_KEYS:
            raise ValueError(
                f"Unknown filter key: {key!r}. Allowed: {sorted(_ALLOWED_FILTER_KEYS)}"
            )
        if isinstance(value, dict):
            for op, operand in value.items():
                pname = f"{prefix}_{idx}"
                idx += 1
                if op == "$eq":
                    clauses.append(f"metadata->>'{key}' = :{pname}")
                    params[pname] = str(operand)
                elif op == "$ne":
                    clauses.append(f"metadata->>'{key}' != :{pname}")
                    params[pname] = str(operand)
                elif op == "$gte":
                    clauses.append(f"(metadata->>'{key}')::int >= :{pname}")
                    params[pname] = int(operand)
                elif op == "$lte":
                    clauses.append(f"(metadata->>'{key}')::int <= :{pname}")
                    params[pname] = int(operand)
                elif op == "$in":
                    if isinstance(operand, list) and len(operand) == 1:
                        # Single-element $in for array-contains check
                        clauses.append(f"metadata->'{key}' ? :{pname}")
                        params[pname] = str(operand[0])
                    else:
                        placeholders = []
                        for i, item in enumerate(operand):
                            p = f"{pname}_{i}"
                            placeholders.append(f":{p}")
                            params[p] = str(item)
                        clauses.append(f"metadata->>'{key}' IN ({', '.join(placeholders)})")
        else:
            # Bare value = exact match
            pname = f"{prefix}_{idx}"
            idx += 1
            clauses.append(f"metadata->>'{key}' = :{pname}")
            params[pname] = str(value)

    return " AND ".join(clauses) if clauses else "TRUE"


class PgvectorStore:
    """PostgreSQL pgvector store implementing VectorStore protocol.

    Uses the same async session factory as the rest of the app — no extra
    connections or drivers needed.
    """

    def __init__(self) -> None:
        self._dimension = settings.gemini_embedding_dimension

    async def upsert(self, vectors: list[dict]) -> None:
        """Insert or update vectors. Each dict must contain: id, values, metadata."""
        if not vectors:
            return

        async with async_session_factory() as session:
            try:
                for i in range(0, len(vectors), _UPSERT_BATCH_SIZE):
                    batch = vectors[i : i + _UPSERT_BATCH_SIZE]
                    # Build a multi-row VALUES clause
                    value_clauses = []
                    params: dict[str, Any] = {}
                    for j, vec in enumerate(batch):
                        vid = f"id_{j}"
                        vcid = f"cid_{j}"
                        vci = f"ci_{j}"
                        vemb = f"emb_{j}"
                        vmeta = f"meta_{j}"

                        params[vid] = vec["id"]
                        params[vcid] = vec["metadata"].get("case_id", "")
                        params[vci] = vec["metadata"].get("chunk_index", 0)
                        params[vemb] = str(vec["values"])
                        params[vmeta] = json.dumps(vec["metadata"])

                        value_clauses.append(
                            f"(:{vid}, :{vcid}::uuid, :{vci}, :{vemb}::vector, :{vmeta}::jsonb)"
                        )

                    sql = text(
                        "INSERT INTO case_vectors (id, case_id, chunk_index, embedding, metadata) "
                        f"VALUES {', '.join(value_clauses)} "
                        "ON CONFLICT (id) DO UPDATE SET "
                        "  embedding = EXCLUDED.embedding, "
                        "  metadata = EXCLUDED.metadata"
                    )
                    await session.execute(sql, params)
                await session.commit()
                logger.info("Upserted %d vectors into pgvector", len(vectors))
            except Exception as exc:
                await session.rollback()
                logger.error("pgvector upsert failed (%d vectors): %s", len(vectors), exc)
                raise RuntimeError(f"pgvector upsert failed: {exc}") from exc

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 20,
        filters: dict | None = None,
        user_scope: str | None = None,
    ) -> list[SearchResult]:
        if user_scope:
            filters = dict(filters) if filters else {}
            filters["user_id"] = user_scope

        params: dict[str, Any] = {
            "query_vec": str(query_vector),
            "top_k": top_k,
        }
        where = "TRUE"
        if filters:
            where = _build_filter_clause(filters, params)

        # Cosine distance: <=> operator. Convert to similarity score (1 - distance).
        sql = text(
            "SELECT id, metadata, 1 - (embedding <=> :query_vec::vector) AS score "
            f"FROM case_vectors WHERE {where} "
            "ORDER BY embedding <=> :query_vec::vector "
            "LIMIT :top_k"
        )
        try:
            async with async_session_factory() as session:
                result = await session.execute(sql, params)
                rows = result.fetchall()
                return [
                    SearchResult(
                        id=row.id,
                        score=float(row.score),
                        metadata=row.metadata if isinstance(row.metadata, dict) else {},
                    )
                    for row in rows
                ]
        except Exception as exc:
            logger.error("pgvector search failed (top_k=%d): %s", top_k, exc)
            return []

    async def delete(self, ids: list[str]) -> None:
        """Delete vectors by their IDs."""
        if not ids:
            return
        async with async_session_factory() as session:
            try:
                # Delete in batches of 1000
                for i in range(0, len(ids), 1000):
                    batch = ids[i : i + 1000]
                    placeholders = ", ".join(f":id_{j}" for j in range(len(batch)))
                    params = {f"id_{j}": vid for j, vid in enumerate(batch)}
                    await session.execute(
                        text(f"DELETE FROM case_vectors WHERE id IN ({placeholders})"),
                        params,
                    )
                await session.commit()
            except Exception as exc:
                await session.rollback()
                logger.error("pgvector delete failed (%d ids): %s", len(ids), exc)
                raise RuntimeError(f"pgvector delete failed: {exc}") from exc

    async def delete_by_metadata(
        self,
        filter: dict[str, Any],
        *,
        exclude_ids: list[str] | None = None,
    ) -> None:
        """Delete vectors matching a metadata filter, optionally excluding specific IDs."""
        params: dict[str, Any] = {}
        where = _build_filter_clause(filter, params, prefix="df")

        if exclude_ids:
            excl_placeholders = ", ".join(f":excl_{i}" for i in range(len(exclude_ids)))
            for i, eid in enumerate(exclude_ids):
                params[f"excl_{i}"] = eid
            where += f" AND id NOT IN ({excl_placeholders})"

        sql = text(f"DELETE FROM case_vectors WHERE {where}")
        try:
            async with async_session_factory() as session:
                result = await session.execute(sql, params)
                await session.commit()
                deleted = result.rowcount
                logger.info(
                    "Deleted %d vectors by metadata filter=%s (excluded %d)",
                    deleted,
                    filter,
                    len(exclude_ids) if exclude_ids else 0,
                )
        except Exception as exc:
            logger.error("pgvector delete_by_metadata failed (filter=%s): %s", filter, exc)
            raise RuntimeError(f"pgvector delete_by_metadata failed: {exc}") from exc
