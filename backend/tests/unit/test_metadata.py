"""Unit tests for metadata extraction and validation."""

import pytest
from datetime import datetime

from app.core.ingestion.metadata import (
    CaseMetadata,
    _parse_judge_names,
    merge_metadata,
    normalize_case_type,
    validate_cross_fields,
    validate_with_regex,
)


class TestValidateWithRegex:
    """Tests for validate_with_regex()."""

    def test_valid_metadata_unchanged(self):
        meta = CaseMetadata(
            title="Test Case",
            year=2023,
            decision_date="2023-03-15",
            court="Supreme Court of India",
            bench_type="division",
            jurisdiction="civil",
            disposal_nature="Allowed",
        )
        result = validate_with_regex(meta)
        assert result.year == 2023
        assert result.decision_date == "2023-03-15"

    def test_impossible_year_cleared(self):
        meta = CaseMetadata(year=1500)
        result = validate_with_regex(meta)
        assert result.year is None

    def test_future_year_cleared(self):
        future_year = datetime.now().year + 5
        meta = CaseMetadata(year=future_year)
        result = validate_with_regex(meta)
        assert result.year is None

    def test_valid_year_preserved(self):
        meta = CaseMetadata(year=1950)
        result = validate_with_regex(meta)
        assert result.year == 1950

    def test_invalid_date_format_cleared(self):
        meta = CaseMetadata(decision_date="15-03-2023")  # Wrong format
        result = validate_with_regex(meta)
        assert result.decision_date is None

    def test_future_date_cleared(self):
        meta = CaseMetadata(decision_date="2099-01-01")
        result = validate_with_regex(meta)
        assert result.decision_date is None

    def test_invalid_bench_type_cleared(self):
        meta = CaseMetadata(bench_type="mega")
        result = validate_with_regex(meta)
        assert result.bench_type is None

    def test_valid_bench_type_normalized(self):
        meta = CaseMetadata(bench_type="Division")
        result = validate_with_regex(meta)
        assert result.bench_type == "division"

    def test_invalid_jurisdiction_cleared(self):
        meta = CaseMetadata(jurisdiction="interplanetary")
        result = validate_with_regex(meta)
        assert result.jurisdiction is None

    def test_invalid_disposal_cleared(self):
        meta = CaseMetadata(disposal_nature="Exploded")
        result = validate_with_regex(meta)
        assert result.disposal_nature is None

    def test_disposal_title_cased(self):
        meta = CaseMetadata(disposal_nature="allowed")
        result = validate_with_regex(meta)
        assert result.disposal_nature == "Allowed"

    def test_non_list_judge_cleared(self):
        meta = CaseMetadata(judge="Not a list")  # type: ignore
        result = validate_with_regex(meta)
        assert result.judge is None

    def test_court_normalized(self):
        meta = CaseMetadata(court="BomHC")
        result = validate_with_regex(meta)
        assert result.court == "High Court of Bombay"


class TestMergeMetadata:
    """Tests for merge_metadata()."""

    def test_parquet_wins_for_title(self):
        parquet = {"title": "Parquet Title"}
        llm = CaseMetadata(title="LLM Title")
        result, _ = merge_metadata(parquet, llm)
        assert result.title == "Parquet Title"

    def test_llm_fallback_for_title(self):
        parquet = {"title": ""}
        llm = CaseMetadata(title="LLM Title")
        result, _ = merge_metadata(parquet, llm)
        assert result.title == "LLM Title"

    def test_llm_wins_for_ratio(self):
        parquet = {}
        llm = CaseMetadata(ratio_decidendi="The court held that...")
        result, _ = merge_metadata(parquet, llm)
        assert result.ratio_decidendi == "The court held that..."

    def test_judge_from_comma_string(self):
        parquet = {"judge": "Justice D.Y. Chandrachud, Justice Sanjiv Khanna"}
        llm = CaseMetadata()
        result, _ = merge_metadata(parquet, llm)
        # _parse_judge_names strips "Justice" prefix for normalized storage
        assert result.judge == ["D.Y. Chandrachud", "Sanjiv Khanna"]

    def test_nc_display_stored_as_case_number_not_case_type(self):
        """nc_display is a case identifier (e.g. 2024Insc446), not a case type."""
        parquet = {"nc_display": "2024Insc446"}
        llm = CaseMetadata(case_type="Civil Appeal")
        result, prov = merge_metadata(parquet, llm)
        assert result.case_type == "Civil Appeal"
        assert result.case_number == "2024Insc446"

    def test_empty_parquet_and_llm(self):
        result, _ = merge_metadata({}, CaseMetadata())
        assert result.title is None
        assert result.court is None


