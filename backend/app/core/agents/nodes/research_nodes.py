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
import uuid
from collections.abc import Callable
from difflib import SequenceMatcher
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.confidence import calculate_confidence, calculate_confidence_detailed
from app.core.legal.precedent_strength import classify_precedent_strength
from app.core.agents.nodes.common import (
    MAX_RESULTS_FOR_LLM,
    deduplicate_with_diversity,
    enrich_results_with_ratio,
    format_community_summaries,
    format_extracted_passages,
    format_search_results_for_llm,
    format_search_results_for_llm_extended,
    parallel_hybrid_search,
    safe_json_parse_list,
    collect_grounding_citations,
    verify_memo_citations,
    detect_overruled_cases,
)
from app.core.agents.state import (
    EvidenceGap,
    ExtractedPassage,
    Footnote,
    LegalQualityResult,
    RelevanceScore,
    ResearchState,
    ResearchTask,
    StrategyAdjustment,
    SynthesisDraft,
    WorkerResult,
)
from app.core.interfaces import EmbeddingProvider, LLMProvider, Reranker, VectorStore
from app.core.legal.prompts import (
    BATCH_COT_WITH_REFLECTION_SCHEMA,
    EVALUATE_AND_EXTRACT_SCHEMA,
    LEGAL_DISCLAIMER,
    LEGAL_QUALITY_CHECK_SCHEMA,
    LEGAL_QUALITY_CHECK_SYSTEM,
    RESEARCH_CLASSIFY_SCHEMA,
    RESEARCH_CLASSIFY_SYSTEM,
    RESEARCH_CONTRADICTIONS_SYSTEM,
    RESEARCH_DECOMPOSE_SCHEMA,
    RESEARCH_DECOMPOSE_SYSTEM,
    RESEARCH_DECOMPOSE_USER,
    RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM,
    RESEARCH_FAST_PATH_SYNTHESIS_SYSTEM,
    RESEARCH_GAP_ANALYSIS_SCHEMA,
    RESEARCH_GAP_ANALYSIS_SYSTEM,
    RESEARCH_PLAN_SCHEMA,
    RESEARCH_PLAN_SYSTEM,
    RESEARCH_REWRITE_SYSTEM,
    RESEARCH_SYNTHESIZE_SYSTEM,
    RESEARCH_SYNTHESIZE_USER,
    RESEARCH_WORKER_COT_SYSTEM,
    SPECULATIVE_DRAFT_SYSTEM,
    SPECULATIVE_MERGE_SYSTEM,
    ADVERSARIAL_SEARCH_SYSTEM,
    ADVERSARIAL_SEARCH_SCHEMA,
)
from app.security.sanitizer import sanitize_search_query

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# [T1] Process Visualization helper — emits structured SSE events
# ---------------------------------------------------------------------------


def emit_status(event_type: str, data: dict) -> dict:
    """Create a process event dict for [T1] Research Process Visualization.

    Event types: plan, searching, found, evaluating, reflection, gap,
    drafting, memo_stream, verification, quality, memo.

    Returns a dict suitable for appending to process_events.
    """
    return {"type": event_type, "data": data}


# Patterns that indicate a degenerate/looping LLM refusal
_REFUSAL_PATTERNS = re.compile(
    r"(I am unable to provide|I cannot provide|I'm sorry.*unable|"
    r"I can provide a comprehensive|cannot fulfill|I am not able to)",
    re.IGNORECASE,
)


def _is_degenerate_output(text: str, min_useful_length: int = 200) -> bool:
    """Detect degenerate LLM output: refusal loops, extreme repetition, or too short.

    Returns True if the output appears broken and should be retried or replaced.
    """
    if not text or len(text.strip()) < min_useful_length:
        return True
    # Check for refusal pattern density — if >30% of sentences are refusals, it's broken
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    if not sentences:
        return True
    refusal_count = sum(1 for s in sentences if _REFUSAL_PATTERNS.search(s))
    if refusal_count > 3 and refusal_count / len(sentences) > 0.3:
        return True
    # Check for extreme repetition — same 50-char substring repeated 5+ times
    if len(text) > 500:
        sample = text[:2000]
        for window_size in (50, 100):
            chunk = sample[:window_size]
            if sample.count(chunk) >= 5:
                return True
    return False


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
    try:
        classification = await llm.generate_structured(
            prompt=query,
            system=RESEARCH_CLASSIFY_SYSTEM,
            output_schema=RESEARCH_CLASSIFY_SCHEMA,
        )
    except Exception as e:
        logger.warning("LLM call failed in classify_query_node: %s", e)
        return {"error": f"Failed to classify query: {e!s}"}

    # Extract target court/bench from classification, falling back to defaults
    result: dict = {"messages": [{"type": "classification", "data": classification}]}

    target_court = classification.get("target_court")
    target_bench = classification.get("target_bench")

    if target_court:
        result["target_court"] = target_court
    if target_bench:
        result["target_bench"] = target_bench

    # [V3] Extract procedural context and client position
    procedural_context = classification.get("procedural_context") or ""
    client_position = classification.get("client_position") or ""
    if procedural_context:
        result["procedural_context"] = procedural_context
    if client_position:
        result["client_position"] = client_position

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
        sanitized_feedback = sanitize_search_query(user_feedback)
        prompt += (
            "\n\nThe user has provided feedback on the previous sub-queries. "
            "Incorporate this feedback:\n"
            f"<user_feedback>{sanitized_feedback}</user_feedback>"
        )

    try:
        result = await llm.generate_structured(
            prompt=prompt,
            system=RESEARCH_DECOMPOSE_SYSTEM,
            output_schema=RESEARCH_DECOMPOSE_SCHEMA,
        )
    except Exception as exc:
        logger.warning("Decompose query failed: %s", exc)
        return {"error": f"Failed to decompose query: {exc}"}

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

    combined = await parallel_hybrid_search(
        sub_queries, llm, embedder, vector_store, reranker, db,
        pre_understood=True,
    )
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

    return {"cross_references": cross_refs, "search_results": list(best.values())}


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

    # Limit results sent to LLM to avoid context overflow
    results_for_llm = sorted(results, key=lambda r: r.get("score", 0), reverse=True)[
        :MAX_RESULTS_FOR_LLM
    ]

    context = format_search_results_for_llm(results_for_llm)

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

    try:
        raw = await llm.generate(
            prompt=prompt,
            system=RESEARCH_CONTRADICTIONS_SYSTEM,
            temperature=0.1,
        )
    except Exception as e:
        logger.warning("LLM call failed in detect_contradictions_node: %s", e)
        return {"contradictions": []}

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

    # Limit results sent to LLM to avoid context overflow
    results_for_llm = sorted(results, key=lambda r: r.get("score", 0), reverse=True)[
        :MAX_RESULTS_FOR_LLM
    ]

    findings = format_search_results_for_llm(results_for_llm)

    # Detect overruling language in search results
    overruled_case_ids = detect_overruled_cases(results)
    treatment_warnings: list[str] = []
    for r in results:
        cid = r.get("case_id", "")
        if cid and cid in overruled_case_ids:
            title = r.get("title", "Unknown")
            citation = r.get("citation", "N/A")
            treatment_warnings.append(
                f"- {title} ({citation}): Contains language suggesting this case "
                f"may have been overruled or declared per incuriam."
            )

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
        evidence=findings,
        passages="No verbatim passages extracted.",
        worker_reasoning="",
        communities="",
        strategy_hint="",
    )

    if treatment_text:
        prompt += treatment_text

    try:
        memo = await llm.generate(
            prompt=prompt,
            system=RESEARCH_SYNTHESIZE_SYSTEM,
            temperature=0.2,
            max_tokens=8192,
        )
    except Exception as exc:
        logger.warning("Memo synthesis failed: %s", exc)
        return {"error": f"Failed to synthesize memo: {exc}"}

    # Append legal disclaimer to the memo
    memo += LEGAL_DISCLAIMER

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
    """Verify citations in the draft memo using shared 3-layer verification."""
    memo = state.get("draft_memo", "")
    if not memo:
        return {"draft_memo": memo}

    grounding_citations = collect_grounding_citations(state.get("search_results", []))
    memo = await verify_memo_citations(memo, db, grounding_citations)
    return {"draft_memo": memo}


# ===========================================================================
# V2 NODE FUNCTIONS — Research Agent V2 orchestrated pipeline
# ===========================================================================


# ---------------------------------------------------------------------------
# V2 Node: rewrite_query_node [S2] — parallel with classify
# ---------------------------------------------------------------------------


async def rewrite_query_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """Rewrite the user's query into a detailed, legally precise formulation.

    [S2] Runs in PARALLEL with classify — both read state["query"],
    neither depends on the other.
    """
    query = state["query"]
    try:
        rewritten = await llm.generate(
            prompt=f"Rewrite this legal research query:\n\n{query}",
            system=RESEARCH_REWRITE_SYSTEM,
            temperature=0.3,
        )
    except Exception as exc:
        logger.warning("Query rewrite failed: %s", exc)
        return {"rewritten_query": query}  # Fallback to original

    return {"rewritten_query": rewritten.strip()}


# ---------------------------------------------------------------------------
# V2 Node: classify_complexity_node [S9] — enhanced classify with complexity
# ---------------------------------------------------------------------------

# The existing classify_query_node already handles this since we updated
# RESEARCH_CLASSIFY_SCHEMA to include the complexity field. We just need
# to extract the complexity value from the classification result.
# The updated classify_query_node now returns complexity via the schema.


# ---------------------------------------------------------------------------
# V2 Node: plan_research_node — orchestrator with dual queries + named cases
# ---------------------------------------------------------------------------


