"""Research Agent V2 — Worker node functions for LangGraph Send() fan-out.

Each worker handles a specific research task type (case_law, named_case, etc.).
Workers follow a search → enrich → return pattern. They do NOT generate CoT
reasoning individually — that's handled by batch_worker_cot_node [S4] which
runs a single Flash call after all workers finish.

Workers use pre-warmed embeddings [S6] when available.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.nodes.common import (
    _search_by_title,
    enrich_results_with_ratio,
    parallel_hybrid_search,
)
from app.core.agents.state import WorkerResult
from app.core.interfaces import EmbeddingProvider, LLMProvider, Reranker, VectorStore
from app.core.search.hybrid import _exact_citation_search
from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker: case_law_worker — dual-query hybrid search
# ---------------------------------------------------------------------------


async def case_law_worker(
    state: dict,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
) -> dict:
    """Search our judgment database using dual NL + boolean queries.

    Wraps the existing parallel_hybrid_search with multi-query support.
    """
    task = state["task"]
    precomputed = state.get("precomputed_embeddings", {})

    # Use BOTH nl_query (vector-heavy) and boolean_query (keyword-heavy)
    queries = [task["nl_query"]]
    if task.get("boolean_query"):
        queries.append(task["boolean_query"])

    try:
        async with async_session_factory() as db:
            results = await parallel_hybrid_search(
                queries, llm, embedder, vector_store, reranker, db,
                precomputed_embeddings=precomputed,
            )
            results = await enrich_results_with_ratio(results, db, max_ratio_len=3000)
    except Exception as exc:
        logger.warning("case_law_worker failed: %s", exc)
        return {"worker_results": [WorkerResult(
            task_id=task["task_id"], task_type="case_law",
            query=task["nl_query"], results=[],
            source_urls=[], metadata={}, error=str(exc),
            reasoning="",
        )]}

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="case_law",
        query=task["nl_query"], results=results,
        source_urls=[], metadata={}, error=None,
        reasoning="",  # Populated by batch_worker_cot_node [S4]
    )]}


# ---------------------------------------------------------------------------
# Worker: named_case_worker — direct citation/title lookup
# ---------------------------------------------------------------------------


async def named_case_worker(
    state: dict,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
) -> dict:
    """Look up specific landmark cases by citation or title.

    Tries exact citation search first, falls back to title-based ILIKE search.
    """
    task = state["task"]
    results: list[dict] = []

    try:
        async with async_session_factory() as db:
            for named in task.get("named_cases", []):
                found: list[Any] = []

                # Try exact citation search first
                if named.get("citation"):
                    from dataclasses import asdict
                    citation_results = await _exact_citation_search(
                        named["citation"], db,
                    )
                    found = [asdict(r) for r in citation_results]

                # Fallback: search by case name in title
                if not found and named.get("name"):
                    found = await _search_by_title(named["name"], db)

                results.extend(found)

            # Enrich with ratio decidendi
            if results:
                results = await enrich_results_with_ratio(
                    results, db, max_ratio_len=3000,
                )
    except Exception as exc:
        logger.warning("named_case_worker failed: %s", exc)
        return {"worker_results": [WorkerResult(
            task_id=task["task_id"], task_type="named_case",
            query=str(task.get("named_cases", [])),
            results=[], source_urls=[], metadata={},
            error=str(exc), reasoning="",
        )]}

    # Also try the NL query as a hybrid search if we have one and few results
    if len(results) < 2 and task.get("nl_query"):
        try:
            async with async_session_factory() as db:
                supplemental = await parallel_hybrid_search(
                    [task["nl_query"]], llm, embedder, vector_store, reranker, db,
                )
                supplemental = await enrich_results_with_ratio(
                    supplemental, db, max_ratio_len=3000,
                )
                # Add only new results (not already found by citation)
                existing_ids = {r.get("case_id") for r in results}
                for r in supplemental:
                    if r.get("case_id") not in existing_ids:
                        results.append(r)
        except Exception:
            pass  # Supplemental search is best-effort

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="named_case",
        query=task.get("nl_query", ""),
        results=results, source_urls=[], metadata={},
        error=None, reasoning="",
    )]}
