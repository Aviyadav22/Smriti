"""Judge analytics service for Indian legal research platform."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa
from sqlalchemy import case as sa_case
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case


@dataclass
class JudgeListItem:
    """A judge entry in the list view."""

    name: str
    total_cases: int
    cases_authored: int


@dataclass
class JudgeProfile:
    """Comprehensive judge profile with analytics."""

    name: str
    total_cases: int
    cases_authored: int
    cases_by_year: dict[int, int] = field(default_factory=dict)
    disposal_patterns: dict[str, int] = field(default_factory=dict)
    bench_combinations: list[dict[str, Any]] = field(default_factory=list)
    top_cited_judgments: list[dict[str, Any]] = field(default_factory=list)
    acts_frequency: dict[str, int] = field(default_factory=dict)
    case_types: dict[str, int] = field(default_factory=dict)


@dataclass
class JudgeCaseItem:
    """A case in the judge's case list."""

    id: uuid.UUID
    title: str
    citation: str | None
    year: int | None
    case_type: str | None
    court: str
    decision_date: Any
    is_author: bool


@dataclass
class PaginatedResult:
    """Generic paginated result wrapper."""

    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass
class CourtStats:
    """Court-level statistics."""

    court: str
    total_cases: int
    cases_by_year: dict[int, int] = field(default_factory=dict)
    case_types: dict[str, int] = field(default_factory=dict)
    disposal_patterns: dict[str, int] = field(default_factory=dict)
    top_judges: list[dict[str, int]] = field(default_factory=list)


