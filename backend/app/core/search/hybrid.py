"""Hybrid search orchestrator with Reciprocal Rank Fusion (RRF).

Runs Pinecone vector search and PostgreSQL FTS in parallel, merges results
using RRF (k=60), reranks with Cohere, and enriches from PostgreSQL.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.interfaces import EmbeddingProvider, LLMProvider, Reranker, VectorStore
from app.core.search.fulltext import FTSResult, search_fulltext
from app.core.search.query import QueryUnderstanding, SearchFilters, understand_query

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchResultItem:
    """A single enriched search result."""

    case_id: str
    score: float
    title: str | None = None
    citation: str | None = None
    court: str | None = None
    year: int | None = None
    date: str | None = None
    case_type: str | None = None
    judge: str | None = None
    snippet: str | None = None
    relevance_sources: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SearchResponse:
    """Complete search response with results, facets, and query analysis."""

    results: list[SearchResultItem]
    total_count: int
    page: int
    page_size: int
    query_understanding: QueryUnderstanding
    facets: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# RRF merge — pure function, easily testable
# ---------------------------------------------------------------------------


def rrf_merge(
    ranked_lists: list[list[tuple[str, float]]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    Each list is a sequence of ``(doc_id, score)`` tuples ordered by
    descending score. The *score* values are ignored; only the rank
    position matters.

    Formula: ``RRF(d) = Σ 1 / (k + rank_i(d))`` for each list *i*.

    Returns a list of ``(doc_id, rrf_score)`` sorted by descending RRF score.
    """
    scores: dict[str, float] = {}

    for ranked in ranked_lists:
        for rank_pos, (doc_id, _original_score) in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank_pos)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def hybrid_search(
    query: str,
    *,
    filters: SearchFilters | None = None,
    page: int = 1,
    page_size: int | None = None,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    db: AsyncSession,
    redis_client=None,
) -> SearchResponse:
    """Execute a hybrid search: LLM parse → parallel vector+FTS → RRF → rerank → enrich."""

    effective_page_size = min(
        page_size or settings.search_default_page_size,
        settings.search_max_page_size,
    )

    # 1. Check Redis cache
    cache_key = _make_cache_key(query, filters, page, effective_page_size)
    if redis_client is not None:
        cached = await _get_cached(redis_client, cache_key)
        if cached is not None:
            return cached

    # 2. Query understanding (LLM)
    qu = await understand_query(query, llm)

    # Merge explicit filters with LLM-extracted filters (explicit wins)
    merged_filters = _merge_filters(filters, qu.filters)

    # 3. Parallel retrieval — vector + FTS
    search_query = qu.expanded_query or query

    vector_task = _vector_search(
        search_query,
        embedder=embedder,
        vector_store=vector_store,
        filters=merged_filters,
    )
    fts_task = search_fulltext(
        search_query,
        filters=merged_filters,
        limit=settings.search_fts_top_k,
        db=db,
    )

    vector_results, fts_results = await asyncio.gather(vector_task, fts_task)

    # 4. RRF merge
    vector_ranked = [(r[0], r[1]) for r in vector_results]
    fts_ranked = [(r.case_id, r.rank) for r in fts_results]

    merged = rrf_merge(
        [vector_ranked, fts_ranked],
        k=settings.search_rrf_k,
    )

    if not merged:
        return SearchResponse(
            results=[],
            total_count=0,
            page=page,
            page_size=effective_page_size,
            query_understanding=qu,
        )

    # 5. Rerank top candidates
    top_ids = [doc_id for doc_id, _ in merged[: settings.search_rerank_top_n * 2]]

    # Fetch text snippets for reranking
    snippets_map = _build_snippets_map(fts_results, vector_results)
    rerank_texts = [snippets_map.get(doc_id, doc_id) for doc_id in top_ids]

    try:
        reranked = await reranker.rerank(
            query=query,
            documents=rerank_texts,
            top_n=settings.search_rerank_top_n,
        )
        reranked_ids = [top_ids[r.index] for r in reranked]
        reranked_scores = {top_ids[r.index]: r.score for r in reranked}
    except (ConnectionError, TimeoutError, RuntimeError) as exc:
        logger.warning("Reranking failed, using RRF order: %s", exc)
        reranked_ids = top_ids[: settings.search_rerank_top_n]
        reranked_scores = dict(merged[: settings.search_rerank_top_n])

    # 6. Paginate
    total_count = len(reranked_ids)
    start = (page - 1) * effective_page_size
    end = start + effective_page_size
    page_ids = reranked_ids[start:end]

    if not page_ids:
        return SearchResponse(
            results=[],
            total_count=total_count,
            page=page,
            page_size=effective_page_size,
            query_understanding=qu,
        )

    # 7. Enrich from PostgreSQL
    enriched = await _enrich_results(page_ids, reranked_scores, snippets_map, db)

    # 8. Build facets from full result set
    facets = await _build_facets(reranked_ids, db)

    response = SearchResponse(
        results=enriched,
        total_count=total_count,
        page=page,
        page_size=effective_page_size,
        query_understanding=qu,
        facets=facets,
    )

    # 9. Cache result
    if redis_client is not None:
        await _set_cached(redis_client, cache_key, response)

    return response


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _vector_search(
    query: str,
    *,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    filters: SearchFilters | None,
) -> list[tuple[str, float]]:
    """Embed query and search Pinecone, returning (case_id, score) pairs."""
    query_vector = await embedder.embed_text(query)

    # Build Pinecone metadata filter
    pinecone_filter: dict = {}
    if filters:
        if filters.court:
            pinecone_filter["court"] = {"$eq": filters.court}
        if filters.year_from is not None:
            pinecone_filter["year"] = pinecone_filter.get("year", {})
            pinecone_filter["year"]["$gte"] = filters.year_from
        if filters.year_to is not None:
            pinecone_filter["year"] = pinecone_filter.get("year", {})
            pinecone_filter["year"]["$lte"] = filters.year_to
        if filters.case_type:
            pinecone_filter["case_type"] = {"$eq": filters.case_type}

    results = await vector_store.search(
        query_vector,
        top_k=settings.search_vector_top_k,
        filters=pinecone_filter if pinecone_filter else None,
    )

    # Deduplicate by case_id (chunks map to same case)
    seen: dict[str, float] = {}
    for r in results:
        case_id = r.metadata.get("case_id", r.id)
        if case_id not in seen or r.score > seen[case_id]:
            seen[case_id] = r.score

    return sorted(seen.items(), key=lambda x: x[1], reverse=True)


