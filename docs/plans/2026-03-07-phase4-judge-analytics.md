# Phase 4: Judge Analytics — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship Judge Analytics feature using the existing ~740 ingested cases — judge directory, judge profiles with stats dashboards, judge comparison, court statistics, and clickable judge links from case detail pages.

**Architecture:** New `api/routes/judges.py` route module with 5 endpoints querying PostgreSQL `cases` table via SQLAlchemy async. A new `core/analytics/judge_analytics.py` service module encapsulates all analytics SQL queries. Redis caching (1-hour TTL) for computed stats. Frontend adds 3 new pages (`/judges`, `/judge/[name]`, `/judges/compare`) plus updates case detail page with clickable judge links. No new external services or interfaces needed — this is pure SQL analytics over existing data.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), Next.js 15 + Tailwind + shadcn/ui + recharts (frontend charts), Redis (caching), Vitest + pytest (tests)

---

## Task 1: Backend — Judge Analytics Service Layer

**Files:**
- Create: `backend/app/core/analytics/__init__.py`
- Create: `backend/app/core/analytics/judge_analytics.py`
- Test: `backend/tests/unit/test_judge_analytics.py`

**Step 1: Write failing tests for judge analytics service**

Create `backend/tests/unit/test_judge_analytics.py`:

```python
"""Unit tests for judge analytics service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import date

from app.core.analytics.judge_analytics import JudgeAnalyticsService


@pytest.fixture
def mock_db():
    """Create a mock async DB session."""
    session = AsyncMock()
    return session


@pytest.fixture
def service(mock_db):
    return JudgeAnalyticsService(mock_db)


# --- list_judges tests ---

class TestListJudges:
    @pytest.mark.asyncio
    async def test_list_judges_returns_judge_names_with_counts(self, service, mock_db):
        """Should return list of judges with their case counts."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("Justice D.Y. Chandrachud", 45, 12),
            ("Justice S.A. Bobde", 30, 8),
        ]
        mock_db.execute.return_value = mock_result

        result = await service.list_judges()

        assert len(result) == 2
        assert result[0]["name"] == "Justice D.Y. Chandrachud"
        assert result[0]["total_cases"] == 45
        assert result[0]["cases_authored"] == 12

    @pytest.mark.asyncio
    async def test_list_judges_with_search_filter(self, service, mock_db):
        """Should filter judges by name search."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("Justice D.Y. Chandrachud", 45, 12),
        ]
        mock_db.execute.return_value = mock_result

        result = await service.list_judges(search="Chandrachud")

        assert len(result) == 1
        assert "Chandrachud" in result[0]["name"]

    @pytest.mark.asyncio
    async def test_list_judges_empty_db(self, service, mock_db):
        """Should return empty list when no cases exist."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await service.list_judges()
        assert result == []


# --- get_judge_profile tests ---

class TestGetJudgeProfile:
    @pytest.mark.asyncio
    async def test_get_judge_profile_returns_stats(self, service, mock_db):
        """Should return comprehensive judge stats."""
        # Mock cases_by_year
        mock_years = MagicMock()
        mock_years.all.return_value = [(2020, 5), (2021, 8), (2022, 3)]

        # Mock disposal_patterns
        mock_disposal = MagicMock()
        mock_disposal.all.return_value = [
            ("Dismissed", 10),
            ("Allowed", 5),
            ("Partly Allowed", 2),
        ]

        # Mock bench_combinations
        mock_bench = MagicMock()
        mock_bench.all.return_value = [
            ("Justice A, Justice B", 5),
            ("Justice A, Justice C", 3),
        ]

        # Mock top_cited (most cited judgments authored)
        mock_cited = MagicMock()
        mock_cited.all.return_value = [
            (uuid4(), "Case Title 1", "(2020) 1 SCC 1", 50),
            (uuid4(), "Case Title 2", "(2021) 2 SCC 2", 30),
        ]

        # Mock acts_frequency
        mock_acts = MagicMock()
        mock_acts.all.return_value = [
            ("Constitution of India", 15),
            ("Indian Penal Code", 8),
        ]

        # Mock total_cases and cases_authored
        mock_total = MagicMock()
        mock_total.scalar_one_or_none.return_value = 45

        mock_authored = MagicMock()
        mock_authored.scalar_one_or_none.return_value = 12

        # Mock case_types
        mock_case_types = MagicMock()
        mock_case_types.all.return_value = [
            ("Criminal Appeal", 20),
            ("Civil Appeal", 15),
        ]

        mock_db.execute.side_effect = [
            mock_total,
            mock_authored,
            mock_years,
            mock_disposal,
            mock_bench,
            mock_cited,
            mock_acts,
            mock_case_types,
        ]

        result = await service.get_judge_profile("Justice D.Y. Chandrachud")

        assert result["name"] == "Justice D.Y. Chandrachud"
        assert result["total_cases"] == 45
        assert result["cases_authored"] == 12
        assert len(result["cases_by_year"]) == 3
        assert len(result["disposal_patterns"]) == 3
        assert len(result["bench_combinations"]) == 2
        assert len(result["top_cited_judgments"]) == 2
        assert len(result["acts_frequency"]) == 2
        assert len(result["case_types"]) == 2

    @pytest.mark.asyncio
    async def test_get_judge_profile_not_found(self, service, mock_db):
        """Should return None when judge has no cases."""
        mock_total = MagicMock()
        mock_total.scalar_one_or_none.return_value = 0
        mock_db.execute.return_value = mock_total

        result = await service.get_judge_profile("Justice Nobody")
        assert result is None


# --- get_judge_cases tests ---

class TestGetJudgeCases:
    @pytest.mark.asyncio
    async def test_get_judge_cases_paginated(self, service, mock_db):
        """Should return paginated list of cases for a judge."""
        case_id = uuid4()
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (case_id, "Test Case", "(2020) 1 SCC 1", "Supreme Court of India",
             2020, "Criminal Appeal", "Dismissed", date(2020, 6, 15)),
        ]
        mock_count = MagicMock()
        mock_count.scalar_one_or_none.return_value = 1

        mock_db.execute.side_effect = [mock_count, mock_result]

        result = await service.get_judge_cases("Justice X", page=1, page_size=20)

        assert result["total"] == 1
        assert len(result["cases"]) == 1
        assert result["cases"][0]["title"] == "Test Case"


# --- compare_judges tests ---

class TestCompareJudges:
    @pytest.mark.asyncio
    async def test_compare_two_judges(self, service, mock_db):
        """Should return comparison data for two judges."""
        # We'll mock get_judge_profile for each judge
        with patch.object(service, "get_judge_profile") as mock_profile:
            mock_profile.side_effect = [
                {
                    "name": "Justice A",
                    "total_cases": 50,
                    "cases_authored": 20,
                    "cases_by_year": [],
                    "disposal_patterns": [{"disposal_nature": "Dismissed", "count": 30}],
                    "bench_combinations": [],
                    "top_cited_judgments": [],
                    "acts_frequency": [],
                    "case_types": [],
                },
                {
                    "name": "Justice B",
                    "total_cases": 30,
                    "cases_authored": 10,
                    "cases_by_year": [],
                    "disposal_patterns": [{"disposal_nature": "Allowed", "count": 20}],
                    "bench_combinations": [],
                    "top_cited_judgments": [],
                    "acts_frequency": [],
                    "case_types": [],
                },
            ]

            result = await service.compare_judges(["Justice A", "Justice B"])

            assert len(result) == 2
            assert result[0]["name"] == "Justice A"
            assert result[1]["name"] == "Justice B"

    @pytest.mark.asyncio
    async def test_compare_judges_max_three(self, service):
        """Should raise error if more than 3 judges compared."""
        with pytest.raises(ValueError, match="at most 3"):
            await service.compare_judges(["A", "B", "C", "D"])


# --- get_court_stats tests ---

class TestGetCourtStats:
    @pytest.mark.asyncio
    async def test_get_court_stats(self, service, mock_db):
        """Should return court-level statistics."""
        mock_total = MagicMock()
        mock_total.scalar_one_or_none.return_value = 740

        mock_years = MagicMock()
        mock_years.all.return_value = [(2020, 100), (2021, 150)]

        mock_types = MagicMock()
        mock_types.all.return_value = [("Criminal Appeal", 300), ("Civil Appeal", 200)]

        mock_disposal = MagicMock()
        mock_disposal.all.return_value = [("Dismissed", 400), ("Allowed", 200)]

        mock_judges = MagicMock()
        mock_judges.all.return_value = [
            ("Justice X", 50),
            ("Justice Y", 40),
        ]

        mock_db.execute.side_effect = [
            mock_total, mock_years, mock_types, mock_disposal, mock_judges,
        ]

        result = await service.get_court_stats("Supreme Court of India")

        assert result["court"] == "Supreme Court of India"
        assert result["total_cases"] == 740
        assert len(result["cases_by_year"]) == 2
        assert len(result["case_types"]) == 2
        assert len(result["disposal_patterns"]) == 2
        assert len(result["top_judges"]) == 2
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_judge_analytics.py -v`
Expected: FAIL (module not found)

