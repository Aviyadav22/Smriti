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
    language: str = "en",
) -> list[FTSResult]:
    """Run a PostgreSQL FTS query against the ``cases`` table.

    Uses the ``searchable_text`` tsvector column and ``ts_rank_cd`` for ranking.
    Dynamically constructs filter clauses from *filters*.

    When *language* is ``"hi"``, returns an empty list immediately — Hindi/
    Devanagari text cannot be tokenized by PostgreSQL's English tsvector.
    The caller should rely on vector search for Hindi queries.
    """
    if not query.strip():
        return []

    if language == "hi":
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

    # ts_rank_cd = cover density ranking: rewards proximity of query terms.
    # Chosen over ts_rank/BM25 for legal text (see ADR-019 in DECISIONS.md).
    sql = text(
        f"SELECT id, title, citation, "
        f"ts_rank_cd(searchable_text, ({tsquery_expr})) AS rank, "
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

    # Build additional filter clauses for the cases table (court, year, etc.)
    extra_clauses, extra_params = _build_filter_clauses(filters, table_alias="c")
    params.update(extra_params)

    extra_where = ""
    if extra_clauses:
        extra_where = "AND " + " AND ".join(extra_clauses) + " "

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
        f"{extra_where}"
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


def _escape_ilike(value: str) -> str:
    """Escape ILIKE wildcard characters (``%`` and ``_``) in user-provided strings."""
    return value.replace("%", "\\%").replace("_", "\\_")


def _build_filter_clauses(
    filters: SearchFilters | None,
    table_alias: str = "",
) -> tuple[list[str], dict]:
    """Build SQL WHERE clauses and bind params from search filters.

    Args:
        filters: Search filters to apply.
        table_alias: Optional table alias prefix (e.g. ``"c"``).  When
            provided, all column references are qualified as ``c.column``.
    """
    clauses: list[str] = []
    params: dict = {}

    if filters is None:
        return clauses, params

    prefix = f"{table_alias}." if table_alias else ""

    if filters.court:
        if len(filters.court) == 1:
            escaped = _escape_ilike(filters.court[0])
            clauses.append(f"{prefix}court ILIKE :court_0")
            params["court_0"] = f"%{escaped}%"
        else:
            court_clauses = []
            for i, c in enumerate(filters.court):
                key = f"court_{i}"
                court_clauses.append(f"{prefix}court ILIKE :{key}")
                params[key] = f"%{_escape_ilike(c)}%"
            clauses.append(f"({' OR '.join(court_clauses)})")

    if filters.year_from is not None:
        clauses.append(f"{prefix}year >= :year_from")
        params["year_from"] = filters.year_from

    if filters.year_to is not None:
        clauses.append(f"{prefix}year <= :year_to")
        params["year_to"] = filters.year_to

    if filters.case_type:
        clauses.append(f"{prefix}case_type ILIKE :case_type")
        params["case_type"] = f"%{_escape_ilike(filters.case_type)}%"

    if filters.bench_type:
        clauses.append(f"{prefix}bench_type = :bench_type")
        params["bench_type"] = filters.bench_type

    if filters.judge:
        clauses.append(
            f"EXISTS (SELECT 1 FROM unnest({prefix}judge) AS j WHERE j ILIKE :judge)"
        )
        params["judge"] = f"%{_escape_ilike(filters.judge)}%"

    if filters.act:
        clauses.append(
            f"EXISTS (SELECT 1 FROM unnest({prefix}acts_cited) AS a WHERE a ILIKE :act)"
        )
        params["act"] = f"%{_escape_ilike(filters.act)}%"

    if filters.disposal_nature:
        clauses.append(f"{prefix}disposal_nature ILIKE :disposal_nature")
        params["disposal_nature"] = f"%{_escape_ilike(filters.disposal_nature)}%"

    return clauses, params
