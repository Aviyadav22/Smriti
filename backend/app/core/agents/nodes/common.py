"""Shared utilities for agent node functions."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import asdict
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.nodes.citation_verifier import (
    check_grounding,
    extract_citations_from_text,
    verify_citations_against_db,
)
from app.core.legal.extractor import extract_citations
from app.core.interfaces import (
    EmbeddingProvider,
    GraphStore,
    LLMProvider,
    Reranker,
    VectorStore,
)
from app.core.legal.treatment import has_overruling_language
from app.core.search.hybrid import hybrid_search

logger = logging.getLogger(__name__)

# UUID v4 regex shared across agent node modules
UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

_BENCH_LABELS = {
    "single": "Single Judge",
    "division": "Division Bench",
    "full": "Full Bench",
    "constitutional": "Constitution Bench",
}


def format_search_results_for_llm(
    results: list[dict],
    max_snippet_len: int = 500,
    max_ratio_len: int = 1500,
) -> str:
    """Format search results into a string for LLM context."""
    if not results:
        return "No results found."
    parts: list[str] = []
    for i, r in enumerate(results, 1):
        snippet = (r.get("snippet") or "")[:max_snippet_len]
        ratio = (r.get("ratio") or "")[:max_ratio_len]

        # Build court string with bench type if available
        court = r.get("court", "Unknown")
        bench_type = r.get("bench_type", "")
        if bench_type:
            bench_label = _BENCH_LABELS.get(bench_type, bench_type)
            court_str = f"{court} ({bench_label})"
        else:
            court_str = str(court)

        block = (
            f"[{i}] {r.get('title', 'Untitled')} ({r.get('citation', 'No citation')})\n"
            f"    Court: {court_str} | Year: {r.get('year', 'Unknown')}"
        )
        if ratio:
            block += f"\n    Ratio Decidendi: {ratio}"
        if snippet:
            block += f"\n    Relevant Passage: {snippet}"

        parts.append(block)
    return "\n\n".join(parts)


async def enrich_results_with_ratio(
    results: list[dict],
    db: AsyncSession,
    max_ratio_len: int = 1500,
) -> list[dict]:
    """Fetch ratio_decidendi and bench_type from PostgreSQL for search results."""
    case_ids: list[str] = []
    seen: set[str] = set()
    for r in results:
        cid = r.get("case_id", "")
        if cid and cid not in seen:
            seen.add(cid)
            case_ids.append(cid)

    if not case_ids:
        return results

    placeholders = ", ".join(f":id_{i}" for i in range(len(case_ids)))
    params = {f"id_{i}": cid for i, cid in enumerate(case_ids)}
    params["max_len"] = max_ratio_len

    query = text(
        f"SELECT id::text, LEFT(ratio_decidendi, :max_len) AS ratio, bench_type "
        f"FROM cases WHERE id::text IN ({placeholders})"
    )

    try:
        result = await db.execute(query, params)
        rows = result.fetchall()
    except Exception:
        logger.warning("Failed to enrich results with ratio_decidendi", exc_info=True)
        return results

    ratio_map: dict[str, dict[str, str]] = {}
    for row in rows:
        ratio_map[row[0]] = {"ratio": row[1] or "", "bench_type": row[2] or ""}

    for r in results:
        cid = r.get("case_id", "")
        if cid in ratio_map:
            if not r.get("ratio"):
                r["ratio"] = ratio_map[cid]["ratio"]
            if not r.get("bench_type"):
                r["bench_type"] = ratio_map[cid]["bench_type"]

    return results


async def verify_case_ids(case_ids: list[str], db: AsyncSession) -> set[str]:
    """Check which case_ids actually exist in the database."""
    if not case_ids:
        return set()
    result = await db.execute(
        text("SELECT id::text FROM cases WHERE id::text = ANY(:ids)"),
        {"ids": case_ids},
    )
    return {row[0] for row in result.fetchall()}


# ---------------------------------------------------------------------------
# Safe JSON parsing helpers for LLM output
# ---------------------------------------------------------------------------


def safe_json_parse(raw: str, default: dict | list | None = None) -> dict | list:
    """Best-effort JSON parsing from LLM output with regex fallback.

    Handles common LLM output quirks:
    - Raw JSON
    - JSON wrapped in markdown code fences
    - JSON embedded in surrounding prose text
    """
    raw = raw.strip()
    # Try raw first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code fence
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try finding first { or [ to last } or ]
    for start, end in [("{", "}"), ("[", "]")]:
        s = raw.find(start)
        e = raw.rfind(end)
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(raw[s : e + 1])
            except json.JSONDecodeError:
                pass
    return default if default is not None else {}


def safe_json_parse_list(raw: str) -> list[dict]:
    """Best-effort extraction of a JSON array from LLM output.

    Convenience wrapper around :func:`safe_json_parse` that guarantees a
    ``list`` return type.
    """
    result = safe_json_parse(raw, default=[])
    if isinstance(result, list):
        return result
    return [result]


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

# Maximum number of search results to pass to the LLM for context.
MAX_RESULTS_FOR_LLM: int = 30

# Hindi language instruction suffix appended to system prompts when the user's
# preferred language is Hindi.
HINDI_SYSTEM_SUFFIX: Final[str] = (
    "\n\nIMPORTANT: Write your entire response in Hindi (Devanagari script). "
    "Keep case names, citations, statute names, and section numbers in English."
)


# ---------------------------------------------------------------------------
# Citation density validation
# ---------------------------------------------------------------------------

# Sections that should contain substantive legal citations
_SUBSTANTIVE_SECTIONS: frozenset[str] = frozenset({
    "grounds",
    "legal_provisions",
    "precedents",
    "analysis",
    "legal_grounds",
    "grounds_for_bail",
    "grounds_for_relief",
    "arguments",
    "legal_arguments",
    "grounds_of_appeal",
})

_MIN_CITATIONS_FOR_SUBSTANTIVE = 2


def check_citation_density(section_text: str, section_name: str) -> str | None:
    """Check whether a substantive section contains enough citations.

    For substantive sections (grounds, legal_provisions, precedents, analysis,
    etc.) a minimum of 2 citations is expected.  Non-substantive sections are
    always considered acceptable.

    Args:
        section_text: The drafted text of a single section.
        section_name: The template section name (e.g. ``"grounds"``).

    Returns:
        A warning string if citation density is too low, or ``None`` if
        the section passes validation.
    """
    normalized_name = section_name.lower().strip().replace(" ", "_")
    if normalized_name not in _SUBSTANTIVE_SECTIONS:
        return None

    citations = extract_citations(section_text)
    count = len(citations)
    if count >= _MIN_CITATIONS_FOR_SUBSTANTIVE:
        return None

    display_name = section_name.replace("_", " ").title()
    return (
        f"\n\n> **Citation Density Warning ({display_name})**: "
        f"This section contains only {count} citation(s). "
        f"Substantive legal sections should cite at least "
        f"{_MIN_CITATIONS_FOR_SUBSTANTIVE} authorities. "
        f"Consider adding relevant case law or statutory references."
    )


# ---------------------------------------------------------------------------
# Citation verification
# ---------------------------------------------------------------------------


async def verify_memo_citations(
    memo: str,
    db: AsyncSession,
    grounding_citations: list[str],
) -> str:
    """Run 3-layer citation verification and append warnings to memo.

    Layer 1: UUID verification against cases table
    Layer 2: Human-readable citation verification
    Layer 3: Grounding check against provided citations

    Returns the memo with any warning sections appended.
    """
    if not memo:
        return memo

    # Step 1: UUID verification
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

    # Step 2: Human-readable citation verification
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

    # Step 3: Grounding check
    if memo_citations:
        ungrounded = check_grounding(memo_citations, grounding_citations)
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

    # Step 4: Semantic holding verification
    # For verified citations, check if the memo's description of the case
    # holding is consistent with the actual ratio_decidendi stored in DB.
    if memo_citations:
        try:
            unverified_holdings = await _check_holding_accuracy(memo, memo_citations, db)
        except Exception:
            logger.warning("Holding accuracy check failed", exc_info=True)
            unverified_holdings = []
        if unverified_holdings:
            warning = (
                "\n\n---\n"
                "**Holding Accuracy Warning**\n"
                "The following cases are cited in this memo, but their described "
                "holdings could not be verified against database records. The "
                "stated legal propositions may be inaccurate:\n"
            )
            for cite_info in unverified_holdings:
                warning += f"- {cite_info}\n"
            warning += (
                "Cross-check the actual ratio decidendi of these cases before "
                "relying on the described holdings.\n"
            )
            memo += warning

    return memo


async def _check_holding_accuracy(
    memo: str,
    citations: list[str],
    db: AsyncSession,
) -> list[str]:
    """Check if cited cases have a ratio_decidendi in DB that we can compare.

    Returns a list of citation strings whose holdings could NOT be verified
    because they have no stored ratio_decidendi (meaning the memo's description
    of their holding is entirely unverifiable).

    This is a lightweight check — we flag cases with no stored ratio rather
    than doing a full LLM comparison, to avoid adding latency and cost.
    A future enhancement could use LLM-based semantic comparison.
    """
    if not citations:
        return []

    # Normalize citations for lookup — query the equivalents table
    try:
        placeholders = ", ".join(f":c_{i}" for i in range(len(citations)))
        params = {f"c_{i}": cite for i, cite in enumerate(citations)}

        result = await db.execute(
            text(
                f"SELECT ce.citation_text, c.ratio_decidendi "
                f"FROM case_citation_equivalents ce "
                f"JOIN cases c ON c.id = ce.case_id "
                f"WHERE ce.citation_text IN ({placeholders})"
            ),
            params,
        )
        rows = result.fetchall()
    except Exception:
        logger.warning("Failed to check holding accuracy", exc_info=True)
        return []

    verified_set: set[str] = set()
    no_ratio: list[str] = []

    for row in rows:
        cite_text = row[0]
        ratio = row[1]
        verified_set.add(cite_text)
        if not ratio or len(ratio.strip()) < 20:
            no_ratio.append(f"{cite_text} [no ratio decidendi on record]")

    # Citations that couldn't be found in DB at all are already flagged
    # by Layer 2 (unverified citations). We only flag those that ARE in DB
    # but have no ratio.
    return no_ratio


def collect_grounding_citations(results: list[dict]) -> list[str]:
    """Extract all citation strings from a list of search result dicts for grounding checks."""
    citations: list[str] = []
    for result in results:
        citation = result.get("citation", "")
        if citation:
            citations.append(citation)
        snippet = result.get("snippet", "")
        if snippet:
            citations.extend(extract_citations_from_text(snippet))
    return citations


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


async def parallel_hybrid_search(
    queries: list[str],
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    db: AsyncSession,
    **search_kwargs: Any,
) -> list[dict]:
    """Run hybrid_search for each query in parallel, return combined results.

    Failed individual searches are logged and skipped (not propagated).
    Each result dict gets a 'source_query' field added.
    """
    if not queries:
        return []

    async def _search_one(sq: str) -> list[dict]:
        response = await hybrid_search(
            sq,
            llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            db=db,
            **search_kwargs,
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
            logger.warning("Hybrid search query failed: %s", result_or_exc)
            continue
        combined.extend(result_or_exc)

    return combined


def detect_overruled_cases(results: list[dict]) -> set[str]:
    """Scan results for overruling language, return set of overruled case IDs."""
    overruled_ids: set[str] = set()
    for r in results:
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
                overruled_ids.add(cid)
    return overruled_ids


async def get_citation_neighbors(
    graph_store: GraphStore,
    top_results: list[dict],
    seen_ids: set[str],
    max_results: int = 5,
) -> list[dict]:
    """Fetch 2-hop citation graph neighbors for top search results in parallel.

    Catches all exceptions gracefully per-result.
    Returns list of neighbor dicts with standard fields.
    """

    async def _fetch_one(case_id: str) -> list[dict]:
        try:
            neighbors = await graph_store.get_neighbors(
                case_id,
                relationship="CITES",
                direction="both",
                depth=2,
            )
            results: list[dict] = []
            for entry in neighbors.get("neighbors", []):
                node = entry.get("node", {}) if isinstance(entry, dict) else {}
                if isinstance(node, dict):
                    nid = node.get("id", node.get("case_id", ""))
                    if nid:
                        results.append({
                            "case_id": nid,
                            "title": node.get("title"),
                            "citation": node.get("citation"),
                            "court": node.get("court"),
                            "year": node.get("year"),
                            "bench_type": node.get("bench_type"),
                            "snippet": node.get("snippet", ""),
                            "score": 0.0,
                            "source": "citation_graph",
                        })
            return results
        except Exception:
            logger.warning("Graph neighbor query failed for case_id=%s", case_id)
            return []

    case_ids = [r.get("case_id", "") for r in top_results[:max_results] if r.get("case_id")]
    all_results = await asyncio.gather(*[_fetch_one(cid) for cid in case_ids])

    # Merge and deduplicate after gather completes to avoid race condition
    combined: list[dict] = []
    for result_list in all_results:
        for item in result_list:
            nid = item.get("case_id", "")
            if nid and nid not in seen_ids:
                seen_ids.add(nid)
                combined.append(item)
    return combined


def deduplicate_by_case_id(results: list[dict]) -> list[dict]:
    """Keep highest-scoring result per case_id."""
    best: dict[str, dict] = {}
    for r in results:
        cid = r.get("case_id", "")
        if not cid:
            continue
        existing = best.get(cid)
        if existing is None or r.get("score", 0) > existing.get("score", 0):
            best[cid] = r
    return list(best.values())


# ---------------------------------------------------------------------------
# Message / feedback helpers
# ---------------------------------------------------------------------------


def get_latest_feedback(messages: list[dict], step: str) -> str | None:
    """Find the last user feedback content for a given checkpoint step."""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("type") == "user_feedback" and m.get("step") == step:
            return m.get("content", "")
    return None


def get_message_data(messages: list[dict], msg_type: str) -> Any:
    """Find the last message of a given type and return its data."""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("type") == msg_type:
            return m.get("data")
    return None


# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------


def apply_language_suffix(system: str, language: str) -> str:
    """Append Hindi instruction to system prompt if language is 'hi'."""
    if language == "hi":
        return system + HINDI_SYSTEM_SUFFIX
    return system
