"""Hybrid search orchestrator with Reciprocal Rank Fusion (RRF).

Runs Pinecone vector search and PostgreSQL FTS in parallel, merges results
using RRF (k=60), reranks with Cohere, and enriches from PostgreSQL.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.core.config import settings
from app.core.legal.extractor import normalize_act_name
from app.core.legal.treatment import has_overruling_language
from app.core.search.fulltext import FTSResult, search_fulltext
from app.core.search.query import (
    QueryEntities,
    QueryUnderstanding,
    SearchFilters,
    expand_statute_references,
    understand_query,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.interfaces import EmbeddingProvider, LLMProvider, Reranker, VectorStore

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
    chunk_text: str | None = None
    bench_type: str | None = None
    equivalent_citations: list[str] = field(default_factory=list)
    relevance_sources: list[str] = field(default_factory=list)
    treatment_warning: str | None = None
    char_start: int = 0
    char_end: int = 0


@dataclass(slots=True)
class SearchResponse:
    """Complete search response with results, facets, and query analysis."""

    results: list[SearchResultItem]
    total_count: int
    page: int
    page_size: int
    query_understanding: QueryUnderstanding
    facets: dict = field(default_factory=dict)
    outcome_bias_warning: str | None = None
    search_degraded: bool = False


# ---------------------------------------------------------------------------
# RRF merge — pure function, easily testable
# ---------------------------------------------------------------------------


def rrf_merge(
    ranked_lists: list[list[tuple[str, float]]],
    *,
    k: int = 60,
    weights: list[float] | None = None,
) -> list[tuple[str, float]]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    Each list is a sequence of ``(doc_id, score)`` tuples ordered by
    descending score. The *score* values are ignored; only the rank
    position matters.

    Formula: ``RRF(d) = Σ w_i / (k + rank_i(d))`` for each list *i*,
    where *w_i* defaults to 1.0 when *weights* is ``None``.

    Args:
        ranked_lists: Ranked result lists to merge.
        k: RRF constant (default 60).
        weights: Optional per-list multipliers. Must have the same length
            as *ranked_lists* if provided.

    Returns a list of ``(doc_id, rrf_score)`` sorted by descending RRF score.

    Raises:
        ValueError: If *weights* length does not match *ranked_lists* length.
    """
    if weights is not None and len(weights) != len(ranked_lists):
        raise ValueError(
            f"weights length ({len(weights)}) must match "
            f"ranked_lists length ({len(ranked_lists)})"
        )

    scores: dict[str, float] = {}

    for list_idx, ranked in enumerate(ranked_lists):
        w = weights[list_idx] if weights is not None else 1.0
        for rank_pos, (doc_id, _original_score) in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + w / (k + rank_pos)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def apply_legal_signal_boost(
    merged: list[tuple[str, float]],
    signal_map: dict[str, float],
    *,
    boost_factor: float = 1.0,
    signal_denominator: float = 500.0,
) -> list[tuple[str, float]]:
    """Boost RRF scores for chunks with high legal_signal density.

    Formula: boosted_score = rrf_score * (1 + boost_factor * legal_signal / signal_denominator)
    """
    if not signal_map:
        return merged
    boosted = [
        (doc_id, score * (1.0 + boost_factor * signal_map.get(doc_id, 0.0) / signal_denominator))
        for doc_id, score in merged
    ]
    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted


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
    language: str = "en",
    pre_understood: bool = False,
    pre_embedded: list[float] | None = None,
) -> SearchResponse:
    """Execute a hybrid search: LLM parse → parallel vector+FTS → RRF → rerank → enrich.

    Args:
        pre_understood: When True, skip the LLM understand_query() call.
            Use this when the query has already been rewritten/understood by
            an upstream agent node (saves ~2s per search).
    """

    effective_page_size = min(
        page_size or settings.search_default_page_size,
        settings.search_max_page_size,
    )

    # 1. Check Redis cache
    cache_key = _make_cache_key(query, filters, page, effective_page_size, language)
    if redis_client is not None:
        cached = await _get_cached(redis_client, cache_key)
        if cached is not None:
            return cached

    # 2. Query understanding (LLM) — [B8] skip when pre_understood
    if pre_understood:
        qu = QueryUnderstanding(
            intent="research",
            original_query=query,
            expanded_query=query,
            filters=SearchFilters(),
            entities=QueryEntities(),
            search_strategy="hybrid",
        )
    else:
        qu = await understand_query(query, llm)

    # Merge explicit filters with LLM-extracted filters (explicit wins)
    merged_filters = _merge_filters(filters, qu.filters)

    # 3. Strategy-based retrieval
    search_query = qu.expanded_query or query

    # Expand old-law / new-law statute references (IPC<->BNS, CrPC<->BNSS, IEA<->BSA)
    # Returns (original_query, expanded_terms) — expanded terms use OR syntax
    # which is meaningful for FTS but not for vector embeddings.
    search_query, expanded_terms = expand_statute_references(search_query)
    fts_query = " OR ".join([search_query, *expanded_terms]) if expanded_terms else search_query

    strategy = qu.search_strategy

    search_degraded = False

    # --- exact_match strategy: try citation lookup first ---
    if strategy == "exact_match":
        exact_results = await _exact_citation_search(query, db)
        if exact_results:
            # Return early — no reranking needed for exact matches
            total_count = len(exact_results)
            start = (page - 1) * effective_page_size
            end = start + effective_page_size
            page_results = exact_results[start:end]

            response = SearchResponse(
                results=page_results,
                total_count=total_count,
                page=page,
                page_size=effective_page_size,
                query_understanding=qu,
            )
            if redis_client is not None:
                await _set_cached(redis_client, cache_key, response)
            return response
        # Fallback: FTS only for exact_match when no citation found
        fts_results = await search_fulltext(
            fts_query,
            filters=merged_filters,
            limit=settings.search_fts_top_k,
            db=db,
            language=language,
        )
        fts_ranked = [(r.case_id, r.rank) for r in fts_results]
        merged = rrf_merge([fts_ranked], k=settings.search_rrf_k_keyword_heavy)
        vector_results: list[tuple[str, float, str]] = []
    else:
        # Parallel retrieval — vector + FTS
        vector_task = _vector_search(
            search_query,
            embedder=embedder,
            vector_store=vector_store,
            filters=merged_filters,
            pre_embedded=pre_embedded,
        )

        if language == "hi":
            # Hindi: skip FTS entirely, vector-only search
            vector_results = await vector_task
            fts_results: list[FTSResult] = []
        else:
            fts_task = search_fulltext(
                fts_query,
                filters=merged_filters,
                limit=settings.search_fts_top_k,
                db=db,
                language=language,
            )

            gather_results = await asyncio.gather(vector_task, fts_task, return_exceptions=True)
            vector_results = (
                gather_results[0] if not isinstance(gather_results[0], Exception) else []
            )
            fts_results = gather_results[1] if not isinstance(gather_results[1], Exception) else []
            vector_failed = isinstance(gather_results[0], Exception)
            fts_failed = isinstance(gather_results[1], Exception)
            if vector_failed:
                logger.warning("Vector search failed, using FTS only: %s", gather_results[0])
            if fts_failed:
                logger.warning("FTS failed, using vector only: %s", gather_results[1])
            search_degraded = vector_failed or fts_failed

        # 4. RRF merge with strategy-specific weights
        vector_ranked = [(r[0], r[1]) for r in vector_results]
        fts_ranked = [(r.case_id, r.rank) for r in fts_results]

        strategy_config: dict[str, dict] = {
            "keyword_heavy": {"weights": [1.0, 2.0], "k": settings.search_rrf_k_keyword_heavy},
            "vector_heavy": {"weights": [2.0, 1.0], "k": settings.search_rrf_k_vector_heavy},
            "balanced": {"weights": [1.0, 1.0], "k": settings.search_rrf_k},
        }
        # Hindi: force vector-heavy since FTS is skipped
        if language == "hi":
            config = {"weights": [2.0, 0.0], "k": settings.search_rrf_k_vector_heavy}
        else:
            config = strategy_config.get(strategy, strategy_config["balanced"])

        merged = rrf_merge(
            [vector_ranked, fts_ranked],
            k=config["k"],
            weights=config["weights"],
        )

        # Post-merge boost: reward chunks with high legal_signal density
        signal_map = {r[0]: r[5] for r in vector_results if len(r) > 5 and r[5] > 0}
        merged = apply_legal_signal_boost(merged, signal_map)

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

    # 6. Paginate — use total merged result count (not truncated reranked count)
    total_count = len(merged)
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
    vector_chunk_map = {cid: text for cid, _score, text, *_pos in vector_results if text}
    char_pos_map = {
        cid: (cs, ce)
        for cid, _score, _text, cs, ce, *_rest in vector_results
        if cs and ce and ce > cs
    }
    enriched = await _enrich_results(
        page_ids, reranked_scores, snippets_map, db, vector_chunk_map, char_pos_map
    )

    # 8. Build facets from full result set
    facets = await _build_facets(reranked_ids, db)

    # Adjust total_count to reflect actually available results
    # (vector store may have IDs not yet in PostgreSQL)
    if len(enriched) < len(page_ids):
        total_count = len(enriched)

    # 8b. Check for outcome bias on bail/sentence queries
    outcome_bias = await _check_outcome_bias(query, reranked_ids, db)

    response = SearchResponse(
        results=enriched,
        total_count=total_count,
        page=page,
        page_size=effective_page_size,
        query_understanding=qu,
        facets=facets,
        outcome_bias_warning=outcome_bias,
        search_degraded=search_degraded,
    )

    # 9. Cache result
    if redis_client is not None:
        await _set_cached(redis_client, cache_key, response)

    return response


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _exact_citation_search(
    query: str,
    db: AsyncSession,
) -> list[SearchResultItem]:
    """Search for cases by exact citation match — checks both cases and equivalents tables."""
    query_clean = query.strip()
    # Escape regex special chars for word-boundary matching
    escaped_re = re.escape(query_clean)
    # Word-boundary regex: prevents "2020 SCC 1" matching "2020 SCC 10"
    boundary_pattern = rf"(^|\s){escaped_re}($|\s|[,;.\)])"

    # 1. Direct match on cases.citation using regex word boundary
    result = await db.execute(
        text(
            "SELECT id, title, citation, court, year, decision_date, "
            "case_type, judge, bench_type "
            "FROM cases WHERE citation ~* :pattern "
            "ORDER BY year DESC NULLS LAST "
            "LIMIT 5"
        ),
        {"pattern": boundary_pattern},
    )
    rows = result.mappings().all()

    # 2. If no direct match, check equivalents table
    if not rows:
        equiv_result = await db.execute(
            text(
                "SELECT c.id, c.title, c.citation, c.court, c.year, "
                "c.decision_date, c.case_type, c.judge, c.bench_type "
                "FROM case_citation_equivalents cce "
                "JOIN cases c ON c.id = cce.case_id "
                "WHERE cce.citation_text ~* :pattern LIMIT 5"
            ),
            {"pattern": boundary_pattern},
        )
        rows = equiv_result.mappings().all()

    if not rows:
        return []

    return [
        SearchResultItem(
            case_id=str(row["id"]),
            score=1.0,
            title=row.get("title"),
            citation=row.get("citation"),
            court=row.get("court"),
            year=row.get("year"),
            date=str(row["decision_date"]) if row.get("decision_date") else None,
            case_type=row.get("case_type"),
            judge=row.get("judge"),
            snippet=None,
            bench_type=row.get("bench_type"),
        )
        for row in rows
    ]


