"""Unit tests for CounselAnalyticsService and name normalization."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.analytics.counsel_analytics import (
    CounselAnalyticsService,
    CounselCaseItem,
    CounselListItem,
    CounselProfile,
    normalize_counsel_name,
    _is_win,
)


# ---------------------------------------------------------------------------
# Name normalization tests
# ---------------------------------------------------------------------------


class TestNormalizeCounselName:
    """Tests for normalize_counsel_name."""

    def test_strips_mr(self) -> None:
        assert normalize_counsel_name("Mr. R.K. Sharma") == "R.K. Sharma"

    def test_strips_mrs(self) -> None:
        assert normalize_counsel_name("Mrs. Priya Patel") == "Priya Patel"

    def test_strips_ms(self) -> None:
        assert normalize_counsel_name("Ms. Anjali Verma") == "Anjali Verma"

    def test_strips_smt(self) -> None:
        assert normalize_counsel_name("Smt. Indira Jaising") == "Indira Jaising"

    def test_strips_shri(self) -> None:
        assert normalize_counsel_name("Shri K.K. Venugopal") == "K.K. Venugopal"

    def test_strips_sri(self) -> None:
        assert normalize_counsel_name("Sri Gopal Subramanium") == "Gopal Subramanium"

    def test_strips_dr(self) -> None:
        assert normalize_counsel_name("Dr. A.M. Singhvi") == "A.M. Singhvi"

    def test_strips_honble(self) -> None:
        assert normalize_counsel_name("Hon'ble Solicitor General") == "Solicitor General"

    def test_strips_adv(self) -> None:
        assert normalize_counsel_name("Adv. Ravi Shankar") == "Ravi Shankar"

    def test_strips_prof(self) -> None:
        assert normalize_counsel_name("Prof. N.R. Madhava Menon") == "N.R. Madhava Menon"

    def test_strips_senior_advocate_suffix(self) -> None:
        assert normalize_counsel_name("R.K. Sharma, Senior Advocate") == "R.K. Sharma"

    def test_strips_sr_adv_suffix(self) -> None:
        assert normalize_counsel_name("R.K. Sharma, Sr. Adv.") == "R.K. Sharma"

    def test_strips_sr_advocate_suffix(self) -> None:
        assert normalize_counsel_name("R.K. Sharma, Sr. Advocate") == "R.K. Sharma"

    def test_full_normalization(self) -> None:
        """Combined honorific + designation suffix."""
        assert normalize_counsel_name("Mr. R.K. Sharma, Sr. Adv.") == "R.K. Sharma"

    def test_strips_trailing_whitespace_and_punctuation(self) -> None:
        assert normalize_counsel_name("  R.K. Sharma,  ") == "R.K. Sharma"

    def test_plain_name_unchanged(self) -> None:
        assert normalize_counsel_name("Fali S. Nariman") == "Fali S. Nariman"

    def test_empty_string(self) -> None:
        assert normalize_counsel_name("") == ""

    def test_only_honorific(self) -> None:
        assert normalize_counsel_name("Mr.") == ""

    def test_case_insensitive_honorific(self) -> None:
        assert normalize_counsel_name("mr. R.K. Sharma") == "R.K. Sharma"


# ---------------------------------------------------------------------------
# Win detection tests
# ---------------------------------------------------------------------------


class TestIsWin:
    """Tests for _is_win helper."""

    def test_petitioner_allowed(self) -> None:
        assert _is_win("petitioner", "Allowed") is True

    def test_petitioner_partly_allowed(self) -> None:
        assert _is_win("petitioner", "Partly Allowed") is True

    def test_petitioner_dismissed(self) -> None:
        assert _is_win("petitioner", "Dismissed") is False

    def test_respondent_dismissed(self) -> None:
        assert _is_win("respondent", "Dismissed") is True

    def test_respondent_allowed(self) -> None:
        assert _is_win("respondent", "Allowed") is False

    def test_none_disposal(self) -> None:
        assert _is_win("petitioner", None) is False

    def test_unknown_side(self) -> None:
        assert _is_win("intervenor", "Allowed") is False


# ---------------------------------------------------------------------------
# Mock session helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    return session


def _mock_execute_returns(session: AsyncMock, *return_values: list[object]) -> None:
    """Set up session.execute() to return successive mock results."""
    mock_results = []
    for val in return_values:
        mock_result = MagicMock()
        if isinstance(val, list):
            mock_result.all.return_value = val
            mock_result.scalar_one_or_none.return_value = None
        else:
            mock_result.scalar_one_or_none.return_value = val
            mock_result.all.return_value = []
        mock_results.append(mock_result)

    session.execute = AsyncMock(side_effect=mock_results)


# ---------------------------------------------------------------------------
# Search counsel tests
# ---------------------------------------------------------------------------


class TestSearchCounsel:
    """Tests for CounselAnalyticsService.search_counsel."""

    @pytest.mark.asyncio
    async def test_returns_matching_counsels(self) -> None:
        session = _make_mock_session()

        result_rows = [
            SimpleNamespace(counsel_name="R.K. Sharma", total_cases=15, designation="senior_advocate"),
            SimpleNamespace(counsel_name="S.K. Sharma", total_cases=8, designation="advocate"),
        ]

        # count query returns 2, then results query returns rows
        _mock_execute_returns(session, 2, result_rows)

        service = CounselAnalyticsService(session)
        items, total = await service.search_counsel("Sharma")

        assert total == 2
        assert len(items) == 2
        assert isinstance(items[0], CounselListItem)
        assert items[0].name == "R.K. Sharma"
        assert items[0].total_cases == 15
        assert items[0].designation == "senior_advocate"

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_match(self) -> None:
        session = _make_mock_session()

        _mock_execute_returns(session, 0)

        service = CounselAnalyticsService(session)
        items, total = await service.search_counsel("Nonexistent")

        assert total == 0
        assert items == []


# ---------------------------------------------------------------------------
# Counsel profile tests
# ---------------------------------------------------------------------------


class TestGetCounselProfile:
    """Tests for CounselAnalyticsService.get_counsel_profile."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_cases(self) -> None:
        session = _make_mock_session()

        # First query (exact name) returns empty, second (normalized) also empty
        _mock_execute_returns(session, [], [])

        service = CounselAnalyticsService(session)
        result = await service.get_counsel_profile("Unknown Counsel")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_profile_with_stats(self) -> None:
        session = _make_mock_session()

        case_id1 = uuid.uuid4()
        case_id2 = uuid.uuid4()

        case_rows = [
            SimpleNamespace(
                id=case_id1, year=2020, case_type="Criminal Appeal",
                disposal_nature="Allowed", party_side="petitioner",
                counsel_name="R.K. Sharma", designation="senior_advocate",
            ),
            SimpleNamespace(
                id=case_id2, year=2021, case_type="Civil Appeal",
                disposal_nature="Dismissed", party_side="respondent",
                counsel_name="R.K. Sharma", designation="senior_advocate",
            ),
        ]

        acts_rows = [
            SimpleNamespace(act="Constitution of India", count=2),
        ]

        # matchups query (inside get_counsel_matchups called by get_counsel_profile)
        matchup_rows: list[object] = []

        # Sequence: cases query, acts query, matchups query
        _mock_execute_returns(session, case_rows, acts_rows, matchup_rows)

        service = CounselAnalyticsService(session)
        result = await service.get_counsel_profile("R.K. Sharma")

        assert result is not None
        assert isinstance(result, CounselProfile)
        assert result.name == "R.K. Sharma"
        assert result.normalized_name == "R.K. Sharma"
        assert result.total_cases == 2
        assert result.petitioner_cases == 1
        assert result.respondent_cases == 1
        # Both cases won (Allowed as petitioner, Dismissed as respondent)
        assert result.win_rate == 100.0
        assert result.designation == "senior_advocate"
        assert result.active_years == (2020, 2021)
        assert "Criminal Appeal" in result.case_types
        assert "Civil Appeal" in result.case_types


