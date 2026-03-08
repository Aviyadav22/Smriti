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
from dataclasses import asdict

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.confidence import calculate_confidence
from app.core.agents.nodes.citation_verifier import (
    check_grounding,
    extract_citations_from_text,
    verify_citations_against_db,
)
from app.core.agents.nodes.common import (
    UUID_RE,
    enrich_results_with_ratio,
    verify_case_ids,
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
    STRATEGY_ANALYZE_FACTS_SCHEMA,
    STRATEGY_ANALYZE_FACTS_SYSTEM,
    STRATEGY_ARGUMENTS_SCHEMA,
    STRATEGY_ARGUMENTS_SYSTEM,
    STRATEGY_ASSESS_STRENGTH_SCHEMA,
    STRATEGY_ASSESS_STRENGTH_SYSTEM,
    STRATEGY_COUNTER_ARGS_SCHEMA,
    STRATEGY_COUNTER_ARGS_SYSTEM,
    STRATEGY_JUDGE_ANALYSIS_SCHEMA,
    STRATEGY_JUDGE_ANALYSIS_SYSTEM,
    STRATEGY_SYNTHESIZE_SYSTEM,
    STRATEGY_SYNTHESIZE_USER,
)
from app.core.legal.treatment import has_overruling_language
from app.core.search.hybrid import hybrid_search
from app.security.sanitizer import sanitize_search_query

logger = logging.getLogger(__name__)

MAX_RESULTS_FOR_LLM = 30


# ---------------------------------------------------------------------------
# Node 1: analyze_facts_node
# ---------------------------------------------------------------------------