**Step 3: Write the judge analytics service**

Create `backend/app/core/analytics/__init__.py` (empty file).

Create `backend/app/core/analytics/judge_analytics.py`:

```python
"""Judge analytics service — computes statistics from existing cases data."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, text, desc, case as sql_case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case


class JudgeAnalyticsService:
    """Computes judge and court analytics from the cases table."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_judges(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[dict]:
        """List all judges with case counts.

        Unnests the judge[] array to count participation,
        and counts author_judge for cases authored.
        """
        # Unnest judge array to get individual judge names
        unnested = (
            select(
                func.unnest(Case.judge).label("judge_name"),
                Case.id.label("case_id"),
                Case.author_judge,
            )
            .where(Case.judge.isnot(None))
            .subquery()
        )

        stmt = (
            select(
                unnested.c.judge_name,
                func.count(func.distinct(unnested.c.case_id)).label("total_cases"),
                func.count(
                    func.distinct(
                        sql_case(
                            (unnested.c.author_judge == unnested.c.judge_name, unnested.c.case_id),
                            else_=None,
                        )
                    )
                ).label("cases_authored"),
            )
            .group_by(unnested.c.judge_name)
            .order_by(desc("total_cases"))
        )

        if search:
            stmt = stmt.where(unnested.c.judge_name.ilike(f"%{search}%"))

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self._db.execute(stmt)
        rows = result.all()

        return [
            {
                "name": row[0],
                "total_cases": row[1],
                "cases_authored": row[2],
            }
            for row in rows
        ]

    async def get_judge_profile(self, judge_name: str) -> dict | None:
        """Get comprehensive stats for a specific judge."""
        # Total cases (bench member)
        total_stmt = select(func.count(Case.id)).where(
            Case.judge.any(judge_name)
        )
        total_result = await self._db.execute(total_stmt)
        total_cases = total_result.scalar_one_or_none() or 0

        if total_cases == 0:
            return None

        # Cases authored
        authored_stmt = select(func.count(Case.id)).where(
            Case.author_judge == judge_name
        )
        authored_result = await self._db.execute(authored_stmt)
        cases_authored = authored_result.scalar_one_or_none() or 0

        # Cases by year
        years_stmt = (
            select(Case.year, func.count(Case.id))
            .where(Case.judge.any(judge_name))
            .where(Case.year.isnot(None))
            .group_by(Case.year)
            .order_by(Case.year)
        )
        years_result = await self._db.execute(years_stmt)
        cases_by_year = [
            {"year": row[0], "count": row[1]}
            for row in years_result.all()
        ]

        # Disposal patterns
        disposal_stmt = (
            select(Case.disposal_nature, func.count(Case.id))
            .where(Case.judge.any(judge_name))
            .where(Case.disposal_nature.isnot(None))
            .group_by(Case.disposal_nature)
            .order_by(desc(func.count(Case.id)))
        )
        disposal_result = await self._db.execute(disposal_stmt)
        disposal_patterns = [
            {"disposal_nature": row[0], "count": row[1]}
            for row in disposal_result.all()
        ]

        # Bench combinations (other judges this judge sat with)
        bench_stmt = (
            select(
                func.array_to_string(Case.judge, ", ").label("bench"),
                func.count(Case.id),
            )
            .where(Case.judge.any(judge_name))
            .where(func.array_length(Case.judge, 1) > 1)
            .group_by(text("bench"))
            .order_by(desc(func.count(Case.id)))
            .limit(10)
        )
        bench_result = await self._db.execute(bench_stmt)
        bench_combinations = [
            {"bench": row[0], "count": row[1]}
            for row in bench_result.all()
        ]

        # Top cited judgments authored by this judge
        cited_stmt = (
            select(Case.id, Case.title, Case.citation, Case.year)
            .where(Case.author_judge == judge_name)
            .where(Case.citation.isnot(None))
            .order_by(Case.year.desc())
            .limit(10)
        )
        cited_result = await self._db.execute(cited_stmt)
        top_cited = [
            {
                "id": str(row[0]),
                "title": row[1],
                "citation": row[2],
                "year": row[3],
            }
            for row in cited_result.all()
        ]

        # Acts frequency
        acts_unnested = (
            select(
                func.unnest(Case.acts_cited).label("act"),
            )
            .where(Case.judge.any(judge_name))
            .where(Case.acts_cited.isnot(None))
            .subquery()
        )
        acts_stmt = (
            select(acts_unnested.c.act, func.count().label("cnt"))
            .group_by(acts_unnested.c.act)
            .order_by(desc("cnt"))
            .limit(15)
        )
        acts_result = await self._db.execute(acts_stmt)
        acts_frequency = [
            {"act": row[0], "count": row[1]}
            for row in acts_result.all()
        ]

        # Case types
        types_stmt = (
            select(Case.case_type, func.count(Case.id))
            .where(Case.judge.any(judge_name))
            .where(Case.case_type.isnot(None))
            .group_by(Case.case_type)
            .order_by(desc(func.count(Case.id)))
        )
        types_result = await self._db.execute(types_stmt)
        case_types = [
            {"case_type": row[0], "count": row[1]}
            for row in types_result.all()
        ]

        return {
            "name": judge_name,
            "total_cases": total_cases,
            "cases_authored": cases_authored,
            "cases_by_year": cases_by_year,
            "disposal_patterns": disposal_patterns,
            "bench_combinations": bench_combinations,
            "top_cited_judgments": top_cited,
            "acts_frequency": acts_frequency,
            "case_types": case_types,
        }

    async def get_judge_cases(
        self,
        judge_name: str,
        page: int = 1,
        page_size: int = 20,
        year: int | None = None,
        case_type: str | None = None,
    ) -> dict:
        """Get paginated list of cases for a judge."""
        base_filter = Case.judge.any(judge_name)

        # Count query
        count_stmt = select(func.count(Case.id)).where(base_filter)
        if year:
            count_stmt = count_stmt.where(Case.year == year)
        if case_type:
            count_stmt = count_stmt.where(Case.case_type == case_type)

        count_result = await self._db.execute(count_stmt)
        total = count_result.scalar_one_or_none() or 0

        # Cases query
        cases_stmt = (
            select(
                Case.id, Case.title, Case.citation, Case.court,
                Case.year, Case.case_type, Case.disposal_nature,
                Case.decision_date,
            )
            .where(base_filter)
            .order_by(Case.year.desc().nullslast(), Case.decision_date.desc().nullslast())
        )
        if year:
            cases_stmt = cases_stmt.where(Case.year == year)
        if case_type:
            cases_stmt = cases_stmt.where(Case.case_type == case_type)

        offset = (page - 1) * page_size
        cases_stmt = cases_stmt.offset(offset).limit(page_size)

        result = await self._db.execute(cases_stmt)
        cases = [
            {
                "id": str(row[0]),
                "title": row[1],
                "citation": row[2],
                "court": row[3],
                "year": row[4],
                "case_type": row[5],
                "disposal_nature": row[6],
                "decision_date": str(row[7]) if row[7] else None,
            }
            for row in result.all()
        ]

        return {
            "judge": judge_name,
            "total": total,
            "page": page,
            "page_size": page_size,
            "cases": cases,
        }

    async def compare_judges(self, judge_names: list[str]) -> list[dict]:
        """Compare 2-3 judges side by side."""
        if len(judge_names) > 3:
            raise ValueError("Can compare at most 3 judges at a time")
        if len(judge_names) < 2:
            raise ValueError("Need at least 2 judges to compare")

        profiles = []
        for name in judge_names:
            profile = await self.get_judge_profile(name)
            if profile:
                profiles.append(profile)

        return profiles

    async def get_court_stats(self, court: str) -> dict | None:
        """Get court-level statistics."""
        # Total cases
        total_stmt = select(func.count(Case.id)).where(Case.court == court)
        total_result = await self._db.execute(total_stmt)
        total_cases = total_result.scalar_one_or_none() or 0

        if total_cases == 0:
            return None

        # Cases by year
        years_stmt = (
            select(Case.year, func.count(Case.id))
            .where(Case.court == court)
            .where(Case.year.isnot(None))
            .group_by(Case.year)
            .order_by(Case.year)
        )
        years_result = await self._db.execute(years_stmt)
        cases_by_year = [
            {"year": row[0], "count": row[1]}
            for row in years_result.all()
        ]

        # Case types
        types_stmt = (
            select(Case.case_type, func.count(Case.id))
            .where(Case.court == court)
            .where(Case.case_type.isnot(None))
            .group_by(Case.case_type)
            .order_by(desc(func.count(Case.id)))
        )
        types_result = await self._db.execute(types_stmt)
        case_types = [
            {"case_type": row[0], "count": row[1]}
            for row in types_result.all()
        ]

        # Disposal patterns
        disposal_stmt = (
            select(Case.disposal_nature, func.count(Case.id))
            .where(Case.court == court)
            .where(Case.disposal_nature.isnot(None))
            .group_by(Case.disposal_nature)
            .order_by(desc(func.count(Case.id)))
        )
        disposal_result = await self._db.execute(disposal_stmt)
        disposal_patterns = [
            {"disposal_nature": row[0], "count": row[1]}
            for row in disposal_result.all()
        ]

        # Top judges at this court
        unnested = (
            select(
                func.unnest(Case.judge).label("judge_name"),
                Case.id.label("case_id"),
            )
            .where(Case.court == court)
            .where(Case.judge.isnot(None))
            .subquery()
        )
        judges_stmt = (
            select(
                unnested.c.judge_name,
                func.count(func.distinct(unnested.c.case_id)).label("case_count"),
            )
            .group_by(unnested.c.judge_name)
            .order_by(desc("case_count"))
            .limit(20)
        )
        judges_result = await self._db.execute(judges_stmt)
        top_judges = [
            {"name": row[0], "case_count": row[1]}
            for row in judges_result.all()
        ]

        return {
            "court": court,
            "total_cases": total_cases,
            "cases_by_year": cases_by_year,
            "case_types": case_types,
            "disposal_patterns": disposal_patterns,
            "top_judges": top_judges,
        }
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_judge_analytics.py -v`
Expected: Tests pass (some may need mock adjustments for SQLAlchemy `.any()` — fix as needed)

