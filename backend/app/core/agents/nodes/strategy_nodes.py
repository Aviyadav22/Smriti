"""Strategy Agent node functions for LangGraph.

Each node function takes the StrategyState as its first argument plus
injected dependencies, performs a single focused operation, and returns
a partial state dict for LangGraph to merge.  Dependencies (llm, db, etc.)
are passed via closures when the graph is built.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import async_session_factory

from app.core.agents.confidence import calculate_confidence
from app.core.agents.nodes.common import (
    MAX_RESULTS_FOR_LLM,
    apply_language_suffix,
    collect_grounding_citations,
    deduplicate_by_case_id,
    detect_overruled_cases,
    enrich_results_with_ratio,
    get_citation_neighbors,
    get_latest_feedback,
    parallel_hybrid_search,
    verify_memo_citations,
)
from app.core.agents.state import StrategyState
from app.core.interfaces import (
    EmbeddingProvider,
    GraphStore,
    LLMProvider,
    Reranker,
    VectorStore,
)
from app.core.legal.precedent_strength import classify_precedent_strength
from app.core.legal.prompts import (
    LEGAL_DISCLAIMER,
    STRATEGY_ADVERSARIAL_SCHEMA,
    STRATEGY_ADVERSARIAL_SYSTEM,
    STRATEGY_ANALYZE_FACTS_SCHEMA,
    STRATEGY_ANALYZE_FACTS_SYSTEM,
    STRATEGY_ARGUMENT_MEMO_SYSTEM,
    STRATEGY_ARGUMENT_MEMO_USER,
    STRATEGY_ARGUMENT_ORDERING_SCHEMA,
    STRATEGY_ARGUMENT_ORDERING_SYSTEM,
    STRATEGY_ARGUMENTS_SCHEMA,
    STRATEGY_ARGUMENTS_SYSTEM,
    STRATEGY_ASSESS_STRENGTH_SCHEMA,
    STRATEGY_ASSESS_STRENGTH_SYSTEM,
    STRATEGY_COUNTER_ARGS_SCHEMA,
    STRATEGY_COUNTER_ARGS_SYSTEM,
    STRATEGY_IRAC_ARGUMENTS_SCHEMA,
    STRATEGY_IRAC_ARGUMENTS_SYSTEM,
    STRATEGY_JUDGE_ANALYSIS_SCHEMA,
    STRATEGY_JUDGE_ANALYSIS_SYSTEM,
    RESEARCH_CONTRADICTIONS_SYSTEM,
)
from app.security.sanitizer import sanitize_search_query

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node 1: analyze_facts_node
# ---------------------------------------------------------------------------


async def analyze_facts_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """Parse case facts into structured form (parties, causes of action, etc.)."""
    case_facts = sanitize_search_query(state["case_facts"])

    prompt = case_facts

    feedback = get_latest_feedback(state.get("messages", []), "analysis")
    if feedback:
        sanitized = sanitize_search_query(feedback)
        prompt += f"\n\nUser revision request: {sanitized}\nPlease address this feedback."

    try:
        fact_analysis = await llm.generate_structured(
            prompt=prompt,
            system=STRATEGY_ANALYZE_FACTS_SYSTEM,
            output_schema=STRATEGY_ANALYZE_FACTS_SCHEMA,
        )
    except Exception as e:
        logger.error("LLM error in analyze_facts_node: %s", e, exc_info=True)
        return {"error": f"LLM error in analyze_facts_node: {e!s}"}

    return {"fact_analysis": fact_analysis}


# ---------------------------------------------------------------------------
# Node 2: fetch_judge_profile_node
# ---------------------------------------------------------------------------


async def fetch_judge_profile_node(
    state: StrategyState,
    db: AsyncSession,
) -> dict:
    """Fetch judge profile data from PostgreSQL for strategy personalisation.

    If no target_judge is set, returns an empty profile.
    """
    target_judge = (state.get("target_judge") or "").strip()
    if not target_judge:
        return {"judge_profile": {}}

    sanitized_judge = sanitize_search_query(target_judge)

    # Use ILIKE for fuzzy matching since judge names vary in format
    # (e.g., "B.R. Gavai", "gavai", "Justice Gavai")
    judge_pattern = f"%{sanitized_judge}%"

    try:
        # Disposal breakdown
        disposal_result = await db.execute(
            sa_text(
                "SELECT disposal_nature, COUNT(*) as cnt "
                "FROM cases "
                "WHERE array_to_string(judge, ' ') ILIKE :judge_pattern "
                "GROUP BY disposal_nature "
                "ORDER BY cnt DESC"
            ),
            {"judge_pattern": judge_pattern},
        )
        disposal_breakdown = [
            {"disposal_nature": row[0], "count": row[1]}
            for row in disposal_result.fetchall()
        ]

        # Top acts cited
        acts_result = await db.execute(
            sa_text(
                "SELECT act, COUNT(*) as cnt "
                "FROM cases, unnest(acts_cited) as act "
                "WHERE array_to_string(judge, ' ') ILIKE :judge_pattern "
                "GROUP BY act "
                "ORDER BY cnt DESC "
                "LIMIT 10"
            ),
            {"judge_pattern": judge_pattern},
        )
        top_acts = [
            {"act": row[0], "count": row[1]}
            for row in acts_result.fetchall()
        ]

        # Total and recent case counts
        counts_result = await db.execute(
            sa_text(
                "SELECT COUNT(*) as total, "
                "COUNT(*) FILTER (WHERE year >= EXTRACT(YEAR FROM NOW()) - 3) as recent "
                "FROM cases "
                "WHERE array_to_string(judge, ' ') ILIKE :judge_pattern"
            ),
            {"judge_pattern": judge_pattern},
        )
        counts_row = counts_result.fetchone()
        total_cases = counts_row[0] if counts_row else 0
        recent_cases = counts_row[1] if counts_row else 0

        profile = {
            "name": target_judge,
            "disposal_breakdown": disposal_breakdown,
            "top_acts": top_acts,
            "total_cases": total_cases,
            "recent_cases": recent_cases,
        }

        return {"judge_profile": profile}

    except Exception:
        logger.warning(
            "Failed to fetch judge profile for '%s'", target_judge, exc_info=True
        )
        return {"judge_profile": {}}


# ---------------------------------------------------------------------------
# Node 3: search_precedents_node
# ---------------------------------------------------------------------------


async def search_precedents_node(
    state: StrategyState,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    graph_store: GraphStore,
    db: AsyncSession,
) -> dict:
    """Run hybrid search for each cause of action and build precedent map.

    1. Generate search queries from causes of action + general case facts.
    2. Run hybrid_search for each query in parallel.
    3. For top results, get 2-hop citation neighbours from graph_store.
    4. Enrich with ratio, detect treatment warnings, classify strength.
    5. Build precedent_map with per-result metadata.
    """
    fact_analysis = state.get("fact_analysis", {})
    causes_of_action = fact_analysis.get("causes_of_action", [])
    case_facts = state.get("case_facts", "")
    target_court = state.get("target_court") or "Supreme Court of India"
    target_bench = state.get("target_bench") or "division"

    # Build search queries: one per cause of action + 1-2 general queries
    queries: list[str] = []
    for coa in causes_of_action:
        title = coa.get("title", "")
        statutory_basis = coa.get("statutory_basis", "")
        query = f"{title} {statutory_basis}".strip()
        if query:
            queries.append(query)

    # Add general queries from case facts (first 200 chars as summary)
    if case_facts:
        general_query = case_facts[:200].strip()
        queries.append(general_query)

    # Add relief-based query if desired_relief is specified
    desired_relief = state.get("desired_relief", "")
    if desired_relief:
        queries.append(f"{sanitize_search_query(desired_relief)} Indian court precedent")

    # Deduplicate queries while preserving order
    queries = list(dict.fromkeys(queries))

    if not queries:
        return {"search_results": [], "precedent_map": []}

    # Parallel hybrid search
    combined = await parallel_hybrid_search(
        queries,
        llm=llm,
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        db=db,
    )

    # Deduplicate by case_id, keeping highest score
    combined = deduplicate_by_case_id(combined)

    # Enrich with ratio and bench_type from PostgreSQL
    combined = await enrich_results_with_ratio(combined, db)

    # Get 2-hop citation neighbours for top 5 results
    top_results = sorted(combined, key=lambda r: r.get("score", 0), reverse=True)[:5]
    seen_ids: set[str] = {r.get("case_id", "") for r in combined}

    neighbor_results = await get_citation_neighbors(
        graph_store, top_results, seen_ids, max_results=5
    )
    combined.extend(neighbor_results)

    # Detect overruling language
    overruled_case_ids = detect_overruled_cases(combined)

    # Build precedent_map
    precedent_map: list[dict] = []
    for r in combined:
        cid = r.get("case_id", "")
        bench = r.get("bench_type")
        court = r.get("court", "")
        is_overruled = cid in overruled_case_ids

        strength = "UNKNOWN"
        if bench and court:
            strength = classify_precedent_strength(
                source_court=court,
                source_bench=bench,
                target_court=target_court,
                target_bench=target_bench,
                overruled=is_overruled,
            ).value

        precedent_map.append({
            "case_id": cid,
            "title": r.get("title"),
            "citation": r.get("citation"),
            "court": court,
            "bench_type": bench,
            "strength": strength,
            "is_overruled": is_overruled,
            "ratio": r.get("ratio", ""),
            "relevance_to_argument": r.get("source_query", ""),
        })

    return {"search_results": combined, "precedent_map": precedent_map}


# ---------------------------------------------------------------------------
# Node 4: assess_strength_node
# ---------------------------------------------------------------------------


async def assess_strength_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """Assess overall case strength based on facts, precedents, and judge profile."""
    fact_analysis = state.get("fact_analysis", {})
    precedent_map = state.get("precedent_map", [])
    judge_profile = state.get("judge_profile", {})

    prompt = (
        "Assess the strength of the following case.\n\n"
        f"Fact Analysis:\n{json.dumps(fact_analysis, indent=2)}\n\n"
        f"Precedent Map ({len(precedent_map)} precedents):\n"
        f"{json.dumps(precedent_map[:MAX_RESULTS_FOR_LLM], indent=2)}\n\n"
    )
    if judge_profile:
        prompt += f"Judge Profile:\n{json.dumps(judge_profile, indent=2)}\n\n"

    try:
        strength_assessment = await llm.generate_structured(
            prompt=prompt,
            system=STRATEGY_ASSESS_STRENGTH_SYSTEM,
            output_schema=STRATEGY_ASSESS_STRENGTH_SCHEMA,
        )
    except Exception as e:
        logger.error("LLM error in assess_strength_node: %s", e, exc_info=True)
        return {"error": f"LLM error in assess_strength_node: {e!s}"}

    return {"strength_assessment": strength_assessment}


# ---------------------------------------------------------------------------
# Node 5: generate_arguments_node
# ---------------------------------------------------------------------------


async def generate_arguments_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """Generate ordered legal arguments with supporting precedents."""
    fact_analysis = state.get("fact_analysis", {})
    precedent_map = state.get("precedent_map", [])
    strength_assessment = state.get("strength_assessment", {})
    desired_relief = state.get("desired_relief", "")

    prompt = (
        "Generate legal arguments for the following case.\n\n"
        f"Fact Analysis:\n{json.dumps(fact_analysis, indent=2)}\n\n"
        f"Precedent Map ({len(precedent_map)} precedents):\n"
        f"{json.dumps(precedent_map[:MAX_RESULTS_FOR_LLM], indent=2)}\n\n"
        f"Strength Assessment:\n{json.dumps(strength_assessment, indent=2)}\n\n"
    )
    if desired_relief:
        prompt += f"Desired Relief: {sanitize_search_query(desired_relief)}\n\n"

    feedback = get_latest_feedback(state.get("messages", []), "arguments")
    if feedback:
        sanitized = sanitize_search_query(feedback)
        prompt += f"\n\nUser revision request: {sanitized}\nPlease address this feedback."

    try:
        result = await llm.generate_structured(
            prompt=prompt,
            system=STRATEGY_ARGUMENTS_SYSTEM,
            output_schema=STRATEGY_ARGUMENTS_SCHEMA,
        )
    except Exception as e:
        logger.error("LLM error in generate_arguments_node: %s", e, exc_info=True)
        return {"error": f"LLM error in generate_arguments_node: {e!s}"}

    return {"legal_arguments": result.get("arguments", [])}


# ---------------------------------------------------------------------------
# Node 5b: generate_arguments_irac_node
# ---------------------------------------------------------------------------


async def generate_arguments_irac_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """Generate IRAC-structured legal arguments with authority ranking."""
    fact_analysis = state.get("fact_analysis", {})
    legal_elements = state.get("legal_elements", [])
    precedent_map = state.get("precedent_map", [])
    strength_assessment = state.get("strength_assessment", {})
    desired_relief = state.get("desired_relief", "")

    prompt = (
        "Generate IRAC-structured legal arguments.\n\n"
        f"Fact Analysis:\n{json.dumps(fact_analysis, indent=2)}\n\n"
        f"Legal Elements:\n{json.dumps(legal_elements, indent=2)}\n\n"
        f"Precedent Map ({len(precedent_map)} precedents):\n"
        f"{json.dumps(precedent_map[:MAX_RESULTS_FOR_LLM], indent=2)}\n\n"
        f"Strength Assessment:\n{json.dumps(strength_assessment, indent=2)}\n\n"
    )
    if desired_relief:
        prompt += f"Desired Relief: {sanitize_search_query(desired_relief)}\n\n"

    feedback = get_latest_feedback(state.get("messages", []), "arguments")
    if feedback:
        prompt += f"\n\nUser revision request: {sanitize_search_query(feedback)}\nPlease address."

    try:
        result = await llm.generate_structured(
            prompt=prompt,
            system=STRATEGY_IRAC_ARGUMENTS_SYSTEM,
            output_schema=STRATEGY_IRAC_ARGUMENTS_SCHEMA,
        )
    except Exception as e:
        logger.error("LLM error in generate_arguments_irac_node: %s", e, exc_info=True)
        return {"error": f"LLM error in generate_arguments_irac_node: {e!s}"}

    irac_args = result.get("irac_arguments", [])
    if not isinstance(irac_args, list):
        irac_args = []

    # Also set legacy legal_arguments for backward compatibility with counter_arguments_node
    legacy_args = [
        {
            "title": a.get("title", ""),
            "statutory_basis": a.get("statutory_basis", ""),
            "supporting_precedents": [auth.get("citation", "") for auth in a.get("rule_authorities", [])],
            "effectiveness_score": a.get("effectiveness_score", 5),
            "reasoning": a.get("application", ""),
        }
        for a in irac_args
    ]

    return {"irac_arguments": irac_args, "legal_arguments": legacy_args}


# ---------------------------------------------------------------------------
# Node 5c: adversarial_search_strategy_node
# ---------------------------------------------------------------------------


async def adversarial_search_strategy_node(
    state: StrategyState,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
) -> dict:
    """Search for cases OPPOSING the client's position."""
    irac_arguments = state.get("irac_arguments", [])
    fact_analysis = state.get("fact_analysis", {})

    if not irac_arguments:
        return {"adversarial_results": []}

    # Summarize arguments for adversarial query generation
    args_summary = "\n".join(
        f"- {a.get('title', '')}: {a.get('conclusion', '')}"
        for a in irac_arguments[:5]
    )

    prompt = (
        f"## Client's Arguments\n{args_summary}\n\n"
        f"## Fact Analysis\n{json.dumps(fact_analysis, indent=2)}\n\n"
        "Generate counter-argument search queries."
    )

    try:
        result = await llm.generate_structured(
            prompt=prompt,
            system=STRATEGY_ADVERSARIAL_SYSTEM,
            output_schema=STRATEGY_ADVERSARIAL_SCHEMA,
        )
        counter_queries = result.get("counter_queries", [])
    except Exception as e:
        logger.warning("Adversarial search LLM failed: %s", e)
        return {"adversarial_results": []}

    if not counter_queries:
        return {"adversarial_results": []}

    # Run all counter-query searches in parallel
    valid_queries = [(cq, cq.get("query", "")) for cq in counter_queries[:5] if cq.get("query", "").strip()]
    if not valid_queries:
        return {"adversarial_results": []}

    async def _search_one(cq: dict, query_text: str) -> list[dict]:
        try:
            async with async_session_factory() as session:
                results = await parallel_hybrid_search(
                    queries=[query_text],
                    llm=llm,
                    embedder=embedder,
                    vector_store=vector_store,
                    reranker=reranker,
                    db=session,
                )
            tagged: list[dict] = []
            for r in results[:3]:
                r["adversarial"] = True
                r["target_weakness"] = cq.get("target_weakness", "")
                tagged.append(r)
            return tagged
        except Exception as e:
            logger.warning("Adversarial search failed for query '%s': %s", query_text[:50], e)
            return []

    batch_results = await asyncio.gather(
        *[_search_one(cq, qt) for cq, qt in valid_queries],
        return_exceptions=False,
    )
    all_results: list[dict] = []
    for batch in batch_results:
        all_results.extend(batch)

    return {"adversarial_results": all_results}


