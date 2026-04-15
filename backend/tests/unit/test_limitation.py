"""Tests for limitation period calculator."""
from datetime import date

from app.core.legal.limitation import (
    LIMITATION_SCHEDULE,
    calculate_deadline,
    get_limitation_for_doc_type,
)


class TestLimitationSchedule:
    def test_schedule_has_entries(self) -> None:
        assert len(LIMITATION_SCHEDULE) >= 25

    def test_breach_of_contract_is_3_years(self) -> None:
        p = LIMITATION_SCHEDULE["breach_of_contract"]
        assert p.period_years == 3

    def test_civil_appeal_first_is_90_days(self) -> None:
        p = LIMITATION_SCHEDULE["civil_appeal_first"]
        assert p.period_days == 90

    def test_slp_civil_is_90_days(self) -> None:
        p = LIMITATION_SCHEDULE["slp_civil"]
        assert p.period_days == 90

    def test_slp_criminal_is_60_days(self) -> None:
        p = LIMITATION_SCHEDULE["slp_criminal"]
        assert p.period_days == 60


class TestCalculateDeadline:
    def test_within_time(self) -> None:
        result = calculate_deadline("breach_of_contract", date(2024, 1, 1))
        assert result["found"] is True
        assert result["deadline"] is not None

    def test_expired(self) -> None:
        result = calculate_deadline("civil_appeal_first", date(2020, 1, 1))
        assert result["found"] is True
        assert result["within_time"] is False

    def test_unknown_cause(self) -> None:
        result = calculate_deadline("nonexistent", date(2024, 1, 1))
        assert result["found"] is False

    def test_no_limitation(self) -> None:
        result = calculate_deadline("bail_application", date(2024, 1, 1))
        assert result["found"] is True
        assert result["deadline"] is None
        assert result["within_time"] is True


class TestGetLimitationForDocType:
    def test_plaint_maps_to_contract(self) -> None:
        p = get_limitation_for_doc_type("plaint")
        assert p is not None
        assert p.period_years == 3

    def test_slp_maps_to_90_days(self) -> None:
        p = get_limitation_for_doc_type("slp")
        assert p is not None
        assert p.period_days == 90

    def test_unknown_doc_type_returns_none(self) -> None:
        assert get_limitation_for_doc_type("nonexistent") is None
