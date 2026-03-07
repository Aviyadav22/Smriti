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
from app.core.legal.treatment import has_overruling_language
from app.core.agents.nodes.citation_verifier import (
    check_grounding,
    extract_citations_from_text,
    verify_citations_against_db,
)
from app.core.legal.precedent_strength import classify_precedent_strength
from app.core.agents.nodes.common import (
    enrich_results_with_ratio,
    format_search_results_for_llm,
    safe_json_parse_list,
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
    Also extracts target_court and target_bench from the classification
    for accurate precedent strength labelling.
    """
    query = state["query"]
    classification = await llm.generate_structured(
        prompt=query,
        system=RESEARCH_CLASSIFY_SYSTEM,
        output_schema=RESEARCH_CLASSIFY_SCHEMA,
    )

    # Extract target court/bench from classification, falling back to defaults
    result: dict = {"messages": [{"type": "classification", "data": classification}]}

    target_court = classification.get("target_court")
    target_bench = classification.get("target_bench")

    if target_court:
        result["target_court"] = target_court
    if target_bench:
        result["target_bench"] = target_bench

    return result


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

    # Retrieve user feedback from HITL checkpoint (if user revised the plan)
    user_feedback = ""
    for msg in state.get("messages", []):
        if isinstance(msg, dict) and msg.get("type") == "user_feedback" and msg.get("step") == "plan":
            user_feedback = msg.get("content", "")

    classification_str = json.dumps(classification) if classification else "N/A"

    prompt = RESEARCH_DECOMPOSE_USER.format(
        query=query,
        classification=classification_str,
    )

    if user_feedback:
        prompt += (
            f"\n\nIMPORTANT — The user has reviewed the previous sub-queries and "
            f"requested the following adjustments:\n\"{user_feedback}\"\n"
            f"Incorporate this feedback into your sub-query decomposition."
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

    contradictions = safe_json_parse_list(raw)
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

    # Detect overruling language in search results
    treatment_warnings: list[str] = []
    overruled_case_ids: set[str] = set()
    for r in results:
        check_text = (r.get("snippet", "") or "") + " " + (r.get("ratio", "") or "") + " " + (r.get("chunk_text", "") or "")
        if check_text.strip() and has_overruling_language(check_text):
            title = r.get("title", "Unknown")
            citation = r.get("citation", "N/A")
            treatment_warnings.append(
                f"- {title} ({citation}): Contains language suggesting this case "
                f"may have been overruled or declared per incuriam."
            )
            cid = r.get("case_id", "")
            if cid:
                overruled_case_ids.add(cid)

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

    treatment_text = ""
    if treatment_warnings:
        treatment_text = (
            "\n\nTREATMENT WARNINGS — The following cases contain language "
            "suggesting they may have been overruled or declared per incuriam. "
            "Highlight these warnings prominently in the memo:\n"
            + "\n".join(treatment_warnings)
        )

    prompt = RESEARCH_SYNTHESIZE_USER.format(
        query=query,
        findings=findings,
        contradictions=contradictions_text,
    )

    if treatment_text:
        prompt += treatment_text

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

    # Classify precedent strength for each result with court and bench data.
    # Use the target court/bench from the state (extracted during query
    # classification) with sensible defaults if the user didn't specify.
    target_court = state.get("target_court") or "Supreme Court of India"
    target_bench = state.get("target_bench") or "division"

    precedent_strengths: list[str] = []
    for r in results:
        bench = r.get("bench_type")
        court = r.get("court", "")
        if bench and court:
            cid = r.get("case_id", "")
            is_overruled = cid in overruled_case_ids
            strength = classify_precedent_strength(
                source_court=court,
                source_bench=bench,
                target_court=target_court,
                target_bench=target_bench,
                overruled=is_overruled,
            )
            precedent_strengths.append(strength.value)

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
    """Verify that case IDs and human-readable citations in the draft memo exist.

    Performs three checks:
    1. UUID-based verification (existing) -- checks case IDs against the DB.
    2. Human-readable citation verification -- checks SCC/AIR/etc. citations
       against ``cases.citation`` and ``case_citation_equivalents.citation_text``.
    3. Grounding check -- flags citations that appear in the memo but were NOT
       in the search results (potentially hallucinated from LLM training data).

    Appends warning sections to the memo for any issues found.
    """
    memo = state.get("draft_memo", "")
    if not memo:
        return {"draft_memo": memo}

    # --- Step 1: UUID verification (existing logic) ---
    found_ids = list(set(_UUID_RE.findall(memo)))
    if found_ids:
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

    # --- Step 2: Human-readable citation verification ---
    memo_citations = extract_citations_from_text(memo)
    if memo_citations:
        _verified, unverified = await verify_citations_against_db(memo_citations, db)

        if unverified:
            warning = (
                "\n\n---\n"
                "**Human-Readable Citation Warning**\n"
                "The following citations could not be verified against the database:\n"
            )
            for cite in unverified:
                warning += f"- {cite}\n"
            warning += (
                "These may be fabricated citations. Please verify independently "
                "before relying on them.\n"
            )
            memo += warning

    # --- Step 3: Grounding check ---
    if memo_citations:
        # Collect citations from search results
        search_results = state.get("search_results", [])
        search_citation_strings: list[str] = []
        for result in search_results:
            citation = result.get("citation", "")
            if citation:
                search_citation_strings.append(citation)
            snippet = result.get("snippet", "")
            if snippet:
                search_citation_strings.extend(extract_citations_from_text(snippet))

        ungrounded = check_grounding(memo_citations, search_citation_strings)
        if ungrounded:
            warning = (
                "\n\n---\n"
                "**Ungrounded Citation Warning**\n"
                "The following citations appear in the memo but were NOT found "
                "in the search results. They may have been hallucinated from "
                "the LLM's training data:\n"
            )
            for cite in ungrounded:
                warning += f"- {cite}\n"
            warning += (
                "Exercise extra caution with these citations and verify them "
                "against primary sources.\n"
            )
            memo += warning

    return {"draft_memo": memo}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Keep a module-level alias so existing imports of _parse_json_list still work
# (e.g. in tests).  New code should use safe_json_parse_list from common.
_parse_json_list = safe_json_parse_list