async def plan_research_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """Generate a structured research plan with typed tasks.

    Produces dual queries (NL + boolean) and named landmark cases
    for each research task.
    """
    query = state.get("rewritten_query") or state["query"]

    # Retrieve classification from messages
    classification: dict = {}
    for msg in state.get("messages", []):
        if isinstance(msg, dict) and msg.get("type") == "classification":
            classification = msg.get("data", {})

    # Retrieve user feedback if this is a re-plan after HITL
    user_feedback = ""
    for msg in state.get("messages", []):
        if isinstance(msg, dict) and msg.get("type") == "user_feedback" and msg.get("step") == "plan":
            user_feedback = msg.get("content", "")

    classification_str = json.dumps(classification) if classification else "N/A"

    # [V3] Format statute context for planning
    statute_parts: list[str] = []
    for s in state.get("statute_context", []):
        entry = f"- {s['act_short_name']} Section {s['section_number']}: {s.get('section_title', '')}"
        entry += f"\n  Text: {s['section_text'][:500]}"
        if s.get("is_repealed"):
            entry += f"\n  [REPEALED → {s.get('replaced_by', '')}]"
        statute_parts.append(entry)

    # [V3] Format legal elements for planning
    element_parts: list[str] = []
    for e in state.get("legal_elements", []):
        entry = f"- {e['element_id']}: {e['description']}"
        entry += f"\n  Statute basis: {e.get('statute_basis', '')}"
        entry += f"\n  Contested: {'Yes' if e.get('is_contested') else 'No'}"
        element_parts.append(entry)

    procedural = state.get("procedural_context", "")
    position = state.get("client_position", "")

    prompt = (
        f"Create a research plan for the following legal question.\n\n"
        f"## Research Question\n{query}\n\n"
        f"## Classification\n{classification_str}\n\n"
        f"## Statute Context\n{chr(10).join(statute_parts) or 'None found'}\n\n"
        f"## Legal Elements\n{chr(10).join(element_parts) or 'None decomposed'}\n\n"
        f"## Procedural Context\n"
        f"Stage: {procedural or 'not specified'}\n"
        f"Client position: {position or 'not specified'}\n\n"
        f"Generate 3-8 typed research tasks with dual queries and named cases. "
        f"Target at least ONE case_law task per legal element."
    )

    if user_feedback:
        sanitized = sanitize_search_query(user_feedback)
        prompt += (
            f"\n\nUser feedback on previous plan:\n"
            f"<user_feedback>{sanitized}</user_feedback>"
        )

    try:
        result = await llm.generate_structured(
            prompt=prompt,
            system=RESEARCH_PLAN_SYSTEM,
            output_schema=RESEARCH_PLAN_SCHEMA,
        )
    except Exception as exc:
        logger.warning("Research planning failed: %s", exc)
        return {"error": f"Failed to create research plan: {exc}"}

    tasks: list[ResearchTask] = []
    for raw_task in result.get("research_tasks", []):
        tasks.append(ResearchTask(
            task_id=str(uuid.uuid4()),
            task_type=raw_task.get("task_type", "case_law"),
            nl_query=raw_task.get("nl_query", ""),
            boolean_query=raw_task.get("boolean_query", ""),
            named_cases=raw_task.get("named_cases", []),
            rationale=raw_task.get("rationale", ""),
            filters=raw_task.get("filters", {}),
            priority=raw_task.get("priority", 2),
        ))

    # Populate sub_queries for backward compat with HITL checkpoint display
    sub_queries = [t["nl_query"] for t in tasks if t.get("nl_query")]

    # [T1] Emit plan event
    plan_event = emit_status("plan", {
        "tasks": [
            {"task_type": t["task_type"], "query": t["nl_query"][:100]}
            for t in tasks
        ],
        "named_cases": [
            c.get("name", c.get("citation", ""))
            for t in tasks for c in t.get("named_cases", [])
        ][:10],
        "total_workers": len(tasks),
    })

    return {
        "research_plan": tasks,
        "sub_queries": sub_queries,
        "process_events": [plan_event],
    }


# ---------------------------------------------------------------------------
# V2 Node: gather_worker_results_node — collect all Send() worker results
# ---------------------------------------------------------------------------


async def gather_worker_results_node(state: ResearchState) -> dict:
    """Collect all worker results, deduplicate with diversity control.

    Worker results arrive via the operator.add reducer on worker_results.
    This node deduplicates and identifies cross-references across workers.
    """
    worker_results = state.get("worker_results", [])
    if not worker_results:
        return {"search_results": [], "cross_references": []}

    # [C2] Deduplicate by task_id — keep latest (last dispatch cycle wins)
    seen_task_ids: dict[str, dict] = {}
    for wr in worker_results:
        tid = wr.get("task_id", "")
        if tid:
            seen_task_ids[tid] = wr  # Later entry overwrites earlier
        else:
            seen_task_ids[id(wr)] = wr  # Fallback for results without task_id
    worker_results = list(seen_task_ids.values())

    # Flatten all results from all workers
    all_results: list[dict] = []
    for wr in worker_results:
        all_results.extend(wr.get("results", []))

    # Deduplicate with diversity control (max 4 chunks per case)
    deduped = deduplicate_with_diversity(all_results, max_chunks_per_case=4)

    # Identify cross-references (cases found by 2+ workers)
    case_workers: dict[str, set[str]] = {}
    for wr in worker_results:
        for r in wr.get("results", []):
            cid = r.get("case_id", "")
            if cid:
                case_workers.setdefault(cid, set()).add(wr.get("task_type", ""))

    cross_refs: list[dict] = []
    for cid, workers in case_workers.items():
        if len(workers) >= 2:
            # Find best result for this case
            best = max(
                (r for r in deduped if r.get("case_id") == cid),
                key=lambda x: x.get("score", 0),
                default=None,
            )
            if best:
                cross_refs.append({
                    "case_id": cid,
                    "title": best.get("title"),
                    "citation": best.get("citation"),
                    "matched_workers": list(workers),
                    "match_count": len(workers),
                })

    cross_refs.sort(key=lambda x: x["match_count"], reverse=True)

    # [T1] Emit found events per worker
    found_events = []
    for wr in worker_results:
        results_list = wr.get("results", [])
        top_case = results_list[0].get("title", "")[:80] if results_list else ""
        found_events.append(emit_status("found", {
            "worker": wr.get("task_type", "unknown"),
            "count": len(results_list),
            "top_case": top_case,
        }))

    # [C6] No-results check — set abort flag + caveat
    result: dict = {
        "search_results": deduped,
        "cross_references": cross_refs,
        "process_events": found_events,
    }
    if not deduped:
        result["draft_memo"] = (
            "**No Results Found**\n\n"
            "The research query did not return any relevant cases or statutes. "
            "This may be because:\n"
            "- The query uses terminology not present in our database\n"
            "- The legal issue is very niche or recent\n"
            "- The case law is primarily from lower courts not yet indexed\n\n"
            "**Suggestions:**\n"
            "1. Try rephrasing the query with broader legal terms\n"
            "2. Include specific statute sections or case citations\n"
            "3. Search for related constitutional provisions\n"
        )
        result["confidence"] = 0.0
    elif len(deduped) < 3:
        # Few results — downstream synthesis will include caveat
        # [H6] Don't overload error field — use a message instead
        result["messages"] = [{"type": "caveat", "content": "Few results found — memo may be less comprehensive"}]

    return result


# ---------------------------------------------------------------------------
# V2 Node: batch_worker_cot_with_reflection_node [S4 + Q5]
# ---------------------------------------------------------------------------


async def batch_worker_cot_with_reflection_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """Single batched CoT + Deep Research reflection for all worker results.

    [S4] Generates MA-RAG chain-of-thought for ALL workers in one Flash call.
    [Q5] Also performs reflection — asks whether findings change understanding
    and whether to pivot strategy. Both in the SAME prompt.
    """
    worker_results = state.get("worker_results", [])
    if not worker_results:
        return {"worker_reasonings": [], "strategy_adjustment": None}

    worker_summaries = []
    for wr in worker_results:
        n_results = len(wr.get("results", []))
        top_titles = [r.get("title", "?")[:80] for r in wr.get("results", [])[:3]]
        top_citations = [r.get("citation", "?")[:60] for r in wr.get("results", [])[:3]]
        worker_summaries.append(
            f"[{wr['task_type']}] Query: {wr['query'][:100]} | "
            f"{n_results} results. Top: {', '.join(top_titles)} "
            f"({', '.join(top_citations)})"
        )

    query = state.get("rewritten_query") or state["query"]
    prompt = (
        f"Research question: {query}\n\n"
        f"Worker results summary:\n" + "\n".join(worker_summaries) + "\n\n"
        "Provide PART 1 (per-worker analysis + cross-worker tensions) "
        "and PART 2 (reflection on whether to pivot strategy)."
    )

    try:
        response = await llm.generate_structured(
            prompt=prompt,
            system=RESEARCH_WORKER_COT_SYSTEM,
            output_schema=BATCH_COT_WITH_REFLECTION_SCHEMA,
        )
    except Exception as exc:
        logger.warning("Batch CoT failed: %s", exc)
        return {"worker_reasonings": [], "strategy_adjustment": None}

    strategy_adj = None
    if response.get("should_pivot"):
        strategy_adj = StrategyAdjustment(
            should_pivot=True,
            pivot_reason=response.get("pivot_reason", ""),
            new_tasks=response.get("new_tasks", []),
            reframe_query=response.get("reframe_query"),
        )

    # [T1] Emit reflection event
    reflection_event = emit_status("reflection", {
        "insights": response.get("reasoning", "")[:200],
        "pivot": bool(strategy_adj and strategy_adj.get("should_pivot")),
        "new_tasks": len(response.get("new_tasks", [])) if strategy_adj else 0,
    })

    return {
        "worker_reasonings": [response.get("reasoning", "")],
        "strategy_adjustment": strategy_adj,
        "process_events": [reflection_event],
    }


# ---------------------------------------------------------------------------
# V2 Node: evaluate_and_extract_node [S3 + Q2 + S12]
# ---------------------------------------------------------------------------


def _chunked(iterable: list, n: int) -> list[list]:
    """Split a list into chunks of size n."""
    return [iterable[i:i + n] for i in range(0, len(iterable), n)]


