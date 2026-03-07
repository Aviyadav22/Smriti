"""Shared utilities for agent node functions."""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

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