**Step 5: Commit**

```bash
git add backend/app/core/analytics/ backend/tests/unit/test_judge_analytics.py
git commit -m "feat: add judge analytics service layer with unit tests"
```

---

## Task 2: Backend — Judge Analytics API Routes

**Files:**
- Create: `backend/app/api/routes/judges.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/unit/test_judge_routes.py`

**Step 1: Write failing tests for judge API routes**

Create `backend/tests/unit/test_judge_routes.py`:

```python
"""Unit tests for judge analytics API routes."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4


class TestJudgeRoutes:
    """Test judge analytics endpoints."""

    def test_list_judges_endpoint_exists(self):
        """GET /api/v1/judges should be registered."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert "/api/v1/judges" in routes or any("/judges" in str(r.path) for r in app.routes)

    def test_judge_profile_endpoint_exists(self):
        """GET /api/v1/judges/{name} should be registered."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("/judges/{name}" in str(r.path) or "/judges/{judge_name}" in str(r.path) for r in app.routes)

    def test_judge_compare_endpoint_exists(self):
        """GET /api/v1/judges/compare should be registered."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("compare" in str(r.path) for r in app.routes)

    def test_court_stats_endpoint_exists(self):
        """GET /api/v1/courts/{court}/stats should be registered."""
        from app.main import app
        routes = [r.path for r in app.routes]
        assert any("courts" in str(r.path) for r in app.routes)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_judge_routes.py -v`
Expected: FAIL

**Step 3: Write the API routes**

Create `backend/app/api/routes/judges.py`:

