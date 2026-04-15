"""Unit tests for JudgeAnalyticsService."""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.analytics.judge_analytics import (
    CourtStats,
    JudgeAnalyticsService,
    JudgeCaseItem,
    JudgeListItem,
    JudgeProfile,
    PaginatedResult,
)


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with a chainable execute()."""
    session = AsyncMock()
    return session


def _mock_execute_returns(session: AsyncMock, *return_values: list[object]) -> None:
    """Set up session.execute() to return successive mock results.

    Each return_value should be a list for .all() or a scalar for .scalar_one_or_none().
    """
    mock_results = []
    for val in return_values:
        mock_result = MagicMock()
        if isinstance(val, list):
            mock_result.all.return_value = val
            # If it's a list with one element and it looks like a count, also set scalar
            mock_result.scalar_one_or_none.return_value = None
        else:
            mock_result.scalar_one_or_none.return_value = val
            mock_result.all.return_value = []
        mock_results.append(mock_result)

    session.execute = AsyncMock(side_effect=mock_results)


class TestListJudges:
    """Tests for JudgeAnalyticsService.list_judges."""

    @pytest.mark.asyncio
    async def test_list_judges_returns_paginated_result(self) -> None:
        session = _make_mock_session()

        judge_rows = [
            SimpleNamespace(judge_name="Justice A", total_cases=50, cases_authored=30),
            SimpleNamespace(judge_name="Justice B", total_cases=40, cases_authored=20),
        ]

        # First call: count query, second call: paginated results
        _mock_execute_returns(session, 2, judge_rows)

        service = JudgeAnalyticsService(session)
        result = await service.list_judges(page=1, page_size=20)

        assert isinstance(result, PaginatedResult)
        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 20
        assert result.total_pages == 1
        assert len(result.items) == 2
        assert isinstance(result.items[0], JudgeListItem)
        assert result.items[0].name == "Justice A"
        assert result.items[0].total_cases == 50
        assert result.items[0].cases_authored == 30

    @pytest.mark.asyncio
    async def test_list_judges_with_search(self) -> None:
        session = _make_mock_session()

        judge_rows = [
            SimpleNamespace(judge_name="Justice Kumar", total_cases=10, cases_authored=5),
        ]

        _mock_execute_returns(session, 1, judge_rows)

        service = JudgeAnalyticsService(session)
        result = await service.list_judges(search="Kumar", page=1, page_size=10)

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].name == "Justice Kumar"

    @pytest.mark.asyncio
    async def test_list_judges_empty_result(self) -> None:
        session = _make_mock_session()

        _mock_execute_returns(session, 0, [])

        service = JudgeAnalyticsService(session)
        result = await service.list_judges()

        assert result.total == 0
        assert result.items == []
        assert result.total_pages == 1  # minimum 1 page

    @pytest.mark.asyncio
    async def test_list_judges_pagination(self) -> None:
        session = _make_mock_session()

        judge_rows = [
            SimpleNamespace(judge_name="Justice C", total_cases=5, cases_authored=2),
        ]

        _mock_execute_returns(session, 25, judge_rows)

        service = JudgeAnalyticsService(session)
        result = await service.list_judges(page=2, page_size=10)

        assert result.total == 25
        assert result.page == 2
        assert result.total_pages == 3  # ceil(25/10)


class TestGetJudgeProfile:
    """Tests for JudgeAnalyticsService.get_judge_profile."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_cases(self) -> None:
        session = _make_mock_session()

        # total_cases query returns 0
        _mock_execute_returns(session, 0)

        service = JudgeAnalyticsService(session)
        result = await service.get_judge_profile("Unknown Judge")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_profile_with_stats(self) -> None:
        session = _make_mock_session()

        case_id = uuid.uuid4()

        # Sequence of query results:
        # 1. total_cases count
        # 2. cases_authored count
        # 3. cases_by_year
        # 4. disposal_patterns
        # 5. bench fallback — select(Case.judge).where(...)
        # 6. top_cited_judgments
        # 7. acts_frequency
        # 8. case_types
        year_rows = [
            SimpleNamespace(year=2020, count=5),
            SimpleNamespace(year=2021, count=8),
        ]
        disposal_rows = [
            SimpleNamespace(disposal_nature="Allowed", count=7),
            SimpleNamespace(disposal_nature="Dismissed", count=6),
        ]
        bench_fallback_rows = [
            (["Justice A", "Justice B"],),
            (["Justice A", "Justice B", "Justice C"],),
        ]
        cited_rows = [
            SimpleNamespace(
                id=case_id,
                title="Landmark Case",
                citation="(2020) 1 SCC 1",
                year=2020,
                citation_count=15,
            ),
        ]
        acts_rows = [
            SimpleNamespace(act="Constitution of India", count=10),
            SimpleNamespace(act="Indian Penal Code", count=5),
        ]
        type_rows = [
            SimpleNamespace(case_type="Criminal Appeal", count=8),
            SimpleNamespace(case_type="Civil Appeal", count=5),
        ]

        _mock_execute_returns(
            session,
            13,  # total_cases
            7,   # cases_authored
            year_rows,
            disposal_rows,
            bench_fallback_rows,  # bench fallback query
            cited_rows,
            acts_rows,
            type_rows,
        )

        service = JudgeAnalyticsService(session)
        result = await service.get_judge_profile("Justice A")

        assert result is not None
        assert isinstance(result, JudgeProfile)
        assert result.name == "Justice A"
        assert result.total_cases == 13
        assert result.cases_authored == 7
        assert result.cases_by_year == {2020: 5, 2021: 8}
        assert result.disposal_patterns == {"Allowed": 7, "Dismissed": 6}
        assert result.acts_frequency == {
            "Constitution of India": 10,
            "Indian Penal Code": 5,
        }
        assert result.case_types == {"Criminal Appeal": 8, "Civil Appeal": 5}

    @pytest.mark.asyncio
    async def test_profile_bench_combinations(self) -> None:
        """Test that bench combinations are computed correctly."""
        session = _make_mock_session()

        # Sequence: total_cases, authored, years, disposal, bench_fallback,
        #           cited, acts, types
        bench_rows = [
            (["Justice A", "Justice B", "Justice C"],),
            (["Justice A", "Justice B"],),
        ]

        _mock_execute_returns(
            session,
            5,   # total_cases
            3,   # cases_authored
            [SimpleNamespace(year=2022, count=5)],  # years
            [],  # disposal
            bench_rows,  # bench fallback
            [],  # cited
            [],  # acts
            [],  # types
        )

        service = JudgeAnalyticsService(session)
        result = await service.get_judge_profile("Justice A")

        assert result is not None
        assert result.bench_combinations == [
            {"judge": "Justice B", "cases_together": 2},
            {"judge": "Justice C", "cases_together": 1},
        ]