def _build_snippets_map(
    fts_results: list[FTSResult],
    vector_results: list[tuple[str, float]],
) -> dict[str, str]:
    """Build a map of case_id → text snippet for reranking."""
    snippets: dict[str, str] = {}
    for r in fts_results:
        if r.snippet:
            snippets[r.case_id] = r.snippet
        elif r.title:
            snippets[r.case_id] = r.title
    return snippets


def _merge_filters(
    explicit: SearchFilters | None,
    llm_extracted: SearchFilters,
) -> SearchFilters:
    """Merge explicit user filters with LLM-extracted filters. Explicit wins."""
    if explicit is None:
        return llm_extracted

    return SearchFilters(
        court=explicit.court or llm_extracted.court,
        year_from=explicit.year_from if explicit.year_from is not None else llm_extracted.year_from,
        year_to=explicit.year_to if explicit.year_to is not None else llm_extracted.year_to,
        case_type=explicit.case_type or llm_extracted.case_type,
        bench_type=explicit.bench_type or llm_extracted.bench_type,
        judge=explicit.judge or llm_extracted.judge,
        act=explicit.act or llm_extracted.act,
        section=explicit.section or llm_extracted.section,
    )


async def _enrich_results(
    case_ids: list[str],
    scores: dict[str, float],
    snippets_map: dict[str, str],
    db: AsyncSession,
) -> list[SearchResultItem]:
    """Fetch full metadata from PostgreSQL for the given case IDs."""
    if not case_ids:
        return []

    placeholders = ", ".join(f":id_{i}" for i in range(len(case_ids)))
    params = {f"id_{i}": cid for i, cid in enumerate(case_ids)}

    sql = text(
        f"SELECT id, title, citation, court, year, decision_date, "
        f"case_type, judge "
        f"FROM cases WHERE id IN ({placeholders})"
    )

    result = await db.execute(sql, params)
    rows = {str(row["id"]): row for row in result.mappings().all()}

    enriched: list[SearchResultItem] = []
    for cid in case_ids:
        row = rows.get(cid)
        if row is None:
            continue
        enriched.append(
            SearchResultItem(
                case_id=cid,
                score=scores.get(cid, 0.0),
                title=row.get("title"),
                citation=row.get("citation"),
                court=row.get("court"),
                year=row.get("year"),
                date=str(row["decision_date"]) if row.get("decision_date") else None,
                case_type=row.get("case_type"),
                judge=row.get("judge"),
                snippet=snippets_map.get(cid),
            )
        )

    return enriched