# ---------------------------------------------------------------------------
# Node 5d: argument_ordering_node
# ---------------------------------------------------------------------------


async def argument_ordering_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """Determine optimal argument presentation order."""
    irac_arguments = state.get("irac_arguments", [])
    judge_profile = state.get("judge_profile", {})
    strength_assessment = state.get("strength_assessment", {})

    if not irac_arguments:
        return {"argument_order": []}

    args_summary = json.dumps([
        {
            "index": i,
            "title": a.get("title", ""),
            "statutory_basis": a.get("statutory_basis", ""),
            "effectiveness_score": a.get("effectiveness_score", 0),
        }
        for i, a in enumerate(irac_arguments)
    ], indent=2)

    prompt = (
        f"## Arguments to Order\n{args_summary}\n\n"
        f"## Judge Profile\n{json.dumps(judge_profile, indent=2)}\n\n"
        f"## Strength Assessment\n{json.dumps(strength_assessment, indent=2)}\n\n"
        "Determine the optimal presentation order."
    )

    try:
        result = await llm.generate_structured(
            prompt=prompt,
            system=STRATEGY_ARGUMENT_ORDERING_SYSTEM,
            output_schema=STRATEGY_ARGUMENT_ORDERING_SCHEMA,
        )
        ordered_indices = result.get("ordered_indices", list(range(len(irac_arguments))))
    except Exception as e:
        logger.warning("Argument ordering failed: %s — using effectiveness order", e)
        ordered_indices = sorted(
            range(len(irac_arguments)),
            key=lambda i: irac_arguments[i].get("effectiveness_score", 0),
            reverse=True,
        )

    return {"argument_order": ordered_indices}


