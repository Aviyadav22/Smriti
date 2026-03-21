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
from app.core.legal.constants import IPC_TO_BNS_MAP, CRPC_TO_BNSS_MAP, EVIDENCE_TO_BSA_MAP
from app.core.legal.extractor import extract_acts_cited, extract_citations, normalize_act_name
from app.core.legal.prompts import (
    ELEMENT_DECOMPOSITION_SYSTEM,
    ELEMENT_DECOMPOSITION_SCHEMA,
)
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

# ---------------------------------------------------------------------------
# [V3] Statute lookup helpers — old↔new code expansion + DB fetch
# ---------------------------------------------------------------------------

# Reverse maps: new-code section → (old_act, old_section)
_NEW_TO_OLD: dict[tuple[str, str], tuple[str, str]] = {
    **{("BNS", v): ("IPC", k) for k, v in IPC_TO_BNS_MAP.items()},
    **{("BNSS", v): ("CrPC", k) for k, v in CRPC_TO_BNSS_MAP.items()},
    **{("BSA", v): ("IEA", k) for k, v in EVIDENCE_TO_BSA_MAP.items()},
}

_OLD_TO_NEW: dict[str, tuple[str, dict[str, str]]] = {
    "IPC": ("BNS", IPC_TO_BNS_MAP),
    "CrPC": ("BNSS", CRPC_TO_BNSS_MAP),
    "IEA": ("BSA", EVIDENCE_TO_BSA_MAP),
}

def _extract_statute_refs(text_input: str) -> list[tuple[str, str]]:
    """Extract (act_short_name, section_number) tuples from text.

    [A1] Delegates to extractor.extract_acts_cited() which recognizes 62+
    acts (via _SHORT_ACT_NAMES) instead of the previous 8-act regex.
    """
    act_refs = extract_acts_cited(text_input)
    refs: list[tuple[str, str]] = []
    for ref in act_refs:
        short_name = normalize_act_name(ref.act_name)
        section = ref.section.strip()
        # Handle Article references → (COI, N) — strip "Article " prefix for DB lookup
        if section.startswith("Article "):
            refs.append(("COI", section[len("Article "):]))
        # Handle Order/Rule references → keep as-is
        elif section.startswith("Order "):
            refs.append((short_name, section))
        else:
            refs.append((short_name, section))
    return refs


