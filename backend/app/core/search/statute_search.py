"""Statute lookup for the research agent: named sections first, then ranked FTS.

The planner's statute tasks are long sentences ("Indian Contract Act 1872
Sections 126 127 128 73 74 text and Specific Relief Act 1963 ..."). Feeding
that to websearch_to_tsquery ANDs every word together and matches nothing, so:

1. Pull explicit section references out of the text and fetch those rows.
2. Rank the rest with an OR query over the text's lexemes (ts_rank_cd).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# "Section 126", "Sections 126, 127 and 128", "S. 73", "Ss. 73-74", "Article 21"
_SECTION_GROUP = re.compile(
    r"\b(?:sections?|secs?\.?|ss?\.|articles?|arts?\.)\s*"
    r"((?:\d+[A-Z]{0,2}(?:\(\d+\))?(?:\s*(?:,|and|&|or|to|-|–)\s*|\s+)?)+)",
    re.IGNORECASE,
)
_SECTION_NUMBER = re.compile(r"\d+[A-Z]{0,2}")


@dataclass(frozen=True)
class Act:
    name: str  # "Indian Contract Act, 1872"
    short: str | None  # "ICA"

    @property
    def base(self) -> str:
        """Name without the year: "Indian Contract Act"."""
        return re.sub(r",?\s*\d{4}\s*$", "", self.name).strip()


async def load_acts(db: AsyncSession) -> list[Act]:
    rows = await db.execute(text("SELECT DISTINCT act_name, act_short_name FROM statutes"))
    return [Act(name=r[0], short=r[1]) for r in rows.fetchall() if r[0]]


def _act_mentions(query: str, acts: list[Act]) -> list[tuple[int, Act]]:
    """(position, act) for every act named in the query, longest names first."""
    found: list[tuple[int, Act]] = []
    taken: list[range] = []
    candidates: list[tuple[str, Act]] = []
    for act in acts:
        candidates.append((act.base, act))
        # Short forms like "IPC" or "CrPC" only count as whole words; "COI" is
        # never how anyone writes the Constitution (handled below).
        if act.short and len(act.short) >= 2 and act.short.upper() != "COI":
            candidates.append((act.short, act))
    for label, act in sorted(candidates, key=lambda c: -len(c[0])):
        for m in re.finditer(rf"\b{re.escape(label)}\b", query, re.IGNORECASE):
            if any(m.start() in r for r in taken):
                continue
            taken.append(range(m.start(), m.end()))
            found.append((m.start(), act))
    if re.search(r"\bconstitution\b", query, re.IGNORECASE):
        const = next((a for a in acts if a.name.lower().startswith("constitution")), None)
        if const and all(a != const for _, a in found):
            found.append((query.lower().index("constitution"), const))
    return sorted(found, key=lambda f: f[0])


# Text allowed between a section list and the act it belongs to:
# "439 CrPC", "34 of the IPC", "21 of the Constitution", "302 under IPC".
_TRAILING_LINK = re.compile(r"^[\s,]*(?:(?:of|under|in)\s+)?(?:the\s+)?$", re.IGNORECASE)


def _owner(query: str, group: re.Match, pool: list[tuple[int, Act]]) -> Act:
    """The act a section group refers to: one named right after it, else the
    nearest one before it, else the nearest overall."""
    after = [m for m in pool if m[0] >= group.end() and _TRAILING_LINK.match(query[group.end() : m[0]])]
    if after:
        return min(after, key=lambda m: m[0])[1]
    before = [m for m in pool if m[0] < group.start()]
    if before:
        return max(before, key=lambda m: m[0])[1]
    return min(pool, key=lambda m: abs(m[0] - group.start()))[1]


def find_section_refs(query: str, acts: list[Act]) -> dict[str, list[str]]:
    """Map act name -> section numbers explicitly mentioned in the query.

    Each "Section(s) ..." group belongs to the act named right after it
    ("Section 126 of the Indian Contract Act") or, failing that, the one before
    it ("Indian Contract Act Sections 126 127").
    """
    mentions = _act_mentions(query, acts)
    if not mentions:
        return {}
    refs: dict[str, list[str]] = {}
    for group in _SECTION_GROUP.finditer(query):
        numbers = _SECTION_NUMBER.findall(group.group(1))
        # Years that sneak in ("Section 73 ... Act 1963") aren't sections here.
        numbers = [n for n in numbers if not (len(n) == 4 and n.isdigit() and 1800 <= int(n) <= 2100)]
        if not numbers:
            continue
        is_article = group.group(0).lower().startswith("art")
        pool = [m for m in mentions if m[1].name.lower().startswith("constitution")] if is_article else mentions
        if not pool:
            continue
        act = _owner(query, group, pool)
        for n in numbers:
            refs.setdefault(act.name, [])
            if n not in refs[act.name]:
                refs[act.name].append(n)
    return refs


async def lookup_sections(db: AsyncSession, refs: dict[str, list[str]]) -> list[dict]:
    rows: list[dict] = []
    for act_name, sections in refs.items():
        result = await db.execute(
            text(
                "SELECT * FROM statutes WHERE act_name = :act AND section_number = ANY(:secs) "
                "ORDER BY is_repealed, section_number"
            ),
            {"act": act_name, "secs": sections},
        )
        rows.extend(dict(r) for r in result.mappings().all())
    return rows


# Words in almost every statute query; matching on them ranks noise first.
_GENERIC_TERMS = (
    "act section sections provision provisions relevant text law laws rule rules "
    "code india indian court courts case cases clause sub subsection article articles "
    "chapter part read under amendment amended year whether"
)


async def ranked_search(db: AsyncSession, query: str, limit: int = 8) -> list[dict]:
    """Sections matching the query's distinctive words, most words matched first."""
    result = await db.execute(
        text(
            "WITH terms AS ("
            "  SELECT ARRAY(SELECT unnest(tsvector_to_array(to_tsvector('english', :q))) "
            "    EXCEPT SELECT unnest(tsvector_to_array(to_tsvector('english', :generic)))) AS words"
            "), q AS ("
            "  SELECT words, to_tsquery('english', array_to_string(ARRAY("
            "    SELECT quote_literal(w) FROM unnest(words) w), ' | ')) AS tsq FROM terms"
            ") "
            "SELECT s.*, ("
            "  SELECT count(*) FROM unnest(q.words) w "
            "  WHERE s.searchable_text @@ to_tsquery('english', quote_literal(w))"
            ") AS hits, ts_rank(s.searchable_text, q.tsq) AS rank "
            "FROM statutes s, q "
            "WHERE cardinality(q.words) > 0 AND s.searchable_text @@ q.tsq "
            "ORDER BY hits DESC, rank DESC LIMIT :limit"
        ),
        {"q": query, "generic": _GENERIC_TERMS, "limit": limit},
    )
    return [dict(r) for r in result.mappings().all()]