class TestGetJudgeCases:
    """Tests for JudgeAnalyticsService.get_judge_cases."""

    @pytest.mark.asyncio
    async def test_returns_paginated_cases(self) -> None:
        session = _make_mock_session()

        case_id = uuid.uuid4()
        case_rows = [
            SimpleNamespace(
                id=case_id,
                title="State vs Citizen",
                citation="(2021) 2 SCC 100",
                year=2021,
                case_type="Criminal Appeal",
                court="Supreme Court of India",
                decision_date=date(2021, 6, 15),
                author_judge="Justice A",
            ),
        ]

        _mock_execute_returns(session, 1, case_rows)

        service = JudgeAnalyticsService(session)
        result = await service.get_judge_cases("Justice A", page=1, page_size=10)

        assert isinstance(result, PaginatedResult)
        assert result.total == 1
        assert len(result.items) == 1

        item = result.items[0]
        assert isinstance(item, JudgeCaseItem)
        assert item.id == case_id
        assert item.title == "State vs Citizen"
        assert item.is_author is True

    @pytest.mark.asyncio
    async def test_is_author_false_when_different_author(self) -> None:
        session = _make_mock_session()

        case_rows = [
            SimpleNamespace(
                id=uuid.uuid4(),
                title="Case X",
                citation=None,
                year=2022,
                case_type="Civil Appeal",
                court="Supreme Court of India",
                decision_date=None,
                author_judge="Justice B",
            ),
        ]

        _mock_execute_returns(session, 1, case_rows)

        service = JudgeAnalyticsService(session)
        result = await service.get_judge_cases("Justice A")

        assert result.items[0].is_author is False

    @pytest.mark.asyncio
    async def test_empty_cases(self) -> None:
        session = _make_mock_session()

        _mock_execute_returns(session, 0, [])

        service = JudgeAnalyticsService(session)
        result = await service.get_judge_cases("Justice Nobody")

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_with_year_and_case_type_filters(self) -> None:
        session = _make_mock_session()

        case_rows = [
            SimpleNamespace(
                id=uuid.uuid4(),
                title="Filtered Case",
                citation="(2020) 5 SCC 50",
                year=2020,
                case_type="Writ Petition",
                court="Supreme Court of India",
                decision_date=date(2020, 3, 1),
                author_judge="Justice A",
            ),
        ]

        _mock_execute_returns(session, 1, case_rows)

        service = JudgeAnalyticsService(session)
        result = await service.get_judge_cases(
            "Justice A", year=2020, case_type="Writ Petition"
        )

        assert result.total == 1
        assert result.items[0].case_type == "Writ Petition"
        assert result.items[0].year == 2020