def _expand_refs(refs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Auto-expand old↔new code refs (IPC 302 → also BNS 103)."""
    expanded = list(refs)
    for act, sec in refs:
        if act in _OLD_TO_NEW:
            new_act, mapping = _OLD_TO_NEW[act]
            new_sec = mapping.get(sec, "")
            if new_sec:
                expanded.append((new_act, new_sec))
        elif (act, sec) in _NEW_TO_OLD:
            expanded.append(_NEW_TO_OLD[(act, sec)])
    return list(set(expanded))


async def _fetch_statute_from_db(
    db: AsyncSession,
    refs: list[tuple[str, str]],
) -> list[dict]:
    """[A4] Batch fetch statute rows from PostgreSQL for given (act, section) pairs.

    Uses a single query with OR conditions instead of N+1 individual queries.
    Also batch-fetches new-code equivalents for repealed sections.
    """
    from sqlalchemy import select, or_, and_
    from app.models.statute import Statute

    if not refs:
        return []

    # Batch query: fetch all matching statutes in one round-trip
    conditions = [
        and_(Statute.act_short_name == act, Statute.section_number == sec)
        for act, sec in refs
    ]
    stmt = select(Statute).where(or_(*conditions))
    row_result = await db.execute(stmt)
    rows = row_result.scalars().all()

    # Build lookup for new-code equivalent fetches
    new_code_refs: list[tuple[str, str]] = []
    for row in rows:
        if row.replaced_by and row.is_repealed:
            parts = row.replaced_by.split(", Section ")
            if len(parts) == 2:
                new_code_refs.append((parts[0].strip(), parts[1].strip()))

    # Batch fetch new-code equivalents
    new_code_map: dict[tuple[str, str], str] = {}
    if new_code_refs:
        new_conditions = [
            and_(Statute.act_short_name == act, Statute.section_number == sec)
            for act, sec in new_code_refs
        ]
        new_stmt = select(Statute).where(or_(*new_conditions))
        new_result = await db.execute(new_stmt)
        for new_row in new_result.scalars().all():
            new_code_map[(new_row.act_short_name, new_row.section_number)] = (
                new_row.section_text or ""
            )

    results: list[dict] = []
    for row in rows:
        new_code_text = ""
        if row.replaced_by and row.is_repealed:
            parts = row.replaced_by.split(", Section ")
            if len(parts) == 2:
                new_code_text = new_code_map.get(
                    (parts[0].strip(), parts[1].strip()), ""
                )

        results.append({
            "act_short_name": row.act_short_name,
            "section_number": row.section_number,
            "section_title": row.section_title or "",
            "section_text": row.section_text or "",
            "is_repealed": row.is_repealed or False,
            "replaced_by": row.replaced_by or "",
            "new_code_text": new_code_text,
        })
    return results


async def statute_lookup_node(
    state: dict,
    db: AsyncSession,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
) -> dict:
    """[V3 Stage 1] Read relevant statute text BEFORE planning.

    Extracts statute references from the rewritten query and key entities,
    auto-expands old↔new code mappings, and fetches text from PostgreSQL.
    Also runs a semantic search in Pinecone for statute/constitution vectors.
    """
    query = state.get("rewritten_query", "") or state.get("query", "")
    key_entities = state.get("key_entities", [])

    # Extract refs from query + entities
    all_text = query + " " + " ".join(str(e) for e in key_entities)
    refs = _extract_statute_refs(all_text)
    refs = _expand_refs(refs)

    # Fetch from PostgreSQL
    statute_context = await _fetch_statute_from_db(db, refs)

    # Also try semantic search for statutes not caught by regex
    try:
        query_vector = await embedder.embed_text(query)
        pinecone_results = await vector_store.search(
            query_vector=query_vector,
            top_k=5,
            filters={"document_type": {"$in": ["statute", "constitution"]}},
        )
        # Add any semantic results not already in context
        existing_keys = {
            (s["act_short_name"], s["section_number"]) for s in statute_context
        }
        for result in pinecone_results:
            # SearchResult is a dataclass with .metadata, not a dict
            meta = result.metadata if hasattr(result, "metadata") else result.get("metadata", {})
            act = meta.get("act_short_name", "")
            sec = meta.get("section_number", "")
            if act and sec and (act, sec) not in existing_keys:
                statute_context.append({
                    "act_short_name": act,
                    "section_number": sec,
                    "section_title": meta.get("section_title", ""),
                    "section_text": meta.get("text", ""),
                    "is_repealed": False,
                    "replaced_by": "",
                    "new_code_text": "",
                })
                existing_keys.add((act, sec))
    except Exception:
        logger.warning("Semantic statute search failed", exc_info=True)

    return {"statute_context": statute_context}


async def element_decomposition_node(
    state: dict,
    llm: LLMProvider,
) -> dict:
    """[V3 Stage 2] Break legal question into constituent elements.

    Uses the statute text found in Stage 1 to identify specific legal elements
    (mens rea, actus reus, exceptions, etc.) that each need independent research.
    """
    query = state.get("rewritten_query", "") or state.get("query", "")
    statute_context = state.get("statute_context", [])
    complexity = state.get("complexity", "complex")

    # Format statute context for LLM
    statute_text_parts: list[str] = []
    for s in statute_context:
        entry = f"**{s['act_short_name']} Section {s['section_number']}** — {s['section_title']}\n"
        entry += s["section_text"][:2000]
        if s.get("is_repealed") and s.get("replaced_by"):
            entry += f"\n[REPEALED — replaced by {s['replaced_by']}]"
            if s.get("new_code_text"):
                entry += f"\nNew code text: {s['new_code_text'][:1000]}"
        statute_text_parts.append(entry)

    statute_text = "\n\n".join(statute_text_parts) if statute_text_parts else "No statute text available."

    user_prompt = (
        f"## Research Question\n{query}\n\n"
        f"## Relevant Statute Text\n{statute_text}\n\n"
        f"## Query Complexity\n{complexity}\n\n"
        "Decompose this question into legal elements."
    )

    try:
        result = await llm.generate_structured(
            user_prompt,
            system=ELEMENT_DECOMPOSITION_SYSTEM,
            output_schema=ELEMENT_DECOMPOSITION_SCHEMA,
        )
        elements = result.get("elements", [])
    except Exception as exc:
        logger.warning("Element decomposition failed: %s — using query as single element", exc)
        elements = [{
            "element_id": "primary_issue",
            "description": query[:200],
            "statute_basis": "",
            "search_query": query,
            "is_contested": True,
        }]

    return {"legal_elements": elements}


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
        # Include citation count as authority signal (IK provides num_cited_by)
        num_cited_by = r.get("num_cited_by", 0)
        if num_cited_by:
            block += f" | Cited by: {num_cited_by} cases"
        if ratio:
            block += f"\n    Ratio Decidendi: {ratio}"
        if snippet:
            block += f"\n    Relevant Passage: {snippet}"

        parts.append(block)
    return "\n\n".join(parts)


def format_search_results_for_llm_extended(
    results: list[dict],
    max_snippet_len: int = 1500,
    max_ratio_len: int = 3000,
) -> str:
    """Format search results with higher context limits for Research Agent V2.

    Uses larger snippet/ratio windows since Gemini Pro has 1M context — we're
    only using <1% of it with the default limits.
    """
    return format_search_results_for_llm(results, max_snippet_len, max_ratio_len)


def _normalize_title_for_dedup(t: str) -> str:
    """Normalize case title for fuzzy cross-source matching."""
    t = t.lower().strip()
    t = re.sub(r'\bv\.?\s*', 'v ', t)
    t = re.sub(r'[^a-z0-9\s]', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def _normalize_score(result: dict) -> float:
    """[H7] Normalize scores to 0-1 range by source type."""
    raw = result.get("score", 0)
    if not isinstance(raw, (int, float)):
        return 0.0
    source = result.get("source", "internal")
    if source == "indian_kanoon":
        return raw  # Already 0-1 from position-based scoring (H8)
    elif source == "citation_graph":
        return min(1.0, raw / 10.0)  # Graph BM25 scores ~0.5-10
    elif source == "web":
        return raw  # Tavily scores are 0-1
    elif source == "statute_pinecone":
        return raw  # Pinecone cosine similarity 0-1
    else:
        return raw  # Cohere reranker scores already 0-1


def deduplicate_with_diversity(
    results: list[dict],
    max_chunks_per_case: int = 4,
) -> list[dict]:
    """Keep top N chunks per case_id, sorted by score.

    Prevents one case from dominating results while still allowing
    multiple relevant chunks from the same judgment.
    Also performs cross-source dedup by title (H9) and score normalization (H7).
    """
    # [H7] Normalize scores before grouping
    for r in results:
        r["score"] = _normalize_score(r)

    case_chunks: dict[str, list[dict]] = {}
    for r in results:
        cid = r.get("case_id", "")
        if not cid:
            continue
        case_chunks.setdefault(cid, []).append(r)

    # [H9] Cross-source dedup: match IK results against internal by title similarity
    seen_titles: dict[str, str] = {}  # normalized_title → case_id
    to_remove: set[str] = set()
    for cid, chunks in case_chunks.items():
        title = chunks[0].get("title", "")
        norm = _normalize_title_for_dedup(title)
        if not norm or len(norm) < 10:
            continue
        if norm in seen_titles:
            existing_cid = seen_titles[norm]
            # Prefer internal (UUID) over IK (ik:xxx) over web (web:xxx)
            if cid.startswith(("ik:", "web:")) and not existing_cid.startswith(("ik:", "web:")):
                to_remove.add(cid)
            elif existing_cid.startswith(("ik:", "web:")) and not cid.startswith(("ik:", "web:")):
                to_remove.add(existing_cid)
                seen_titles[norm] = cid
        else:
            seen_titles[norm] = cid

    deduped: list[dict] = []
    for cid, chunks in case_chunks.items():
        if cid in to_remove:
            continue
        chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        deduped.extend(chunks[:max_chunks_per_case])

    deduped.sort(key=lambda x: x.get("score", 0), reverse=True)
    return deduped


async def _search_by_title(title: str, db: AsyncSession) -> list[dict]:
    """Fuzzy + ILIKE search on cases.title for named case retrieval.

    First tries ILIKE for exact substring matches, then falls back to
    pg_trgm similarity() for fuzzy matching (handles misspellings).
    Returns results in the same dict format as other search functions.
    """
    if not title or not title.strip():
        return []

    sanitized = title.strip()[:200]

    # Try ILIKE first (fast, exact substring)
    ilike_query = text(
        "SELECT id::text AS case_id, title, citation, court, "
        "EXTRACT(YEAR FROM decision_date)::int AS year, "
        "bench_type, LEFT(ratio_decidendi, 3000) AS ratio "
        "FROM cases WHERE title ILIKE :pattern "
        "ORDER BY decision_date DESC NULLS LAST LIMIT 5"
    )
    try:
        result = await db.execute(ilike_query, {"pattern": f"%{sanitized}%"})
        rows = result.fetchall()
    except Exception:
        logger.warning("Title ILIKE search failed for: %s", sanitized, exc_info=True)
        rows = []

    # Fallback: pg_trgm fuzzy search if ILIKE found nothing
    if not rows:
        fuzzy_query = text(
            "SELECT id::text AS case_id, title, citation, court, "
            "EXTRACT(YEAR FROM decision_date)::int AS year, "
            "bench_type, LEFT(ratio_decidendi, 3000) AS ratio, "
            "similarity(title, :name) AS sim "
            "FROM cases WHERE similarity(title, :name) > :threshold "
            "ORDER BY sim DESC LIMIT 5"
        )
        try:
            # [M26] Try 0.4 threshold first, then 0.3 if no results (raised from 0.2 to reduce false matches)
            result = await db.execute(fuzzy_query, {"name": sanitized, "threshold": 0.4})
            rows = result.fetchall()
            if not rows:
                result = await db.execute(fuzzy_query, {"name": sanitized, "threshold": 0.3})
                rows = result.fetchall()
        except Exception:
            logger.warning("Title fuzzy search failed for: %s", sanitized, exc_info=True)
            rows = []

    return [
        {
            "case_id": row[0],
            "title": row[1] or "",
            "citation": row[2] or "",
            "court": row[3] or "",
            "year": row[4],
            "bench_type": row[5] or "",
            "ratio": row[6] or "",
            "score": 0.9,  # High score for direct title match
            "source": "title_search",
        }
        for row in rows
    ]


def format_extracted_passages(passages: list[dict]) -> str:
    """Format extracted passages for LLM context in synthesis."""
    if not passages:
        return "No verbatim passages extracted."
    parts: list[str] = []
    for i, p in enumerate(passages, 1):
        verbatim_tag = "[verbatim]" if p.get("is_verbatim", True) else "[paraphrased]"
        parts.append(
            f"[P{i}] {p.get('citation', 'Unknown')} {verbatim_tag}\n"
            f"    Source: {p.get('source_field', 'unknown')}\n"
            f"    Relevance: {p.get('relevance', '')}\n"
            f"    Text: {p.get('passage', '')[:2000]}"
        )
    return "\n\n".join(parts)


def format_community_summaries(summaries: list[dict]) -> str:
    """Format GraphRAG community summaries for LLM context."""
    if not summaries:
        return ""
    parts: list[str] = []
    for cs in summaries:
        parts.append(
            f"[Community: {cs.get('title', 'Unknown')}] "
            f"({cs.get('size', 0)} cases)\n"
            f"    {cs.get('summary', '')[:1000]}\n"
            f"    Key principles: {', '.join(cs.get('legal_principles', [])[:5])}"
        )
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
    embedder: EmbeddingProvider | None = None,
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
            unverified_holdings = await _check_holding_accuracy(memo, memo_citations, db, embedder)
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
    embedder: EmbeddingProvider | None = None,
) -> list[str]:
    """Check citation accuracy: missing ratios + semantic holding verification.

    Returns a list of warning strings for:
    - Citations with no stored ratio_decidendi (unverifiable)
    - [B16] Citations where memo's claim semantically diverges from actual ratio
      (misrepresented holdings, cosine similarity < 0.75)

    Uses batch embedding for efficiency. Falls back to ratio-only check
    if embedder is unavailable.
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

    warnings: list[str] = []
    cite_to_ratio: dict[str, str] = {}

    for row in rows:
        cite_text = row[0]
        ratio = row[1]
        if not ratio or len(ratio.strip()) < 20:
            warnings.append(f"{cite_text} [no ratio decidendi on record]")
        else:
            cite_to_ratio[cite_text] = ratio.strip()

    # [B16] Semantic holding verification via embedding similarity
    if embedder and cite_to_ratio:
        try:
            # Extract memo's claim about each citation (sentence containing citation)
            claims: dict[str, str] = {}
            for cite in cite_to_ratio:
                # Find sentences mentioning this citation in the memo
                for sentence in memo.split(". "):
                    if cite in sentence:
                        claims[cite] = sentence.strip()[:500]
                        break

            if claims:
                # Batch embed: claims + ratios
                cite_keys = list(claims.keys())
                claim_texts = [claims[k] for k in cite_keys]
                ratio_texts = [cite_to_ratio[k][:500] for k in cite_keys]

                all_texts = claim_texts + ratio_texts
                all_vectors = await embedder.embed_batch(all_texts)

                # Compare claim vs ratio embeddings
                n = len(cite_keys)
                for i, cite in enumerate(cite_keys):
                    claim_vec = all_vectors[i]
                    ratio_vec = all_vectors[n + i]
                    # Cosine similarity
                    dot = sum(a * b for a, b in zip(claim_vec, ratio_vec))
                    mag_a = sum(a * a for a in claim_vec) ** 0.5
                    mag_b = sum(b * b for b in ratio_vec) ** 0.5
                    if mag_a > 0 and mag_b > 0:
                        sim = dot / (mag_a * mag_b)
                    else:
                        sim = 0.0

                    if sim < 0.75:
                        label = "misrepresented" if sim < 0.5 else "partially_accurate"
                        warnings.append(
                            f"{cite} [holding {label}: similarity={sim:.2f}]"
                        )
        except Exception:
            logger.warning("Semantic holding verification failed", exc_info=True)

    return warnings


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
    precomputed_embeddings: dict[str, list[float]] | None = None,
    **search_kwargs: Any,
) -> list[dict]:
    """Run hybrid_search for each query in parallel, return combined results.

    Failed individual searches are logged and skipped (not propagated).
    Each result dict gets a 'source_query' field added.

    Each parallel search opens its **own** ``AsyncSession`` to avoid
    SQLAlchemy's "concurrent operations are not permitted" error when
    multiple FTS queries hit the same session concurrently.  The caller's
    *db* is intentionally unused here — callers that need a session for
    post-search work (e.g. ``enrich_results_with_ratio``) should keep
    their own.
    """
    from app.db.postgres import async_session_factory

    if not queries:
        return []

    _embeddings = precomputed_embeddings or {}

    async def _search_one(sq: str) -> list[dict]:
        async with async_session_factory() as session:
            response = await hybrid_search(
                sq,
                llm=llm,
                embedder=embedder,
                vector_store=vector_store,
                reranker=reranker,
                db=session,
                pre_embedded=_embeddings.get(sq),
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


async def cached_embed_text(embedder: EmbeddingProvider, text_input: str) -> list[float]:
    """[S8-L4] Embed text with Redis cache. Falls through on cache failure."""
    from app.core.agents.research_cache import get_cached_embedding, set_cached_embedding
    from app.db.redis_client import get_redis

    try:
        redis = await get_redis()
    except Exception:
        redis = None

    cached = await get_cached_embedding(redis, text_input)
    if cached is not None:
        return cached

    vector = await embedder.embed_text(text_input)
    await set_cached_embedding(redis, text_input, vector)
    return vector