class JudgeAnalyticsService:
    """Service for judge and court analytics queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_judges(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        """List judges with participation and authorship counts.

        Unnests the judge[] array to get unique judge names with counts.
        """
        # Unnest the judge array to get individual judge names
        unnested = select(
            func.unnest(Case.judge).label("judge_name"),
            Case.author_judge,
        ).where(Case.judge.isnot(None)).subquery()

        # Base query for judge names with counts
        base_query = (
            select(
                unnested.c.judge_name,
                func.count().label("total_cases"),
                func.count(
                    sa_case(
                        (unnested.c.author_judge == unnested.c.judge_name, literal_column("1")),
                        else_=None,
                    )
                ).label("cases_authored"),
            )
            .group_by(unnested.c.judge_name)
        )

        if search:
            search = search.replace("%", "\\%").replace("_", "\\_")
            base_query = base_query.where(
                unnested.c.judge_name.ilike(f"%{search}%")
            )

        # Count total distinct judges
        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self._session.execute(count_query)
        total = count_result.scalar_one_or_none() or 0

        # Paginated results ordered by total_cases desc
        offset = (page - 1) * page_size
        paginated_query = (
            base_query
            .order_by(func.count().desc(), unnested.c.judge_name)
            .offset(offset)
            .limit(page_size)
        )

        result = await self._session.execute(paginated_query)
        rows = result.all()

        items = [
            JudgeListItem(
                name=row.judge_name,
                total_cases=row.total_cases,
                cases_authored=row.cases_authored,
            )
            for row in rows
        ]

        total_pages = max(1, (total + page_size - 1) // page_size)

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_judge_profile(self, judge_name: str) -> JudgeProfile | None:
        """Get comprehensive judge profile with analytics.

        Returns None if no cases found for the judge.
        """
        # Total cases where judge participated
        total_query = select(func.count()).where(
            Case.judge.any(judge_name)
        )
        total_result = await self._session.execute(total_query)
        total_cases = total_result.scalar_one_or_none() or 0

        if total_cases == 0:
            return None

        # Cases authored
        authored_query = select(func.count()).where(
            Case.author_judge == judge_name
        )
        authored_result = await self._session.execute(authored_query)
        cases_authored = authored_result.scalar_one_or_none() or 0

        # Cases by year
        year_query = (
            select(Case.year, func.count().label("count"))
            .where(Case.judge.any(judge_name))
            .where(Case.year.isnot(None))
            .group_by(Case.year)
            .order_by(Case.year)
        )
        year_result = await self._session.execute(year_query)
        cases_by_year = {row.year: row.count for row in year_result.all()}

        # Disposal patterns
        disposal_query = (
            select(Case.disposal_nature, func.count().label("count"))
            .where(Case.judge.any(judge_name))
            .where(Case.disposal_nature.isnot(None))
            .group_by(Case.disposal_nature)
            .order_by(func.count().desc())
        )
        disposal_result = await self._session.execute(disposal_query)
        disposal_patterns = {
            row.disposal_nature: row.count for row in disposal_result.all()
        }

        # Bench combinations — other judges who sat with this judge
        # Use the Python-based fallback directly since the SQL approach with
        # UNNEST in HAVING is not supported and leaves the transaction aborted.
        bench_combinations = await self._get_bench_combinations_fallback(
            judge_name
        )

        # Top cited judgments (cases with most citations in cases_cited)
        cited_query = (
            select(
                Case.id,
                Case.title,
                Case.citation,
                Case.year,
                func.array_length(Case.cases_cited, 1).label("citation_count"),
            )
            .where(Case.judge.any(judge_name))
            .where(Case.cases_cited.isnot(None))
            .order_by(func.array_length(Case.cases_cited, 1).desc().nullslast())
            .limit(10)
        )
        cited_result = await self._session.execute(cited_query)
        top_cited_judgments = [
            {
                "id": str(row.id),
                "title": row.title,
                "citation": row.citation,
                "year": row.year,
                "citation_count": row.citation_count or 0,
            }
            for row in cited_result.all()
        ]

        # Acts frequency
        acts_query = (
            select(
                func.unnest(Case.acts_cited).label("act"),
                func.count().label("count"),
            )
            .where(Case.judge.any(judge_name))
            .where(Case.acts_cited.isnot(None))
            .group_by(literal_column("act"))
            .order_by(func.count().desc())
            .limit(20)
        )
        acts_result = await self._session.execute(acts_query)
        acts_frequency = {row.act: row.count for row in acts_result.all()}

        # Case types
        type_query = (
            select(Case.case_type, func.count().label("count"))
            .where(Case.judge.any(judge_name))
            .where(Case.case_type.isnot(None))
            .group_by(Case.case_type)
            .order_by(func.count().desc())
        )
        type_result = await self._session.execute(type_query)
        case_types = {row.case_type: row.count for row in type_result.all()}

        return JudgeProfile(
            name=judge_name,
            total_cases=total_cases,
            cases_authored=cases_authored,
            cases_by_year=cases_by_year,
            disposal_patterns=disposal_patterns,
            bench_combinations=bench_combinations,
            top_cited_judgments=top_cited_judgments,
            acts_frequency=acts_frequency,
            case_types=case_types,
        )

    async def _get_bench_combinations_fallback(
        self, judge_name: str
    ) -> list[dict[str, Any]]:
        """Fallback method for bench combinations using a simpler query."""
        cases_query = (
            select(Case.judge)
            .where(Case.judge.any(judge_name))
            .limit(5000)
        )
        cases_result = await self._session.execute(cases_query)
        rows = cases_result.all()

        co_judge_counts: dict[str, int] = {}
        for row in rows:
            judges = row[0] or []
            for j in judges:
                if j != judge_name:
                    co_judge_counts[j] = co_judge_counts.get(j, 0) + 1

        sorted_judges = sorted(
            co_judge_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return [
            {"judge": name, "cases_together": count}
            for name, count in sorted_judges
        ]

    async def get_judge_cases(
        self,
        judge_name: str,
        page: int = 1,
        page_size: int = 20,
        year: int | None = None,
        case_type: str | None = None,
    ) -> PaginatedResult:
        """Get paginated cases for a judge with optional filters."""
        base_filter = Case.judge.any(judge_name)

        # Build where conditions
        conditions = [base_filter]
        if year is not None:
            conditions.append(Case.year == year)
        if case_type is not None:
            conditions.append(Case.case_type == case_type)

        # Count total
        count_query = select(func.count()).where(*conditions)
        count_result = await self._session.execute(count_query)
        total = count_result.scalar_one_or_none() or 0

        # Fetch paginated cases
        offset = (page - 1) * page_size
        cases_query = (
            select(
                Case.id,
                Case.title,
                Case.citation,
                Case.year,
                Case.case_type,
                Case.court,
                Case.decision_date,
                Case.author_judge,
            )
            .where(*conditions)
            .order_by(Case.decision_date.desc().nullslast(), Case.year.desc().nullslast())
            .offset(offset)
            .limit(page_size)
        )

        result = await self._session.execute(cases_query)
        rows = result.all()

        items = [
            JudgeCaseItem(
                id=row.id,
                title=row.title,
                citation=row.citation,
                year=row.year,
                case_type=row.case_type,
                court=row.court,
                decision_date=row.decision_date,
                is_author=(row.author_judge == judge_name),
            )
            for row in rows
        ]

        total_pages = max(1, (total + page_size - 1) // page_size)

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def compare_judges(
        self, judge_names: list[str]
    ) -> list[JudgeProfile | None]:
        """Compare 2-3 judges by fetching profiles for each.

        Raises ValueError if fewer than 2 or more than 3 names provided.
        """
        if len(judge_names) < 2:
            raise ValueError("At least 2 judge names are required for comparison")
        if len(judge_names) > 3:
            raise ValueError("At most 3 judge names can be compared at once")

        profiles: list[JudgeProfile | None] = []
        for name in judge_names:
            profile = await self.get_judge_profile(name)
            profiles.append(profile)

        return profiles

    # ------------------------------------------------------------------
    # Enhanced analytics: disposal rates, temporal trends, sentencing stats
    # ------------------------------------------------------------------

    async def calculate_disposal_rates(
        self, judge_name: str
    ) -> dict[str, Any]:
        """Calculate disposal (conviction/acquittal) rates for a judge.

        Groups all cases authored by this judge by disposal_nature and
        returns counts and percentages for each category.

        Returns:
            {
                "total": N,
                "breakdown": {
                    "allowed": {"count": X, "pct": Y},
                    "dismissed": {"count": X, "pct": Y},
                    ...
                }
            }
            Returns {"total": 0, "breakdown": {}} if no cases found.
        """
        # Total authored cases
        total_query = select(func.count()).where(
            Case.author_judge == judge_name
        )
        total_result = await self._session.execute(total_query)
        total = total_result.scalar_one_or_none() or 0

        if total == 0:
            return {"total": 0, "breakdown": {}}

        # Group by disposal_nature
        disposal_query = (
            select(
                Case.disposal_nature,
                func.count().label("count"),
            )
            .where(Case.author_judge == judge_name)
            .where(Case.disposal_nature.isnot(None))
            .group_by(Case.disposal_nature)
            .order_by(func.count().desc())
        )
        disposal_result = await self._session.execute(disposal_query)

        breakdown: dict[str, dict[str, int | float]] = {}
        for row in disposal_result.all():
            nature = row.disposal_nature.lower().strip() if row.disposal_nature else "unknown"
            pct = round((row.count / total) * 100, 2) if total > 0 else 0.0
            breakdown[nature] = {"count": row.count, "pct": pct}

        return {"total": total, "breakdown": breakdown}

    async def calculate_temporal_trends(
        self, judge_name: str
    ) -> list[dict[str, Any]]:
        """Calculate year-over-year trends for a judge's authored cases.

        Groups cases by year (from decision_date, falling back to year column)
        and computes allowed/dismissed counts and percentages per year.

        Returns:
            [
                {
                    "year": YYYY,
                    "total": N,
                    "allowed": N,
                    "dismissed": N,
                    "allowed_pct": float
                },
                ...
            ]
            Returns [] if no cases found.
        """
        # Use COALESCE(EXTRACT(YEAR FROM decision_date), year) for the year
        year_expr = func.coalesce(
            func.extract("year", Case.decision_date).cast(sa.Integer),
            Case.year,
        )

        trends_query = (
            select(
                year_expr.label("yr"),
                func.count().label("total"),
                func.count(
                    sa_case(
                        (func.lower(Case.disposal_nature) == "allowed", literal_column("1")),
                        else_=None,
                    )
                ).label("allowed"),
                func.count(
                    sa_case(
                        (func.lower(Case.disposal_nature) == "dismissed", literal_column("1")),
                        else_=None,
                    )
                ).label("dismissed"),
            )
            .where(Case.author_judge == judge_name)
            .where(
                sa.or_(
                    Case.decision_date.isnot(None),
                    Case.year.isnot(None),
                )
            )
            .group_by(year_expr)
            .order_by(year_expr)
        )

        result = await self._session.execute(trends_query)
        rows = result.all()

        trends: list[dict[str, Any]] = []
        for row in rows:
            if row.yr is None:
                continue
            allowed_pct = round((row.allowed / row.total) * 100, 2) if row.total > 0 else 0.0
            trends.append({
                "year": int(row.yr),
                "total": row.total,
                "allowed": row.allowed,
                "dismissed": row.dismissed,
                "allowed_pct": allowed_pct,
            })

        return trends

    async def calculate_sentencing_stats(
        self, judge_name: str
    ) -> dict[str, Any]:
        """Calculate case type distribution for a judge's authored cases.

        Groups by case_type and returns counts and percentages, giving
        insight into the kinds of matters this judge typically handles.

        Returns:
            {
                "total": N,
                "case_types": {
                    "Criminal Appeal": {"count": X, "pct": Y},
                    "Civil Appeal": {"count": X, "pct": Y},
                    ...
                }
            }
            Returns {"total": 0, "case_types": {}} if no cases found.
        """
        total_query = select(func.count()).where(
            Case.author_judge == judge_name
        )
        total_result = await self._session.execute(total_query)
        total = total_result.scalar_one_or_none() or 0

        if total == 0:
            return {"total": 0, "case_types": {}}

        type_query = (
            select(
                Case.case_type,
                func.count().label("count"),
            )
            .where(Case.author_judge == judge_name)
            .where(Case.case_type.isnot(None))
            .group_by(Case.case_type)
            .order_by(func.count().desc())
        )
        type_result = await self._session.execute(type_query)

        case_types: dict[str, dict[str, int | float]] = {}
        for row in type_result.all():
            pct = round((row.count / total) * 100, 2) if total > 0 else 0.0
            case_types[row.case_type] = {"count": row.count, "pct": pct}

        return {"total": total, "case_types": case_types}

    async def get_court_stats(self, court: str) -> CourtStats | None:
        """Get court-level statistics.

        Returns None if no cases found for the court.
        """
        # Total cases
        total_query = select(func.count()).where(Case.court == court)
        total_result = await self._session.execute(total_query)
        total_cases = total_result.scalar_one_or_none() or 0

        if total_cases == 0:
            return None

        # Cases by year
        year_query = (
            select(Case.year, func.count().label("count"))
            .where(Case.court == court)
            .where(Case.year.isnot(None))
            .group_by(Case.year)
            .order_by(Case.year)
        )
        year_result = await self._session.execute(year_query)
        cases_by_year = {row.year: row.count for row in year_result.all()}

        # Case types
        type_query = (
            select(Case.case_type, func.count().label("count"))
            .where(Case.court == court)
            .where(Case.case_type.isnot(None))
            .group_by(Case.case_type)
            .order_by(func.count().desc())
        )
        type_result = await self._session.execute(type_query)
        case_types = {row.case_type: row.count for row in type_result.all()}

        # Disposal patterns
        disposal_query = (
            select(Case.disposal_nature, func.count().label("count"))
            .where(Case.court == court)
            .where(Case.disposal_nature.isnot(None))
            .group_by(Case.disposal_nature)
            .order_by(func.count().desc())
        )
        disposal_result = await self._session.execute(disposal_query)
        disposal_patterns = {
            row.disposal_nature: row.count for row in disposal_result.all()
        }

        # Top judges
        judge_query = (
            select(
                func.unnest(Case.judge).label("judge_name"),
                func.count().label("count"),
            )
            .where(Case.court == court)
            .where(Case.judge.isnot(None))
            .group_by(literal_column("judge_name"))
            .order_by(func.count().desc())
            .limit(20)
        )
        judge_result = await self._session.execute(judge_query)
        top_judges = [
            {"judge": row.judge_name, "cases": row.count}
            for row in judge_result.all()
        ]

        return CourtStats(
            court=court,
            total_cases=total_cases,
            cases_by_year=cases_by_year,
            case_types=case_types,
            disposal_patterns=disposal_patterns,
            top_judges=top_judges,
        )


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


async def calculate_disposal_rates(
    judge_name: str, db: AsyncSession
) -> dict[str, Any]:
    """Calculate disposal (conviction/acquittal) rates for a judge.

    Convenience wrapper around JudgeAnalyticsService.calculate_disposal_rates.
    """
    service = JudgeAnalyticsService(db)
    return await service.calculate_disposal_rates(judge_name)


async def calculate_temporal_trends(
    judge_name: str, db: AsyncSession
) -> list[dict[str, Any]]:
    """Calculate year-over-year trends for a judge's authored cases.

    Convenience wrapper around JudgeAnalyticsService.calculate_temporal_trends.
    """
    service = JudgeAnalyticsService(db)
    return await service.calculate_temporal_trends(judge_name)


async def calculate_sentencing_stats(
    judge_name: str, db: AsyncSession
) -> dict[str, Any]:
    """Calculate case type distribution for a judge's authored cases.

    Convenience wrapper around JudgeAnalyticsService.calculate_sentencing_stats.
    """
    service = JudgeAnalyticsService(db)
    return await service.calculate_sentencing_stats(judge_name)
