"""Research Agent node functions for LangGraph.

Each node function takes the ResearchState as its first argument plus
injected dependencies, performs a single focused operation, and returns
a partial state dict for LangGraph to merge.  Dependencies (llm, db, etc.)
are passed via closures when the graph is built.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import Counter
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.confidence import calculate_confidence
from app.core.agents.nodes.common import (
    enrich_results_with_ratio,
    format_search_results_for_llm,
    verify_case_ids,
)
from app.core.agents.state import ResearchState
from app.core.interfaces import EmbeddingProvider, LLMProvider, Reranker, VectorStore
from app.core.legal.prompts import (
    RESEARCH_CLASSIFY_SCHEMA,
    RESEARCH_CLASSIFY_SYSTEM,
    RESEARCH_CONTRADICTIONS_SYSTEM,
    RESEARCH_DECOMPOSE_SCHEMA,
    RESEARCH_DECOMPOSE_SYSTEM,
    RESEARCH_DECOMPOSE_USER,
    RESEARCH_SYNTHESIZE_SYSTEM,
    RESEARCH_SYNTHESIZE_USER,
)
from app.core.search.hybrid import SearchResultItem, hybrid_search

logger = logging.getLogger(__name__)

# UUID v4 regex for citation verification
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Node 1: classify_query_node
# ---------------------------------------------------------------------------


async def classify_query_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """Classify the research query by topic, complexity, and entities.

    Stores the classification in messages so downstream nodes can read it.
    """
    query = state["query"]
    classification = await llm.generate_structured(
        prompt=query,
        system=RESEARCH_CLASSIFY_SYSTEM,
        output_schema=RESEARCH_CLASSIFY_SCHEMA,
    )
    return {"messages": [{"type": "classification", "data": classification}]}


# ---------------------------------------------------------------------------
# Node 2: decompose_query_node
# ---------------------------------------------------------------------------


async def decompose_query_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """Decompose the research query into focused sub-queries."""
    query = state["query"]

    # Retrieve classification from messages (set by classify_query_node)
    classification: dict = {}
    for msg in state.get("messages", []):
        if isinstance(msg, dict) and msg.get("type") == "classification":
            classification = msg.get("data", {})

    classification_str = json.dumps(classification) if classification else "N/A"

    prompt = RESEARCH_DECOMPOSE_USER.format(
        query=query,
        classification=classification_str,
    )
    result = await llm.generate_structured(
        prompt=prompt,
        system=RESEARCH_DECOMPOSE_SYSTEM,
        output_schema=RESEARCH_DECOMPOSE_SCHEMA,
    )

    sub_queries = [sq["query"] for sq in result.get("sub_queries", [])]
    return {"sub_queries": sub_queries}


# ---------------------------------------------------------------------------
# Node 3: parallel_search_node
# ---------------------------------------------------------------------------


async def parallel_search_node(
    state: ResearchState,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    db: AsyncSession,
) -> dict:
    """Run hybrid_search for each sub-query in parallel and collect results."""
    sub_queries = state.get("sub_queries", [])
    if not sub_queries:
        return {"search_results": []}

    async def _search_one(sq: str) -> list[dict]:
        response = await hybrid_search(
            sq,
            llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            db=db,
        )
        results: list[dict] = []
        for item in response.results:
            d = asdict(item)
            d["source_query"] = sq
            results.append(d)
        return results

    all_lists = await asyncio.gather(
        *[_search_one(sq) for sq in sub_queries],
        return_exceptions=True,
    )

    combined: list[dict] = []
    for result_or_exc in all_lists:
        if isinstance(result_or_exc, BaseException):
            logger.warning("Sub-query search failed: %s", result_or_exc)
            continue
        combined.extend(result_or_exc)

    combined = await enrich_results_with_ratio(combined, db)

    return {"search_results": combined}


# ---------------------------------------------------------------------------
# Node 4: gather_results_node
# ---------------------------------------------------------------------------


async def gather_results_node(state: ResearchState) -> dict:
    """Deduplicate search results and identify cross-referenced cases.

    A case appearing in results from 2+ different sub-queries is
    considered a cross-reference.
    """
    results = state.get("search_results", [])

    # Deduplicate by case_id, keeping highest score
    best: dict[str, dict] = {}
    query_hits: dict[str, set[str]] = {}

    for r in results:
        cid = r.get("case_id", "")
        if not cid:
            continue

        source_query = r.get("source_query", "")
        query_hits.setdefault(cid, set()).add(source_query)

        existing = best.get(cid)
        if existing is None or r.get("score", 0) > existing.get("score", 0):
            best[cid] = r

    # Cross-references: cases found across 2+ sub-queries
    cross_refs: list[dict] = []
    for cid, queries in query_hits.items():
        if len(queries) >= 2:
            case_data = best[cid]
            cross_refs.append({
                "case_id": cid,
                "title": case_data.get("title"),
                "citation": case_data.get("citation"),
                "matched_queries": list(queries),
                "match_count": len(queries),
            })

    cross_refs.sort(key=lambda x: x["match_count"], reverse=True)

    return {"cross_references": cross_refs}


# ---------------------------------------------------------------------------
# Node 5: detect_contradictions_node
# ---------------------------------------------------------------------------


async def detect_contradictions_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """Detect contradictions among the gathered search results."""
    results = state.get("search_results", [])
    if not results:
        return {"contradictions": []}

    context = format_search_results_for_llm(results)

    prompt = (
        "Analyze the following Indian court judgment search results and identify "
        "any contradictions or conflicts between the holdings.\n\n"
        f"{context}\n\n"
        "Return your analysis as a JSON array of contradiction objects, each with:\n"
        '- "case_a": title/citation of the first case\n'
        '- "case_b": title/citation of the second case\n'
        '- "description": what the contradiction is\n'
        '- "resolution": which holding is currently binding and why\n'
        "If no contradictions exist, return an empty JSON array: []"
    )

    raw = await llm.generate(
        prompt=prompt,
        system=RESEARCH_CONTRADICTIONS_SYSTEM,
        temperature=0.1,
    )

    contradictions = _parse_json_list(raw)
    return {"contradictions": contradictions}


# ---------------------------------------------------------------------------
# Node 6: synthesize_memo_node
# ---------------------------------------------------------------------------


async def synthesize_memo_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """Synthesize all findings into a structured research memo."""
    query = state["query"]
    results = state.get("search_results", [])
    cross_refs = state.get("cross_references", [])
    contradictions = state.get("contradictions", [])

    findings = format_search_results_for_llm(results)

    cross_ref_text = ""
    if cross_refs:
        parts: list[str] = []
        for cr in cross_refs:
            parts.append(
                f"- {cr.get('title', 'Unknown')} ({cr.get('citation', 'N/A')}) "
                f"— matched {cr.get('match_count', 0)} sub-queries"
            )
        cross_ref_text = "\n".join(parts)
    else:
        cross_ref_text = "None identified."

    contradictions_text = json.dumps(contradictions, indent=2) if contradictions else "None identified."

    prompt = RESEARCH_SYNTHESIZE_USER.format(
        query=query,
        findings=findings,
        contradictions=contradictions_text,
    )

    memo = await llm.generate(
        prompt=prompt,
        system=RESEARCH_SYNTHESIZE_SYSTEM,
        temperature=0.2,
        max_tokens=8192,
    )

    # Collect reranker scores from results
    reranker_scores = sorted(
        [r.get("score", 0.0) for r in results if r.get("score")],
        reverse=True,
    )

    # Cross-reference ratio
    cross_ref_count = len(cross_refs)
    sub_query_count = len(state.get("sub_queries", []))
    cross_ref_ratio = cross_ref_count / max(sub_query_count, 1)

    # Precedent strengths (placeholder -- will be enriched later)
    precedent_strengths: list[str] = []

    confidence = calculate_confidence(
        reranker_scores=reranker_scores,
        cross_ref_ratio=cross_ref_ratio,
        precedent_strengths=precedent_strengths,
        contradiction_count=len(contradictions),
        total_results=len(results),
    )

    return {"draft_memo": memo, "confidence": confidence}


# ---------------------------------------------------------------------------
# Node 7: verify_citations_node
# ---------------------------------------------------------------------------


async def verify_citations_node(
    state: ResearchState,
    db: AsyncSession,
) -> dict:
    """Verify that case IDs referenced in the draft memo exist in the database.

    Appends a warning section to the memo if any IDs cannot be verified.
    """
    memo = state.get("draft_memo", "")
    if not memo:
        return {"draft_memo": memo}

    # Extract UUID-like patterns from the memo
    found_ids = list(set(_UUID_RE.findall(memo)))
    if not found_ids:
        return {"draft_memo": memo}

    valid_ids = await verify_case_ids(found_ids, db)
    invalid_ids = [uid for uid in found_ids if uid not in valid_ids]

    if invalid_ids:
        warning = (
            "\n\n---\n"
            "**Citation Verification Warning**\n"
            "The following case identifiers referenced in this memo could not "
            "be verified against the database:\n"
        )
        for uid in invalid_ids:
            warning += f"- {uid}\n"
        warning += (
            "These references may be hallucinated or refer to cases not yet "
            "ingested. Please verify independently.\n"
        )
        memo += warning

    return {"draft_memo": memo}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_json_list(raw: str) -> list[dict]:
    """Best-effort extraction of a JSON array from LLM output."""
    # Try direct parse
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    match = re.search(r"```(?:json)?\s*(\[.*?])\s*```", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try finding any JSON array in the text
    match = re.search(r"\[.*]", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    return []