# ---------------------------------------------------------------------------
# Node 6: counter_arguments_node
# ---------------------------------------------------------------------------


async def counter_arguments_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """Anticipate opposing counsel's counter-arguments with rebuttals."""
    fact_analysis = state.get("fact_analysis", {})
    legal_arguments = state.get("legal_arguments", [])
    precedent_map = state.get("precedent_map", [])
    adversarial_results = state.get("adversarial_results", [])

    # Build combined citation pool (precedent_map + adversarial results)
    all_precedents = list(precedent_map[:MAX_RESULTS_FOR_LLM])
    for ar in adversarial_results:
        all_precedents.append({
            "title": ar.get("title", ""),
            "citation": ar.get("citation", ""),
            "ratio": ar.get("chunk_text", "") or ar.get("snippet", ""),
            "strength": ar.get("strength", "UNKNOWN"),
            "adversarial": True,
        })

    # Build set of known citations for post-generation grounding check
    known_citations: set[str] = set()
    for p in all_precedents:
        title = (p.get("title") or "").upper().strip()
        citation = (p.get("citation") or "").strip()
        if title:
            known_citations.add(title[:40])
        if citation:
            known_citations.add(citation)

    prompt = (
        "Identify the most likely counter-arguments the opposing side will raise.\n\n"
        f"Fact Analysis:\n{json.dumps(fact_analysis, indent=2)}\n\n"
        f"Client's Arguments:\n{json.dumps(legal_arguments, indent=2)}\n\n"
        f"Available Precedents ({len(all_precedents)} cases — use ONLY these):\n"
        f"{json.dumps(all_precedents[:MAX_RESULTS_FOR_LLM], indent=2)}\n\n"
        "Order by impact (most dangerous first)."
    )

    try:
        result = await llm.generate_structured(
            prompt=prompt,
            system=STRATEGY_COUNTER_ARGS_SYSTEM,
            output_schema=STRATEGY_COUNTER_ARGS_SCHEMA,
        )
    except Exception as e:
        logger.error("LLM error in counter_arguments_node: %s", e, exc_info=True)
        return {"error": f"LLM error in counter_arguments_node: {e!s}"}

    counter_arguments = result.get("counter_arguments", [])
    if not isinstance(counter_arguments, list):
        counter_arguments = []

    # Post-generation grounding: flag citations not in our precedent pool
    for ca in counter_arguments:
        for field in ("likely_precedents", "rebuttal_precedents"):
            grounded: list[str] = []
            for cite in ca.get(field, []):
                cite_upper = cite.upper().strip()[:40]
                is_grounded = any(cite_upper[:25] in kc for kc in known_citations)
                if is_grounded:
                    grounded.append(cite)
                else:
                    logger.warning(
                        "Ungrounded citation in counter_arguments stripped: %s", cite[:80]
                    )
            ca[field] = grounded

    return {"counter_arguments": counter_arguments}


