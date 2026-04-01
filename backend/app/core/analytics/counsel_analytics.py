"""Counsel analytics service for Indian legal research platform."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

_HONORIFICS_RE = re.compile(
    r"\b(?:Mr\.|Mrs\.|Ms\.|Smt\.|Shri|Sri|Dr\.|Hon'ble|Adv\.|Prof\.)\s*",
    re.IGNORECASE,
)

_DESIGNATION_SUFFIXES_RE = re.compile(
    r",?\s*(?:Senior\s+Advocate|Sr\.?\s*Adv\.?(?:ocate)?\.?|Sr\.?\s+Advocate)\s*$",
    re.IGNORECASE,
)


def normalize_counsel_name(name: str) -> str:
    """Strip honorifics and normalize designation suffixes.

    Examples:
        "Mr. R.K. Sharma, Sr. Adv." -> "R.K. Sharma"
        "Smt. Indira Jaising, Senior Advocate" -> "Indira Jaising"
        "Dr. A.M. Singhvi" -> "A.M. Singhvi"
    """
    # Strip designation suffixes FIRST (before honorifics, since "Adv." appears in both)
    result = _DESIGNATION_SUFFIXES_RE.sub("", name)
    result = _HONORIFICS_RE.sub("", result)
    # Strip trailing commas, periods, and whitespace
    result = result.strip(" ,.")
    return result


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CounselListItem:
    """A counsel entry in the search/list view."""

    name: str
    total_cases: int
    designation: str  # most common designation


@dataclass
class CounselProfile:
    """Comprehensive counsel profile with analytics."""

    name: str
    normalized_name: str
    total_cases: int
    petitioner_cases: int
    respondent_cases: int
    win_rate: float
    case_types: dict[str, int] = field(default_factory=dict)
    acts_frequency: dict[str, int] = field(default_factory=dict)
    designation: str = ""
    active_years: tuple[int, int] = (0, 0)
    top_matchups: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CounselCaseItem:
    """A case in the counsel's case list."""

    id: str
    title: str
    citation: str | None
    year: int | None
    case_type: str | None
    party_side: str  # petitioner / respondent
    outcome: str | None
    won: bool


# ---------------------------------------------------------------------------
# Win-rate helpers
# ---------------------------------------------------------------------------

_FAVORABLE_PETITIONER = {"allowed", "partly allowed"}
_FAVORABLE_RESPONDENT = {"dismissed"}


