"""Case Prep Agent node functions for LangGraph.

Each node function takes the CasePrepState as its first argument plus
injected dependencies, performs a single focused operation, and returns
a partial state dict for LangGraph to merge.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.core.agents.nodes.common import (
    collect_grounding_citations,
    enrich_results_with_ratio,
    get_citation_neighbors,
    get_latest_feedback,
    safe_json_parse_list,
    verify_memo_citations,
)
from app.core.legal.prompts import (
    CASE_PREP_ARGUMENT_ORDER_SYSTEM,
    CASE_PREP_PRIORITIZE_SCHEMA,
    CASE_PREP_PRIORITIZE_SYSTEM,
    CASE_PREP_PRIORITIZE_USER,
    CASE_PREP_STRATEGY_SYSTEM,
    CASE_PREP_STRATEGY_USER,
    LEGAL_DISCLAIMER,
)
from app.core.search.hybrid import hybrid_search
from app.security.sanitizer import sanitize_search_query

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.agents.state import CasePrepState
    from app.core.interfaces import (
        EmbeddingProvider,
        GraphStore,
        LLMProvider,
        Reranker,
        VectorStore,
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node 1: load_analysis_node
# ---------------------------------------------------------------------------


async def load_analysis_node(
    state: CasePrepState,
    db: AsyncSession,
) -> dict:
    """Fetch DocumentAnalysis from DB by document_id.

    Converts the stored analysis into a dict with keys:
    issues, parties, key_facts, relief_sought, counter_arguments, research_memo.
    """
    document_id = state["document_id"]

    result = await db.execute(
        text(
            "SELECT issues, parties, key_facts, relief_sought, counter_arguments, research_memo FROM document_analyses WHERE document_id = :doc_id"
        ),
        {"doc_id": document_id},
    )
    row = result.mappings().first()

    if row is None:
        logger.warning("No DocumentAnalysis found for document_id=%s", document_id)
        return {
            "error": f"No analysis found for document {document_id}. Please upload and analyze the document first.",
            "analysis": {
                "issues": [],
                "parties": {},
                "key_facts": [],
                "relief_sought": None,
                "counter_arguments": [],
                "research_memo": "",
            },
        }

    row_dict = dict(row)

    # Parse JSON fields that may be stored as strings
    def _parse_json_field(value: object) -> object:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        return value

    analysis_dict: dict = {
        "issues": _parse_json_field(row_dict.get("issues", [])),
        "parties": _parse_json_field(row_dict.get("parties", {})),
        "key_facts": _parse_json_field(row_dict.get("key_facts", [])),
        "relief_sought": row_dict.get("relief_sought"),
        "counter_arguments": _parse_json_field(row_dict.get("counter_arguments", [])),
        "research_memo": row_dict.get("research_memo", ""),
    }

    return {"analysis": analysis_dict}


# ---------------------------------------------------------------------------
# Node 2: prioritize_issues_node
# ---------------------------------------------------------------------------


async def prioritize_issues_node(
    state: CasePrepState,
    llm: LLMProvider,
) -> dict:
    """Prioritize legal issues by strength, relevance, trend, and strategic value."""
    analysis = state.get("analysis", {})
    issues = analysis.get("issues", [])

    if not issues:
        return {"prioritized_issues": []}

    issues_text = json.dumps(issues, indent=2)
    parties = json.dumps(analysis.get("parties", {}))
    relief_sought = analysis.get("relief_sought") or "Not specified"

    prompt = CASE_PREP_PRIORITIZE_USER.format(
        issues=issues_text,
        parties=parties,
        relief_sought=relief_sought,
    )

    feedback = get_latest_feedback(state.get("messages", []), "issues")
    if feedback:
        sanitized = sanitize_search_query(feedback)
        prompt += f"\n\nUser revision request: {sanitized}\nPlease address this feedback."

    try:
        result = await llm.generate_structured(
            prompt=prompt,
            system=CASE_PREP_PRIORITIZE_SYSTEM,
            output_schema=CASE_PREP_PRIORITIZE_SCHEMA,
        )
    except Exception as e:
        logger.warning("LLM call failed in prioritize_issues_node: %s", e)
        return {"error": f"Failed to prioritize issues: {e!s}"}

    prioritized = result.get("prioritized_issues", [])

    # Sort by composite_score descending
    prioritized.sort(key=lambda x: x.get("composite_score", 0), reverse=True)

    # Label scores as AI estimates — they haven't been validated against actual precedents yet
    for issue in prioritized:
        issue["score_note"] = (
            "AI-estimated scores — will be validated against actual precedents in next step"
        )

    return {"prioritized_issues": prioritized}


# ---------------------------------------------------------------------------
# Node 3: deep_precedent_search_node
# ---------------------------------------------------------------------------


async def deep_precedent_search_node(
    state: CasePrepState,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    graph_store: GraphStore,
    db: AsyncSession,
) -> dict:
    """Run deep precedent search for top 3 prioritized issues.

    For each issue:
    1. Run hybrid_search for the issue text
    2. For top results, get 2-hop citation neighbors via graph_store
    3. Merge and deduplicate
    """
    prioritized = state.get("prioritized_issues", [])
    top_issues = prioritized[:3]

    if not top_issues:
        return {"messages": [{"type": "deep_precedents", "data": []}]}

    async def _search_issue(issue: dict) -> dict:
        title = issue.get("title", "")
        description = issue.get("description", "")
        query = f"{title}: {description}"

        # Step 1: Hybrid search
        try:
            search_response = await hybrid_search(
                query,
                page=1,
                page_size=5,
                llm=llm,
                embedder=embedder,
                vector_store=vector_store,
                reranker=reranker,
                db=db,
            )
            search_results = [asdict(item) for item in search_response.results]
        except (TimeoutError, ConnectionError, ValueError):
            logger.exception("Hybrid search failed for issue: %s", title)
            search_results = []

        # Step 2: Get 2-hop citation neighbors for top results
        seen = {sr.get("case_id", "") for sr in search_results}
        neighbor_results = await get_citation_neighbors(
            graph_store, search_results, seen, max_results=3
        )

        # Step 3: Merge search results with citation graph neighbors
        merged = list(search_results)
        merged.extend(neighbor_results)

        return {
            "issue_title": title,
            "results": merged,
        }

    findings = await asyncio.gather(
        *[_search_issue(issue) for issue in top_issues],
        return_exceptions=True,
    )

    precedent_findings: list[dict] = []
    failure_count = 0
    for finding in findings:
        if isinstance(finding, BaseException):
            logger.warning("Deep precedent search failed: %s", finding)
            failure_count += 1
            continue
        # Enrich each issue's results with ratio_decidendi and bench_type
        finding["results"] = await enrich_results_with_ratio(finding.get("results", []), db)
        precedent_findings.append(finding)

    # If ALL searches failed, set a warning in the state
    if not precedent_findings and failure_count > 0:
        logger.error("All %d deep precedent searches failed", failure_count)
        return {
            "messages": [{"type": "deep_precedents", "data": []}],
            "error": (
                f"All {failure_count} deep precedent searches failed. "
                "Please check search service availability and try again."
            ),
        }

    # Update prioritized issue scores based on actual precedent findings
    prioritized = state.get("prioritized_issues", [])
    for issue in prioritized:
        issue_title = issue.get("title", "")
        # Find matching precedent findings for this issue
        matched_results: list[dict] = []
        for finding in precedent_findings:
            if finding.get("issue_title", "") == issue_title:
                matched_results = finding.get("results", [])
                break

        result_count = len(matched_results)
        # Count binding precedents (Supreme Court cases)
        binding_count = sum(
            1 for r in matched_results if "supreme" in (r.get("court", "") or "").lower()
        )

        # Update the score note based on actual findings
        if result_count == 0:
            issue["score_note"] = (
                "\u26a0 No supporting precedents found — scores are AI estimates only"
            )
        elif binding_count >= 3:
            # Boost legal_strength if we found strong binding precedents
            old_strength = issue.get("legal_strength", 5)
            issue["legal_strength"] = min(10, old_strength + 1)
            issue["score_note"] = f"Validated: {binding_count} binding precedents found"
        elif result_count >= 3:
            issue["score_note"] = (
                f"Partially validated: {result_count} precedents found ({binding_count} binding)"
            )
        else:
            issue["score_note"] = f"Limited validation: only {result_count} precedent(s) found"

    return {
        "messages": [{"type": "deep_precedents", "data": precedent_findings}],
        "prioritized_issues": prioritized,
    }


# ---------------------------------------------------------------------------
# Node 4: build_argument_order_node
# ---------------------------------------------------------------------------


async def build_argument_order_node(
    state: CasePrepState,
    llm: LLMProvider,
) -> dict:
    """Build recommended argument ordering from prioritized issues and precedents."""
    prioritized = state.get("prioritized_issues", [])

    # Retrieve deep precedent findings from messages
    precedent_findings: list[dict] = []
    for msg in state.get("messages", []):
        if isinstance(msg, dict) and msg.get("type") == "deep_precedents":
            precedent_findings.extend(msg.get("data", []))

    issues_summary = json.dumps(prioritized, indent=2)
    precedents_summary = (
        json.dumps(precedent_findings, indent=2) if precedent_findings else "None found."
    )

    prompt = (
        f"Prioritized Issues:\n{issues_summary}\n\n"
        f"Deep Precedent Findings:\n{precedents_summary}\n\n"
        "Based on the above, recommend the optimal argument presentation order. "
        "Return a JSON array where each element has:\n"
        '- "position": integer (1-based order)\n'
        '- "issue_title": the issue title\n'
        '- "role": "primary", "alternative", or "fallback"\n'
        '- "rationale": why this position is recommended\n'
        '- "preliminary": boolean (true if this is a threshold/preliminary issue)\n'
    )

    feedback = get_latest_feedback(state.get("messages", []), "strategy")
    if feedback:
        sanitized = sanitize_search_query(feedback)
        prompt += f"\n\nUser revision request: {sanitized}\nPlease address this feedback."

    try:
        raw = await llm.generate(
            prompt=prompt,
            system=CASE_PREP_ARGUMENT_ORDER_SYSTEM,
            temperature=0.2,
        )
    except Exception as e:
        logger.warning("LLM call failed in build_argument_order_node: %s", e)
        raw = ""

    ordered_args = safe_json_parse_list(raw)

    # Fallback: if LLM output couldn't be parsed, create order from prioritized issues
    if not ordered_args and prioritized:
        ordered_args = [
            {
                "position": i + 1,
                "issue_title": issue.get("title", f"Issue {i + 1}"),
                "role": "primary" if i < 2 else "alternative",
                "rationale": "Ordered by composite score",
                "preliminary": False,
            }
            for i, issue in enumerate(prioritized)
        ]

    return {"argument_order": ordered_args}


# ---------------------------------------------------------------------------
# Node 5: generate_strategy_memo_node
# ---------------------------------------------------------------------------


async def generate_strategy_memo_node(
    state: CasePrepState,
    llm: LLMProvider,
) -> dict:
    """Generate a comprehensive case preparation strategy memo."""
    analysis = state.get("analysis", {})
    prioritized = state.get("prioritized_issues", [])
    state.get("argument_order", [])

    # Retrieve deep precedent findings from messages
    precedent_findings: list[dict] = []
    for msg in state.get("messages", []):
        if isinstance(msg, dict) and msg.get("type") == "deep_precedents":
            precedent_findings.extend(msg.get("data", []))

    issues_analysis = json.dumps(prioritized, indent=2) if prioritized else "No issues analyzed."
    precedent_text = (
        json.dumps(precedent_findings, indent=2) if precedent_findings else "No precedents found."
    )
    counter_arguments = (
        json.dumps(analysis.get("counter_arguments", []), indent=2)
        if analysis.get("counter_arguments")
        else "None identified."
    )
    parties = json.dumps(analysis.get("parties", {}))
    relief_sought = analysis.get("relief_sought") or "Not specified"

    prompt = CASE_PREP_STRATEGY_USER.format(
        issues_analysis=issues_analysis,
        precedent_findings=precedent_text,
        counter_arguments=counter_arguments,
        parties=parties,
        relief_sought=relief_sought,
    )

    feedback = get_latest_feedback(state.get("messages", []), "memo")
    if feedback:
        sanitized = sanitize_search_query(feedback)
        prompt += f"\n\nUser revision request: {sanitized}\nPlease address this feedback."

    try:
        memo = await llm.generate(
            prompt=prompt,
            system=CASE_PREP_STRATEGY_SYSTEM,
            temperature=0.2,
            max_tokens=8192,
        )
    except Exception as e:
        logger.warning("LLM call failed in generate_strategy_memo_node: %s", e)
        return {"error": f"Failed to generate strategy memo: {e!s}"}

    # Append legal disclaimer to the memo
    memo += LEGAL_DISCLAIMER

    return {"enhanced_memo": memo}


# ---------------------------------------------------------------------------
# Node 6: verify_citations_node
# ---------------------------------------------------------------------------


async def verify_citations_node(
    state: CasePrepState,
    db: AsyncSession,
) -> dict:
    """Verify citations in the strategy memo using shared 3-layer verification."""
    memo = state.get("enhanced_memo", "")
    if not memo:
        return {"enhanced_memo": memo}

    # Collect grounding citations from deep precedent search results
    grounding_citations: list[str] = []
    for msg in state.get("messages", []):
        if isinstance(msg, dict) and msg.get("type") == "deep_precedents":
            for finding in msg.get("data", []):
                grounding_citations.extend(collect_grounding_citations(finding.get("results", [])))

    memo = await verify_memo_citations(memo, db, grounding_citations)
    return {"enhanced_memo": memo}