async def evaluate_and_extract_node(
    state: ResearchState,
    llm: LLMProvider,
    db: AsyncSession,
    *,
    ik_client: Any | None = None,
) -> dict:
    """Merged CRAG relevance scoring + passage extraction + deep read.

    [S3] Combines CRAG and extract into ONE Flash call per batch.
    [Q2] For "ambiguous" results, fetches full HOLDINGS/RATIO sections
    from case_sections table before final verdict.
    For IK results, fetches query-specific fragment via IK API as deep-read.
    [S12] All batches processed in PARALLEL via asyncio.gather().
    """
    worker_results = state.get("worker_results", [])
    if not worker_results:
        return {
            "relevance_scores": [],
            "extracted_passages": [],
        }

    # Flatten all results
    all_results: list[dict] = []
    for wr in worker_results:
        all_results.extend(wr.get("results", []))

    if not all_results:
        return {
            "relevance_scores": [],
            "extracted_passages": [],
        }

    query = state.get("rewritten_query") or state["query"]

    # [Q2] Deep read helper — local DB for our cases, IK fragment API for IK cases
    async def deep_read_sections(case_id: str) -> str:
        """Fetch HOLDINGS + RATIO from case_sections, or IK fragment for IK cases."""
        if case_id.startswith("ik:"):
            # IK deep-read: fetch query-specific fragment via IK API
            if ik_client is None:
                return ""
            try:
                ik_doc_id = case_id.removeprefix("ik:")
                fragment = await ik_client.get_fragment(ik_doc_id, query)
                frag_text = fragment.get("headline", fragment.get("fragment", ""))
                if isinstance(frag_text, list):
                    frag_text = " ".join(frag_text)
                import re
                return re.sub(r"<[^>]+>", "", frag_text).strip()[:5000]
            except Exception:
                return ""
        try:
            from app.models.case_section import CaseSection
            result = await db.execute(
                select(CaseSection.content).where(
                    CaseSection.case_id == case_id,
                    CaseSection.section_type.in_(
                        ["HOLDINGS", "RATIO_DECIDENDI", "ANALYSIS"],
                    ),
                )
            )
            sections = [row[0] for row in result.fetchall()]
            return "\n\n".join(sections)[:5000]
        except Exception:
            return ""

    # [S12] Process batches in PARALLEL
    batches = _chunked(all_results, 15)

    async def process_batch(batch: list[dict]) -> dict:
        formatted = format_search_results_for_llm_extended(batch)
        return await llm.generate_structured(
            prompt=f"Research question: {query}\n\nDocuments:\n{formatted}",
            system=RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM,
            output_schema=EVALUATE_AND_EXTRACT_SCHEMA,
        )

    try:
        evaluations = await asyncio.gather(
            *[process_batch(b) for b in batches],
            return_exceptions=True,
        )
    except Exception as exc:
        logger.warning("Evaluate and extract failed: %s", exc)
        return {
            "relevance_scores": [],
            "extracted_passages": [],
        }

    relevance_scores: list[RelevanceScore] = []
    extracted_passages: list[ExtractedPassage] = []
    ambiguous_ids: list[tuple[str, list[dict]]] = []

    for evaluation, batch in zip(evaluations, batches):
        if isinstance(evaluation, Exception):
            logger.warning("Batch evaluation failed: %s", evaluation)
            continue

        for ev in evaluation.get("evaluations", []):
            relevance_scores.append(RelevanceScore(
                case_id=ev["case_id"],
                score=ev["score"],
                verdict=ev["verdict"],
                reason=ev["reason"],
                action=ev["action"],
            ))
            if ev["verdict"] == "ambiguous":
                ambiguous_ids.append((ev["case_id"], batch))
            if ev.get("passage") and ev["verdict"] != "incorrect":
                citation = next(
                    (r.get("citation", "") for r in batch
                     if r.get("case_id") == ev["case_id"]),
                    "",
                )
                extracted_passages.append(ExtractedPassage(
                    case_id=ev["case_id"],
                    citation=citation,
                    passage=ev["passage"],
                    source_field=ev.get("passage_source_field", "chunk_text"),
                    relevance=ev["reason"],
                    is_verbatim=ev.get("is_verbatim", True),
                ))

    # [Q2] Deep read pass for ambiguous results (up to 10)
    if ambiguous_ids:
        deep_tasks = [deep_read_sections(cid) for cid, _ in ambiguous_ids[:10]]
        section_texts = await asyncio.gather(*deep_tasks, return_exceptions=True)

        for (case_id, _), section_text in zip(ambiguous_ids[:10], section_texts):
            if isinstance(section_text, Exception) or not section_text:
                continue
            try:
                re_eval = await llm.generate_structured(
                    prompt=(
                        f"Research question: {query}\n\n"
                        f"Full HOLDINGS/RATIO for re-evaluation:\n{section_text}"
                    ),
                    system=RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM,
                    output_schema=EVALUATE_AND_EXTRACT_SCHEMA,
                )
                for ev in re_eval.get("evaluations", []):
                    if ev["case_id"] == case_id:
                        # Update score if deep read changed verdict
                        for i, s in enumerate(relevance_scores):
                            if s["case_id"] == case_id:
                                relevance_scores[i] = RelevanceScore(
                                    case_id=case_id,
                                    score=ev["score"],
                                    verdict=ev["verdict"],
                                    reason=f"[deep_read] {ev['reason']}",
                                    action=ev["action"],
                                )
                        if ev.get("passage") and ev["verdict"] == "correct":
                            extracted_passages.append(ExtractedPassage(
                                case_id=case_id,
                                citation="",
                                passage=ev["passage"],
                                source_field="case_sections",
                                relevance=ev["reason"],
                                is_verbatim=ev.get("is_verbatim", True),
                            ))
            except Exception:
                logger.warning("Deep read re-eval failed for %s", case_id)

    # Filter incorrect results
    incorrect_ids = {
        s["case_id"] for s in relevance_scores if s["verdict"] == "incorrect"
    }
    filtered_worker_results: list[WorkerResult] = []
    for wr in worker_results:
        filtered = [
            r for r in wr["results"]
            if r.get("case_id") not in incorrect_ids
        ]
        filtered_worker_results.append(WorkerResult(
            task_id=wr["task_id"],
            task_type=wr["task_type"],
            query=wr["query"],
            results=filtered,
            source_urls=wr.get("source_urls", []),
            metadata=wr.get("metadata", {}),
            error=wr.get("error"),
            reasoning=wr.get("reasoning", ""),
        ))

    # [T1] Emit evaluating event
    correct_count = sum(1 for s in relevance_scores if s["verdict"] == "correct")
    ambiguous_count = sum(1 for s in relevance_scores if s["verdict"] == "ambiguous")
    deep_read_count = len(ambiguous_ids[:10]) if ambiguous_ids else 0
    evaluating_event = emit_status("evaluating", {
        "total": len(relevance_scores),
        "correct": correct_count,
        "ambiguous": ambiguous_count,
        "filtered": len(incorrect_ids),
        "deep_read": deep_read_count,
    })

    # [B17] Distinguish vs contradict classification for ambiguous/incorrect results
    contradictions: list[dict] = []
    if incorrect_ids and llm:
        try:
            # Build pairs of conflicting holdings
            incorrect_results = []
            for wr in worker_results:
                for r in wr.get("results", []):
                    if r.get("case_id") in incorrect_ids:
                        incorrect_results.append(r)

            if incorrect_results and len(incorrect_results) <= 10:
                conflict_text = "\n".join(
                    f"- {r.get('citation', '?')}: {r.get('title', '?')[:80]} "
                    f"— {r.get('ratio', r.get('snippet', ''))[:200]}"
                    for r in incorrect_results[:5]
                )
                distinguish_prompt = (
                    f"Research question: {state.get('query', '')}\n\n"
                    f"These cases were flagged as potentially contradicting the research question:\n"
                    f"{conflict_text}\n\n"
                    "For each case, classify as ONE of:\n"
                    '- "contradicts": directly opposes the research position\n'
                    '- "distinguishable": can be distinguished on facts/law\n'
                    '- "limited": limited applicability (different jurisdiction, obiter)\n\n'
                    "Return a JSON array: [{\"citation\": \"...\", \"category\": \"...\", \"reasoning\": \"...\"}]"
                )
                raw = await llm.generate(
                    prompt=distinguish_prompt,
                    system="You are a legal analyst. Classify each contradicting case. Return JSON only.",
                )
                contradictions = safe_json_parse_list(raw)
        except Exception:
            logger.warning("Distinguish classification failed", exc_info=True)

    # IMPORTANT: Do NOT write filtered results back to worker_results!
    # worker_results uses operator.add reducer (needed for Send() fan-out),
    # so writing here would APPEND duplicates instead of replacing.
    # Instead, flatten filtered results into search_results (simple replace).
    filtered_search_results: list[dict] = []
    for wr in filtered_worker_results:
        filtered_search_results.extend(wr.get("results", []))

    return {
        "relevance_scores": relevance_scores,
        "extracted_passages": extracted_passages,
        "search_results": filtered_search_results,
        "contradictions": contradictions,
        "process_events": [evaluating_event],
    }


# ---------------------------------------------------------------------------
# V2 Node: gap_analysis_node [Q1 MC-RAG + Q5 reflection integration]
# ---------------------------------------------------------------------------