# ---------------------------------------------------------------------------
# Counsel cases tests
# ---------------------------------------------------------------------------


class TestGetCounselCases:
    """Tests for CounselAnalyticsService.get_counsel_cases."""

    @pytest.mark.asyncio
    async def test_returns_paginated_cases(self) -> None:
        session = _make_mock_session()

        case_id = str(uuid.uuid4())
        case_rows = [
            SimpleNamespace(
                id=case_id, title="State vs Citizen",
                citation="(2021) 2 SCC 100", year=2021,
                case_type="Criminal Appeal", disposal_nature="Allowed",
                party_side="petitioner",
            ),
        ]

        _mock_execute_returns(session, 1, case_rows)

        service = CounselAnalyticsService(session)
        items, total = await service.get_counsel_cases("R.K. Sharma")

        assert total == 1
        assert len(items) == 1
        assert isinstance(items[0], CounselCaseItem)
        assert items[0].id == case_id
        assert items[0].title == "State vs Citizen"
        assert items[0].party_side == "petitioner"
        assert items[0].won is True

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_counsel(self) -> None:
        session = _make_mock_session()

        _mock_execute_returns(session, 0)

        service = CounselAnalyticsService(session)
        items, total = await service.get_counsel_cases("Nonexistent")

        assert total == 0
        assert items == []