class TestNormalizeCaseType:
    """Tests for expanded case_type normalization (C12)."""

    def test_curative_petition(self):
        assert normalize_case_type("Curative Petition") == "Curative Petition"
        assert normalize_case_type("cur.pet.") == "Curative Petition"

    def test_miscellaneous_application(self):
        assert normalize_case_type("miscellaneous application") == "Miscellaneous Application"
        assert normalize_case_type("M.A.") == "Miscellaneous Application"

    def test_arbitration_petition(self):
        assert normalize_case_type("arbitration petition") == "Arbitration Petition"
        assert normalize_case_type("arb.p.") == "Arbitration Petition"

    def test_suo_motu(self):
        assert normalize_case_type("suo motu") == "Suo Motu"

    def test_election_petition(self):
        assert normalize_case_type("election petition") == "Election Petition"

    def test_slp_civil_criminal(self):
        assert normalize_case_type("SLP (Civil)") == "Special Leave Petition"
        assert normalize_case_type("SLP (Criminal)") == "Special Leave Petition"

    def test_appeal_abbreviations(self):
        assert normalize_case_type("c.a.") == "Civil Appeal"
        assert normalize_case_type("crl.a.") == "Criminal Appeal"

    def test_interlocutory_application(self):
        assert normalize_case_type("i.a.") == "Interlocutory Application"
        assert normalize_case_type("Interlocutory Application") == "Interlocutory Application"

    def test_letters_patent_appeal(self):
        assert normalize_case_type("l.p.a.") == "Letters Patent Appeal"
        assert normalize_case_type("letters patent appeal") == "Letters Patent Appeal"

    def test_existing_types_still_work(self):
        assert normalize_case_type("SLP") == "Special Leave Petition"
        assert normalize_case_type("writ petition") == "Writ Petition"
        assert normalize_case_type("r.p.") == "Review Petition"


class TestValidateCrossFields:
    """Tests for cross-field validations (C14)."""

    def test_year_synced_from_decision_date(self):
        meta = CaseMetadata(year=2020, decision_date="2023-05-01")
        result = validate_cross_fields(meta)
        assert result.year == 2023

    def test_bench_type_cleared_when_single_with_many_judges(self):
        meta = CaseMetadata(
            bench_type="single",
            judge=["A", "B", "C"],
        )
        result = validate_cross_fields(meta)
        assert result.bench_type is None

    def test_bench_type_single_with_one_judge_preserved(self):
        meta = CaseMetadata(
            bench_type="single",
            judge=["A"],
        )
        result = validate_cross_fields(meta)
        assert result.bench_type == "single"

    def test_author_judge_not_in_list_warns(self, caplog):
        meta = CaseMetadata(
            author_judge="X",
            judge=["A", "B"],
        )
        with caplog.at_level("WARNING"):
            result = validate_cross_fields(meta)
        assert "not found in judge list" in caplog.text
        # author_judge should NOT be cleared, only warned
        assert result.author_judge == "X"

    def test_author_judge_in_list_no_warning(self, caplog):
        meta = CaseMetadata(
            author_judge="A",
            judge=["A", "B"],
        )
        with caplog.at_level("WARNING"):
            validate_cross_fields(meta)
        assert "not found in judge list" not in caplog.text

    def test_same_petitioner_respondent_clears_respondent(self):
        meta = CaseMetadata(
            petitioner="Union of India",
            respondent="UNION OF INDIA",
        )
        result = validate_cross_fields(meta)
        assert result.respondent is None

    def test_different_petitioner_respondent_preserved(self):
        meta = CaseMetadata(
            petitioner="Union of India",
            respondent="State of Maharashtra",
        )
        result = validate_cross_fields(meta)
        assert result.respondent == "State of Maharashtra"

    def test_writ_petition_criminal_warns(self, caplog):
        meta = CaseMetadata(
            case_type="Writ Petition",
            jurisdiction="criminal",
        )
        with caplog.at_level("WARNING"):
            validate_cross_fields(meta)
        assert "unusual" in caplog.text