async def _build_facets(
    case_ids: list[str],
    db: AsyncSession,
) -> dict:
    """Build facet counts from the result set."""
    if not case_ids:
        return {}

    placeholders = ", ".join(f":id_{i}" for i in range(len(case_ids)))
    params = {f"id_{i}": cid for i, cid in enumerate(case_ids)}

    sql = text(
        f"SELECT court, case_type, year, bench_type "
        f"FROM cases WHERE id IN ({placeholders})"
    )

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    courts: dict[str, int] = {}
    case_types: dict[str, int] = {}
    years: dict[int, int] = {}
    bench_types: dict[str, int] = {}

    for row in rows:
        if row.get("court"):
            courts[row["court"]] = courts.get(row["court"], 0) + 1
        if row.get("case_type"):
            case_types[row["case_type"]] = case_types.get(row["case_type"], 0) + 1
        if row.get("year"):
            years[row["year"]] = years.get(row["year"], 0) + 1
        if row.get("bench_type"):
            bench_types[row["bench_type"]] = bench_types.get(row["bench_type"], 0) + 1

    return {
        "courts": courts,
        "case_types": case_types,
        "years": years,
        "bench_types": bench_types,
    }


# ---------------------------------------------------------------------------
# Redis caching
# ---------------------------------------------------------------------------


def _make_cache_key(
    query: str,
    filters: SearchFilters | None,
    page: int,
    page_size: int,
) -> str:
    """Build a deterministic cache key from search parameters."""
    raw = json.dumps(
        {
            "q": query.lower().strip(),
            "f": asdict(filters) if filters else None,
            "p": page,
            "ps": page_size,
        },
        sort_keys=True,
    )
    return f"search:{hashlib.sha256(raw.encode()).hexdigest()}"


async def _get_cached(redis_client, key: str) -> SearchResponse | None:
    """Try to retrieve a cached search response."""
    try:
        data = await redis_client.get(key)
        if data is not None:
            logger.debug("Search cache hit: %s", key)
            parsed = json.loads(data)
            return _deserialize_response(parsed)
    except (ConnectionError, TimeoutError, ValueError):
        pass
    return None


async def _set_cached(redis_client, key: str, response: SearchResponse) -> None:
    """Cache a search response with TTL."""
    try:
        data = _serialize_response(response)
        await redis_client.setex(
            key,
            settings.search_cache_ttl,
            json.dumps(data),
        )
    except (ConnectionError, TimeoutError, ValueError):
        pass


def _serialize_response(response: SearchResponse) -> dict:
    """Convert SearchResponse to a JSON-serializable dict."""
    return {
        "results": [asdict(r) for r in response.results],
        "total_count": response.total_count,
        "page": response.page,
        "page_size": response.page_size,
        "query_understanding": asdict(response.query_understanding),
        "facets": response.facets,
    }


def _deserialize_response(data: dict) -> SearchResponse:
    """Reconstruct SearchResponse from cached dict."""
    from app.core.search.query import QueryEntities

    qu_data = data["query_understanding"]
    qu = QueryUnderstanding(
        intent=qu_data["intent"],
        original_query=qu_data["original_query"],
        expanded_query=qu_data["expanded_query"],
        filters=SearchFilters(**qu_data["filters"]),
        entities=QueryEntities(**qu_data["entities"]),
        search_strategy=qu_data["search_strategy"],
    )

    results = [SearchResultItem(**r) for r in data["results"]]

    return SearchResponse(
        results=results,
        total_count=data["total_count"],
        page=data["page"],
        page_size=data["page_size"],
        query_understanding=qu,
        facets=data.get("facets", {}),
    )