class TestCompareJudges:
    """Tests for JudgeAnalyticsService.compare_judges."""

    @pytest.mark.asyncio
    async def test_raises_for_single_judge(self) -> None:
        session = _make_mock_session()
        service = JudgeAnalyticsService(session)

        with pytest.raises(ValueError, match="At least 2"):
            await service.compare_judges(["Justice A"])

    @pytest.mark.asyncio
    async def test_raises_for_empty_list(self) -> None:
        session = _make_mock_session()
        service = JudgeAnalyticsService(session)

        with pytest.raises(ValueError, match="At least 2"):
            await service.compare_judges([])

    @pytest.mark.asyncio
    async def test_raises_for_more_than_three(self) -> None:
        session = _make_mock_session()
        service = JudgeAnalyticsService(session)

        with pytest.raises(ValueError, match="At most 3"):
            await service.compare_judges(
                ["Justice A", "Justice B", "Justice C", "Justice D"]
            )

    @pytest.mark.asyncio
    async def test_compare_two_judges(self) -> None:
        session = _make_mock_session()
        service = JudgeAnalyticsService(session)

        profile_a = JudgeProfile(name="Justice A", total_cases=10, cases_authored=5)
        profile_b = JudgeProfile(name="Justice B", total_cases=8, cases_authored=3)

        with patch.object(
            service,
            "get_judge_profile",
            side_effect=[profile_a, profile_b],
        ):
            result = await service.compare_judges(["Justice A", "Justice B"])

        assert len(result) == 2
        assert result[0] is profile_a
        assert result[1] is profile_b

    @pytest.mark.asyncio
    async def test_compare_three_judges(self) -> None:
        session = _make_mock_session()
        service = JudgeAnalyticsService(session)

        profiles = [
            JudgeProfile(name=f"Justice {c}", total_cases=i, cases_authored=i)
            for i, c in enumerate(["A", "B", "C"], 1)
        ]

        with patch.object(
            service,
            "get_judge_profile",
            side_effect=profiles,
        ):
            result = await service.compare_judges(
                ["Justice A", "Justice B", "Justice C"]
            )

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_compare_with_unknown_judge_returns_none(self) -> None:
        session = _make_mock_session()
        service = JudgeAnalyticsService(session)

        profile_a = JudgeProfile(name="Justice A", total_cases=10, cases_authored=5)

        with patch.object(
            service,
            "get_judge_profile",
            side_effect=[profile_a, None],
        ):
            result = await service.compare_judges(["Justice A", "Unknown"])

        assert result[0] is profile_a
        assert result[1] is None


