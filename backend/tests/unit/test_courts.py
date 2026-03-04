"""Unit tests for court name normalization and hierarchy classification."""

import pytest

from app.core.legal.courts import (
    AIR_COURT_CODES,
    COURT_NAME_MAP,
    get_court_level,
    normalize_court_name,
)


class TestNormalizeCourtName:
    """Tests for normalize_court_name()."""

    def test_supreme_court_abbreviation(self):
        assert normalize_court_name("SC") == "Supreme Court of India"

    def test_supreme_court_full_name(self):
        assert normalize_court_name("Supreme Court of India") == "Supreme Court of India"

    def test_high_court_abbreviation(self):
        assert normalize_court_name("BomHC") == "High Court of Bombay"

    def test_air_code_delhi(self):
        assert normalize_court_name("Del") == "High Court of Delhi"

    def test_air_code_allahabad(self):
        assert normalize_court_name("All") == "High Court of Allahabad"

    def test_case_insensitive_lookup(self):
        assert normalize_court_name("sc") == "Supreme Court of India"
        assert normalize_court_name("bomhc") == "High Court of Bombay"

    def test_tribunal_nclt(self):
        assert normalize_court_name("NCLT") == "National Company Law Tribunal"

    def test_unknown_court_returns_input(self):
        assert normalize_court_name("Some Random Court") == "Some Random Court"

    def test_punjab_haryana_variants(self):
        assert normalize_court_name("P&HHC") == "High Court of Punjab and Haryana"
        assert normalize_court_name("PHHC") == "High Court of Punjab and Haryana"

    def test_telangana(self):
        assert normalize_court_name("TelHC") == "High Court of Telangana"

    def test_jk_ladakh(self):
        assert normalize_court_name("JKHC") == "High Court of Jammu & Kashmir and Ladakh"


class TestGetCourtLevel:
    """Tests for get_court_level()."""

    def test_supreme_court(self):
        assert get_court_level("SC") == "supreme"
        assert get_court_level("Supreme Court of India") == "supreme"

    def test_high_court(self):
        assert get_court_level("BomHC") == "high"
        assert get_court_level("High Court of Bombay") == "high"

    def test_tribunal(self):
        assert get_court_level("NCLT") == "tribunal"
        assert get_court_level("National Green Tribunal") == "tribunal"

    def test_district_court_keyword(self):
        assert get_court_level("District Court of Mumbai") == "district"
        assert get_court_level("Sessions Court, Delhi") == "district"

    def test_unknown(self):
        assert get_court_level("Some Unknown Body") == "unknown"

    def test_air_code_gives_correct_level(self):
        assert get_court_level("Del") == "high"
        assert get_court_level("Bom") == "high"


class TestDataIntegrity:
    """Ensure all lookups are consistent."""

    def test_all_air_codes_have_valid_courts(self):
        for code, name in AIR_COURT_CODES.items():
            level = get_court_level(name)
            assert level in ("supreme", "high"), f"AIR code {code} → {name} → unexpected level {level}"

    def test_court_name_map_no_empty_values(self):
        for key, value in COURT_NAME_MAP.items():
            assert key.strip(), "Empty key found"
            assert value.strip(), f"Empty value for key {key}"