# ---------------------------------------------------------------------------
# Matchups tests
# ---------------------------------------------------------------------------


class TestGetCounselMatchups:
    """Tests for CounselAnalyticsService.get_counsel_matchups."""

    @pytest.mark.asyncio
    async def test_returns_opponent_records(self) -> None:
        session = _make_mock_session()

        case_id1 = uuid.uuid4()
        case_id2 = uuid.uuid4()

        matchup_rows = [
            SimpleNamespace(
                id=case_id1,
                disposal_nature="Allowed",
                counsel_list=[
                    {"counsel_name": "R.K. Sharma", "party": "petitioner"},
                    {"counsel_name": "A.B. Singh", "party": "respondent"},
                ],
            ),
            SimpleNamespace(
                id=case_id2,
                disposal_nature="Dismissed",
                counsel_list=[
                    {"counsel_name": "R.K. Sharma", "party": "petitioner"},
                    {"counsel_name": "A.B. Singh", "party": "respondent"},
                ],
            ),
        ]

        _mock_execute_returns(session, matchup_rows)

        service = CounselAnalyticsService(session)
        result = await service.get_counsel_matchups("R.K. Sharma")

        assert len(result) == 1
        assert result[0]["opponent"] == "A.B. Singh"
        assert result[0]["total"] == 2
        assert result[0]["wins"] == 1
        assert result[0]["losses"] == 1
        assert result[0]["win_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_cases(self) -> None:
        session = _make_mock_session()

        _mock_execute_returns(session, [])

        service = CounselAnalyticsService(session)
        result = await service.get_counsel_matchups("Unknown")

        assert result == []


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    """Test dataclass initialization and defaults."""

    def test_counsel_list_item(self) -> None:
        item = CounselListItem(name="Test", total_cases=5, designation="advocate")
        assert item.name == "Test"
        assert item.total_cases == 5

    def test_counsel_profile_defaults(self) -> None:
        profile = CounselProfile(
            name="Test",
            normalized_name="Test",
            total_cases=10,
            petitioner_cases=5,
            respondent_cases=5,
            win_rate=50.0,
        )
        assert profile.case_types == {}
        assert profile.acts_frequency == {}
        assert profile.designation == ""
        assert profile.active_years == (0, 0)
        assert profile.top_matchups == []

    def test_counsel_case_item(self) -> None:
        item = CounselCaseItem(
            id="abc-123",
            title="Test Case",
            citation=None,
            year=2020,
            case_type="Appeal",
            party_side="petitioner",
            outcome="Allowed",
            won=True,
        )
        assert item.id == "abc-123"
        assert item.won is True