async def gap_analysis_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """FAIR-RAG evidence assessment with MC-RAG conditioned retrieval.

    [Q1] Round 2+ queries are CONDITIONED on round 1 findings.
    [Q5] Integrates strategy_adjustment from reflection.
    """
    query = state.get("rewritten_query") or state["query"]
    research_plan = state.get("research_plan", [])
    worker_results = state.get("worker_results", [])
    relevance_scores = state.get("relevance_scores", [])
    worker_reasonings = state.get("worker_reasonings", [])
    strategy_adj = state.get("strategy_adjustment")
    refinement_round = state.get("refinement_round", 0)

    if not worker_results:
        return {"evidence_gaps": [], "refinement_round": refinement_round}

    # Build summary of what was found
    results_summary = []
    for wr in worker_results:
        n = len(wr.get("results", []))
        top = [
            f"{r.get('title', '?')[:60]} ({r.get('citation', '?')[:40]})"
            for r in wr.get("results", [])[:5]
        ]
        results_summary.append(
            f"[{wr['task_type']}] {n} results: {', '.join(top)}"
        )

    # CRAG quality summary
    crag_summary = ""
    if relevance_scores:
        correct = sum(1 for s in relevance_scores if s["verdict"] == "correct")
        ambiguous = sum(1 for s in relevance_scores if s["verdict"] == "ambiguous")
        incorrect = sum(1 for s in relevance_scores if s["verdict"] == "incorrect")
        crag_summary = (
            f"\nCRAG quality: {correct} correct, {ambiguous} ambiguous, "
            f"{incorrect} incorrect (filtered)"
        )
        web_needed = any(s["action"] == "needs_web_fallback" for s in relevance_scores)
        if web_needed:
            crag_summary += " — Web fallback recommended for some results."

    # [Q5] Strategy adjustment
    strategy_text = ""
    if strategy_adj and strategy_adj.get("should_pivot"):
        strategy_text = (
            f"\n\nSTRATEGY ADJUSTMENT (from reflection): "
            f"{strategy_adj.get('pivot_reason', '')}"
        )
        if strategy_adj.get("reframe_query"):
            strategy_text += f"\nReframed query: {strategy_adj['reframe_query']}"

    # Worker CoT reasoning
    cot_text = ""
    if worker_reasonings:
        cot_text = f"\n\nWorker reasoning:\n{chr(10).join(worker_reasonings)}"

    # [Q1] MC-RAG: provide top results from prior rounds as conditioning context
    top_results_summary = ""
    if refinement_round > 0:
        top_results = []
        for wr in worker_results:
            for r in wr.get("results", [])[:3]:
                top_results.append(
                    f"- {r.get('citation', '?')}: {r.get('title', '?')[:80]}"
                )
        if top_results:
            top_results_summary = (
                "\n\nTOP RESULTS FROM PRIOR ROUNDS (condition follow-up queries on these):\n"
                + "\n".join(top_results[:15])
            )

    prompt = (
        f"Research question: {query}\n\n"
        f"Research plan: {json.dumps([dict(t) for t in research_plan], default=str)[:2000]}\n\n"
        f"Results found:\n{chr(10).join(results_summary)}"
        f"{crag_summary}{cot_text}{strategy_text}{top_results_summary}\n\n"
        f"Refinement round: {refinement_round} (max 2)\n\n"
        "Identify evidence gaps and generate targeted follow-up queries."
    )

    try:
        result = await llm.generate_structured(
            prompt=prompt,
            system=RESEARCH_GAP_ANALYSIS_SYSTEM,
            output_schema=RESEARCH_GAP_ANALYSIS_SCHEMA,
        )
    except Exception as exc:
        logger.warning("Gap analysis failed: %s", exc)
        return {"evidence_gaps": [], "refinement_round": refinement_round}

    gaps: list[EvidenceGap] = []
    for raw_gap in result.get("gaps", []):
        gaps.append(EvidenceGap(
            description=raw_gap.get("description", ""),
            suggested_query=raw_gap.get("suggested_query", ""),
            suggested_source=raw_gap.get("suggested_source", "case_law"),
            priority=raw_gap.get("priority", 2),
            conditioned_on=raw_gap.get("conditioned_on", []),
            conditioning_context=raw_gap.get("conditioning_context", ""),
        ))

    # [Q5] If strategy adjustment recommended new tasks, add them as gaps
    if strategy_adj and strategy_adj.get("should_pivot"):
        for new_task in strategy_adj.get("new_tasks", []):
            gaps.append(EvidenceGap(
                description=f"[Strategy pivot] {new_task.get('rationale', '')}",
                suggested_query=new_task.get("nl_query", ""),
                suggested_source=new_task.get("task_type", "case_law"),
                priority=1,  # Strategy pivots are high priority
                conditioned_on=[],
                conditioning_context=strategy_adj.get("pivot_reason", ""),
            ))

    # [T1] Emit gap event
    gap_event = emit_status("gap", {
        "gaps": [g["description"][:100] for g in gaps[:5]],
        "refinement_round": refinement_round,
        "conditioned_on": [
            c for g in gaps for c in g.get("conditioned_on", [])
        ][:10],
    })

    # Convert gaps to new research tasks for dispatch
    if gaps and refinement_round < 2:
        new_tasks: list[ResearchTask] = []
        for gap in gaps:
            new_tasks.append(ResearchTask(
                task_id=str(uuid.uuid4()),
                task_type=gap["suggested_source"],
                nl_query=gap["suggested_query"],
                boolean_query="",
                named_cases=[],
                rationale=gap["description"],
                filters={},
                priority=gap["priority"],
            ))
        return {
            "evidence_gaps": gaps,
            "research_plan": new_tasks,
            "sub_queries": [t["nl_query"] for t in new_tasks],
            "refinement_round": refinement_round + 1,
            "process_events": [gap_event],
        }

    # Clear gaps when max refinement rounds reached to prevent infinite loops
    return {
        "evidence_gaps": [],
        "refinement_round": refinement_round,
        "process_events": [gap_event],
    }


# ---------------------------------------------------------------------------
# V2 Node: fast_path_search_node [S9]
# ---------------------------------------------------------------------------


async def fast_path_search_node(
    state: ResearchState,
    llm: LLMProvider,
    flash_llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    db: AsyncSession,
) -> dict:
    """Single-worker search for simple queries.

    [S9] Routes to exactly ONE worker based on classify intent.
    Falls back to full pipeline if insufficient results.
    """
    # Determine intent from classification
    intent = "topic_search"
    for msg in state.get("messages", []):
        if isinstance(msg, dict) and msg.get("type") == "classification":
            data = msg.get("data", {})
            # Map topic to intent heuristic
            if data.get("topic") == "constitutional":
                intent = "statute_search"
            break

    query = state.get("rewritten_query") or state["query"]

    try:
        results = await parallel_hybrid_search(
            [query], llm, embedder, vector_store, reranker, db,
            pre_understood=True,
        )
        results = await enrich_results_with_ratio(results, db, max_ratio_len=3000)
    except Exception as exc:
        logger.warning("Fast path search failed: %s", exc)
        return {"complexity": "complex"}  # Fall back to full pipeline

    # Quality gate: fall back to full pipeline if too few results
    if len(results) < 3:
        return {"complexity": "complex"}

    return {
        "search_results": results,
        "worker_results": [WorkerResult(
            task_id="fast_path",
            task_type=intent,
            query=query,
            results=results,
            source_urls=[],
            metadata={},
            error=None,
            reasoning="",
        )],
    }


# ---------------------------------------------------------------------------
# V2 Node: fast_path_synthesis_node [S9]
# ---------------------------------------------------------------------------


async def fast_path_synthesis_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """Lightweight Flash synthesis for simple queries.

    [S9] Single Flash call, no speculative drafts, shorter output.
    """
    query = state.get("rewritten_query") or state["query"]
    results = state.get("search_results", [])

    if not results:
        return {"draft_memo": "No results found for this query.", "confidence": 0.0}

    findings = format_search_results_for_llm_extended(
        sorted(results, key=lambda r: r.get("score", 0), reverse=True)[:15],
    )

    # [V3] Format statute context for grounded answers
    statute_context = state.get("statute_context", [])
    statute_text = ""
    if statute_context:
        parts = []
        for s in statute_context:
            entry = f"{s['act_short_name']} Section {s['section_number']}: {s['section_text'][:500]}"
            if s.get("is_repealed"):
                entry += f" [REPEALED → {s.get('replaced_by', '')}]"
            parts.append(entry)
        statute_text = "\n".join(parts)

    prompt_parts = []
    if statute_text:
        prompt_parts.append(f"## Relevant Statute Text\n{statute_text}\n")
    prompt_parts.append(f"Research Question: {query}\n\nSearch Results:\n{findings}\n\n"
                        "Write a concise research response with footnotes.")

    try:
        memo = await llm.generate(
            prompt="\n".join(prompt_parts),
            system=RESEARCH_FAST_PATH_SYNTHESIS_SYSTEM,
            temperature=0.2,
            max_tokens=4096,
        )
    except Exception as exc:
        logger.warning("Fast path synthesis failed: %s", exc)
        return {"error": f"Fast path synthesis failed: {exc}"}

    memo += LEGAL_DISCLAIMER

    # Simple confidence based on result count and scores
    scores = [r.get("score", 0) for r in results if r.get("score")]
    confidence = min(0.9, sum(scores[:5]) / max(len(scores[:5]), 1))

    return {"draft_memo": memo, "confidence": confidence}


# ---------------------------------------------------------------------------
# V2 Node: pre_warm_embeddings_node [S6]
# ---------------------------------------------------------------------------


async def pre_warm_embeddings_node(
    state: ResearchState,
    embedder: EmbeddingProvider,
) -> dict:
    """Pre-compute embeddings during HITL wait. Non-blocking, best-effort.

    [S6] Workers check precomputed_embeddings before calling embed_text().
    """
    queries: list[str] = []
    for task in state.get("research_plan", []):
        if task.get("nl_query"):
            queries.append(task["nl_query"])
        if task.get("boolean_query"):
            queries.append(task["boolean_query"])

    if not queries:
        return {"precomputed_embeddings": {}}

    try:
        vectors = await embedder.embed_batch(queries)
        return {"precomputed_embeddings": dict(zip(queries, vectors))}
    except Exception:
        return {"precomputed_embeddings": {}}


# ---------------------------------------------------------------------------
# V2 Node: speculative_synthesis_with_contradictions_node [S1 + S5]
# ---------------------------------------------------------------------------


