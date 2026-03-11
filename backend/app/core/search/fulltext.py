"""PostgreSQL full-text search using tsvector index on the cases table.

Uses ts_rank_cd (cover density ranking) for search quality. All queries
are parameterized via SQLAlchemy text() to prevent injection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.search.query import SearchFilters

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FTSResult:
    """A single full-text search result."""

    case_id: str
    rank: float
    title: str | None = None
    citation: str | None = None
    snippet: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def search_fulltext(
    query: str,
    *,
    filters: SearchFilters | None = None,
    limit: int = 20,
    db: AsyncSession,
) -> list[FTSResult]:
    """Run a PostgreSQL FTS query against the ``cases`` table.

    Uses the ``searchable_text`` tsvector column and ``ts_rank_cd`` for ranking.
    Dynamically constructs filter clauses from *filters*.
    """
    if not query.strip():
        return []

    if filters and filters.judgment_section:
        return await _search_sections(query, filters=filters, limit=limit, db=db)

    where_clauses, params = _build_filter_clauses(filters)

    # Detect quoted phrases for phraseto_tsquery support
    tsquery_expr = _build_tsquery_expr(query, params)

    # Core FTS clause
    where_clauses.insert(
        0, f"searchable_text @@ ({tsquery_expr})"
    )
    params["limit"] = limit

    where_sql = " AND ".join(where_clauses)

    sql = text(
        f"SELECT id, title, citation, "
        f"ts_rank_cd(searchable_text, ({tsquery_expr})) "
        f"  * (1.0 + LN(1 + COALESCE(cited_by_count, 0))) AS rank, "
        f"ts_headline('english', COALESCE(full_text, COALESCE(description, '')), "
        f"({tsquery_expr}), "
        f"'StartSel=**, StopSel=**, MaxWords=50, MinWords=20') AS snippet "
        f"FROM cases "
        f"WHERE {where_sql} "
        f"ORDER BY rank DESC "
        f"LIMIT :limit"
    )

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    return [
        FTSResult(
            case_id=str(row["id"]),
            rank=float(row["rank"]),
            title=row.get("title"),
            citation=row.get("citation"),
            snippet=row.get("snippet"),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Regex to find double-quoted phrases in the query string
_QUOTED_PHRASE_RE = re.compile(r'"([^"]+)"')


def _build_tsquery_expr(query: str, params: dict) -> str:
    """Build a tsquery SQL expression that uses ``phraseto_tsquery`` for quoted
    phrases and ``websearch_to_tsquery`` for the remaining unquoted text.

    ``websearch_to_tsquery`` supports Google-like search syntax including
    boolean operators (AND, OR), negation (-term), and quoted phrases natively.

    Quoted parts are combined with ``&&`` (AND) with the plain part so that
    the phrase proximity requirement is enforced.

    Updates *params* in-place with the bind values for each query fragment.
    Returns a raw SQL expression string (safe -- all user input goes through
    bind parameters).
    """
    phrases = _QUOTED_PHRASE_RE.findall(query)
    remainder = _QUOTED_PHRASE_RE.sub("", query).strip()

    # No quoted phrases -- use websearch_to_tsquery for boolean operator support
    if not phrases:
        params["query"] = query
        return "websearch_to_tsquery('english', :query)"

    parts: list[str] = []

    for i, phrase in enumerate(phrases):
        phrase_stripped = phrase.strip()
        if not phrase_stripped:
            continue
        key = f"phrase_{i}"
        params[key] = phrase_stripped
        parts.append(f"phraseto_tsquery('english', :{key})")

    if remainder:
        params["query"] = remainder
        parts.append("websearch_to_tsquery('english', :query)")

    if not parts:
        # Edge case: only empty quotes -- fall back to full query
        params["query"] = query
        return "websearch_to_tsquery('english', :query)"

    return " && ".join(parts)


async def _search_sections(
    query: str,
    *,
    filters: SearchFilters,
    limit: int = 20,
    db: AsyncSession,
) -> list[FTSResult]:
    """Search within specific judgment sections using case_sections table."""
    params: dict = {
        "query": query,
        "section_type": filters.judgment_section,
        "limit": limit,
    }

    sql = text(
        "SELECT cs.case_id AS id, c.title, c.citation, "
        "ts_rank_cd("
        "  COALESCE(cs.searchable_content, to_tsvector('english', cs.content)),"
        "  websearch_to_tsquery('english', :query)"
        ") AS rank, "
        "ts_headline('english', LEFT(cs.content, 500), "
        "websearch_to_tsquery('english', :query), "
        "'StartSel=**, StopSel=**, MaxWords=50, MinWords=20') AS snippet "
        "FROM case_sections cs "
        "JOIN cases c ON c.id = cs.case_id "
        "WHERE cs.section_type = :section_type "
        "AND COALESCE(cs.searchable_content, to_tsvector('english', cs.content)) "
        "    @@ websearch_to_tsquery('english', :query) "
        "ORDER BY rank DESC "
        "LIMIT :limit"
    )

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    return [
        FTSResult(
            case_id=str(row["id"]),
            rank=float(row["rank"]),
            title=row.get("title"),
            citation=row.get("citation"),
            snippet=row.get("snippet"),
        )
        for row in rows
    ]


def _build_filter_clauses(
    filters: SearchFilters | None,
) -> tuple[list[str], dict]:
    """Build SQL WHERE clauses and bind params from search filters."""
    clauses: list[str] = []
    params: dict = {}

    if filters is None:
        return clauses, params

    if filters.court:
        if len(filters.court) == 1:
            clauses.append("court ILIKE :court_0")
            params["court_0"] = f"%{filters.court[0]}%"
        else:
            court_clauses = []
            for i, c in enumerate(filters.court):
                key = f"court_{i}"
                court_clauses.append(f"court ILIKE :{key}")
                params[key] = f"%{c}%"
            clauses.append(f"({' OR '.join(court_clauses)})")

    if filters.year_from is not None:
        clauses.append("year >= :year_from")
        params["year_from"] = filters.year_from

    if filters.year_to is not None:
        clauses.append("year <= :year_to")
        params["year_to"] = filters.year_to

    if filters.case_type:
        clauses.append("case_type ILIKE :case_type")
        params["case_type"] = f"%{filters.case_type}%"

    if filters.bench_type:
        clauses.append("bench_type = :bench_type")
        params["bench_type"] = filters.bench_type

    if filters.judge:
        clauses.append(
            "EXISTS (SELECT 1 FROM unnest(judge) AS j WHERE j ILIKE :judge)"
        )
        params["judge"] = f"%{filters.judge}%"

    if filters.act:
        clauses.append(
            "EXISTS (SELECT 1 FROM unnest(acts_cited) AS a WHERE a ILIKE :act)"
        )
        params["act"] = f"%{filters.act}%"

    if filters.disposal_nature:
        clauses.append("disposal_nature ILIKE :disposal_nature")
        params["disposal_nature"] = f"%{filters.disposal_nature}%"

    return clauses, params