async def analyze_facts_node(
    state: StrategyState,
    llm: LLMProvider,
) -> dict:
    """Parse case facts into structured form (parties, causes of action, etc.)."""
    case_facts = sanitize_search_query(state["case_facts"])

    try:
        fact_analysis = await llm.generate_structured(
            prompt=case_facts,
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

    try:
        # Disposal breakdown
        disposal_result = await db.execute(
            sa_text(
                "SELECT disposal_nature, COUNT(*) as cnt "
                "FROM cases "
                "WHERE :judge_name = ANY(judge) "
                "GROUP BY disposal_nature "
                "ORDER BY cnt DESC"
            ),
            {"judge_name": sanitized_judge},
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
                "WHERE :judge_name = ANY(judge) "
                "GROUP BY act "
                "ORDER BY cnt DESC "
                "LIMIT 10"
            ),
            {"judge_name": sanitized_judge},
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
                "WHERE :judge_name = ANY(judge)"
            ),
            {"judge_name": sanitized_judge},
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

    if not queries:
        return {"search_results": [], "precedent_map": []}

    # Parallel hybrid search (same pattern as research_nodes.parallel_search_node)
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
        *[_search_one(sq) for sq in queries],
        return_exceptions=True,
    )

    combined: list[dict] = []
    for result_or_exc in all_lists:
        if isinstance(result_or_exc, BaseException):
            logger.warning("Strategy search query failed: %s", result_or_exc)
            continue
        combined.extend(result_or_exc)

    # Deduplicate by case_id, keeping highest score
    best: dict[str, dict] = {}
    for r in combined:
        cid = r.get("case_id", "")
        if not cid:
            continue
        existing = best.get(cid)
        if existing is None or r.get("score", 0) > existing.get("score", 0):
            best[cid] = r
    combined = list(best.values())

    # Enrich with ratio and bench_type from PostgreSQL
    combined = await enrich_results_with_ratio(combined, db)

    # Get 2-hop citation neighbours for top 5 results
    top_results = sorted(combined, key=lambda r: r.get("score", 0), reverse=True)[:5]
    neighbor_results: list[dict] = []
    seen_ids: set[str] = {r.get("case_id", "") for r in combined}

    for sr in top_results:
        case_id = sr.get("case_id", "")
        if not case_id:
            continue
        try:
            neighbors = await graph_store.get_neighbors(
                case_id,
                relationship="CITES",
                direction="both",
                depth=2,
            )
            neighbor_entries = neighbors.get("neighbors", [])
            for entry in neighbor_entries:
                node = entry.get("node", {}) if isinstance(entry, dict) else {}
                if isinstance(node, dict):
                    nid = node.get("id", node.get("case_id", ""))
                    if nid and nid not in seen_ids:
                        seen_ids.add(nid)
                        neighbor_results.append({
                            "case_id": nid,
                            "title": node.get("title"),
                            "citation": node.get("citation"),
                            "court": node.get("court"),
                            "year": node.get("year"),
                            "snippet": node.get("snippet", ""),
                            "score": 0.0,
                            "source": "citation_graph",
                        })
        except (ConnectionError, TimeoutError):
            logger.warning("Graph neighbor query failed for case_id=%s", case_id)

    combined.extend(neighbor_results)

    # Detect overruling language and classify precedent strength
    overruled_case_ids: set[str] = set()
    for r in combined:
        check_text = (
            (r.get("snippet", "") or "")
            + " "
            + (r.get("ratio", "") or "")
            + " "
            + (r.get("chunk_text", "") or "")
        )
        if check_text.strip() and has_overruling_language(check_text):
            cid = r.get("case_id", "")
            if cid:
                overruled_case_ids.add(cid)

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

    prompt = (
        "Identify the most likely counter-arguments the opposing side will raise.\n\n"
        f"Fact Analysis:\n{json.dumps(fact_analysis, indent=2)}\n\n"
        f"Client's Arguments:\n{json.dumps(legal_arguments, indent=2)}\n\n"
        f"Precedent Map ({len(precedent_map)} precedents):\n"
        f"{json.dumps(precedent_map[:MAX_RESULTS_FOR_LLM], indent=2)}\n\n"
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
    """Synthesize all analysis into a comprehensive strategy memo."""
    case_facts = sanitize_search_query(state.get("case_facts", ""))
    strength_assessment = state.get("strength_assessment", {})
    legal_arguments = state.get("legal_arguments", [])
    counter_arguments = state.get("counter_arguments", [])
    judge_considerations = state.get("judge_considerations", [])
    procedural_suggestions = state.get("procedural_suggestions", [])
    search_results = state.get("search_results", [])
    precedent_map = state.get("precedent_map", [])
    target_court = state.get("target_court") or "Supreme Court of India"
    target_bench = state.get("target_bench") or "division"

    prompt = STRATEGY_SYNTHESIZE_USER.format(
        case_facts=case_facts,
        strength_assessment=json.dumps(strength_assessment, indent=2),
        legal_arguments=json.dumps(legal_arguments, indent=2),
        counter_arguments=json.dumps(counter_arguments, indent=2),
        judge_considerations=json.dumps(judge_considerations, indent=2),
        procedural_suggestions=json.dumps(procedural_suggestions, indent=2),
    )

    # If language is Hindi, append instruction to write in Devanagari
    system = STRATEGY_SYNTHESIZE_SYSTEM
    if state.get("language", "en") == "hi":
        system += (
            "\n\nIMPORTANT: Write your entire response in Hindi (Devanagari script). "
            "Keep case names, citations, statute names, and section numbers in English."
        )

    try:
        memo = await llm.generate(
            prompt=prompt,
            system=system,
            temperature=0.2,
            max_tokens=8192,
        )
    except Exception as e:
        logger.error("LLM error in synthesize_strategy_node: %s", e, exc_info=True)
        return {"error": f"LLM error in synthesize_strategy_node: {e!s}"}

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
        contradiction_count=0,  # Strategy agent doesn't detect contradictions
        total_results=len(search_results),
    )

    return {"strategy_memo": memo, "confidence": confidence}


# ---------------------------------------------------------------------------
# Node 9: verify_citations_node
# ---------------------------------------------------------------------------


async def verify_citations_node(
    state: StrategyState,
    db: AsyncSession,
) -> dict:
    """Verify case IDs and human-readable citations in the strategy memo.

    Performs the same three-layer verification as research_nodes:
    1. UUID-based verification — checks case IDs against the DB.
    2. Human-readable citation verification — checks SCC/AIR/etc. citations
       against ``cases.citation`` and ``case_citation_equivalents.citation_text``.
    3. Grounding check — flags citations in the memo that were NOT in the
       search results (potentially hallucinated from LLM training data).
    """
    memo = state.get("strategy_memo", "")
    if not memo:
        return {"strategy_memo": memo}

    # --- Step 1: UUID verification ---
    found_ids = list(set(UUID_RE.findall(memo)))
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

    return {"strategy_memo": memo}