async def speculative_synthesis_with_contradictions_node(
    state: ResearchState,
    llm: LLMProvider,
    flash_llm: LLMProvider,
    stream_callback: Callable[[str], None] | None = None,
) -> dict:
    """Speculative RAG: 3x Flash drafts → Pro verification/merge/contradiction-detection.

    [S1] Contradictions detected inside Pro merge (no separate Pro call).
    [S5] Pro output streamed to frontend via stream_callback.
    """
    # Use search_results (post-evaluation, filtered & deduplicated) instead of
    # raw worker_results (which accumulates via operator.add across dispatch cycles).
    all_results: list[dict] = state.get("search_results", [])
    passages = state.get("extracted_passages", [])
    relevance_scores = {
        s["case_id"]: s["score"]
        for s in state.get("relevance_scores", [])
    }
    worker_reasonings = state.get("worker_reasonings", [])

    # Extract community summaries from raw worker_results (these aren't in search_results)
    raw_worker_results = state.get("worker_results", [])
    community_summaries = [
        r for wr in raw_worker_results if wr.get("task_type") == "graph_community"
        for r in wr.get("results", [])
    ]

    if not all_results:
        return {
            "draft_memo": "No evidence found to synthesize.",
            "confidence": 0.0,
            "synthesis_drafts": [],
            "footnotes": [],
            "source_attribution": {},
            "research_audit": {},
        }

    # --- Partition evidence into 3 strategies ---

    # Strategy A: Top by CRAG relevance score
    strategy_a = sorted(
        all_results,
        key=lambda r: relevance_scores.get(r.get("case_id", ""), 0.5),
        reverse=True,
    )[:15]

    # Strategy B: Top by precedent strength (binding > persuasive > distinguishable)
    strength_order = {
        "BINDING": 4, "PERSUASIVE": 3, "DISTINGUISHABLE": 2, "OVERRULED": 1,
    }
    strategy_b = sorted(
        all_results,
        key=lambda r: strength_order.get(
            r.get("precedent_strength", "PERSUASIVE"), 2,
        ),
        reverse=True,
    )[:15]

    # Strategy C: Max diversity — 2-3 per source type
    strategy_c: list[dict] = []
    by_source: dict[str, list[dict]] = {}
    for r in all_results:
        source = r.get("source", "internal")
        by_source.setdefault(source, []).append(r)
    for _source, items in by_source.items():
        strategy_c.extend(items[:3])
    strategy_c = strategy_c[:15]

    # --- Fan out 3 Flash drafts in parallel ---
    shared_context = {
        "query": state.get("rewritten_query") or state["query"],
        "passages": format_extracted_passages(passages),
        "worker_reasoning": "\n".join(worker_reasonings),
        "communities": format_community_summaries(community_summaries),
    }

    # [T1] Collect drafting events
    process_events: list[dict] = []

    async def generate_draft(
        strategy_name: str, evidence_subset: list[dict],
    ) -> SynthesisDraft:
        formatted_evidence = format_search_results_for_llm_extended(evidence_subset)
        memo = await flash_llm.generate(
            prompt=RESEARCH_SYNTHESIZE_USER.format(
                query=shared_context["query"],
                evidence=formatted_evidence,
                passages=shared_context["passages"],
                worker_reasoning=shared_context["worker_reasoning"],
                communities=shared_context["communities"],
                strategy_hint=f"Focus on {strategy_name} — organize by {strategy_name}.",
            ),
            system=SPECULATIVE_DRAFT_SYSTEM,
            temperature=0.3,
            max_tokens=6000,
        )
        # Validate draft — retry once with higher temperature if degenerate
        if _is_degenerate_output(memo, min_useful_length=200):
            logger.warning(
                "Draft '%s' produced degenerate output (%d chars), retrying...",
                strategy_name, len(memo or ""),
            )
            memo = await flash_llm.generate(
                prompt=RESEARCH_SYNTHESIZE_USER.format(
                    query=shared_context["query"],
                    evidence=formatted_evidence,
                    passages=shared_context["passages"],
                    worker_reasoning=shared_context["worker_reasoning"],
                    communities=shared_context["communities"],
                    strategy_hint=f"Focus on {strategy_name} — organize by {strategy_name}.",
                ),
                system=SPECULATIVE_DRAFT_SYSTEM,
                temperature=0.7,
                max_tokens=6000,
            )
            if _is_degenerate_output(memo, min_useful_length=200):
                logger.error("Draft '%s' still degenerate after retry", strategy_name)
                memo = (
                    f"[Draft {strategy_name} unavailable — LLM generation failed. "
                    f"Evidence contained {len(evidence_subset)} results but the model "
                    f"was unable to synthesize them into a coherent draft.]"
                )
        return SynthesisDraft(
            draft_id=str(uuid4()),
            strategy=strategy_name,
            memo_text=memo,
            confidence=0.0,
            sources_used=[
                r.get("citation", "") for r in evidence_subset if r.get("citation")
            ],
        )

    # [T1] Emit drafting-start events
    for s in ("relevance", "authority", "breadth"):
        process_events.append(emit_status("drafting", {
            "strategy": s, "status": "generating",
        }))

    # [H22] Use return_exceptions=True to prevent one draft failure from killing all
    _strategy_names = ["relevance", "authority", "breadth"]
    raw_drafts = await asyncio.gather(
        generate_draft("relevance", strategy_a),
        generate_draft("authority", strategy_b),
        generate_draft("breadth", strategy_c),
        return_exceptions=True,
    )
    drafts = []
    for i, d in enumerate(raw_drafts):
        if isinstance(d, BaseException):
            logger.warning("Draft %d (%s) failed: %s", i, _strategy_names[i], d)
            drafts.append(SynthesisDraft(
                draft_id=str(uuid4()), strategy=_strategy_names[i],
                memo_text=f"[Draft unavailable — generation failed: {d}]",
                confidence=0.0, sources_used=[],
            ))
        else:
            drafts.append(d)

    # [T1] Emit drafting-complete events
    for s in ("relevance", "authority", "breadth"):
        process_events.append(emit_status("drafting", {
            "strategy": s, "status": "complete",
        }))

    # --- Pro verifier/merger [S1 + S5] ---
    all_formatted = format_search_results_for_llm_extended(all_results[:30])

    # [V3] Include temporal warnings in evidence context
    temporal_section = ""
    temporal_warnings = state.get("temporal_warnings", [])
    if temporal_warnings:
        tw_parts = [f"- {w['warning']}" for w in temporal_warnings]
        temporal_section = f"\n\nTEMPORAL VALIDITY WARNINGS:\n" + "\n".join(tw_parts) + "\n"

    # [V3] Mark adversarial results separately
    adversarial_section = ""
    adv_results = [
        wr for wr in raw_worker_results
        if isinstance(wr, dict) and wr.get("metadata", {}).get("adversarial")
    ]
    if adv_results:
        adv_formatted_parts = []
        for wr in adv_results:
            for r in wr.get("results", [])[:3]:
                adv_formatted_parts.append(
                    f"- {r.get('title', 'Unknown')}: {r.get('snippet', '')[:200]}"
                )
        if adv_formatted_parts:
            adversarial_section = (
                "\n\nCOUNTER-ARGUMENT EVIDENCE (opposing counsel perspective):\n"
                + "\n".join(adv_formatted_parts) + "\n"
            )

    verification_prompt = (
        f"RESEARCH QUESTION: {shared_context['query']}\n\n"
        f"COMPLETE EVIDENCE (all sources):\n{all_formatted}\n\n"
        f"EXTRACTED PASSAGES (verbatim quotes):\n{shared_context['passages']}\n\n"
        f"CITATION COMMUNITY CONTEXT:\n{shared_context['communities']}\n\n"
        f"WORKER REASONING:\n{shared_context['worker_reasoning']}\n"
        f"{temporal_section}"
        f"{adversarial_section}\n"
        f"--- DRAFT A (organized by relevance) ---\n{drafts[0]['memo_text']}\n\n"
        f"--- DRAFT B (organized by authority/precedent) ---\n{drafts[1]['memo_text']}\n\n"
        f"--- DRAFT C (organized by source diversity) ---\n{drafts[2]['memo_text']}\n\n"
        "---\n\n"
        "Produce the FINAL research memo following your system instructions."
    )

    # Check if all drafts are broken — skip Pro merge and use direct generation
    valid_drafts = [d for d in drafts if not _is_degenerate_output(d["memo_text"], 100)]
    if not valid_drafts:
        logger.warning("All 3 Flash drafts are degenerate — falling back to direct Pro generation")
        # Direct Pro generation without speculative drafts
        direct_prompt = (
            f"RESEARCH QUESTION: {shared_context['query']}\n\n"
            f"COMPLETE EVIDENCE (all sources):\n{all_formatted}\n\n"
            f"EXTRACTED PASSAGES (verbatim quotes):\n{shared_context['passages']}\n\n"
            f"CITATION COMMUNITY CONTEXT:\n{shared_context['communities']}\n\n"
            f"WORKER REASONING:\n{shared_context['worker_reasoning']}\n"
            f"{temporal_section}{adversarial_section}\n"
            "Produce a comprehensive legal research memo following your system instructions."
        )
        verification_prompt = direct_prompt

    # [S5] Stream Pro output to frontend for progressive rendering
    if stream_callback:
        final_memo_chunks: list[str] = []
        async for chunk in llm.stream(
            system=SPECULATIVE_MERGE_SYSTEM,
            prompt=verification_prompt,
        ):
            final_memo_chunks.append(chunk)
            stream_callback(chunk)
        final_memo = "".join(final_memo_chunks)
    else:
        final_memo = await llm.generate(
            prompt=verification_prompt,
            system=SPECULATIVE_MERGE_SYSTEM,
            temperature=0.2,
            max_tokens=8192,
        )

    # Validate final output — retry once if degenerate
    if _is_degenerate_output(final_memo, min_useful_length=300):
        logger.warning("Final memo is degenerate (%d chars), retrying with simplified prompt...", len(final_memo or ""))
        simplified_prompt = (
            f"Write a legal research memo answering: {shared_context['query']}\n\n"
            f"Available evidence:\n{all_formatted}\n\n"
            f"Passages:\n{shared_context['passages']}\n\n"
            "Structure: Executive Summary, Quick Reference Table, Detailed Analysis (IRAC), "
            "Contradictions, Conclusion, Footnotes."
        )
        final_memo = await llm.generate(
            prompt=simplified_prompt,
            system=SPECULATIVE_MERGE_SYSTEM,
            temperature=0.4,
            max_tokens=8192,
        )
        if _is_degenerate_output(final_memo, min_useful_length=300):
            logger.error("Final memo still degenerate after retry")
            final_memo = (
                "## Synthesis Failed\n\n"
                "The AI model was unable to produce a coherent research memo from the "
                "available evidence. This may be due to:\n"
                "- Insufficient relevant evidence for the specific legal question\n"
                "- Evidence quality issues (low relevance scores)\n\n"
                "**Recommendation:** Try refining your query to be more specific, "
                "or try again with different search parameters.\n\n"
                f"*{len(all_results)} results were found but could not be synthesized.*"
            )

    # Append legal disclaimer
    final_memo += LEGAL_DISCLAIMER

    # Build source attribution
    source_attribution = _build_source_attribution(all_results)

    # Build research audit
    research_audit = _build_research_audit(state, all_results)

    # [C5] Calculate confidence with 3-dimensional breakdown
    scores = [r.get("score", 0) for r in all_results if r.get("score")]
    contradictions = state.get("contradictions", [])
    precedent_strs = [r.get("bench_type", "PERSUASIVE") for r in all_results if r.get("bench_type")]
    breakdown = calculate_confidence_detailed(
        reranker_scores=scores[:10],
        cross_ref_ratio=min(1.0, len(all_results) / max(len(state.get("research_plan", [])), 1)),
        precedent_strengths=[s.upper() for s in precedent_strs] if precedent_strs else [],
        contradiction_count=len(contradictions),
        total_results=len(all_results),
    )
    confidence = breakdown["overall"]

    return {
        "draft_memo": final_memo,
        "synthesis_drafts": drafts,
        "source_attribution": source_attribution,
        "research_audit": research_audit,
        "confidence": confidence,
        "confidence_breakdown": dict(breakdown),
        "process_events": process_events,
    }