# ---------------------------------------------------------------------------
# Node 7: judge_considerations_node
# ---------------------------------------------------------------------------


async def judge_considerations_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """Generate judge-specific strategic considerations.

    If no judge profile is available, returns generic bench-type considerations.
    """
    judge_profile = state.get("judge_profile", {})
    legal_arguments = state.get("legal_arguments", [])
    strength_assessment = state.get("strength_assessment", {})
    target_bench = state.get("target_bench", "")

    if not judge_profile:
        # Return generic bench-type considerations
        bench_label = target_bench or "unknown bench type"
        return {
            "judge_considerations": [
                {
                    "insight": (
                        f"No specific judge profile available. Prepare arguments "
                        f"suitable for a {bench_label} bench with standard "
                        f"procedural expectations."
                    ),
                    "source": "generic",
                },
            ],
            "procedural_suggestions": [
                "Prepare comprehensive written submissions to supplement oral arguments.",
                "Ensure all cited precedents are from authoritative sources with correct citations.",
                "File a compilation of cited judgments in advance.",
            ],
        }

    prompt = (
        "Generate judge-specific strategic insights and procedural suggestions.\n\n"
        f"Judge Profile:\n{json.dumps(judge_profile, indent=2)}\n\n"
        f"Client's Arguments:\n{json.dumps(legal_arguments, indent=2)}\n\n"
        f"Strength Assessment:\n{json.dumps(strength_assessment, indent=2)}\n\n"
    )

    try:
        parsed = await llm.generate_structured(
            prompt=prompt,
            system=STRATEGY_JUDGE_ANALYSIS_SYSTEM,
            output_schema=STRATEGY_JUDGE_ANALYSIS_SCHEMA,
        )
    except Exception as e:
        logger.error("LLM error in judge_considerations_node: %s", e, exc_info=True)
        return {"error": f"LLM error in judge_considerations_node: {e!s}"}

    if not isinstance(parsed, dict):
        parsed = {}

    judge_considerations = parsed.get("strategic_insights", [])
    procedural_suggestions = parsed.get("procedural_suggestions", [])

    # Ensure list types
    if not isinstance(judge_considerations, list):
        judge_considerations = []
    if not isinstance(procedural_suggestions, list):
        procedural_suggestions = []

    return {
        "judge_considerations": judge_considerations,
        "procedural_suggestions": procedural_suggestions,
    }


