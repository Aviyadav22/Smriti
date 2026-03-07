"""Case Prep Agent node functions for LangGraph.

Each node function takes the CasePrepState as its first argument plus
injected dependencies, performs a single focused operation, and returns
a partial state dict for LangGraph to merge.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import asdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.nodes.common import (
    enrich_results_with_ratio,
    format_search_results_for_llm,
    verify_case_ids,
)
from app.core.agents.state import CasePrepState
from app.core.interfaces import EmbeddingProvider, GraphStore, LLMProvider, Reranker, VectorStore
from app.core.legal.prompts import (
    CASE_PREP_ARGUMENT_ORDER_SYSTEM,
    CASE_PREP_PRIORITIZE_SCHEMA,
    CASE_PREP_PRIORITIZE_SYSTEM,
    CASE_PREP_PRIORITIZE_USER,
    CASE_PREP_STRATEGY_SYSTEM,
    CASE_PREP_STRATEGY_USER,
)
from app.core.search.hybrid import hybrid_search

logger = logging.getLogger(__name__)

# UUID v4 regex for citation verification
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


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
        text("SELECT * FROM document_analyses WHERE document_id = :doc_id"),
        {"doc_id": document_id},
    )
    row = result.mappings().first()

    if row is None:
        logger.warning("No DocumentAnalysis found for document_id=%s", document_id)
        return {
            "analysis": {
                "error": f"No analysis found for document_id={document_id}",
                "issues": [],
                "parties": {},
                "key_facts": [],
                "relief_sought": None,
                "counter_arguments": [],
                "research_memo": "",
            }
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

    result = await llm.generate_structured(
        prompt=prompt,
        system=CASE_PREP_PRIORITIZE_SYSTEM,
        output_schema=CASE_PREP_PRIORITIZE_SCHEMA,
    )

    prioritized = result.get("prioritized_issues", [])

    # Sort by composite_score descending
    prioritized.sort(key=lambda x: x.get("composite_score", 0), reverse=True)

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
        except Exception:
            logger.exception("Hybrid search failed for issue: %s", title)
            search_results = []

        # Step 2: Get 2-hop citation neighbors for top results
        neighbor_results: list[dict] = []
        for sr in search_results[:3]:
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
                # neighbors is a dict; extract neighbor node data
                neighbor_nodes = neighbors.get("nodes", [])
                for node in neighbor_nodes:
                    if isinstance(node, dict) and node.get("id") != case_id:
                        neighbor_results.append(node)
            except Exception:
                logger.warning("Graph neighbor query failed for case_id=%s", case_id)

        # Step 3: Deduplicate by case_id
        seen: set[str] = {sr.get("case_id", "") for sr in search_results}
        merged = list(search_results)
        for nr in neighbor_results:
            nid = nr.get("id", nr.get("case_id", ""))
            if nid and nid not in seen:
                seen.add(nid)
                merged.append({
                    "case_id": nid,
                    "title": nr.get("title"),
                    "citation": nr.get("citation"),
                    "court": nr.get("court"),
                    "year": nr.get("year"),
                    "snippet": nr.get("snippet", ""),
                    "score": 0.0,
                    "source": "citation_graph",
                })

        return {
            "issue_title": title,
            "results": merged,
        }

    findings = await asyncio.gather(
        *[_search_issue(issue) for issue in top_issues],
        return_exceptions=True,
    )

    precedent_findings: list[dict] = []
    for finding in findings:
        if isinstance(finding, BaseException):
            logger.warning("Deep precedent search failed: %s", finding)
            continue
        # Enrich each issue's results with ratio_decidendi and bench_type
        finding["results"] = await enrich_results_with_ratio(
            finding.get("results", []), db
        )
        precedent_findings.append(finding)

    return {"messages": [{"type": "deep_precedents", "data": precedent_findings}]}


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
            precedent_findings = msg.get("data", [])

    issues_summary = json.dumps(prioritized, indent=2)
    precedents_summary = json.dumps(precedent_findings, indent=2) if precedent_findings else "None found."

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

    raw = await llm.generate(
        prompt=prompt,
        system=CASE_PREP_ARGUMENT_ORDER_SYSTEM,
        temperature=0.2,
    )

    ordered_args = _parse_json_list(raw)

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
    argument_order = state.get("argument_order", [])

    # Retrieve deep precedent findings from messages
    precedent_findings: list[dict] = []
    for msg in state.get("messages", []):
        if isinstance(msg, dict) and msg.get("type") == "deep_precedents":
            precedent_findings = msg.get("data", [])

    issues_analysis = json.dumps(prioritized, indent=2) if prioritized else "No issues analyzed."
    precedent_text = json.dumps(precedent_findings, indent=2) if precedent_findings else "No precedents found."
    counter_arguments = json.dumps(
        analysis.get("counter_arguments", []), indent=2
    ) if analysis.get("counter_arguments") else "None identified."
    parties = json.dumps(analysis.get("parties", {}))
    relief_sought = analysis.get("relief_sought") or "Not specified"

    prompt = CASE_PREP_STRATEGY_USER.format(
        issues_analysis=issues_analysis,
        precedent_findings=precedent_text,
        counter_arguments=counter_arguments,
        parties=parties,
        relief_sought=relief_sought,
    )

    memo = await llm.generate(
        prompt=prompt,
        system=CASE_PREP_STRATEGY_SYSTEM,
        temperature=0.2,
        max_tokens=8192,
    )

    return {"enhanced_memo": memo}


# ---------------------------------------------------------------------------
# Node 6: verify_citations_node
# ---------------------------------------------------------------------------


async def verify_citations_node(
    state: CasePrepState,
    db: AsyncSession,
) -> dict:
    """Verify that case IDs referenced in the strategy memo exist in the database.

    Appends a warning section if any IDs cannot be verified.
    """
    memo = state.get("enhanced_memo", "")
    if not memo:
        return {"enhanced_memo": memo}

    # Extract UUID-like patterns from the memo
    found_ids = list(set(_UUID_RE.findall(memo)))
    if not found_ids:
        return {"enhanced_memo": memo}

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

    return {"enhanced_memo": memo}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_json_list(raw: str) -> list[dict]:
    """Best-effort extraction of a JSON array from LLM output."""
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