async def _vector_search(
    query: str,
    *,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    filters: SearchFilters | None,
    pre_embedded: list[float] | None = None,
) -> list[tuple[str, float, str]]:
    """Embed query and search Pinecone, returning (case_id, score, chunk_text) triples."""
    query_vector = pre_embedded if pre_embedded else await embedder.embed_text(query)

    # Build Pinecone metadata filter
    pinecone_filter: dict = {}
    if filters:
        if filters.court:
            if len(filters.court) == 1:
                pinecone_filter["court"] = {"$eq": filters.court[0]}
            else:
                pinecone_filter["court"] = {"$in": filters.court}
        if filters.year_from is not None:
            pinecone_filter["year"] = pinecone_filter.get("year", {})
            pinecone_filter["year"]["$gte"] = filters.year_from
        if filters.year_to is not None:
            pinecone_filter["year"] = pinecone_filter.get("year", {})
            pinecone_filter["year"]["$lte"] = filters.year_to
        if filters.case_type:
            pinecone_filter["case_type"] = {"$eq": filters.case_type}
        if filters.judgment_section:
            pinecone_filter["section_type"] = {"$eq": filters.judgment_section}
        if filters.bench_type:
            pinecone_filter["bench_type"] = {"$eq": filters.bench_type}
        if filters.disposal_nature:
            pinecone_filter["disposal_nature"] = {"$eq": filters.disposal_nature}
        if filters.judge:
            pinecone_filter["author_judge"] = {"$eq": filters.judge}
        if filters.act:
            normalized_act = normalize_act_name(filters.act)
            pinecone_filter["acts_cited"] = {"$in": [normalized_act]}
        if filters.vector_types:
            pinecone_filter["vector_type"] = {"$in": filters.vector_types}

    results = await vector_store.search(
        query_vector,
        top_k=settings.search_vector_top_k,
        filters=pinecone_filter if pinecone_filter else None,
    )

    # Deduplicate by case_id (chunks map to same case), keeping best chunk text
    # Also preserve char_start/char_end for passage expansion and legal_signal score
    seen: dict[str, tuple[float, str, int, int, float]] = {}
    for r in results:
        case_id = r.metadata.get("case_id", r.id)
        chunk_text = r.metadata.get("text", "") or r.metadata.get("chunk_text", "")
        char_start = int(r.metadata.get("char_start", 0) or 0)
        char_end = int(r.metadata.get("char_end", 0) or 0)
        legal_signal = float(r.metadata.get("legal_signal", 0.0) or 0.0)
        if case_id not in seen or r.score > seen[case_id][0]:
            seen[case_id] = (r.score, chunk_text, char_start, char_end, legal_signal)

    return sorted(
        [(cid, score, text, cs, ce, sig) for cid, (score, text, cs, ce, sig) in seen.items()],
        key=lambda x: x[1],
        reverse=True,
    )