# ---------------------------------------------------------------------------
# V2 Node: format_footnotes_node — post-processing [8.2a]
# ---------------------------------------------------------------------------


def _infer_source_label(source_type: str) -> str:
    """Map internal source_type to a human-readable display label."""
    return {
        "case_law": "Case", "ik_search": "Case", "named_case": "Case",
        "statute": "Statute", "constitution": "Constitution",
        "web": "Web", "graph": "Case", "graph_community": "Case",
    }.get(source_type, "Source")


def _normalize_citation(text: str) -> str:
    """Normalize citation text for fuzzy matching."""
    # Lowercase, collapse whitespace, strip punctuation noise
    t = re.sub(r"\s+", " ", text.strip().lower())
    # Remove common prefixes the LLM adds
    t = re.sub(r"^(see|cf\.?|per|in)\s+", "", t)
    return t


def _fuzzy_lookup(
    citation_text: str,
    citation_lookup: dict[str, dict],
    _norm_index: dict[str, str] | None = None,
) -> dict:
    """Match footnote citation text to citation_lookup using fallback chain.

    Tries: exact → normalized exact → substring containment → best overlap.
    Returns matched metadata dict, or empty dict if no match.
    """
    # 1. Exact match
    if citation_text in citation_lookup:
        return citation_lookup[citation_text]

    # Build normalized index on first call
    if _norm_index is None:
        _norm_index = {}
    if not _norm_index:
        for key in citation_lookup:
            _norm_index[_normalize_citation(key)] = key

    norm_text = _normalize_citation(citation_text)

    # 2. Normalized exact match
    if norm_text in _norm_index:
        return citation_lookup[_norm_index[norm_text]]

    # 3. Substring containment (either direction)
    best_key = None
    best_len = 0
    for norm_key, orig_key in _norm_index.items():
        if norm_text in norm_key or norm_key in norm_text:
            # Prefer longest match
            if len(norm_key) > best_len:
                best_len = len(norm_key)
                best_key = orig_key
    if best_key:
        return citation_lookup[best_key]

    # 4. Token overlap — at least 60% of tokens must match
    text_tokens = set(norm_text.split())
    if len(text_tokens) >= 2:
        best_overlap = 0.0
        best_key = None
        for norm_key, orig_key in _norm_index.items():
            key_tokens = set(norm_key.split())
            if not key_tokens:
                continue
            overlap = len(text_tokens & key_tokens) / max(len(text_tokens), len(key_tokens))
            if overlap > best_overlap:
                best_overlap = overlap
                best_key = orig_key
        if best_overlap >= 0.6 and best_key:
            return citation_lookup[best_key]

    return {}


def _build_source_url(case_id: str | None, ik_doc_id: str, url: str) -> str:
    """Build best available source URL for a footnote."""
    if case_id and not str(case_id).startswith("ik:"):
        return f"/case/{case_id}"
    # Task 4: Generate IK URL from ik_doc_id when source_url is empty
    if ik_doc_id:
        return f"https://indiankanoon.org/doc/{ik_doc_id}/"
    if url:
        return url
    return ""


async def format_footnotes_node(state: ResearchState) -> dict:
    """Post-processing: extract [^N] references, build structured footnotes.

    Parses the memo for [^N] references and builds Footnote entries with
    source URLs. Also identifies searched-but-not-cited sources.
    Uses fuzzy citation matching (Task 1) and includes statute/web sources (Task 2).
    """
    memo = state.get("draft_memo", "")
    if not memo:
        return {"footnotes": []}

    # Use search_results (filtered, deduplicated) as primary source for footnotes,
    # with fallback to raw worker_results for citation lookup coverage
    search_results = state.get("search_results", [])
    worker_results = state.get("worker_results", [])

    # Parse [^N] references from memo
    refs_in_memo = set(re.findall(r"\[\^(\d+)\]", memo))

    # Build a lookup from citation → result metadata
    # Task 2: Include ALL source types (statute, web, community), not just case law
    citation_lookup: dict[str, dict] = {}
    # First populate from filtered search_results
    for r in search_results:
        citation = r.get("citation", "")
        if citation and citation not in citation_lookup:
            citation_lookup[citation] = r
    # Then fill gaps from raw worker_results (for citations that might have been filtered)
    for wr in worker_results:
        task_type = wr.get("task_type", "case_law")
        for r in wr.get("results", []):
            citation = r.get("citation", "")

            # Task 2: Generate synthetic keys for non-case sources
            if not citation:
                title = r.get("title", "")
                if task_type in ("statute", "constitution"):
                    # Use act + section as synthetic citation key
                    act = r.get("act_name", r.get("title", ""))
                    section = r.get("section", "")
                    citation = f"{act} Section {section}".strip() if section else act
                elif task_type == "ik_search":
                    # Indian Kanoon: synthesize citation from title + court
                    court = r.get("court", r.get("docsource", ""))
                    date = r.get("date", "")
                    if court and date:
                        citation = f"{title} ({court}, {date})"
                    elif court:
                        citation = f"{title} ({court})"
                    else:
                        citation = title
                elif task_type == "web":
                    # Use title or URL as key
                    citation = title or r.get("url", "")
                elif task_type == "graph_community":
                    citation = title or r.get("community_id", "")
                else:
                    citation = title

            if citation and citation not in citation_lookup:
                ik_doc_id = r.get("ik_doc_id", "")
                raw_url = r.get("url", r.get("source_url", ""))
                citation_lookup[citation] = {
                    "case_id": r.get("case_id"),
                    "source_type": task_type,
                    "court": r.get("court", r.get("docsource", "")),
                    "year": r.get("year"),
                    "snippet": (r.get("snippet") or r.get("ratio") or "")[:300],
                    "title": r.get("title", ""),
                    "author": r.get("author", r.get("judge", "")),
                    "bench": r.get("bench_type", ""),
                    "ik_doc_id": ik_doc_id,
                    "url": raw_url,
                }

    # Pre-build normalized index for fuzzy matching (Task 1)
    norm_index: dict[str, str] = {
        _normalize_citation(k): k for k in citation_lookup
    }

    # Extract footnote definitions from the memo itself (if LLM wrote them)
    footnote_defs: dict[int, dict] = {}
    # Pattern: [^N]: Citation text | Court, Year | Source: ... | URL
    fn_pattern = re.compile(
        r"\[\^(\d+)\]:\s*(.+?)(?:\n|$)", re.MULTILINE,
    )
    for match in fn_pattern.finditer(memo):
        fn_num = int(match.group(1))
        fn_text = match.group(2).strip()
        # Try to parse structured format: Citation | Court, Year | Source | URL
        parts = [p.strip() for p in fn_text.split("|")]
        footnote_defs[fn_num] = {
            "citation": parts[0] if parts else fn_text,
            "court_year": parts[1] if len(parts) > 1 else "",
            "source_label": parts[2] if len(parts) > 2 else "",
            "url": parts[3] if len(parts) > 3 else "",
        }

    footnotes: list[Footnote] = []
    matched_keys: set[str] = set()  # Track which citation_lookup keys were matched
    for ref_str in sorted(refs_in_memo, key=int):
        ref_num = int(ref_str)
        fn_def = footnote_defs.get(ref_num, {})
        citation = fn_def.get("citation", f"[Citation {ref_num}]")

        # Task 1: Fuzzy lookup instead of exact match
        meta = _fuzzy_lookup(citation, citation_lookup, norm_index)
        case_id = meta.get("case_id")
        ik_doc_id = meta.get("ik_doc_id", "")

        # Track matched citation_lookup key for unused-source tracking
        if meta:
            for k, v in citation_lookup.items():
                if v is meta:
                    matched_keys.add(k)
                    break

        # Task 4: Build source URL with IK URL generation
        source_url = _build_source_url(case_id, ik_doc_id, fn_def.get("url", ""))

        # Determine source type
        source_type = meta.get("source_type", "case_law")
        if "ik" in source_type or "indiankanoon" in fn_def.get("url", "").lower():
            source_type = "ik_search"

        footnotes.append(Footnote(
            number=ref_num,
            citation=citation,
            source_type=source_type,
            source_url=source_url,
            case_id=case_id,
            excerpt=meta.get("snippet", fn_def.get("citation", ""))[:300],
            is_used=True,
            verification_status="pending",
            verified_against="none",
            title=meta.get("title", fn_def.get("citation", "")),
            court=meta.get("court", ""),
            year=meta.get("year"),
            author=meta.get("author", ""),
            bench=meta.get("bench", ""),
            ik_doc_id=ik_doc_id,
            pdf_available=bool(case_id and not str(case_id).startswith("ik:")),
            source_label=_infer_source_label(source_type),
        ))

    # Add unused sources (searched but not cited)
    next_num = max((fn["number"] for fn in footnotes), default=0) + 1
    for citation, meta in citation_lookup.items():
        if citation in matched_keys:
            continue
        unused_source_type = meta.get("source_type", "case_law")
        unused_case_id = meta.get("case_id")
        unused_ik_doc_id = meta.get("ik_doc_id", "")
        footnotes.append(Footnote(
            number=next_num,
            citation=citation,
            source_type=unused_source_type,
            source_url=_build_source_url(unused_case_id, unused_ik_doc_id, meta.get("url", "")),
            case_id=unused_case_id,
            excerpt=meta.get("snippet", "")[:300],
            is_used=False,
            verification_status="pending",
            verified_against="none",
            title=meta.get("title", ""),
            court=meta.get("court", ""),
            year=meta.get("year"),
            author=meta.get("author", ""),
            bench=meta.get("bench", ""),
            ik_doc_id=unused_ik_doc_id,
            pdf_available=bool(meta.get("pdf_storage_path")),
            source_label=_infer_source_label(unused_source_type),
        ))
        next_num += 1

    return {"footnotes": footnotes}


# ---------------------------------------------------------------------------
# V2 Node: verify_citations_v2_node [Q6 + T4] — Dual-stage verification
# ---------------------------------------------------------------------------