```python
"""Judge analytics API routes."""
from __future__ import annotations

import json
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analytics.judge_analytics import JudgeAnalyticsService
from app.db.postgres import get_db
from app.db.redis_client import get_redis

router = APIRouter(prefix="/api/v1", tags=["judges"])

JUDGE_CACHE_TTL = 3600  # 1 hour


async def _get_cached_or_compute(
    redis_client, cache_key: str, compute_fn, ttl: int = JUDGE_CACHE_TTL
):
    """Try Redis cache first, compute and cache on miss."""
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    result = await compute_fn()

    if redis_client and result is not None:
        try:
            await redis_client.set(cache_key, json.dumps(result, default=str), ex=ttl)
        except Exception:
            pass

    return result


@router.get("/judges")
async def list_judges(
    search: str | None = Query(None, description="Filter judges by name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all judges with case counts."""
    service = JudgeAnalyticsService(db)
    judges = await service.list_judges(search=search, page=page, page_size=page_size)
    return {"judges": judges, "page": page, "page_size": page_size}


@router.get("/judges/compare")
async def compare_judges(
    names: str = Query(..., description="Comma-separated judge names (2-3)"),
    db: AsyncSession = Depends(get_db),
):
    """Compare 2-3 judges side by side."""
    judge_names = [n.strip() for n in unquote(names).split(",") if n.strip()]

    if len(judge_names) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 judge names")
    if len(judge_names) > 3:
        raise HTTPException(status_code=400, detail="Can compare at most 3 judges")

    service = JudgeAnalyticsService(db)
    try:
        profiles = await service.compare_judges(judge_names)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"judges": profiles}


@router.get("/judges/{judge_name}")
async def get_judge_profile(
    judge_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive judge profile with analytics."""
    decoded_name = unquote(judge_name)
    service = JudgeAnalyticsService(db)

    redis_client = None
    try:
        redis_client = await get_redis()
    except Exception:
        pass

    cache_key = f"judge:profile:{decoded_name}"

    async def compute():
        return await service.get_judge_profile(decoded_name)

    profile = await _get_cached_or_compute(redis_client, cache_key, compute)

    if profile is None:
        raise HTTPException(status_code=404, detail=f"No cases found for judge: {decoded_name}")

    return profile


@router.get("/judges/{judge_name}/cases")
async def get_judge_cases(
    judge_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    year: int | None = Query(None),
    case_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of cases for a judge."""
    decoded_name = unquote(judge_name)
    service = JudgeAnalyticsService(db)
    return await service.get_judge_cases(
        decoded_name, page=page, page_size=page_size, year=year, case_type=case_type
    )


@router.get("/courts/{court_name}/stats")
async def get_court_stats(
    court_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get court-level statistics."""
    decoded_name = unquote(court_name)
    service = JudgeAnalyticsService(db)

    redis_client = None
    try:
        redis_client = await get_redis()
    except Exception:
        pass

    cache_key = f"court:stats:{decoded_name}"

    async def compute():
        return await service.get_court_stats(decoded_name)

    stats = await _get_cached_or_compute(redis_client, cache_key, compute)

    if stats is None:
        raise HTTPException(status_code=404, detail=f"No cases found for court: {decoded_name}")

    return stats
```

**Step 4: Register the router in main.py**

Add to `backend/app/main.py` after existing router imports:

```python
from app.api.routes.judges import router as judges_router
```

And register it:
```python
app.include_router(judges_router)
```

**Step 5: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_judge_routes.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/api/routes/judges.py backend/app/main.py backend/tests/unit/test_judge_routes.py
git commit -m "feat: add judge analytics API routes with caching"
```

---

## Task 3: Frontend — Types, API Client, and Charts Dependency

**Files:**
- Modify: `frontend/src/lib/types.ts` (add judge analytics types)
- Modify: `frontend/src/lib/api.ts` (add judge API functions)
- Modify: `frontend/package.json` (add recharts)

**Step 1: Install recharts for charts**

Run: `cd frontend && pnpm add recharts`

**Step 2: Add TypeScript types**

Add to `frontend/src/lib/types.ts`:

```typescript
// --- Judge Analytics Types ---

export interface JudgeListItem {
  name: string;
  total_cases: number;
  cases_authored: number;
}

export interface JudgeListResponse {
  judges: JudgeListItem[];
  page: number;
  page_size: number;
}

export interface YearCount {
  year: number;
  count: number;
}

export interface DisposalPattern {
  disposal_nature: string;
  count: number;
}

export interface BenchCombination {
  bench: string;
  count: number;
}

export interface JudgmentSummary {
  id: string;
  title: string;
  citation: string | null;
  year: number | null;
}

export interface ActFrequency {
  act: string;
  count: number;
}

export interface CaseTypeCount {
  case_type: string;
  count: number;
}

export interface JudgeProfile {
  name: string;
  total_cases: number;
  cases_authored: number;
  cases_by_year: YearCount[];
  disposal_patterns: DisposalPattern[];
  bench_combinations: BenchCombination[];
  top_cited_judgments: JudgmentSummary[];
  acts_frequency: ActFrequency[];
  case_types: CaseTypeCount[];
}

export interface JudgeCaseItem {
  id: string;
  title: string;
  citation: string | null;
  court: string;
  year: number | null;
  case_type: string | null;
  disposal_nature: string | null;
  decision_date: string | null;
}

export interface JudgeCasesResponse {
  judge: string;
  total: number;
  page: number;
  page_size: number;
  cases: JudgeCaseItem[];
}

export interface JudgeCompareResponse {
  judges: JudgeProfile[];
}

export interface CourtJudge {
  name: string;
  case_count: number;
}

export interface CourtStats {
  court: string;
  total_cases: number;
  cases_by_year: YearCount[];
  case_types: CaseTypeCount[];
  disposal_patterns: DisposalPattern[];
  top_judges: CourtJudge[];
}
```

**Step 3: Add API client functions**

Add to `frontend/src/lib/api.ts`:

```typescript
// --- Judge Analytics ---

export async function getJudges(params?: {
  search?: string;
  page?: number;
  page_size?: number;
}): Promise<JudgeListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.search) searchParams.set("search", params.search);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  const qs = searchParams.toString();
  return apiFetch<JudgeListResponse>(`/judges${qs ? `?${qs}` : ""}`);
}

export async function getJudgeProfile(name: string): Promise<JudgeProfile> {
  return apiFetch<JudgeProfile>(`/judges/${encodeURIComponent(name)}`);
}

export async function getJudgeCases(
  name: string,
  params?: { page?: number; page_size?: number; year?: number; case_type?: string }
): Promise<JudgeCasesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.year) searchParams.set("year", String(params.year));
  if (params?.case_type) searchParams.set("case_type", params.case_type);
  const qs = searchParams.toString();
  return apiFetch<JudgeCasesResponse>(
    `/judges/${encodeURIComponent(name)}/cases${qs ? `?${qs}` : ""}`
  );
}

export async function compareJudges(names: string[]): Promise<JudgeCompareResponse> {
  const namesParam = names.map(n => encodeURIComponent(n)).join(",");
  return apiFetch<JudgeCompareResponse>(`/judges/compare?names=${namesParam}`);
}

export async function getCourtStats(court: string): Promise<CourtStats> {
  return apiFetch<CourtStats>(`/courts/${encodeURIComponent(court)}/stats`);
}
```

Add the imports at the top of `api.ts` for the new types.

**Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat: add judge analytics types, API client, and recharts dependency"
```

---

## Task 4: Frontend — Judge Directory Page (`/judges`)

**Files:**
- Create: `frontend/src/app/judges/page.tsx`
- Test: `frontend/src/__tests__/judges-page.test.tsx`

**Step 1: Write failing tests**

Create `frontend/src/__tests__/judges-page.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderWithProviders } from "./test-utils";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import JudgesPage from "../app/judges/page";

vi.mock("@/lib/api", () => ({
  getJudges: vi.fn(),
}));

import { getJudges } from "@/lib/api";
const mockGetJudges = vi.mocked(getJudges);

describe("JudgesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetJudges.mockResolvedValue({
      judges: [
        { name: "Justice D.Y. Chandrachud", total_cases: 45, cases_authored: 12 },
        { name: "Justice S.A. Bobde", total_cases: 30, cases_authored: 8 },
      ],
      page: 1,
      page_size: 50,
    });
  });

  it("renders the page title", async () => {
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      expect(screen.getByText(/Judge Directory/i)).toBeInTheDocument();
    });
  });

  it("displays judge names", async () => {
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      expect(screen.getByText("Justice D.Y. Chandrachud")).toBeInTheDocument();
      expect(screen.getByText("Justice S.A. Bobde")).toBeInTheDocument();
    });
  });

  it("displays case counts", async () => {
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      expect(screen.getByText("45")).toBeInTheDocument();
      expect(screen.getByText("30")).toBeInTheDocument();
    });
  });

  it("has search input", async () => {
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search judges/i)).toBeInTheDocument();
    });
  });

  it("shows loading state", () => {
    mockGetJudges.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<JudgesPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("links to judge profile", async () => {
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      const link = screen.getByText("Justice D.Y. Chandrachud").closest("a");
      expect(link).toHaveAttribute("href", expect.stringContaining("/judge/"));
    });
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm test -- --run src/__tests__/judges-page.test.tsx`
Expected: FAIL