def _build_snippets_map(
    fts_results: list[FTSResult],
    vector_results: list[tuple[str, float, str, int, int, float]],
) -> dict[str, str]:
    """Build a map of case_id -> text snippet for reranking.

    FTS headlines take priority. For cases found only via vector search,
    the Pinecone chunk text is used as fallback (instead of the case_id UUID).
    """
    snippets: dict[str, str] = {}
    for r in fts_results:
        if r.snippet:
            snippets[r.case_id] = r.snippet
        elif r.title:
            snippets[r.case_id] = r.title
    # Fill in vector chunk text for cases not already covered by FTS
    for case_id, _score, chunk_text, *_pos in vector_results:
        if case_id not in snippets and chunk_text:
            snippets[case_id] = chunk_text
    return snippets


def _merge_filters(
    explicit: SearchFilters | None,
    llm_extracted: SearchFilters,
) -> SearchFilters:
    """Merge explicit user filters with LLM-extracted filters. Explicit wins."""
    if explicit is None:
        return llm_extracted

    # For court lists, explicit always wins if provided
    merged_court = explicit.court if explicit.court else llm_extracted.court

    return SearchFilters(
        court=merged_court,
        year_from=explicit.year_from if explicit.year_from is not None else llm_extracted.year_from,
        year_to=explicit.year_to if explicit.year_to is not None else llm_extracted.year_to,
        case_type=explicit.case_type or llm_extracted.case_type,
        bench_type=explicit.bench_type or llm_extracted.bench_type,
        judge=explicit.judge or llm_extracted.judge,
        act=explicit.act or llm_extracted.act,
        judgment_section=explicit.judgment_section or llm_extracted.judgment_section,
        disposal_nature=explicit.disposal_nature or llm_extracted.disposal_nature,
        vector_types=explicit.vector_types or llm_extracted.vector_types,
    )


