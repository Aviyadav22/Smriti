"""Research Agent V2 — Worker node functions for LangGraph Send() fan-out.

Each worker handles a specific research task type (case_law, named_case, etc.).
Workers follow a search → enrich → return pattern. They do NOT generate CoT
reasoning individually — that's handled by batch_worker_cot_node [S4] which
runs a single Flash call after all workers finish.

Workers use pre-warmed embeddings [S6] when available.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.nodes.common import (
    _search_by_title,
    enrich_results_with_ratio,
    parallel_hybrid_search,
)
from app.core.agents.research_cache import (
    get_cached_community,
    get_cached_ik_fragment,
    get_cached_ik_search,
    set_cached_community,
    set_cached_ik_fragment,
    set_cached_ik_search,
)
from app.core.agents.state import WorkerResult
from app.core.interfaces import (
    EmbeddingProvider,
    ExternalDocProvider,
    GraphStore,
    LLMProvider,
    Reranker,
    VectorStore,
    WebSearchProvider,
)
from app.core.search.hybrid import _exact_citation_search
from app.core.search.query import expand_statute_references
from app.db.postgres import async_session_factory
from app.db.redis_client import get_redis

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
    task_filters = task.get("filters", {})

    # Use BOTH nl_query (vector-heavy) and boolean_query (keyword-heavy)
    nl_query = task["nl_query"]

    # [V3] Element context enrichment — prepend element description to query
    element_context = task_filters.get("element_context", "")
    if element_context:
        nl_query = f"{element_context}. {nl_query}"

    queries = [nl_query]
    if task.get("boolean_query"):
        # [M2] Convert IK boolean operators to PostgreSQL websearch_to_tsquery format
        fts_query = task["boolean_query"]
        fts_query = re.sub(r'\bANDD\b', 'AND', fts_query)
        fts_query = re.sub(r'\bORR\b', 'OR', fts_query)
        fts_query = re.sub(r'\bNOTT\b', 'NOT', fts_query)
        fts_query = re.sub(r'\bNEAR\b', 'AND', fts_query)  # NEAR → AND (closest FTS equivalent)
        queries.append(fts_query)

    # [B8] Skip understand_query — agent has already rewritten the query
    search_kwargs: dict = {"pre_understood": True}
    # [V3] Bench-strength filtering
    target_bench = task_filters.get("target_bench")
    if target_bench:
        bench_map = {
            "constitutional": "constitutional",
            "full": "full",
            "division": "division",
            "single": "single",
        }
        bench_value = bench_map.get(target_bench)
        if bench_value:
            from app.core.search.query import SearchFilters
            search_kwargs["filters"] = SearchFilters(bench_type=bench_value)

    # [H10] Propagate court and date range filters from research plan
    court_filter = task_filters.get("court")
    from_year = task_filters.get("from_year")
    to_year = task_filters.get("to_year")
    if court_filter or from_year or to_year:
        from app.core.search.query import SearchFilters
        existing = search_kwargs.get("filters")
        if not existing:
            existing = SearchFilters()
            search_kwargs["filters"] = existing
        if court_filter:
            existing.court = [court_filter] if isinstance(court_filter, str) else court_filter
        if from_year:
            existing.year_from = int(from_year)
        if to_year:
            existing.year_to = int(to_year)

    # [B13] Pass precomputed embeddings to skip redundant embed_text() calls
    precomputed = state.get("precomputed_embeddings") or {}

    try:
        async with async_session_factory() as db:
            results = await parallel_hybrid_search(
                queries, llm, embedder, vector_store, reranker, db,
                precomputed_embeddings=precomputed,
                **search_kwargs,
            )
            results = await enrich_results_with_ratio(results, db, max_ratio_len=3000)
    except Exception as exc:
        logger.exception("case_law_worker failed: %s", exc)
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
        logger.exception("named_case_worker failed: %s", exc)
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
                    pre_understood=True,
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


# ---------------------------------------------------------------------------
# Worker: statute_worker — PG lookup + Pinecone semantic + code mapping [T3]
# ---------------------------------------------------------------------------


async def statute_worker(
    state: dict,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
) -> dict:
    """Look up statutes from PostgreSQL + Pinecone semantic search.

    Uses [T3] code mapping to auto-search both old and new codes
    (e.g., IPC 302 → also searches BNS 103).
    """
    task = state["task"]
    results: list[dict] = []

    try:
        # [T3] Expand statute references to include old↔new equivalents
        original_query = task["nl_query"]
        _, expanded_terms = expand_statute_references(original_query)

        # All queries to search (original + expanded old/new code refs)
        all_queries = [original_query] + expanded_terms

        async with async_session_factory() as db:
            from app.models.statute import Statute

            for query_text in all_queries:
                # Try exact section lookup via PG FTS
                stmt = (
                    select(Statute)
                    .where(
                        Statute.searchable_text.op("@@")(
                            func_websearch_to_tsquery(query_text)
                        )
                    )
                    .limit(10)
                )
                try:
                    db_result = await db.execute(stmt)
                    for s in db_result.scalars().all():
                        results.append({
                            "case_id": f"statute:{s.id}",
                            "title": f"{s.act_short_name} Section {s.section_number}",
                            "section_title": s.section_title or "",
                            "section_text": s.section_text[:2000],
                            "act_name": s.act_name,
                            "act_short_name": s.act_short_name,
                            "section_number": s.section_number,
                            "document_type": s.document_type,
                            "is_repealed": s.is_repealed,
                            "replaced_by": s.replaced_by,
                            "source": "statute_db",
                        })
                except Exception:
                    pass  # FTS may fail on some queries, fall through to semantic

        # Semantic search in Pinecone for statute chunks
        query_embedding = await embedder.embed_text(original_query)
        pinecone_results = await vector_store.search(
            query_vector=query_embedding,
            top_k=5,
            filters={"document_type": {"$in": ["statute", "constitution"]}},
        )
        for r in pinecone_results:
            meta = r.metadata if hasattr(r, "metadata") else {}
            results.append({
                "case_id": f"statute:{r.id}",
                "title": meta.get("title", ""),
                "section_text": meta.get("text", "")[:2000],
                "act_name": meta.get("act_name", ""),
                "section_number": meta.get("section_number", ""),
                "document_type": meta.get("document_type", "statute"),
                "source": "statute_pinecone",
                "score": r.score,
            })

        # Deduplicate by title
        seen_titles: set[str] = set()
        deduped: list[dict] = []
        for r in results:
            key = r.get("title", "")
            if key not in seen_titles:
                seen_titles.add(key)
                deduped.append(r)
        results = deduped

    except Exception as exc:
        logger.warning("statute_worker failed: %s", exc)
        return {"worker_results": [WorkerResult(
            task_id=task["task_id"], task_type="statute",
            query=task["nl_query"], results=[],
            source_urls=[], metadata={}, error=str(exc),
            reasoning="",
        )]}

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="statute",
        query=task["nl_query"], results=results,
        source_urls=[],
        metadata={"expanded_terms": expanded_terms if expanded_terms else []},
        error=None, reasoning="",
    )]}


def func_websearch_to_tsquery(query: str):
    """Create a websearch_to_tsquery SQL function call."""
    from sqlalchemy import func, text
    return func.websearch_to_tsquery("english", query)


# ---------------------------------------------------------------------------
# Worker: ik_search_worker — Indian Kanoon API search
# ---------------------------------------------------------------------------


_MAX_IK_FRAGMENT_CALLS = 5  # Cost control: Rs 0.05/fragment
_MIN_HEADLINE_LEN = 50  # Use search headline if >= this many chars (free)
_IK_ALWAYS_FRAGMENT_TOP_N = 3  # Always fetch fragment for top N (richer evidence)
_IK_MAX_PAGES = 2  # Fetch 2 pages (20 results) to avoid missing good cases


def _strip_html_tags(text: str) -> str:
    """Strip HTML tags from IK API responses (headlines contain <b>, <em>, etc.)."""
    import re
    if not text:
        return text
    return re.sub(r"<[^>]+>", "", text).strip()


async def ik_search_worker(
    state: dict,
    ik_client: ExternalDocProvider,
) -> dict:
    """Search Indian Kanoon API with full filter propagation.

    Uses /search/ for discovery + /docfragment/ for targeted passage extraction.
    Propagates filters (court, dates, boolean_query) from the research plan.
    Limits fragment calls to top N results for cost control.
    """
    task = state["task"]
    filters = task.get("filters", {})

    # [S8-L3] Best-effort Redis cache — failures fall through
    try:
        redis = await get_redis()
    except Exception:
        redis = None

    # Build IK-specific search params from research plan filters
    court_filter = filters.get("court")
    from_year = filters.get("from_year")
    to_year = filters.get("to_year")
    # IK uses DD-MM-YYYY format
    from_date = f"01-01-{from_year}" if from_year else None
    to_date = f"31-12-{to_year}" if to_year else None
    boolean_query = task.get("boolean_query") or None
    sort_by = filters.get("sort_by")  # "mostrecent" for recency queries
    title_filter = filters.get("title")
    author_filter = filters.get("author")
    bench_filter = filters.get("bench")

    # Build cache key that includes ALL search parameters (not just nl_query)
    cache_filters = {
        k: v for k, v in {
            "court": court_filter, "from_date": from_date, "to_date": to_date,
            "boolean_query": boolean_query, "sort_by": sort_by,
            "title": title_filter, "author": author_filter, "bench": bench_filter,
        }.items() if v is not None
    }

    try:
        # [S8-L3] Check IK search cache (with filter-aware key)
        cached_results = await get_cached_ik_search(
            redis, task["nl_query"], **cache_filters,
        )
        if cached_results is not None:
            logger.debug("IK search cache hit for: %s", task["nl_query"][:60])
            return {"worker_results": [WorkerResult(
                task_id=task["task_id"], task_type="ik_search",
                query=task["nl_query"], results=cached_results,
                source_urls=[f"https://indiankanoon.org/doc/{r.get('ik_doc_id', '')}/" for r in cached_results],
                metadata={"source": "indian_kanoon", "cached": True},
                error=None, reasoning="",
            )]}

        logger.info(
            "IK search: nl_query=%s, boolean_query=%s, court=%s, dates=%s-%s",
            task["nl_query"][:80], boolean_query[:80] if boolean_query else None,
            court_filter, from_date, to_date,
        )

        search_results = await ik_client.search(
            task["nl_query"],
            max_results=10,
            boolean_query=boolean_query,
            court_filter=court_filter,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
            title_filter=title_filter,
            author_filter=author_filter,
            bench_filter=bench_filter,
            max_cites=5,  # Get citation list for free
            max_pages=_IK_MAX_PAGES,  # Fetch 2 pages for broader coverage
        )

        # Fallback 1: if boolean_query returned 0 results, retry with NL query
        if not search_results and boolean_query:
            logger.info(
                "IK boolean query returned 0 results, retrying with NL query: %s",
                task["nl_query"][:80],
            )
            search_results = await ik_client.search(
                task["nl_query"],
                max_results=10,
                court_filter=court_filter,
                from_date=from_date,
                to_date=to_date,
                sort_by=sort_by,
                title_filter=title_filter,
                author_filter=author_filter,
                bench_filter=bench_filter,
                max_cites=5,
                max_pages=_IK_MAX_PAGES,
            )

        # Fallback 2: if court filter is too restrictive, broaden it
        if not search_results and court_filter:
            logger.info(
                "IK court-filtered query returned 0 results, retrying without court filter",
            )
            search_results = await ik_client.search(
                task["nl_query"],
                max_results=10,
                from_date=from_date,
                to_date=to_date,
                sort_by=sort_by,
                max_cites=5,
                max_pages=_IK_MAX_PAGES,
            )

        results: list[dict] = []
        source_urls: list[str] = []
        for idx, doc in enumerate(search_results):
            doc_id = str(doc.get("tid", ""))
            if not doc_id:
                continue

            # Use search headline or fetch fragment for richer evidence.
            # Always fetch fragment for top N results (even if headline is long)
            # because fragment is query-specific and provides better context.
            search_headline = _strip_html_tags(doc.get("headline", ""))
            snippet = ""
            if idx < _IK_ALWAYS_FRAGMENT_TOP_N:
                # Always fetch fragment for top results — richer, query-specific
                try:
                    cached_frag = await get_cached_ik_fragment(redis, doc_id, task["nl_query"])
                    if cached_frag is not None:
                        fragment = cached_frag
                    else:
                        fragment = await ik_client.get_fragment(doc_id, task["nl_query"])
                        await set_cached_ik_fragment(redis, doc_id, task["nl_query"], fragment)
                    frag_headline = fragment.get("headline", fragment.get("fragment", ""))
                    if isinstance(frag_headline, list):
                        snippet = _strip_html_tags(" ".join(frag_headline))
                    else:
                        snippet = _strip_html_tags(frag_headline)
                except Exception:
                    snippet = search_headline  # fallback to search headline
            elif len(search_headline) >= _MIN_HEADLINE_LEN:
                # Free: headline already in search results, long enough
                snippet = search_headline
            elif idx < _MAX_IK_FRAGMENT_CALLS:
                # Paid: Rs 0.05/call — only for short/missing headlines
                try:
                    cached_frag = await get_cached_ik_fragment(redis, doc_id, task["nl_query"])
                    if cached_frag is not None:
                        fragment = cached_frag
                    else:
                        fragment = await ik_client.get_fragment(doc_id, task["nl_query"])
                        await set_cached_ik_fragment(redis, doc_id, task["nl_query"], fragment)
                    frag_headline = fragment.get("headline", fragment.get("fragment", ""))
                    if isinstance(frag_headline, list):
                        snippet = _strip_html_tags(" ".join(frag_headline))
                    else:
                        snippet = _strip_html_tags(frag_headline)
                except Exception:
                    snippet = search_headline  # fallback to short headline
            else:
                snippet = search_headline  # beyond fragment limit, use whatever we have

            # Build citation — IK API often returns empty citation field,
            # so synthesize one from title + court + date for footnote matching
            ik_citation = doc.get("citation", "")
            if not ik_citation:
                title = doc.get("title", "")
                court = doc.get("docsource", doc.get("court", ""))
                date = doc.get("publishdate", "")
                # Format: "Title (Court, Date)" or just "Title"
                if court and date:
                    ik_citation = f"{title} ({court}, {date})"
                elif court:
                    ik_citation = f"{title} ({court})"
                else:
                    ik_citation = title

            results.append({
                "case_id": f"ik:{doc_id}",
                "title": doc.get("title", ""),
                "citation": ik_citation,
                "court": doc.get("docsource", doc.get("court", "")),
                "author": doc.get("author", ""),
                "date": doc.get("publishdate", ""),
                "year": doc.get("year"),
                "num_cites": doc.get("numcites", 0),
                "num_cited_by": doc.get("numcitedby", 0),
                "snippet": snippet,
                "score": max(0.3, 1.0 - (idx * 0.05)),  # [H8] Position-based score
                "source": "indian_kanoon",
                "ik_doc_id": doc_id,
                "court_copy_url": f"https://indiankanoon.org/origdoc/{doc_id}/",
            })
            source_urls.append(f"https://indiankanoon.org/doc/{doc_id}/")

        # [S8-L3] Cache IK search results (with filter-aware key)
        await set_cached_ik_search(redis, task["nl_query"], results, **cache_filters)

    except Exception as exc:
        logger.warning("ik_search_worker failed: %s", exc)
        return {"worker_results": [WorkerResult(
            task_id=task["task_id"], task_type="ik_search",
            query=task["nl_query"], results=[],
            source_urls=[], metadata={"source": "indian_kanoon"},
            error=str(exc), reasoning="",
        )]}

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="ik_search",
        query=task["nl_query"], results=results,
        source_urls=source_urls,
        metadata={"source": "indian_kanoon", "filters_applied": bool(filters)},
        error=None, reasoning="",
    )]}


# ---------------------------------------------------------------------------
# Worker: web_search_worker — Tavily web search for recent developments
# ---------------------------------------------------------------------------


async def web_search_worker(
    state: dict,
    web_search: WebSearchProvider,
) -> dict:
    """Search the web for recent legal developments via Tavily.

    Propagates filters (recency, domains) from the research plan.
    Always sets country=IN and requests raw markdown content.
    Non-blocking — failure returns empty results rather than erroring the pipeline.
    """
    task = state["task"]
    filters = task.get("filters", {})

    # Map task filters to Tavily params
    time_range = filters.get("recency")  # day|week|month|year
    include_domains = filters.get("domains")  # Override default domains if specified

    try:
        search_results = await web_search.search(
            task["nl_query"],
            max_results=5,
            search_depth="advanced",
            include_domains=include_domains,
            time_range=time_range,
            country="IN",
            include_raw_content=True,
        )

        results: list[dict] = []
        source_urls: list[str] = []
        for r in search_results:
            url = r.get("url", "")
            results.append({
                "case_id": f"web:{hash(url) & 0xFFFFFFFF}",  # [H29] Unique ID for dedup
                "title": r.get("title", ""),
                "snippet": r.get("raw_content", r.get("content", ""))[:2000],
                "url": url,
                "score": r.get("score", 0.0),
                "source": "web",
            })
            if r.get("url"):
                source_urls.append(r["url"])

    except Exception as exc:
        logger.warning("web_search_worker failed (non-blocking): %s", exc)
        return {"worker_results": [WorkerResult(
            task_id=task["task_id"], task_type="web",
            query=task["nl_query"], results=[],
            source_urls=[], metadata={"source": "web"},
            error=str(exc), reasoning="",
        )]}

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="web",
        query=task["nl_query"], results=results,
        source_urls=source_urls,
        metadata={"source": "web", "country": "IN"},
        error=None, reasoning="",
    )]}


# ---------------------------------------------------------------------------
# Worker: graph_worker — Neo4j citation graph traversal
# ---------------------------------------------------------------------------


async def graph_worker(
    state: dict,
    graph_store: GraphStore,
) -> dict:
    """Traverse the Neo4j citation graph for citing/cited-by/related cases.

    Also traverses APPLIES edges for statute→case queries.
    """
    task = state["task"]

    try:
        # Search for cases related to the query via citation graph
        # First, try to find seed cases from the query entities
        query = task["nl_query"]

        # [B11] 2-hop bidirectional query: seeds → cited → cited-by
        # Traverses CITES, OVERRULES, and APPLIES edges for richer graph results
        graph_results = await graph_store.query(
            """
            CALL db.index.fulltext.queryNodes('case_search', $query)
            YIELD node, score
            WITH node AS seed, score
            WHERE score > 0.5
            ORDER BY score DESC
            LIMIT 5
            // Hop 1: seed cites/overrules → target
            OPTIONAL MATCH (seed)-[r1:CITES|OVERRULES|APPLIES]->(hop1:Case)
            // Hop 2: target cites → hop2
            OPTIONAL MATCH (hop1)-[r2:CITES|OVERRULES]->(hop2:Case)
            WHERE hop2 <> seed
            // Also get cited_by count for authority ranking
            WITH seed, score, hop1, r1, hop2
            OPTIONAL MATCH (hop1)<-[:CITES]-(citer:Case)
            WITH seed, score, hop1, r1, hop2,
                 count(DISTINCT citer) AS cited_by_count
            RETURN seed.id AS seed_id, seed.title AS seed_title,
                   seed.citation AS seed_citation, score AS seed_score,
                   hop1.id AS hop1_id, hop1.title AS hop1_title,
                   hop1.citation AS hop1_citation,
                   type(r1) AS rel_type, r1.treatment AS treatment,
                   cited_by_count,
                   hop2.id AS hop2_id, hop2.title AS hop2_title,
                   hop2.citation AS hop2_citation
            ORDER BY seed_score DESC, cited_by_count DESC
            LIMIT 40
            """,
            params={"query": query},
        )

        results: list[dict] = []
        seen_ids: set[str] = set()
        for r in graph_results:
            # Add seed case
            case_id = r.get("seed_id", "")
            if case_id and case_id not in seen_ids:
                seen_ids.add(case_id)
                results.append({
                    "case_id": case_id,
                    "title": r.get("seed_title", ""),
                    "citation": r.get("seed_citation", ""),
                    "source": "citation_graph",
                    "graph_score": r.get("seed_score", 0.0),
                })
            # Add hop-1 case
            hop1_id = r.get("hop1_id", "")
            if hop1_id and hop1_id not in seen_ids:
                seen_ids.add(hop1_id)
                results.append({
                    "case_id": hop1_id,
                    "title": r.get("hop1_title", ""),
                    "citation": r.get("hop1_citation", ""),
                    "treatment": r.get("treatment"),
                    "rel_type": r.get("rel_type"),
                    "cited_by_count": r.get("cited_by_count", 0),
                    "source": "citation_graph",
                })
            # Add hop-2 case (if exists)
            hop2_id = r.get("hop2_id", "")
            if hop2_id and hop2_id not in seen_ids:
                seen_ids.add(hop2_id)
                results.append({
                    "case_id": hop2_id,
                    "title": r.get("hop2_title", ""),
                    "citation": r.get("hop2_citation", ""),
                    "source": "citation_graph_hop2",
                })

        # [E1] Also query doctrine nodes if the query mentions a doctrine
        try:
            doctrine_results = await graph_store.query(
                """
                CALL db.index.fulltext.queryNodes('case_search', $query)
                YIELD node, score
                WITH node AS seed, score
                WHERE score > 0.5 AND 'Doctrine' IN labels(seed)
                LIMIT 3
                OPTIONAL MATCH (case:Case)-[:APPLIES_DOCTRINE]->(seed)
                RETURN seed.name AS doctrine_name, seed.description AS doctrine_desc,
                       case.id AS case_id, case.title AS case_title,
                       case.citation AS case_citation
                LIMIT 10
                """,
                params={"query": query},
            )
            for dr in doctrine_results:
                cid = dr.get("case_id", "")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    results.append({
                        "case_id": cid,
                        "title": dr.get("case_title", ""),
                        "citation": dr.get("case_citation", ""),
                        "doctrine": dr.get("doctrine_name", ""),
                        "source": "doctrine_graph",
                    })
        except Exception:
            pass  # Best-effort — doctrine search is supplementary

        # Cap at 20 results, sorted by cited_by_count for authority
        results.sort(key=lambda x: x.get("cited_by_count", 0), reverse=True)
        results = results[:20]

        # [M24] Enrich graph results with ratio from PostgreSQL
        if results:
            try:
                async with async_session_factory() as db:
                    results = await enrich_results_with_ratio(results, db, max_ratio_len=3000)
            except Exception:
                logger.warning("Graph result DB enrichment failed", exc_info=True)

    except Exception as exc:
        logger.exception("graph_worker failed: %s", exc)
        return {"worker_results": [WorkerResult(
            task_id=task["task_id"], task_type="graph",
            query=task["nl_query"], results=[],
            source_urls=[], metadata={"source": "citation_graph"},
            error=str(exc), reasoning="",
        )]}

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="graph",
        query=task["nl_query"], results=results,
        source_urls=[], metadata={"source": "citation_graph"},
        error=None, reasoning="",
    )]}


# ---------------------------------------------------------------------------
# Worker: graph_community_worker — GraphRAG community retrieval
# ---------------------------------------------------------------------------


def _detect_communities(G: nx.Graph, resolution: float = 1.0) -> dict[str, int]:
    """Run community detection on a graph. Returns {node_id: community_id}.

    Uses NetworkX's built-in Louvain algorithm (modularity-based, similar
    to Leiden). Falls back to graspologic's hierarchical_leiden if available.
    """
    if len(G.nodes) == 0:
        return {}

    try:
        # NetworkX Louvain is always available (no extra deps)
        partition_sets = nx.community.louvain_communities(
            G, resolution=resolution, seed=42,
        )
        communities: dict[str, int] = {}
        for idx, community_set in enumerate(partition_sets):
            for node in community_set:
                communities[str(node)] = idx
        return communities
    except Exception as exc:
        logger.warning("Louvain community detection failed: %s — falling back", exc)
        communities = {}
        for idx, component in enumerate(nx.connected_components(G)):
            for node in component:
                communities[str(node)] = idx
        return communities


async def graph_community_worker(
    state: dict,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    graph_store: GraphStore,
) -> dict:
    """Retrieve relevant citation communities for the research question.

    Two retrieval strategies:
    1. Semantic: Embed the query, search Pinecone for document_type="community"
    2. Graph: If other workers already found cases, look up their communities via BELONGS_TO

    Returns CommunitySummary objects that give the synthesis node macro-level context.
    """
    task = state["task"]
    parent = state.get("parent_state", {})

    community_results: list[dict] = []
    # [S8-L5] Best-effort Redis cache
    try:
        redis = await get_redis()
    except Exception:
        redis = None

    try:
        # Strategy 1: Semantic search for relevant communities
        query_embedding = await embedder.embed_text(task["nl_query"])
        pinecone_results = await vector_store.search(
            query_vector=query_embedding,
            top_k=5,
            filters={"document_type": "community"},
        )
        for r in pinecone_results:
            meta = r.metadata if hasattr(r, "metadata") else {}
            comm_id = meta.get("community_id")
            # [S8-L5] Check community cache
            if comm_id:
                cached_comm = await get_cached_community(redis, str(comm_id))
                if cached_comm is not None:
                    cached_comm["retrieval_method"] = "semantic"
                    cached_comm["score"] = r.score
                    community_results.append(cached_comm)
                    continue
            comm_data = {
                "community_id": comm_id,
                "title": meta.get("title"),
                "summary": meta.get("text", ""),
                "legal_principles": (meta.get("legal_principles", "") or "").split("; "),
                "size": meta.get("size", 0),
                "retrieval_method": "semantic",
                "score": r.score,
            }
            community_results.append(comm_data)
            # [S8-L5] Cache community summary
            if comm_id:
                await set_cached_community(redis, str(comm_id), comm_data)

        # Strategy 2: Graph lookup from already-found case IDs
        existing_case_ids: list[str] = []
        for wr in parent.get("worker_results", []):
            for r in wr.get("results", []):
                if cid := r.get("case_id"):
                    if not str(cid).startswith("ik:"):  # Only internal cases
                        existing_case_ids.append(str(cid))

        if existing_case_ids:
            graph_communities = await graph_store.query(
                """
                MATCH (case:Case)-[:BELONGS_TO]->(comm:Community)
                WHERE case.id IN $case_ids
                RETURN DISTINCT comm.id AS id, comm.title AS title,
                       comm.summary AS summary, comm.legal_principles AS principles,
                       comm.size AS size, count(case) AS overlap
                ORDER BY overlap DESC
                LIMIT 3
                """,
                params={"case_ids": existing_case_ids[:20]},
            )

            for gc in graph_communities:
                # Avoid duplicates from semantic search
                if not any(cr["community_id"] == gc["id"] for cr in community_results):
                    # [S8-L5] Check community cache
                    cached_gc = await get_cached_community(redis, str(gc["id"])) if gc.get("id") else None
                    if cached_gc is not None:
                        cached_gc["retrieval_method"] = "graph_overlap"
                        cached_gc["overlap_count"] = gc["overlap"]
                        community_results.append(cached_gc)
                    else:
                        comm_data = {
                            "community_id": gc["id"],
                            "title": gc["title"],
                            "summary": gc["summary"],
                            "legal_principles": gc["principles"] or [],
                            "size": gc["size"],
                            "retrieval_method": "graph_overlap",
                            "overlap_count": gc["overlap"],
                        }
                        community_results.append(comm_data)
                        if gc.get("id"):
                            await set_cached_community(redis, str(gc["id"]), comm_data)

    except Exception as exc:
        logger.warning("graph_community_worker failed: %s", exc)
        return {"worker_results": [WorkerResult(
            task_id=task["task_id"], task_type="graph_community",
            query=task["nl_query"], results=[],
            source_urls=[], metadata={"source": "graph_community"},
            error=str(exc), reasoning="",
        )]}

    # [MA-RAG] Generate CoT reasoning about communities found
    reasoning = f"Found {len(community_results)} relevant citation communities. "
    if community_results:
        reasoning += (
            f"Top community: '{community_results[0]['title']}' "
            f"({community_results[0].get('size', 0)} cases). "
            "These provide macro-level legal context for synthesis."
        )
    else:
        reasoning += "No pre-computed communities matched — synthesis will rely on individual case analysis."

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="graph_community",
        query=task["nl_query"], results=community_results,
        source_urls=[], metadata={"source": "graph_community"},
        error=None, reasoning=reasoning,
    )]}