# ---------------------------------------------------------------------------
# Node 8: synthesize_strategy_node
# ---------------------------------------------------------------------------


async def synthesize_strategy_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """Synthesize all analysis into a comprehensive argument memo."""
    case_facts = sanitize_search_query(state.get("case_facts", ""))
    legal_elements = state.get("legal_elements", [])
    strength_assessment = state.get("strength_assessment", {})
    irac_arguments = state.get("irac_arguments", [])
    argument_order = state.get("argument_order", [])
    counter_arguments = state.get("counter_arguments", [])
    adversarial_results = state.get("adversarial_results", [])
    judge_considerations = state.get("judge_considerations", [])
    procedural_suggestions = state.get("procedural_suggestions", [])
    search_results = state.get("search_results", [])
    precedent_map = state.get("precedent_map", [])

    # Order irac_arguments using argument_order
    if argument_order:
        ordered_args = [irac_arguments[i] for i in argument_order if 0 <= i < len(irac_arguments)]
    else:
        ordered_args = irac_arguments

    prompt = STRATEGY_ARGUMENT_MEMO_USER.format(
        case_facts=case_facts,
        legal_elements=json.dumps(legal_elements, indent=2),
        strength_assessment=json.dumps(strength_assessment, indent=2),
        irac_arguments=json.dumps(ordered_args, indent=2),
        counter_arguments=json.dumps(counter_arguments, indent=2),
        adversarial_results=json.dumps(adversarial_results, indent=2),
        judge_considerations=json.dumps(judge_considerations, indent=2),
        procedural_suggestions=json.dumps(procedural_suggestions, indent=2),
    )

    feedback = get_latest_feedback(state.get("messages", []), "memo")
    if feedback:
        sanitized = sanitize_search_query(feedback)
        prompt += f"\n\nUser revision request: {sanitized}\nPlease address this feedback."

    system = apply_language_suffix(
        STRATEGY_ARGUMENT_MEMO_SYSTEM,
        state.get("language", "en"),
    )

    try:
        memo = await llm.generate(
            prompt=prompt,
            system=system,
            temperature=0.2,
            max_tokens=4096,
        )
    except Exception as e:
        logger.error("LLM error in synthesize_strategy_node: %s", e, exc_info=True)
        return {"error": f"LLM error in synthesize_strategy_node: {e!s}"}

    # Append legal disclaimer to the memo
    memo += LEGAL_DISCLAIMER

    # Detect contradictions using search results (richer text) rather than precedent_map
    contradictions: list[dict] = []
    if search_results and len(search_results) > 3:
        # Build richer context from search results which have snippets/ratio text
        contra_context = []
        for r in search_results[:15]:
            snippet = r.get("ratio", "") or r.get("snippet", "") or r.get("text", "")
            if snippet:
                contra_context.append({
                    "title": r.get("title", "Unknown"),
                    "citation": r.get("citation", ""),
                    "holding": snippet[:500],
                })

        if len(contra_context) > 3:
            try:
                contra_prompt = (
                    "Analyze these case holdings for contradictions:\n\n"
                    + json.dumps(contra_context, indent=2)
                    + "\n\nIdentify genuine legal contradictions between holdings."
                )
                contra_result = await llm.generate_structured(
                    prompt=contra_prompt,
                    system=RESEARCH_CONTRADICTIONS_SYSTEM,
                    output_schema={
                        "type": "object",
                        "properties": {
                            "contradictions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "case_a": {"type": "string"},
                                        "case_b": {"type": "string"},
                                        "description": {"type": "string"},
                                        "resolution": {"type": "string"},
                                    },
                                    "required": ["case_a", "case_b", "description", "resolution"],
                                },
                            },
                        },
                        "required": ["contradictions"],
                    },
                )
                contradictions = contra_result.get("contradictions", [])
            except Exception as e:
                logger.warning("Contradiction detection failed: %s", e)

    # Calculate confidence (same pattern as research_nodes)
    reranker_scores = sorted(
        [r.get("score", 0.0) for r in search_results if r.get("score")],
        reverse=True,
    )

    # Precedent strength labels
    precedent_strengths: list[str] = [
        p.get("strength", "UNKNOWN")
        for p in precedent_map
        if p.get("strength") and p.get("strength") != "UNKNOWN"
    ]

    # Cross-reference ratio: proportion of causes of action with matching results
    fact_analysis = state.get("fact_analysis", {})
    causes_count = len(fact_analysis.get("causes_of_action", []))
    queries_with_results = len({
        r.get("source_query", "")
        for r in search_results
        if r.get("source_query")
    })
    cross_ref_ratio = queries_with_results / max(causes_count, 1)

    confidence = calculate_confidence(
        reranker_scores=reranker_scores,
        cross_ref_ratio=min(cross_ref_ratio, 1.0),
        precedent_strengths=precedent_strengths,
        contradiction_count=len(contradictions),
        total_results=len(search_results),
    )

    return {"strategy_memo": memo, "confidence": confidence, "contradictions": contradictions}