async def verify_citations_v2_node(
    state: ResearchState,
    db: AsyncSession,
    graph_store: object | None = None,
    ik_client: object | None = None,
) -> dict:
    """[Q6] Dual-stage citation verification + [T4] zero-tolerance guardrail.

    Stage 1: Deterministic checks (regex, DB lookup, fuzzy quote match)
    Stage 2: Verify each citation against primary sources (PG → IK → Neo4j)
    Unverifiable citations are REMOVED [T4].
    """
    memo = state.get("draft_memo", "")
    footnotes = list(state.get("footnotes", []))
    extracted_passages = state.get("extracted_passages", [])

    if not memo or not footnotes:
        return {
            "footnotes": footnotes,
            "citation_verification_results": [],
            "research_audit": state.get("research_audit", {}),
        }

    # --- Stage 1: Deterministic verification [Q6] ---
    issues = await _deterministic_verify(
        memo, footnotes, extracted_passages, db, graph_store,
    )

    # --- Stage 2: Verify citations against primary sources [T4] ---
    verified_footnotes = await _verify_citations_against_sources(
        footnotes, db, ik_client, graph_store,
    )

    # Count results
    verified_count = sum(
        1 for fn in verified_footnotes
        if fn["verification_status"].startswith("verified") and fn["is_used"]
    )
    removed_count = sum(
        1 for fn in verified_footnotes
        if fn["verification_status"] == "unverified" and fn["is_used"]
    )

    # Build verification banner
    if removed_count == 0:
        banner = (
            "All citations in this memo have been verified against "
            "primary sources (PostgreSQL / Indian Kanoon / Neo4j)."
        )
    else:
        banner = (
            f"{removed_count} citation(s) could not be verified against "
            f"primary sources and have been flagged."
        )

    # Update research audit with verification info
    research_audit = dict(state.get("research_audit", {}))
    research_audit["verification_banner"] = banner
    research_audit["citations_verified"] = verified_count
    research_audit["citations_removed"] = removed_count

    # [T1] Emit verification event
    verification_event = emit_status("verification", {
        "citations_verified": verified_count,
        "citations_removed": removed_count,
        "quotes_verified": sum(
            1 for i in issues if i["type"] != "unverified_quote"
        ),
    })

    return {
        "footnotes": verified_footnotes,
        "citation_verification_results": issues,
        "research_audit": research_audit,
        "process_events": [verification_event],
    }


async def _deterministic_verify(
    memo: str,
    footnotes: list[Footnote],
    extracted_passages: list[ExtractedPassage],
    db: AsyncSession,
    graph_store: object | None = None,
) -> list[dict]:
    """[Q6] Stage 1: Instant deterministic checks — no LLM needed."""
    issues: list[dict] = []

    # 1. Footnote reference completeness: every [^N] has a footnote entry
    refs_in_memo = set(re.findall(r"\[\^(\d+)\]", memo))
    footnote_numbers = {str(f["number"]) for f in footnotes}
    for ref in refs_in_memo - footnote_numbers:
        issues.append({
            "type": "missing_footnote", "ref": ref, "severity": "HIGH",
        })

    # 2. Citation format validation: matches known Indian citation patterns
    for fn in footnotes:
        if fn["is_used"] and not _matches_indian_citation_pattern(fn["citation"]):
            issues.append({
                "type": "invalid_citation_format",
                "footnote": fn["number"],
                "citation": fn["citation"],
                "severity": "MEDIUM",
            })

    # 3. Quote verification: quoted strings in memo match extracted_passages
    quotes_in_memo = re.findall(r'"([^"]{20,})"', memo)
    passage_texts = [p["passage"] for p in extracted_passages]
    for quote in quotes_in_memo:
        if passage_texts and not any(
            _fuzzy_match(quote, p) for p in passage_texts
        ):
            issues.append({
                "type": "unverified_quote",
                "quote": quote[:100],
                "severity": "HIGH",
            })

    # 4. Overruled case check via Neo4j (if available)
    if graph_store and hasattr(graph_store, "query"):
        cited_case_ids = [
            fn["case_id"] for fn in footnotes
            if fn.get("case_id") and fn["is_used"]
        ]
        for case_id in cited_case_ids:
            try:
                overruled = await graph_store.query(
                    "MATCH (c:Case {id: $id})<-[r:CITES {treatment: 'overruled'}]"
                    "-(newer:Case) RETURN newer.title, newer.citation LIMIT 1",
                    {"id": case_id},
                )
                if overruled:
                    issues.append({
                        "type": "cites_overruled_case",
                        "case_id": case_id,
                        "overruled_by": str(overruled[0]),
                        "severity": "HIGH",
                    })
            except Exception:
                logger.warning("Overruled check failed for %s", case_id)

    # 5. URL/case_id existence validation
    for fn in footnotes:
        if (
            fn.get("case_id")
            and fn["is_used"]
            and not str(fn["case_id"]).startswith("ik:")
        ):
            try:
                exists = await db.execute(
                    text("SELECT 1 FROM cases WHERE id = :case_id::uuid"),
                    {"case_id": fn["case_id"]},
                )
                if not exists.scalar():
                    issues.append({
                        "type": "nonexistent_case_id",
                        "case_id": fn["case_id"],
                        "footnote": fn["number"],
                        "severity": "CRITICAL",
                    })
            except Exception:
                logger.warning("Case existence check failed for %s", fn.get("case_id"))

    return issues


async def _verify_citations_against_sources(
    footnotes: list[Footnote],
    db: AsyncSession,
    ik_client: object | None,
    graph_store: object | None,
) -> list[Footnote]:
    """[T4] Verify every citation against at least ONE primary source.

    [B9] Uses batch DB query for PostgreSQL verification instead of N+1.
    Falls back to IK/Neo4j for footnotes not found in PG.
    """
    # [B9] Batch PostgreSQL verification — single query for all case_ids
    pg_case_ids: list[str] = []
    for fn in footnotes:
        cid = fn.get("case_id")
        if cid and not str(cid).startswith("ik:"):
            pg_case_ids.append(str(cid))

    valid_pg_ids: set[str] = set()
    if pg_case_ids:
        try:
            from app.core.agents.nodes.common import verify_case_ids
            valid_pg_ids = await verify_case_ids(pg_case_ids, db)
        except Exception:
            logger.warning("Batch PG verification failed", exc_info=True)

    sem = asyncio.Semaphore(5)  # Max 5 concurrent IK/Neo4j verifications

    async def _verify_one(fn: Footnote) -> Footnote:
        async with sem:
            status = "unverified"

            # Check 1: PostgreSQL — use batch result
            cid = fn.get("case_id")
            if cid and str(cid) in valid_pg_ids:
                status = "verified_pg"

            # Check 2: Indian Kanoon API — use cite: filter for precision
            if status == "unverified" and ik_client and fn.get("citation"):
                try:
                    ik_results = await ik_client.search(
                        fn["citation"],
                        max_results=1,
                        cite_filter=fn["citation"],
                    )
                    if ik_results:
                        status = "verified_ik"
                except Exception:
                    pass  # IK failure is non-fatal

            # Check 3: Neo4j Case node
            if status == "unverified" and graph_store and fn.get("citation"):
                try:
                    neo4j_match = await graph_store.query(
                        "MATCH (c:Case) WHERE c.citation CONTAINS $cit "
                        "RETURN c.id LIMIT 1",
                        {"cit": fn["citation"][:30]},
                    )
                    if neo4j_match:
                        status = "verified_neo4j"
                except Exception:
                    pass  # Neo4j failure is non-fatal

            fn_copy = dict(fn)
            fn_copy["verification_status"] = status
            fn_copy["verified_against"] = (
                status.replace("verified_", "") if status != "unverified" else "none"
            )

            if status == "unverified" and fn_copy.get("is_used", False):
                fn_copy["citation"] = (
                    f"[CITATION REMOVED — unable to verify: {fn['citation']}]"
                )
                fn_copy["is_used"] = False
                logger.warning(
                    "T4 guardrail: removed unverifiable citation footnote %s: %s",
                    fn["number"], fn["citation"],
                )

            return Footnote(**fn_copy)

    return list(await asyncio.gather(*(_verify_one(fn) for fn in footnotes)))


def _matches_indian_citation_pattern(citation: str) -> bool:
    """Check if a citation matches known Indian legal citation formats."""
    patterns = [
        r"\(\d{4}\)\s+\d+\s+SCC\s+\d+",       # (YYYY) X SCC XXX
        r"AIR\s+\d{4}\s+SC\s+\d+",              # AIR YYYY SC XXX
        r"\d{4}:\w+:\d+",                         # YYYY:INSC:NNNN (neutral)
        r"\d{4}\s+SCC\s+\(Cri\)",                # SCC (Cri) sub-reporter
        r"\(\d{4}\)\s+\d+\s+SCC\s+\(Cri\)",     # (YYYY) X SCC (Cri) XXX
        r"MANU/SC/\d+/\d{4}",                     # MANU reporter
        r"Section\s+\d+",                          # Statute reference
        r"Article\s+\d+",                          # Constitutional article
    ]
    return any(re.search(p, citation) for p in patterns)


def _fuzzy_match(quote: str, passage: str, threshold: int = 85) -> bool:
    """Word + trigram fuzzy match — more accurate than character overlap.

    Three-tier matching:
    1. Exact substring check (fast path)
    2. Word-level overlap ratio (semantic accuracy)
    3. Trigram overlap (catches typos/OCR errors)
    """
    if not quote or not passage:
        return False
    # Normalize whitespace
    q = " ".join(quote.lower().split())
    p = " ".join(passage.lower().split())
    # Exact substring check (fast path)
    if q in p:
        return True
    # Word-level overlap (much more accurate than char-level)
    q_words = set(q.split())
    p_words = set(p.split())
    if not q_words:
        return False
    word_overlap = len(q_words & p_words)
    word_ratio = (word_overlap / len(q_words)) * 100
    if word_ratio >= threshold:
        return True
    # Trigram overlap as fallback for near-exact matches (typos, OCR errors)
    def _trigrams(s: str) -> set[str]:
        return {s[i:i + 3] for i in range(max(0, len(s) - 2))}
    q_tri = _trigrams(q)
    p_tri = _trigrams(p)
    if not q_tri:
        return False
    tri_ratio = (len(q_tri & p_tri) / len(q_tri)) * 100
    return tri_ratio >= threshold