async def _enrich_results(
    case_ids: list[str],
    scores: dict[str, float],
    snippets_map: dict[str, str],
    db: AsyncSession,
    vector_chunk_map: dict[str, str] | None = None,
    char_pos_map: dict[str, tuple[int, int]] | None = None,
) -> list[SearchResultItem]:
    """Fetch full metadata from PostgreSQL for the given case IDs."""
    if not case_ids:
        return []

    # Separate statute IDs (e.g. "statute:CrPC:438") from case UUIDs
    statute_ids = [cid for cid in case_ids if ":" in cid]
    case_ids = [cid for cid in case_ids if ":" not in cid]

    if not case_ids and not statute_ids:
        return []

    enriched: list[SearchResultItem] = []

    # Enrich case UUIDs from PostgreSQL
    if case_ids:
        placeholders = ", ".join(f":id_{i}" for i in range(len(case_ids)))
        params = {f"id_{i}": cid for i, cid in enumerate(case_ids)}

        sql = text(
            f"SELECT id, title, citation, court, year, decision_date, "
            f"case_type, judge, bench_type, disposal_nature "
            f"FROM cases WHERE id IN ({placeholders})"
        )

        result = await db.execute(sql, params)
        rows = {str(row["id"]): row for row in result.mappings().all()}

        # Fetch equivalent citations
        equiv_map: dict[str, list[str]] = {}
        try:
            equiv_result = await db.execute(
                text(
                    f"SELECT case_id, citation_text FROM case_citation_equivalents "
                    f"WHERE case_id IN ({placeholders})"
                ),
                params,
            )
            equiv_rows = equiv_result.mappings().all()
            for er in equiv_rows:
                equiv_map.setdefault(str(er["case_id"]), []).append(er["citation_text"])
        except Exception:
            pass  # Table may not exist in all environments

        for cid in case_ids:
            row = rows.get(cid)
            if row is None:
                continue

            # Check snippet and chunk text for overruling language
            snippet = snippets_map.get(cid)
            chunk = (vector_chunk_map or {}).get(cid)
            treatment_warning: str | None = None
            check_text = (snippet or "") + " " + (chunk or "")
            if check_text.strip() and has_overruling_language(check_text):
                treatment_warning = (
                    "This case may have been overruled or declared per incuriam. "
                    "Verify current status before relying on it."
                )

            pos = (char_pos_map or {}).get(cid, (0, 0))
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
                    snippet=snippet,
                    chunk_text=chunk,
                    bench_type=row.get("bench_type"),
                    equivalent_citations=equiv_map.get(cid, []),
                    treatment_warning=treatment_warning,
                    char_start=pos[0],
                    char_end=pos[1],
                )
            )

    # Build results for statute IDs from Pinecone metadata (no PostgreSQL row)
    for sid in statute_ids:
        chunk = (vector_chunk_map or {}).get(sid, "")
        # Parse human-readable title from ID like "statute:CrPC:438"
        parts = sid.replace("statute:", "", 1).split(":")
        title = f"{parts[0]} Section {parts[1]}" if len(parts) >= 2 else sid
        enriched.append(
            SearchResultItem(
                case_id=sid,
                score=scores.get(sid, 0.0),
                title=title,
                snippet=chunk[:500] if chunk else None,
                chunk_text=chunk or None,
                case_type="statute",
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

    # Filter out Pinecone statute IDs (e.g. "statute:CrPC:438")
    case_ids = [cid for cid in case_ids if ":" not in cid]
    if not case_ids:
        return {}

    placeholders = ", ".join(f":id_{i}" for i in range(len(case_ids)))
    params = {f"id_{i}": cid for i, cid in enumerate(case_ids)}

    sql = text(
        f"SELECT court, case_type, year, bench_type " f"FROM cases WHERE id IN ({placeholders})"
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
# Outcome bias detection
# ---------------------------------------------------------------------------

_OUTCOME_BIAS_KEYWORDS = re.compile(r"\b(bail|sentence|sentencing)\b", re.IGNORECASE)


async def _check_outcome_bias(
    query: str,
    case_ids: list[str],
    db: AsyncSession,
) -> str | None:
    """Detect if all top results share the same disposal_nature for bail/sentence queries.

    Returns a warning string if bias is detected, ``None`` otherwise.
    This is a lightweight informational check — results are never filtered.
    """
    if not _OUTCOME_BIAS_KEYWORDS.search(query):
        return None

    if len(case_ids) < 2:
        return None

    # Check top 10 results at most, filtering out non-case IDs
    check_ids = [cid for cid in case_ids[:10] if ":" not in cid]
    if len(check_ids) < 2:
        return None
    placeholders = ", ".join(f":bias_id_{i}" for i in range(len(check_ids)))
    params = {f"bias_id_{i}": cid for i, cid in enumerate(check_ids)}

    result = await db.execute(
        text(
            f"SELECT disposal_nature FROM cases "
            f"WHERE id IN ({placeholders}) AND disposal_nature IS NOT NULL"
        ),
        params,
    )
    rows = result.mappings().all()
    natures = {row["disposal_nature"] for row in rows}

    if len(natures) == 1 and len(rows) >= 2:
        nature = natures.pop()
        logger.warning(
            "Outcome bias detected: all %d top results have disposal_nature='%s' " "for query: %s",
            len(rows),
            nature,
            query,
        )
        return (
            f"All top results have the same outcome ({nature}). "
            f"Consider broadening your search to see cases with different outcomes."
        )

    return None


# ---------------------------------------------------------------------------
# Redis caching
# ---------------------------------------------------------------------------


async def invalidate_search_cache(redis_client) -> int:
    """Delete all search-related cache keys (search results, facets, suggestions).

    Uses SCAN to avoid blocking Redis on large key spaces. Call this after
    bulk ingestion to prevent serving stale results.

    Returns the number of keys deleted.
    """
    if redis_client is None:
        return 0

    deleted = 0
    # Patterns covering search result cache, facets, and suggestions
    patterns = ["search:*", "suggest:*"]

    try:
        for pattern in patterns:
            cursor = "0"
            while True:
                cursor, keys = await redis_client.scan(cursor=cursor, match=pattern, count=200)
                if keys:
                    await redis_client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0 or cursor == "0" or cursor == b"0":
                    break
        logger.info("Invalidated %d search cache keys", deleted)
    except (ConnectionError, TimeoutError, Exception) as exc:
        logger.warning("Failed to invalidate search cache: %s", exc)

    return deleted


def _make_cache_key(
    query: str,
    filters: SearchFilters | None,
    page: int,
    page_size: int,
    language: str = "en",
) -> str:
    """Build a deterministic cache key from search parameters."""
    raw = json.dumps(
        {
            "q": query.lower().strip(),
            "f": asdict(filters) if filters else None,
            "p": page,
            "ps": page_size,
            "lang": language,
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
        "outcome_bias_warning": response.outcome_bias_warning,
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
        outcome_bias_warning=data.get("outcome_bias_warning"),
    )