# ---------------------------------------------------------------------------
# Node 9: verify_citations_node
# ---------------------------------------------------------------------------


async def verify_citations_node(
    state: StrategyState,
    db: AsyncSession,
) -> dict:
    """Verify case IDs and human-readable citations in the strategy memo.

    Performs the same three-layer verification as research_nodes:
    1. UUID-based verification -- checks case IDs against the DB.
    2. Human-readable citation verification -- checks SCC/AIR/etc. citations
       against ``cases.citation`` and ``case_citation_equivalents.citation_text``.
    3. Grounding check -- flags citations in the memo that were NOT in the
       search results (potentially hallucinated from LLM training data).
    """
    memo = state.get("strategy_memo", "")
    if not memo:
        return {"strategy_memo": memo}

    search_results = state.get("search_results", [])
    grounding_citations = collect_grounding_citations(search_results)

    memo = await verify_memo_citations(memo, db, grounding_citations)

    # Misgrounding check: verify propositions match cited case ratio
    # Extract citation-proposition pairs from memo
    citation_refs = re.findall(r'\[(\d+)\]\s*([^[.\n]{20,200})', memo)
    misgrounding_warnings: list[str] = []

    for ref_num, proposition in citation_refs[:5]:
        # Find the corresponding search result
        matching = [
            r for r in search_results
            if str(r.get("ref_num")) == ref_num
            or r.get("citation", "").strip() == ref_num
        ]
        if not matching:
            continue
        result = matching[0]
        ratio = result.get("ratio", "") or result.get("snippet", "")
        if ratio and proposition.strip():
            # Simple semantic check: does the proposition align with the ratio?
            prop_words = set(proposition.lower().split())
            ratio_words = set(ratio.lower().split())
            overlap = len(prop_words & ratio_words) / max(len(prop_words), 1)
            if overlap < 0.15:  # Very low overlap suggests misgrounding
                misgrounding_warnings.append(
                    f"[{ref_num}] may be misgrounded: proposition doesn't align with source ratio"
                )

    if misgrounding_warnings:
        memo += "\n\n---\n**Verification Warnings:**\n" + "\n".join(
            f"- {w}" for w in misgrounding_warnings
        )

    return {"strategy_memo": memo}
