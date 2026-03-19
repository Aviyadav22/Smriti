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
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.confidence import calculate_confidence
from app.core.legal.precedent_strength import classify_precedent_strength
from app.core.agents.nodes.common import (
    MAX_RESULTS_FOR_LLM,
    deduplicate_with_diversity,
    enrich_results_with_ratio,
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
    RelevanceScore,
    ResearchState,
    ResearchTask,
    StrategyAdjustment,
    WorkerResult,
)
from app.core.interfaces import EmbeddingProvider, LLMProvider, Reranker, VectorStore
from app.core.legal.prompts import (
    BATCH_COT_WITH_REFLECTION_SCHEMA,
    EVALUATE_AND_EXTRACT_SCHEMA,
    LEGAL_DISCLAIMER,
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
)
from app.security.sanitizer import sanitize_search_query

logger = logging.getLogger(__name__)


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
        sub_queries, llm, embedder, vector_store, reranker, db
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
        findings=findings,
        contradictions=contradictions_text,
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

    prompt = (
        f"Create a research plan for the following legal question.\n\n"
        f"Research Question: {query}\n\n"
        f"Classification: {classification_str}\n\n"
        f"Generate 3-8 typed research tasks with dual queries and named cases."
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

    return {
        "research_plan": tasks,
        "sub_queries": sub_queries,
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

    return {
        "search_results": deduped,
        "cross_references": cross_refs,
    }


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

    return {
        "worker_reasonings": [response.get("reasoning", "")],
        "strategy_adjustment": strategy_adj,
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
) -> dict:
    """Merged CRAG relevance scoring + passage extraction + deep read.

    [S3] Combines CRAG and extract into ONE Flash call per batch.
    [Q2] For "ambiguous" results, fetches full HOLDINGS/RATIO sections
    from case_sections table before final verdict.
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

    # [Q2] Deep read helper
    async def deep_read_sections(case_id: str) -> str:
        """Fetch HOLDINGS + RATIO from case_sections for deeper evaluation."""
        if case_id.startswith("ik:"):
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

    return {
        "relevance_scores": relevance_scores,
        "extracted_passages": extracted_passages,
        "worker_results": filtered_worker_results,
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
        }

    return {"evidence_gaps": gaps, "refinement_round": refinement_round}


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

    try:
        memo = await llm.generate(
            prompt=(
                f"Research Question: {query}\n\n"
                f"Search Results:\n{findings}\n\n"
                "Write a concise research response with footnotes."
            ),
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