**Step 3: Write the judges page**

Create `frontend/src/app/judges/page.tsx`:

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Search, Users, Loader2, Gavel, ChevronRight } from "lucide-react";
import { getJudges } from "@/lib/api";
import type { JudgeListItem } from "@/lib/types";

export default function JudgesPage() {
  const [judges, setJudges] = useState<JudgeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchJudges = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getJudges({
        search: debouncedSearch || undefined,
        page,
        page_size: 50,
      });
      setJudges(data.judges);
    } catch {
      setJudges([]);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, page]);

  useEffect(() => {
    fetchJudges();
  }, [fetchJudges]);

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight mb-2 flex items-center gap-3">
            <Gavel className="h-7 w-7 text-primary" />
            Judge Directory
          </h1>
          <p className="text-muted-foreground">
            Browse judges and view their analytics — disposal patterns, bench combinations, and authored judgments.
          </p>
        </div>

        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search judges by name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border bg-card text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Loading judges...
          </div>
        ) : judges.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">
            <Users className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p>No judges found{search ? ` matching "${search}"` : ""}.</p>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-[1fr,80px,80px,32px] gap-4 px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground font-medium">
              <span>Judge</span>
              <span className="text-right">Cases</span>
              <span className="text-right">Authored</span>
              <span />
            </div>
            {judges.map((judge) => (
              <Link
                key={judge.name}
                href={`/judge/${encodeURIComponent(judge.name)}`}
                className="grid grid-cols-[1fr,80px,80px,32px] gap-4 items-center px-4 py-3 rounded-lg border bg-card hover:bg-muted/50 transition-colors group"
              >
                <span className="font-medium text-sm truncate">{judge.name}</span>
                <span className="text-right text-sm tabular-nums">{judge.total_cases}</span>
                <span className="text-right text-sm tabular-nums text-muted-foreground">
                  {judge.cases_authored}
                </span>
                <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
              </Link>
            ))}
          </div>
        )}

        {!loading && judges.length > 0 && (
          <div className="flex justify-center gap-2 mt-6">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-sm rounded border bg-card hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="px-3 py-1.5 text-sm text-muted-foreground">Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={judges.length < 50}
              className="px-3 py-1.5 text-sm rounded border bg-card hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 4: Run tests**

Run: `cd frontend && pnpm test -- --run src/__tests__/judges-page.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/app/judges/ frontend/src/__tests__/judges-page.test.tsx
git commit -m "feat: add judge directory page with search and pagination"
```

---

## Task 5: Frontend — Judge Profile Page (`/judge/[name]`)

**Files:**
- Create: `frontend/src/app/judge/[name]/page.tsx`
- Test: `frontend/src/__tests__/judge-profile-page.test.tsx`

**Step 1: Write failing tests**

Create `frontend/src/__tests__/judge-profile-page.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderWithProviders } from "./test-utils";
import { screen, waitFor } from "@testing-library/react";
import JudgeProfilePage from "../app/judge/[name]/page";

vi.mock("next/navigation", async () => {
  const actual = await vi.importActual("next/navigation");
  return {
    ...actual,
    useParams: () => ({ name: "Justice D.Y. Chandrachud" }),
    useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  };
});

vi.mock("@/lib/api", () => ({
  getJudgeProfile: vi.fn(),
  getJudgeCases: vi.fn(),
}));

import { getJudgeProfile, getJudgeCases } from "@/lib/api";
const mockGetProfile = vi.mocked(getJudgeProfile);
const mockGetCases = vi.mocked(getJudgeCases);

const mockProfile = {
  name: "Justice D.Y. Chandrachud",
  total_cases: 45,
  cases_authored: 12,
  cases_by_year: [
    { year: 2020, count: 10 },
    { year: 2021, count: 15 },
    { year: 2022, count: 20 },
  ],
  disposal_patterns: [
    { disposal_nature: "Dismissed", count: 20 },
    { disposal_nature: "Allowed", count: 15 },
    { disposal_nature: "Partly Allowed", count: 10 },
  ],
  bench_combinations: [
    { bench: "Justice Chandrachud, Justice Kaul", count: 8 },
  ],
  top_cited_judgments: [
    { id: "uuid-1", title: "Puttaswamy v. Union of India", citation: "(2017) 10 SCC 1", year: 2017 },
  ],
  acts_frequency: [
    { act: "Constitution of India", count: 30 },
    { act: "Indian Penal Code", count: 10 },
  ],
  case_types: [
    { case_type: "Criminal Appeal", count: 20 },
    { case_type: "Civil Appeal", count: 15 },
  ],
};

describe("JudgeProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetProfile.mockResolvedValue(mockProfile);
    mockGetCases.mockResolvedValue({
      judge: "Justice D.Y. Chandrachud",
      total: 1,
      page: 1,
      page_size: 20,
      cases: [
        {
          id: "uuid-1",
          title: "Test Case",
          citation: "(2020) 1 SCC 1",
          court: "Supreme Court of India",
          year: 2020,
          case_type: "Criminal Appeal",
          disposal_nature: "Dismissed",
          decision_date: "2020-06-15",
        },
      ],
    });
  });

  it("renders judge name", async () => {
    renderWithProviders(<JudgeProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Justice D.Y. Chandrachud")).toBeInTheDocument();
    });
  });

  it("shows total cases stat", async () => {
    renderWithProviders(<JudgeProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("45")).toBeInTheDocument();
    });
  });

  it("shows cases authored stat", async () => {
    renderWithProviders(<JudgeProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("12")).toBeInTheDocument();
    });
  });

  it("renders disposal patterns section", async () => {
    renderWithProviders(<JudgeProfilePage />);
    await waitFor(() => {
      expect(screen.getByText(/Disposal Patterns/i)).toBeInTheDocument();
    });
  });

  it("renders cases by year section", async () => {
    renderWithProviders(<JudgeProfilePage />);
    await waitFor(() => {
      expect(screen.getByText(/Cases by Year/i)).toBeInTheDocument();
    });
  });

  it("renders top cited judgments", async () => {
    renderWithProviders(<JudgeProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Puttaswamy v. Union of India")).toBeInTheDocument();
    });
  });

  it("renders acts frequency", async () => {
    renderWithProviders(<JudgeProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Constitution of India")).toBeInTheDocument();
    });
  });

  it("shows loading state", () => {
    mockGetProfile.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<JudgeProfilePage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && pnpm test -- --run src/__tests__/judge-profile-page.test.tsx`
Expected: FAIL

**Step 3: Write the judge profile page**

Create `frontend/src/app/judge/[name]/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Loader2,
  Gavel,
  FileText,
  Users,
  Scale,
  ArrowLeft,
  BookOpen,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { getJudgeProfile, getJudgeCases } from "@/lib/api";
import type { JudgeProfile, JudgeCaseItem } from "@/lib/types";

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
  "#8884d8",
  "#82ca9d",
  "#ffc658",
];

export default function JudgeProfilePage() {
  const params = useParams();
  const judgeName = decodeURIComponent(params.name as string);

  const [profile, setProfile] = useState<JudgeProfile | null>(null);
  const [cases, setCases] = useState<JudgeCaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const [profileData, casesData] = await Promise.all([
          getJudgeProfile(judgeName),
          getJudgeCases(judgeName, { page: 1, page_size: 10 }),
        ]);
        setProfile(profileData);
        setCases(casesData.cases);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load judge profile");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [judgeName]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading judge profile...
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen text-muted-foreground">
        <p>{error || "Judge not found"}</p>
        <Link href="/judges" className="mt-4 text-sm underline">
          Back to Judge Directory
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/judges"
            className="text-sm text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1"
          >
            <ArrowLeft className="h-3 w-3" /> Judge Directory
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight mt-2 flex items-center gap-3">
            <Gavel className="h-7 w-7 text-primary" />
            {profile.name}
          </h1>
        </div>

        {/* Stats cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard icon={<FileText className="h-4 w-4" />} label="Total Cases" value={profile.total_cases} />
          <StatCard icon={<Scale className="h-4 w-4" />} label="Cases Authored" value={profile.cases_authored} />
          <StatCard
            icon={<Users className="h-4 w-4" />}
            label="Bench Combinations"
            value={profile.bench_combinations.length}
          />
          <StatCard
            icon={<BookOpen className="h-4 w-4" />}
            label="Case Types"
            value={profile.case_types.length}
          />
        </div>

        {/* Charts row */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* Cases by Year */}
          <div className="border rounded-lg bg-card p-5">
            <h3 className="text-sm font-medium mb-4">Cases by Year</h3>
            {profile.cases_by_year.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={profile.cases_by_year}>
                  <XAxis dataKey="year" fontSize={12} />
                  <YAxis fontSize={12} />
                  <Tooltip />
                  <Bar dataKey="count" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground">No year data available</p>
            )}
          </div>

          {/* Disposal Patterns */}
          <div className="border rounded-lg bg-card p-5">
            <h3 className="text-sm font-medium mb-4">Disposal Patterns</h3>
            {profile.disposal_patterns.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={profile.disposal_patterns}
                    dataKey="count"
                    nameKey="disposal_nature"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ disposal_nature, percent }) =>
                      `${disposal_nature} (${(percent * 100).toFixed(0)}%)`
                    }
                    labelLine={false}
                  >
                    {profile.disposal_patterns.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Legend />
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground">No disposal data available</p>
            )}
          </div>
        </div>

        {/* Case Types & Acts */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* Case Types */}
          <div className="border rounded-lg bg-card p-5">
            <h3 className="text-sm font-medium mb-4">Case Types</h3>
            {profile.case_types.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={profile.case_types} layout="vertical">
                  <XAxis type="number" fontSize={12} />
                  <YAxis type="category" dataKey="case_type" fontSize={11} width={140} />
                  <Tooltip />
                  <Bar dataKey="count" fill="hsl(var(--chart-2))" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground">No case type data</p>
            )}
          </div>

          {/* Acts Frequency */}
          <div className="border rounded-lg bg-card p-5">
            <h3 className="text-sm font-medium mb-4">Acts/Statutes Cited</h3>
            {profile.acts_frequency.length > 0 ? (
              <div className="space-y-2">
                {profile.acts_frequency.slice(0, 10).map((item) => (
                  <div key={item.act} className="flex items-center justify-between text-sm">
                    <span className="truncate mr-4">{item.act}</span>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2 rounded-full bg-[hsl(var(--chart-3))]"
                        style={{
                          width: `${(item.count / profile.acts_frequency[0].count) * 100}px`,
                        }}
                      />
                      <span className="text-muted-foreground tabular-nums w-8 text-right">
                        {item.count}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No acts data</p>
            )}
          </div>
        </div>

        {/* Bench Combinations */}
        {profile.bench_combinations.length > 0 && (
          <div className="border rounded-lg bg-card p-5 mb-8">
            <h3 className="text-sm font-medium mb-4">Frequent Bench Combinations</h3>
            <div className="space-y-2">
              {profile.bench_combinations.map((combo) => (
                <div
                  key={combo.bench}
                  className="flex items-center justify-between text-sm py-1.5 px-3 rounded bg-muted/30"
                >
                  <span className="truncate">{combo.bench}</span>
                  <span className="text-muted-foreground tabular-nums ml-4">
                    {combo.count} cases
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top Cited Judgments */}
        {profile.top_cited_judgments.length > 0 && (
          <div className="border rounded-lg bg-card p-5 mb-8">
            <h3 className="text-sm font-medium mb-4">Authored Judgments</h3>
            <div className="space-y-2">
              {profile.top_cited_judgments.map((j) => (
                <Link
                  key={j.id}
                  href={`/case/${j.id}`}
                  className="flex items-center justify-between text-sm py-2 px-3 rounded hover:bg-muted/50 transition-colors"
                >
                  <div className="truncate mr-4">
                    <span className="font-medium">{j.title}</span>
                    {j.citation && (
                      <span className="text-muted-foreground ml-2">{j.citation}</span>
                    )}
                  </div>
                  {j.year && (
                    <span className="text-xs text-muted-foreground">{j.year}</span>
                  )}
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Recent Cases */}
        {cases.length > 0 && (
          <div className="border rounded-lg bg-card p-5">
            <h3 className="text-sm font-medium mb-4">Recent Cases</h3>
            <div className="space-y-2">
              {cases.map((c) => (
                <Link
                  key={c.id}
                  href={`/case/${c.id}`}
                  className="flex items-center justify-between text-sm py-2 px-3 rounded hover:bg-muted/50 transition-colors"
                >
                  <div className="truncate mr-4">
                    <span>{c.title}</span>
                    {c.citation && (
                      <span className="text-muted-foreground ml-2">{c.citation}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
                    {c.disposal_nature && <span>{c.disposal_nature}</span>}
                    {c.year && <span>{c.year}</span>}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="border rounded-lg bg-card p-4">
      <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
        {icon}
        {label}
      </div>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}
```

**Step 4: Run tests**

Run: `cd frontend && pnpm test -- --run src/__tests__/judge-profile-page.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/app/judge/ frontend/src/__tests__/judge-profile-page.test.tsx
git commit -m "feat: add judge profile page with charts and stats"
```

---

## Task 6: Frontend — Judge Comparison Page (`/judges/compare`)

**Files:**
- Create: `frontend/src/app/judges/compare/page.tsx`
- Test: `frontend/src/__tests__/judge-compare-page.test.tsx`

**Step 1: Write failing tests**

Create `frontend/src/__tests__/judge-compare-page.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderWithProviders } from "./test-utils";
import { screen, waitFor } from "@testing-library/react";
import JudgeComparePage from "../app/judges/compare/page";

vi.mock("@/lib/api", () => ({
  getJudges: vi.fn(),
  compareJudges: vi.fn(),
}));

import { getJudges, compareJudges } from "@/lib/api";
const mockGetJudges = vi.mocked(getJudges);
const mockCompare = vi.mocked(compareJudges);

describe("JudgeComparePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetJudges.mockResolvedValue({
      judges: [
        { name: "Justice A", total_cases: 50, cases_authored: 20 },
        { name: "Justice B", total_cases: 30, cases_authored: 10 },
      ],
      page: 1,
      page_size: 50,
    });
  });

  it("renders the page title", async () => {
    renderWithProviders(<JudgeComparePage />);
    expect(screen.getByText(/Compare Judges/i)).toBeInTheDocument();
  });

  it("shows judge selection inputs", async () => {
    renderWithProviders(<JudgeComparePage />);
    await waitFor(() => {
      expect(screen.getByText(/Select judges/i)).toBeInTheDocument();
    });
  });

  it("shows comparison results when judges are compared", async () => {
    mockCompare.mockResolvedValue({
      judges: [
        {
          name: "Justice A",
          total_cases: 50,
          cases_authored: 20,
          cases_by_year: [],
          disposal_patterns: [{ disposal_nature: "Dismissed", count: 30 }],
          bench_combinations: [],
          top_cited_judgments: [],
          acts_frequency: [],
          case_types: [],
        },
        {
          name: "Justice B",
          total_cases: 30,
          cases_authored: 10,
          cases_by_year: [],
          disposal_patterns: [{ disposal_nature: "Allowed", count: 20 }],
          bench_combinations: [],
          top_cited_judgments: [],
          acts_frequency: [],
          case_types: [],
        },
      ],
    });

    renderWithProviders(<JudgeComparePage />);
    // Page should render without error
    expect(screen.getByText(/Compare Judges/i)).toBeInTheDocument();
  });
});
```

**Step 2: Write the comparison page**

Create `frontend/src/app/judges/compare/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, Scale, Plus, X } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { getJudges, compareJudges } from "@/lib/api";
import type { JudgeProfile, JudgeListItem } from "@/lib/types";

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
];

export default function JudgeComparePage() {
  const [selectedNames, setSelectedNames] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<JudgeListItem[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [profiles, setProfiles] = useState<JudgeProfile[]>([]);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(query: string) {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    try {
      const data = await getJudges({ search: query, page_size: 10 });
      setSearchResults(data.judges.filter((j) => !selectedNames.includes(j.name)));
    } catch {
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }

  function addJudge(name: string) {
    if (selectedNames.length >= 3) return;
    setSelectedNames((prev) => [...prev, name]);
    setSearchQuery("");
    setSearchResults([]);
  }

  function removeJudge(name: string) {
    setSelectedNames((prev) => prev.filter((n) => n !== name));
    setProfiles([]);
  }

  async function handleCompare() {
    if (selectedNames.length < 2) return;
    setComparing(true);
    setError(null);
    try {
      const data = await compareJudges(selectedNames);
      setProfiles(data.judges);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setComparing(false);
    }
  }

  // Build disposal comparison data
  const disposalCompare = profiles.length > 0
    ? (() => {
        const allNatures = new Set<string>();
        profiles.forEach((p) =>
          p.disposal_patterns.forEach((d) => allNatures.add(d.disposal_nature))
        );
        return Array.from(allNatures).map((nature) => {
          const row: Record<string, string | number> = { disposal_nature: nature };
          profiles.forEach((p) => {
            const match = p.disposal_patterns.find((d) => d.disposal_nature === nature);
            row[p.name] = match?.count ?? 0;
          });
          return row;
        });
      })()
    : [];

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-4 py-8">
        <Link
          href="/judges"
          className="text-sm text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-3 w-3" /> Judge Directory
        </Link>

        <h1 className="text-3xl font-semibold tracking-tight mt-2 mb-2 flex items-center gap-3">
          <Scale className="h-7 w-7 text-primary" />
          Compare Judges
        </h1>
        <p className="text-muted-foreground mb-6">
          Select judges to compare their statistics side by side.
        </p>

        {/* Selection area */}
        <div className="border rounded-lg bg-card p-5 mb-6">
          <p className="text-sm font-medium mb-3">Select judges (2-3):</p>
          <div className="flex flex-wrap gap-2 mb-3">
            {selectedNames.map((name) => (
              <span
                key={name}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-primary/10 text-sm"
              >
                {name}
                <button onClick={() => removeJudge(name)}>
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>

          {selectedNames.length < 3 && (
            <div className="relative">
              <input
                type="text"
                placeholder="Search to add a judge..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full px-3 py-2 rounded border bg-background text-sm"
              />
              {searchResults.length > 0 && (
                <div className="absolute z-10 top-full left-0 right-0 mt-1 border rounded bg-card shadow-lg max-h-48 overflow-y-auto">
                  {searchResults.map((j) => (
                    <button
                      key={j.name}
                      onClick={() => addJudge(j.name)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-muted flex items-center gap-2"
                    >
                      <Plus className="h-3 w-3" />
                      {j.name} ({j.total_cases} cases)
                    </button>
                  ))}
                </div>
              )}
              {searchLoading && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                </div>
              )}
            </div>
          )}

          <button
            onClick={handleCompare}
            disabled={selectedNames.length < 2 || comparing}
            className="mt-4 px-4 py-2 rounded bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {comparing ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Comparing...
              </span>
            ) : (
              "Compare"
            )}
          </button>
        </div>

        {error && (
          <p className="text-sm text-red-500 mb-4">{error}</p>
        )}

        {/* Comparison results */}
        {profiles.length > 0 && (
          <>
            {/* Stats comparison */}
            <div className="grid md:grid-cols-3 gap-4 mb-6">
              {profiles.map((p, i) => (
                <div key={p.name} className="border rounded-lg bg-card p-5">
                  <div
                    className="w-3 h-3 rounded-full mb-2"
                    style={{ backgroundColor: COLORS[i] }}
                  />
                  <Link href={`/judge/${encodeURIComponent(p.name)}`} className="font-medium text-sm hover:underline">
                    {p.name}
                  </Link>
                  <div className="mt-3 space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Cases</span>
                      <span className="tabular-nums">{p.total_cases}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Authored</span>
                      <span className="tabular-nums">{p.cases_authored}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Case Types</span>
                      <span className="tabular-nums">{p.case_types.length}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Disposal comparison chart */}
            {disposalCompare.length > 0 && (
              <div className="border rounded-lg bg-card p-5 mb-6">
                <h3 className="text-sm font-medium mb-4">Disposal Patterns Comparison</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={disposalCompare}>
                    <XAxis dataKey="disposal_nature" fontSize={12} />
                    <YAxis fontSize={12} />
                    <Tooltip />
                    <Legend />
                    {profiles.map((p, i) => (
                      <Bar key={p.name} dataKey={p.name} fill={COLORS[i]} radius={[4, 4, 0, 0]} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
```

**Step 3: Run tests**

Run: `cd frontend && pnpm test -- --run src/__tests__/judge-compare-page.test.tsx`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/app/judges/compare/ frontend/src/__tests__/judge-compare-page.test.tsx
git commit -m "feat: add judge comparison page with side-by-side stats"
```

---

## Task 7: Frontend — Update Header Nav + Case Detail Judge Links

**Files:**
- Modify: `frontend/src/components/header.tsx` (add Judges nav link)
- Modify: `frontend/src/app/case/[id]/page.tsx` (make judge names clickable)

**Step 1: Update header to include Judges link**

In `header.tsx`, add a "Judges" navigation button after "Graph" in both desktop and mobile nav:

```tsx
<Link href="/judges">
  <Button variant="ghost" size="sm" className="gap-1.5 text-xs">
    <Gavel className="h-3.5 w-3.5" />
    <span className="hidden lg:inline">Judges</span>
  </Button>
</Link>
```

Import `Gavel` from `lucide-react`.

**Step 2: Update case detail page to make judge names clickable**

In `frontend/src/app/case/[id]/page.tsx`, replace the judge display card with clickable links:

Replace the plain text judge display with:
```tsx
{caseData.judge && (
  <Card className="p-4 rounded-md">
    <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground mb-2">Bench</h4>
    <div className="space-y-1">
      {(Array.isArray(caseData.judge) ? caseData.judge : caseData.judge.split(", ")).map(
        (judgeName: string) => (
          <Link
            key={judgeName}
            href={`/judge/${encodeURIComponent(judgeName.trim())}`}
            className="block text-sm hover:underline text-primary"
          >
            {judgeName.trim()}
            {caseData.author_judge && judgeName.trim() === caseData.author_judge && (
              <span className="text-xs text-muted-foreground ml-1">(Author)</span>
            )}
          </Link>
        )
      )}
    </div>
  </Card>
)}
```

**Step 3: Run existing tests to make sure nothing breaks**

Run: `cd frontend && pnpm test`
Expected: All existing tests still pass

**Step 4: Commit**

```bash
git add frontend/src/components/header.tsx frontend/src/app/case/[id]/page.tsx
git commit -m "feat: add Judges nav link and clickable judge names in case detail"
```

---

## Task 8: Frontend — Court Statistics Page (`/courts`)

**Files:**
- Create: `frontend/src/app/courts/page.tsx`
- Test: `frontend/src/__tests__/courts-page.test.tsx`

**Step 1: Write failing test**

Create `frontend/src/__tests__/courts-page.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderWithProviders } from "./test-utils";
import { screen, waitFor } from "@testing-library/react";
import CourtsPage from "../app/courts/page";

vi.mock("@/lib/api", () => ({
  getCourtStats: vi.fn(),
}));

import { getCourtStats } from "@/lib/api";
const mockGetCourtStats = vi.mocked(getCourtStats);

describe("CourtsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCourtStats.mockResolvedValue({
      court: "Supreme Court of India",
      total_cases: 740,
      cases_by_year: [{ year: 2020, count: 100 }],
      case_types: [{ case_type: "Criminal Appeal", count: 300 }],
      disposal_patterns: [{ disposal_nature: "Dismissed", count: 400 }],
      top_judges: [{ name: "Justice X", case_count: 50 }],
    });
  });

  it("renders the page title", () => {
    renderWithProviders(<CourtsPage />);
    expect(screen.getByText(/Court Statistics/i)).toBeInTheDocument();
  });

  it("loads Supreme Court stats by default", async () => {
    renderWithProviders(<CourtsPage />);
    await waitFor(() => {
      expect(screen.getByText("740")).toBeInTheDocument();
    });
  });

  it("shows top judges", async () => {
    renderWithProviders(<CourtsPage />);
    await waitFor(() => {
      expect(screen.getByText("Justice X")).toBeInTheDocument();
    });
  });
});
```

**Step 2: Write the courts page**

Create `frontend/src/app/courts/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Building2, FileText } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { getCourtStats } from "@/lib/api";
import type { CourtStats } from "@/lib/types";

const COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
];

export default function CourtsPage() {
  const [stats, setStats] = useState<CourtStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      setLoading(true);
      try {
        const data = await getCourtStats("Supreme Court of India");
        setStats(data);
      } catch {
        setStats(null);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-semibold tracking-tight mb-2 flex items-center gap-3">
          <Building2 className="h-7 w-7 text-primary" />
          Court Statistics
        </h1>
        <p className="text-muted-foreground mb-8">
          Aggregate statistics for courts in the database.
        </p>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Loading court statistics...
          </div>
        ) : !stats ? (
          <p className="text-center py-20 text-muted-foreground">No statistics available.</p>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
              <div className="border rounded-lg bg-card p-4">
                <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                  <Building2 className="h-3 w-3" /> Court
                </div>
                <p className="font-medium text-sm">{stats.court}</p>
              </div>
              <div className="border rounded-lg bg-card p-4">
                <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                  <FileText className="h-3 w-3" /> Total Cases
                </div>
                <p className="text-2xl font-semibold tabular-nums">{stats.total_cases}</p>
              </div>
              <div className="border rounded-lg bg-card p-4">
                <div className="text-xs text-muted-foreground mb-1">Judges</div>
                <p className="text-2xl font-semibold tabular-nums">{stats.top_judges.length}</p>
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-6 mb-8">
              {/* Cases by Year */}
              <div className="border rounded-lg bg-card p-5">
                <h3 className="text-sm font-medium mb-4">Cases by Year</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={stats.cases_by_year}>
                    <XAxis dataKey="year" fontSize={12} />
                    <YAxis fontSize={12} />
                    <Tooltip />
                    <Bar dataKey="count" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Disposal Patterns */}
              <div className="border rounded-lg bg-card p-5">
                <h3 className="text-sm font-medium mb-4">Disposal Patterns</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={stats.disposal_patterns}
                      dataKey="count"
                      nameKey="disposal_nature"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      label={({ disposal_nature, percent }) =>
                        `${disposal_nature} (${(percent * 100).toFixed(0)}%)`
                      }
                      labelLine={false}
                    >
                      {stats.disposal_patterns.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Legend />
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Judges */}
            <div className="border rounded-lg bg-card p-5">
              <h3 className="text-sm font-medium mb-4">Top Judges</h3>
              <div className="space-y-2">
                {stats.top_judges.map((j) => (
                  <Link
                    key={j.name}
                    href={`/judge/${encodeURIComponent(j.name)}`}
                    className="flex items-center justify-between text-sm py-2 px-3 rounded hover:bg-muted/50 transition-colors"
                  >
                    <span>{j.name}</span>
                    <span className="text-muted-foreground tabular-nums">{j.case_count} cases</span>
                  </Link>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

**Step 3: Run tests**

Run: `cd frontend && pnpm test -- --run src/__tests__/courts-page.test.tsx`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/app/courts/ frontend/src/__tests__/courts-page.test.tsx
git commit -m "feat: add court statistics page with charts"
```

---

## Task 9: Run All Tests + Fix Failures

**Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All tests pass (190+ existing + new judge analytics tests)

**Step 2: Run all frontend tests**

Run: `cd frontend && pnpm test`
Expected: All tests pass (88+ existing + new judge tests)

**Step 3: Run frontend build**

Run: `cd frontend && pnpm build`
Expected: Clean build

**Step 4: Fix any failures**

Address test or build failures as they come up.

**Step 5: Final commit**

```bash
git add -A
git commit -m "fix: address test failures for Phase 4 judge analytics"
```

---

## Task 10: Mark Phase 4 Complete + Final Commit

**Step 1: Update PHASE_PLAN.md**

Mark all Phase 4 items as complete with `[x]`.

**Step 2: Final commit**

```bash
git add docs/PHASE_PLAN.md
git commit -m "docs: mark Phase 4 (Judge Analytics) as COMPLETE"
```

---

## Summary

| Task | Component | Estimated Steps |
|------|-----------|----------------|
| 1 | Backend: Judge analytics service + tests | 5 |
| 2 | Backend: API routes + registration + tests | 6 |
| 3 | Frontend: Types, API client, recharts | 4 |
| 4 | Frontend: Judge directory page + tests | 5 |
| 5 | Frontend: Judge profile page + tests | 5 |
| 6 | Frontend: Judge comparison page + tests | 4 |
| 7 | Frontend: Header nav + case detail links | 4 |
| 8 | Frontend: Court statistics page + tests | 4 |
| 9 | Run all tests + fix failures | 5 |
| 10 | Mark phase complete | 2 |