# ---------------------------------------------------------------------------
# V2 Node: legal_quality_check_node [Q4] — LeMAJ-inspired verification
# ---------------------------------------------------------------------------


async def legal_quality_check_node(
    state: ResearchState,
    llm: LLMProvider,
) -> dict:
    """[Q4] LeMAJ-inspired legal reasoning verification.

    Decomposes memo into Legal Data Points, checks each against evidence.
    If overall_quality < 0.7, HITL checkpoint will show specific issues.
    """
    memo = state.get("draft_memo", "")
    if not memo:
        return {
            "legal_quality_result": LegalQualityResult(
                overall_score=0.0,
                data_points=[],
                omissions=[],
                logical_issues=["No memo to evaluate"],
                pass_threshold=False,
            ),
        }

    # Flatten evidence for context
    worker_results = state.get("worker_results", [])
    all_evidence: list[dict] = []
    for wr in worker_results:
        all_evidence.extend(wr.get("results", []))
    evidence = format_search_results_for_llm_extended(all_evidence[:30])

    try:
        result = await llm.generate_structured(
            prompt=f"MEMO:\n{memo}\n\nEVIDENCE:\n{evidence}",
            system=LEGAL_QUALITY_CHECK_SYSTEM,
            output_schema=LEGAL_QUALITY_CHECK_SCHEMA,
        )
    except Exception as exc:
        logger.warning("Legal quality check failed: %s", exc)
        return {
            "legal_quality_result": LegalQualityResult(
                overall_score=0.5,
                data_points=[],
                omissions=[],
                logical_issues=[f"Quality check failed: {exc}"],
                pass_threshold=False,
            ),
        }

    quality_result = LegalQualityResult(
        overall_score=result.get("overall_score", 0.0),
        data_points=result.get("data_points", []),
        omissions=result.get("omissions", []),
        logical_issues=result.get("logical_issues", []),
        pass_threshold=result.get("overall_score", 0.0) >= 0.7,
    )

    # [B3] Increment quality attempts counter
    attempts = state.get("quality_attempts", 0) + 1

    # [T1] Emit quality event
    quality_event = emit_status("quality", {
        "overall_score": quality_result["overall_score"],
        "pass_threshold": quality_result["pass_threshold"],
        "data_points_count": len(quality_result["data_points"]),
        "omissions_count": len(quality_result["omissions"]),
        "logical_issues_count": len(quality_result["logical_issues"]),
        "attempt": attempts,
    })

    result: dict = {
        "legal_quality_result": quality_result,
        "quality_attempts": attempts,
        "process_events": [quality_event],
    }

    # [B3] On failure, append quality feedback for retry synthesis
    if not quality_result["pass_threshold"] and attempts < 2:
        feedback_parts: list[str] = []
        if quality_result["logical_issues"]:
            feedback_parts.append(
                "Logical issues: " + "; ".join(quality_result["logical_issues"])
            )
        if quality_result["omissions"]:
            omission_strs = [
                o.get("missed_authority", "unknown") for o in quality_result["omissions"]
            ]
            feedback_parts.append("Omitted authorities: " + ", ".join(omission_strs))
        unsupported = [
            dp.get("claim", "?") for dp in quality_result["data_points"]
            if not dp.get("supported", True)
        ]
        if unsupported:
            feedback_parts.append("Unsupported claims: " + "; ".join(unsupported[:5]))
        if feedback_parts:
            result["error"] = "[QUALITY_RETRY] " + " | ".join(feedback_parts)

    return result


# ---------------------------------------------------------------------------
# Helper functions for synthesis post-processing
# ---------------------------------------------------------------------------


def _build_source_attribution(all_results: list[dict]) -> dict:
    """Build source attribution mapping: citation → metadata."""
    attribution: dict[str, dict] = {}
    for r in all_results:
        citation = r.get("citation", "")
        if citation and citation not in attribution:
            # Build correct URL based on source type
            case_id = r.get("case_id", "")
            if case_id and str(case_id).startswith("ik:"):
                ik_doc_id = r.get("ik_doc_id", str(case_id).removeprefix("ik:"))
                url = f"https://indiankanoon.org/doc/{ik_doc_id}/"
            elif case_id:
                url = f"/case/{case_id}"
            else:
                url = r.get("url", r.get("source_url", ""))
            attribution[citation] = {
                "source_type": r.get("source", "internal"),
                "case_id": case_id,
                "url": url,
                "court": r.get("court", ""),
                "year": r.get("year"),
            }
    return attribution


def _build_research_audit(state: ResearchState, all_results: list[dict]) -> dict:
    """Build research audit trail metadata."""
    worker_results = state.get("worker_results", [])

    # Count unique sources by type
    source_counts: dict[str, int] = {}
    for wr in worker_results:
        task_type = wr.get("task_type", "unknown")
        source_counts[task_type] = source_counts.get(task_type, 0) + len(
            wr.get("results", []),
        )

    total_sources = len(all_results)
    # cited count will be updated after footnotes are generated
    return {
        "total_sources_searched": total_sources,
        "sources_cited": 0,  # Updated by format_footnotes_node
        "sources_unused": total_sources,
        "searches_executed": len(worker_results),
        "refinement_rounds": state.get("refinement_round", 0),
        "source_counts": source_counts,
        "deep_reads_performed": sum(
            1 for s in state.get("relevance_scores", [])
            if "[deep_read]" in s.get("reason", "")
        ),
        "strategy_pivots": 1 if state.get("strategy_adjustment") else 0,
    }


# ---------------------------------------------------------------------------
# [V3] Adversarial search — find cases AGAINST the emerging conclusion
# ---------------------------------------------------------------------------


async def _run_adversarial_search(
    counter_args: list[dict],
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
) -> list[dict]:
    """Execute searches for each counter-argument query in parallel.

    [B5] Uses asyncio.gather() instead of sequential loop — saves ~16s
    (3 searches × ~8s each → ~8s total).
    """
    from app.core.agents.nodes.worker_nodes import case_law_worker

    async def _search_one(ca: dict) -> list[dict]:
        task = {
            "task_id": f"adversarial_{ca.get('priority', 0)}",
            "task_type": ca.get("target_source", "case_law"),
            "nl_query": ca["search_query"],
            "boolean_query": ca.get("boolean_query", ""),
            "named_cases": [],
            "rationale": f"Adversarial: {ca['counter_thesis']}",
            "filters": {},
            "priority": 1,
        }
        try:
            worker_result = await case_law_worker(
                {"task": task, "precomputed_embeddings": {}},
                llm, embedder, vector_store, reranker,
            )
            one_results: list[dict] = []
            for wr in worker_result.get("worker_results", []):
                wr["metadata"] = {**wr.get("metadata", {}), "adversarial": True}
                wr["reasoning"] = f"Counter-argument: {ca['counter_thesis']}"
                one_results.append(wr)
            return one_results
        except Exception as exc:
            logger.warning(
                "Adversarial search failed for %s: %s",
                ca["counter_thesis"][:50], exc,
            )
            return []

    all_results = await asyncio.gather(
        *[_search_one(ca) for ca in counter_args[:3]],
    )
    return [wr for batch in all_results for wr in batch]


async def adversarial_search_node(
    state: dict,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
) -> dict:
    """[V3 Stage 4] Find cases AGAINST the emerging conclusion.

    Only runs when state["include_adversarial"] is True (user-toggled at HITL).
    Generates counter-argument queries via LLM and dispatches to case_law_worker.
    Results are tagged with metadata.adversarial=True.
    """
    if not state.get("include_adversarial", False):
        return {}

    worker_results = state.get("worker_results", [])
    elements = state.get("legal_elements", [])
    reasonings = state.get("worker_reasonings", [])
    query = state.get("rewritten_query", "") or state.get("query", "")

    # Summarize findings for the adversarial LLM
    findings_summary: list[str] = []
    for wr in worker_results[:10]:
        if isinstance(wr, dict):
            for r in wr.get("results", [])[:3]:
                findings_summary.append(
                    f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}"
                )

    user_prompt = (
        f"## Research Question\n{query}\n\n"
        f"## Current Findings\n" + "\n".join(findings_summary[:20]) + "\n\n"
        f"## Worker Reasoning\n" + "\n".join(reasonings[:3]) + "\n\n"
        "Generate counter-arguments."
    )

    try:
        result = await llm.generate_structured(
            user_prompt,
            system=ADVERSARIAL_SEARCH_SYSTEM,
            output_schema=ADVERSARIAL_SEARCH_SCHEMA,
        )
        counter_args = result.get("counter_arguments", [])
    except Exception as exc:
        logger.warning("Adversarial search LLM call failed: %s", exc)
        return {}

    if not counter_args:
        return {}

    adv_results = await _run_adversarial_search(
        counter_args, llm, embedder, vector_store, reranker,
    )
    return {"worker_results": adv_results} if adv_results else {}


# ---------------------------------------------------------------------------
# [V3] Temporal validation — deterministic old/new code comparison
# ---------------------------------------------------------------------------


def _text_similarity(a: str, b: str) -> float:
    """Compute normalized text similarity between two strings."""
    if not a or not b:
        return 0.0
    a_norm = " ".join(a.lower().split())
    b_norm = " ".join(b.lower().split())
    return SequenceMatcher(None, a_norm, b_norm).ratio()


async def temporal_validation_node(state: dict) -> dict:
    """[V3 Stage 4] Check old-code cases against new-code wording.

    Deterministic — no LLM call. Compares statute text between old and new codes.
    Warns when the wording has materially changed (similarity < 0.8).
    """
    statute_context = state.get("statute_context", [])
    warnings: list[dict] = []

    for s in statute_context:
        if not s.get("is_repealed") or not s.get("new_code_text"):
            continue

        old_text = s.get("section_text", "")
        new_text = s.get("new_code_text", "")

        if not old_text or not new_text:
            continue

        similarity = _text_similarity(old_text, new_text)
        if similarity < 0.8:
            warnings.append({
                "case_id": "",
                "case_citation": "",
                "old_section": f"{s['act_short_name']} {s['section_number']}",
                "new_section": s.get("replaced_by", ""),
                "similarity": round(similarity, 2),
                "warning": (
                    f"{s['act_short_name']} Section {s['section_number']} wording "
                    f"changed ({similarity:.0%} similar to new code). "
                    f"Cases interpreting the old section may not apply directly."
                ),
            })

    return {"temporal_warnings": warnings}