def _is_win(party_side: str, disposal_nature: str | None) -> bool:
    """Determine whether the disposal was favorable for the given side."""
    if not disposal_nature:
        return False
    dn = disposal_nature.strip().lower()
    if party_side == "petitioner":
        return dn in _FAVORABLE_PETITIONER
    if party_side == "respondent":
        return dn in _FAVORABLE_RESPONDENT
    return False


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CounselAnalyticsService:
    """Service for counsel analytics queries using party_counsel JSONB."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -----------------------------------------------------------------------
    # search_counsel
    # -----------------------------------------------------------------------

    async def search_counsel(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CounselListItem], int]:
        """Search counsel names in the party_counsel JSONB column.

        Returns (items, total_count).
        """
        safe_query = query.replace("%", "\\%").replace("_", "\\_")
        name_pattern = f"%{safe_query}%"

        # Count distinct counsel names matching the query
        count_sql = text(
            """
            WITH counsel_names AS (
                SELECT DISTINCT elem->>'counsel_name' AS counsel_name
                FROM cases c,
                     jsonb_array_elements(c.party_counsel) AS elem
                WHERE c.party_counsel IS NOT NULL
                  AND lower(elem->>'counsel_name') LIKE lower(:name_pattern)
            )
            SELECT COUNT(*) FROM counsel_names
            """
        )

        count_result = await self._session.execute(
            count_sql, {"name_pattern": name_pattern}
        )
        total = count_result.scalar_one_or_none() or 0

        if total == 0:
            return [], 0

        offset = (page - 1) * page_size

        results_sql = text(
            """
            WITH counsel_entries AS (
                SELECT
                    c.id AS case_id,
                    elem->>'counsel_name' AS counsel_name,
                    elem->>'designation' AS designation
                FROM cases c,
                     jsonb_array_elements(c.party_counsel) AS elem
                WHERE c.party_counsel IS NOT NULL
                  AND lower(elem->>'counsel_name') LIKE lower(:name_pattern)
            )
            SELECT
                counsel_name,
                COUNT(DISTINCT case_id) AS total_cases,
                MODE() WITHIN GROUP (ORDER BY designation) AS designation
            FROM counsel_entries
            GROUP BY counsel_name
            ORDER BY total_cases DESC, counsel_name
            OFFSET :offset
            LIMIT :limit
            """
        )

        result = await self._session.execute(
            results_sql,
            {"name_pattern": name_pattern, "offset": offset, "limit": page_size},
        )
        rows = result.all()

        items = [
            CounselListItem(
                name=row.counsel_name,
                total_cases=row.total_cases,
                designation=row.designation or "advocate",
            )
            for row in rows
        ]

        return items, total

    # -----------------------------------------------------------------------
    # get_counsel_profile
    # -----------------------------------------------------------------------

    async def get_counsel_profile(self, name: str) -> CounselProfile | None:
        """Get comprehensive counsel profile with analytics.

        Uses normalized name matching. Returns None if no cases found.
        """
        normalized = normalize_counsel_name(name)

        # Fetch all cases where this counsel appeared
        cases_sql = text(
            """
            SELECT
                c.id, c.year, c.case_type, c.disposal_nature,
                elem->>'party' AS party_side,
                elem->>'counsel_name' AS counsel_name,
                elem->>'designation' AS designation
            FROM cases c,
                 jsonb_array_elements(c.party_counsel) AS elem
            WHERE c.party_counsel IS NOT NULL
              AND lower(elem->>'counsel_name') = lower(:name)
            """
        )

        result = await self._session.execute(cases_sql, {"name": name})
        rows = result.all()

        if not rows:
            # Try normalized name
            result = await self._session.execute(cases_sql, {"name": normalized})
            rows = result.all()

        if not rows:
            return None

        # Compute stats
        case_ids = set()
        petitioner_cases = 0
        respondent_cases = 0
        wins = 0
        total_with_outcome = 0
        case_types: dict[str, int] = {}
        designations: dict[str, int] = {}
        years: list[int] = []

        for row in rows:
            case_ids.add(row.id)
            side = (row.party_side or "").lower()
            if side == "petitioner":
                petitioner_cases += 1
            elif side == "respondent":
                respondent_cases += 1

            if row.disposal_nature:
                total_with_outcome += 1
                if _is_win(side, row.disposal_nature):
                    wins += 1

            if row.case_type:
                case_types[row.case_type] = case_types.get(row.case_type, 0) + 1

            if row.designation:
                designations[row.designation] = designations.get(row.designation, 0) + 1

            if row.year:
                years.append(row.year)

        total_cases = len(case_ids)
        win_rate = round((wins / total_with_outcome) * 100, 2) if total_with_outcome > 0 else 0.0

        # Most common designation
        designation = max(designations, key=designations.get) if designations else "advocate"

        # Active years
        active_years = (min(years), max(years)) if years else (0, 0)

        # Acts frequency — fetch from the matched cases
        acts_frequency: dict[str, int] = {}
        if case_ids:
            acts_sql = text(
                """
                SELECT act, COUNT(*) AS count
                FROM (
                    SELECT unnest(acts_cited) AS act
                    FROM cases
                    WHERE id = ANY(:case_ids)
                      AND acts_cited IS NOT NULL
                ) sub
                GROUP BY act
                ORDER BY count DESC
                LIMIT 20
                """
            )
            acts_result = await self._session.execute(
                acts_sql, {"case_ids": list(case_ids)}
            )
            acts_frequency = {r.act: r.count for r in acts_result.all()}

        # Top matchups
        matchups = await self.get_counsel_matchups(name, limit=10)

        return CounselProfile(
            name=name,
            normalized_name=normalized,
            total_cases=total_cases,
            petitioner_cases=petitioner_cases,
            respondent_cases=respondent_cases,
            win_rate=win_rate,
            case_types=case_types,
            acts_frequency=acts_frequency,
            designation=designation,
            active_years=active_years,
            top_matchups=matchups,
        )

    # -----------------------------------------------------------------------
    # get_counsel_cases
    # -----------------------------------------------------------------------

    async def get_counsel_cases(
        self,
        name: str,
        page: int = 1,
        page_size: int = 20,
        year_from: int | None = None,
        year_to: int | None = None,
        case_type: str | None = None,
    ) -> tuple[list[CounselCaseItem], int]:
        """Get paginated case list for a counsel.

        Returns (items, total_count).
        """
        # Build WHERE conditions dynamically
        conditions = [
            "c.party_counsel IS NOT NULL",
            "lower(elem->>'counsel_name') = lower(:name)",
        ]
        params: dict[str, Any] = {"name": name}

        if year_from is not None:
            conditions.append("c.year >= :year_from")
            params["year_from"] = year_from
        if year_to is not None:
            conditions.append("c.year <= :year_to")
            params["year_to"] = year_to
        if case_type is not None:
            conditions.append("c.case_type = :case_type")
            params["case_type"] = case_type

        where_clause = " AND ".join(conditions)

        # Count
        count_sql = text(
            f"""
            SELECT COUNT(DISTINCT c.id)
            FROM cases c,
                 jsonb_array_elements(c.party_counsel) AS elem
            WHERE {where_clause}
            """
        )
        count_result = await self._session.execute(count_sql, params)
        total = count_result.scalar_one_or_none() or 0

        if total == 0:
            return [], 0

        offset = (page - 1) * page_size

        results_sql = text(
            f"""
            SELECT * FROM (
                SELECT DISTINCT ON (c.id)
                    c.id::text AS id,
                    c.title,
                    c.citation,
                    c.year,
                    c.case_type,
                    c.disposal_nature,
                    elem->>'party' AS party_side
                FROM cases c,
                     jsonb_array_elements(c.party_counsel) AS elem
                WHERE {where_clause}
                ORDER BY c.id, c.year DESC NULLS LAST
            ) sub
            ORDER BY sub.year DESC NULLS LAST
            LIMIT :limit OFFSET :offset
            """
        )
        params["limit"] = page_size
        params["offset"] = offset

        result = await self._session.execute(results_sql, params)
        rows = result.all()

        items = [
            CounselCaseItem(
                id=row.id,
                title=row.title,
                citation=row.citation,
                year=row.year,
                case_type=row.case_type,
                party_side=row.party_side or "unknown",
                outcome=row.disposal_nature,
                won=_is_win(row.party_side or "", row.disposal_nature),
            )
            for row in rows
        ]

        return items, total

    # -----------------------------------------------------------------------
    # get_counsel_matchups
    # -----------------------------------------------------------------------

    async def get_counsel_matchups(
        self,
        name: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find opposing counsels and head-to-head records.

        For each case where this counsel appeared, find counsel(s) on the
        opposite side. Aggregate: {opponent, total, wins, losses, win_rate}.
        """
        # Fetch cases with all counsel entries for cases where this counsel appeared
        cases_sql = text(
            """
            SELECT
                c.id,
                c.disposal_nature,
                jsonb_agg(
                    jsonb_build_object(
                        'counsel_name', elem->>'counsel_name',
                        'party', elem->>'party'
                    )
                ) AS counsel_list
            FROM cases c,
                 jsonb_array_elements(c.party_counsel) AS elem
            WHERE c.party_counsel IS NOT NULL
              AND c.id IN (
                  SELECT c2.id
                  FROM cases c2,
                       jsonb_array_elements(c2.party_counsel) AS e2
                  WHERE lower(e2->>'counsel_name') = lower(:name)
              )
            GROUP BY c.id, c.disposal_nature
            """
        )

        result = await self._session.execute(cases_sql, {"name": name})
        rows = result.all()

        # Process in Python to find opposing counsel
        opponent_stats: dict[str, dict[str, int]] = {}

        for row in rows:
            counsel_list = row.counsel_list
            if not counsel_list:
                continue

            # Find this counsel's side
            my_side = None
            for entry in counsel_list:
                if entry.get("counsel_name", "").lower() == name.lower():
                    my_side = (entry.get("party") or "").lower()
                    break

            if not my_side:
                continue

            # Find opponents (opposite side)
            opposite_side = "respondent" if my_side == "petitioner" else "petitioner"
            disposal = row.disposal_nature
            i_won = _is_win(my_side, disposal)

            for entry in counsel_list:
                opp_name = entry.get("counsel_name", "")
                opp_side = (entry.get("party") or "").lower()
                if opp_side == opposite_side and opp_name.lower() != name.lower():
                    if opp_name not in opponent_stats:
                        opponent_stats[opp_name] = {"total": 0, "wins": 0, "losses": 0}
                    opponent_stats[opp_name]["total"] += 1
                    if i_won:
                        opponent_stats[opp_name]["wins"] += 1
                    elif disposal:  # Only count as loss if there was an outcome
                        opponent_stats[opp_name]["losses"] += 1

        # Sort by total cases and return top N
        sorted_opponents = sorted(
            opponent_stats.items(), key=lambda x: x[1]["total"], reverse=True
        )[:limit]

        return [
            {
                "opponent": opp_name,
                "total": stats["total"],
                "wins": stats["wins"],
                "losses": stats["losses"],
                "win_rate": round(
                    (stats["wins"] / stats["total"]) * 100, 2
                ) if stats["total"] > 0 else 0.0,
            }
            for opp_name, stats in sorted_opponents
        ]
