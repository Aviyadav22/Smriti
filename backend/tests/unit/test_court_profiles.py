"""Tests for court-specific formatting profiles."""

from dataclasses import FrozenInstanceError

import pytest

from app.core.drafting.court_profiles import (
    COURT_PROFILES,
    CourtProfile,
    get_court_profile,
)


class TestCourtProfile:
    """Verify individual profile data and dataclass behaviour."""

    def test_supreme_court_profile_exists(self) -> None:
        assert "supreme_court" in COURT_PROFILES

    def test_supreme_court_has_correct_formatting(self) -> None:
        sc = COURT_PROFILES["supreme_court"]
        assert sc.font_size_body == 14
        assert sc.line_spacing == 1.5
        assert sc.margin_left_cm == 4.0
        assert sc.margin_right_cm == 4.0
        assert sc.paper_size == "A4"
        assert sc.requires_synopsis is True
        assert sc.print_both_sides is True
        assert sc.font_size_heading == 16
        assert sc.font_size_quote == 12
        assert sc.margin_top_cm == 2.0
        assert sc.margin_bottom_cm == 2.0

    def test_delhi_hc_profile_exists(self) -> None:
        dhc = COURT_PROFILES["delhi_hc"]
        assert dhc.font_size_body == 14
        assert dhc.line_spacing == 2.0

    def test_bombay_hc_uses_legal_paper(self) -> None:
        bhc = COURT_PROFILES["bombay_hc"]
        assert bhc.paper_size == "legal"

    def test_default_profile_exists(self) -> None:
        default = COURT_PROFILES["default"]
        assert default.font_size_body == 12
        assert default.paper_size == "A4"

    def test_all_eight_profiles_exist(self) -> None:
        expected = {
            "supreme_court",
            "delhi_hc",
            "bombay_hc",
            "madras_hc",
            "karnataka_hc",
            "calcutta_hc",
            "nclt",
            "default",
        }
        assert set(COURT_PROFILES.keys()) == expected

    def test_profiles_are_frozen(self) -> None:
        sc = COURT_PROFILES["supreme_court"]
        with pytest.raises(FrozenInstanceError):
            sc.font_size_body = 10  # type: ignore[misc]


class TestGetCourtProfile:
    """Verify alias resolution and fallback behaviour."""

    def test_exact_match(self) -> None:
        profile = get_court_profile("supreme_court")
        assert profile.court_id == "supreme_court"

    def test_alias_sc(self) -> None:
        profile = get_court_profile("SC")
        assert profile.court_id == "supreme_court"

    def test_alias_supreme_court_text(self) -> None:
        profile = get_court_profile("Supreme Court")
        assert profile.court_id == "supreme_court"

    def test_alias_delhi_high_court(self) -> None:
        profile = get_court_profile("Delhi High Court")
        assert profile.court_id == "delhi_hc"

    def test_alias_dhc(self) -> None:
        profile = get_court_profile("DHC")
        assert profile.court_id == "delhi_hc"

    def test_alias_bombay_hc(self) -> None:
        profile = get_court_profile("Bombay HC")
        assert profile.court_id == "bombay_hc"

    def test_alias_nclt(self) -> None:
        profile = get_court_profile("NCLT")
        assert profile.court_id == "nclt"

    def test_unknown_court_returns_default(self) -> None:
        profile = get_court_profile("Imaginary Court of Narnia")
        assert profile.court_id == "default"

    def test_empty_string_returns_default(self) -> None:
        profile = get_court_profile("")
        assert profile.court_id == "default"

    def test_case_insensitive(self) -> None:
        profile = get_court_profile("supreme court")
        assert profile.court_id == "supreme_court"
        profile2 = get_court_profile("DELHI HIGH COURT")
        assert profile2.court_id == "delhi_hc"