class TestGetCourtStats:
    """Tests for JudgeAnalyticsService.get_court_stats."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_cases(self) -> None:
        session = _make_mock_session()

        _mock_execute_returns(session, 0)

        service = JudgeAnalyticsService(session)
        result = await service.get_court_stats("Nonexistent Court")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_court_stats(self) -> None:
        session = _make_mock_session()

        year_rows = [
            SimpleNamespace(year=2020, count=100),
            SimpleNamespace(year=2021, count=120),
        ]
        type_rows = [
            SimpleNamespace(case_type="Criminal Appeal", count=80),
            SimpleNamespace(case_type="Civil Appeal", count=60),
        ]
        disposal_rows = [
            SimpleNamespace(disposal_nature="Allowed", count=90),
            SimpleNamespace(disposal_nature="Dismissed", count=70),
        ]
        judge_rows = [
            SimpleNamespace(judge_name="Justice A", count=50),
            SimpleNamespace(judge_name="Justice B", count=40),
        ]

        _mock_execute_returns(
            session,
            500,  # total_cases
            year_rows,
            type_rows,
            disposal_rows,
            judge_rows,
        )

        service = JudgeAnalyticsService(session)
        result = await service.get_court_stats("Supreme Court of India")

        assert result is not None
        assert isinstance(result, CourtStats)
        assert result.court == "Supreme Court of India"
        assert result.total_cases == 500
        assert result.cases_by_year == {2020: 100, 2021: 120}
        assert result.case_types == {"Criminal Appeal": 80, "Civil Appeal": 60}
        assert result.disposal_patterns == {"Allowed": 90, "Dismissed": 70}
        assert len(result.top_judges) == 2
        assert result.top_judges[0] == {"judge": "Justice A", "cases": 50}

    @pytest.mark.asyncio
    async def test_court_stats_empty_subcategories(self) -> None:
        """Court with cases but no year/type/disposal data."""
        session = _make_mock_session()

        _mock_execute_returns(
            session,
            10,  # total_cases
            [],  # cases_by_year
            [],  # case_types
            [],  # disposal_patterns
            [],  # top_judges
        )

        service = JudgeAnalyticsService(session)
        result = await service.get_court_stats("Delhi High Court")

        assert result is not None
        assert result.total_cases == 10
        assert result.cases_by_year == {}
        assert result.case_types == {}
        assert result.disposal_patterns == {}
        assert result.top_judges == []


class TestDataclasses:
    """Test dataclass initialization and defaults."""

    def test_judge_list_item(self) -> None:
        item = JudgeListItem(name="Justice X", total_cases=10, cases_authored=5)
        assert item.name == "Justice X"
        assert item.total_cases == 10

    def test_judge_profile_defaults(self) -> None:
        profile = JudgeProfile(name="Justice X", total_cases=10, cases_authored=5)
        assert profile.cases_by_year == {}
        assert profile.disposal_patterns == {}
        assert profile.bench_combinations == []
        assert profile.top_cited_judgments == []
        assert profile.acts_frequency == {}
        assert profile.case_types == {}

    def test_paginated_result(self) -> None:
        result = PaginatedResult(
            items=[], total=0, page=1, page_size=20, total_pages=1
        )
        assert result.items == []
        assert result.total_pages == 1

    def test_court_stats_defaults(self) -> None:
        stats = CourtStats(court="SC", total_cases=100)
        assert stats.cases_by_year == {}
        assert stats.top_judges == []

    def test_judge_case_item(self) -> None:
        cid = uuid.uuid4()
        item = JudgeCaseItem(
            id=cid,
            title="Test",
            citation=None,
            year=2020,
            case_type="Appeal",
            court="SC",
            decision_date=date(2020, 1, 1),
            is_author=True,
        )
        assert item.id == cid
        assert item.is_author is True