class TestJurisdictionIPCommercial:
    """Tests for ip/commercial jurisdiction (C16)."""

    def test_ip_commercial_accepted(self):
        meta = CaseMetadata(jurisdiction="ip/commercial")
        result = validate_with_regex(meta)
        assert result.jurisdiction == "ip/commercial"

    def test_ip_alias_normalized(self):
        meta = CaseMetadata(jurisdiction="IP")
        result = validate_with_regex(meta)
        assert result.jurisdiction == "ip/commercial"

    def test_ip_commercial_mixed_case(self):
        meta = CaseMetadata(jurisdiction="IP/Commercial")
        result = validate_with_regex(meta)
        assert result.jurisdiction == "ip/commercial"


class TestParseJudgeNamesPrefixes:
    """Tests for _parse_judge_names with new prefixes (C18)."""

    def test_dr_justice_prefix(self):
        result = _parse_judge_names("Dr. Justice D.Y. Chandrachud")
        assert result == ["D.Y. Chandrachud"]

    def test_dr_prefix(self):
        result = _parse_judge_names("Dr. B.S. Chauhan")
        assert result == ["B.S. Chauhan"]

    def test_smt_prefix(self):
        result = _parse_judge_names("Smt. Indira Banerjee")
        assert result == ["Indira Banerjee"]

    def test_shri_prefix(self):
        result = _parse_judge_names("Shri N.V. Ramana")
        assert result == ["N.V. Ramana"]

    def test_existing_prefixes_still_work(self):
        result = _parse_judge_names("Hon'ble Mr. Justice A.K. Sikri")
        assert result == ["A.K. Sikri"]

    def test_trailing_j_stripped(self):
        result = _parse_judge_names("B.R. Gavai J.")
        assert result == ["B.R. Gavai"]

    def test_initial_j_preserved(self):
        result = _parse_judge_names("J. Chelameswar")
        assert result == ["Chelameswar"]  # "J." is stripped as prefix

    def test_multiple_judges_mixed_prefixes(self):
        result = _parse_judge_names("Dr. Justice X; Smt. Y; Shri Z")
        assert result == ["X", "Y", "Z"]


# ---------------------------------------------------------------------------
# V3: Cross-validation tests
# ---------------------------------------------------------------------------


def test_cross_validate_synthesizes_ratio_from_propositions():
    from app.core.ingestion.metadata import CaseMetadata, cross_validate_propositions
    meta = CaseMetadata(
        legal_propositions=[
            {"proposition_text": "Section 302 requires mens rea.", "is_novel": False},
            {"proposition_text": "Circumstantial evidence must be conclusive.", "is_novel": True},
        ],
        ratio_decidendi=None,
    )
    result = cross_validate_propositions(meta)
    assert "Section 302" in result.ratio_decidendi
    assert "mens rea" in result.ratio_decidendi


def test_cross_validate_creates_proposition_from_ratio():
    from app.core.ingestion.metadata import CaseMetadata, cross_validate_propositions
    meta = CaseMetadata(
        ratio_decidendi="The right to privacy is a fundamental right under Article 21.",
        legal_propositions=None,
    )
    result = cross_validate_propositions(meta)
    assert len(result.legal_propositions) == 1
    assert "privacy" in result.legal_propositions[0]["proposition_text"]
