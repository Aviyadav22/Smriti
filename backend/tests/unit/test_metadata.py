"""Unit tests for metadata extraction and validation."""

import pytest
from datetime import datetime

from app.core.ingestion.metadata import (
    CaseMetadata,
    _parse_judge_names,
    _strip_unreliable_llm_fields,
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


# ---------------------------------------------------------------------------
# Task 2: Newline stripping + cases_cited cleanup
# ---------------------------------------------------------------------------


class TestNewlineStrippingInListFields:
    """Tests for embedded newline removal in list fields (Task 2)."""

    def test_newlines_stripped_from_cases_cited(self):
        meta = CaseMetadata(
            cases_cited=["Union of India\nv.\nState of Kerala", "Ram\nv. Shyam"]
        )
        result = validate_with_regex(meta)
        assert result.cases_cited == [
            "Union of India v. State of Kerala",
            "Ram v. Shyam",
        ]

    def test_newlines_stripped_from_acts_cited(self):
        meta = CaseMetadata(
            acts_cited=["Indian Penal\nCode, 1860", "Code of Criminal\nProcedure"]
        )
        result = validate_with_regex(meta)
        # Both should have newlines replaced with spaces
        assert all("\n" not in a for a in result.acts_cited)

    def test_double_spaces_collapsed(self):
        meta = CaseMetadata(
            cases_cited=["Union of India  v.   State of Kerala"]
        )
        result = validate_with_regex(meta)
        assert result.cases_cited == ["Union of India v. State of Kerala"]

    def test_carriage_return_stripped(self):
        meta = CaseMetadata(
            keywords=["constitutional\r\nlaw", "fundamental\rrights"]
        )
        result = validate_with_regex(meta)
        assert result.keywords == ["constitutional law", "fundamental rights"]

    def test_empty_after_strip_removed(self):
        meta = CaseMetadata(cases_cited=["\n", "  \n  ", "Real Case v. Real"])
        result = validate_with_regex(meta)
        assert result.cases_cited == ["Real Case v. Real"]

    def test_deduplication_after_strip(self):
        meta = CaseMetadata(
            cases_cited=["A v. B", "A v.  B", "A v.\nB"]
        )
        result = validate_with_regex(meta)
        assert result.cases_cited == ["A v. B"]


class TestSelfCitationRemoval:
    """Tests for self-citation and docket number removal (Task 2)."""

    def test_self_citation_removed(self):
        meta = CaseMetadata(
            citation="(2023) 5 SCC 100",
            cases_cited=["(2023) 5 SCC 100", "AIR 2020 SC 500"],
        )
        result = validate_cross_fields(meta)
        assert result.cases_cited == ["AIR 2020 SC 500"]

    def test_self_citation_whitespace_normalized(self):
        meta = CaseMetadata(
            citation="(2023)  5  SCC  100",
            cases_cited=["(2023) 5 SCC 100", "Other Case"],
        )
        result = validate_cross_fields(meta)
        assert result.cases_cited == ["Other Case"]

    def test_docket_number_removed(self):
        meta = CaseMetadata(
            cases_cited=["5095 Of 2025", "1040 of 2022", "Real Case v. State"]
        )
        result = validate_cross_fields(meta)
        assert result.cases_cited == ["Real Case v. State"]

    def test_all_docket_numbers_yields_none(self):
        meta = CaseMetadata(
            cases_cited=["5095 Of 2025", "1040 of 2022"]
        )
        result = validate_cross_fields(meta)
        assert result.cases_cited is None

    def test_no_citation_no_self_removal(self):
        meta = CaseMetadata(
            citation=None,
            cases_cited=["Laxman v. State of Maharashtra, (2002) 6 SCC 710"],
        )
        result = validate_cross_fields(meta)
        assert result.cases_cited == ["Laxman v. State of Maharashtra, (2002) 6 SCC 710"]

    def test_bare_citation_moved_to_citation_refs(self):
        """Bare reporter refs are classified into citation_refs, not cases_cited."""
        meta = CaseMetadata(
            citation=None,
            cases_cited=["(2023) 5 SCC 100", "Ram v. State, (2020) 3 SCC 200"],
        )
        result = validate_cross_fields(meta)
        # Named citation stays in cases_cited
        assert result.cases_cited == ["Ram v. State, (2020) 3 SCC 200"]
        # Bare ref moved to citation_refs
        assert result.citation_refs == ["(2023) 5 SCC 100"]


# ---------------------------------------------------------------------------
# Task 3: Disposal nature merge fallback
# ---------------------------------------------------------------------------


class TestDisposalNatureMerge:
    """Tests for disposal_nature LLM-priority merge in merge_metadata."""

    def test_llm_disposal_wins_over_parquet(self):
        """LLM extraction takes priority over Parquet for disposal_nature."""
        parquet = {"disposal_nature": "Allowed"}
        llm = CaseMetadata(disposal_nature="Dismissed")
        result, prov = merge_metadata(parquet, llm)
        assert result.disposal_nature == "Dismissed"
        assert prov["disposal_nature"] == "llm"

    def test_llm_none_falls_back_to_parquet(self):
        """When LLM has no disposal_nature, fall back to Parquet."""
        parquet = {"disposal_nature": "Allowed"}
        llm = CaseMetadata(disposal_nature=None)
        result, prov = merge_metadata(parquet, llm)
        assert result.disposal_nature == "Allowed"
        assert prov["disposal_nature"] == "parquet_fallback"

    def test_both_none_stays_none(self):
        parquet = {}
        llm = CaseMetadata(disposal_nature=None)
        result, prov = merge_metadata(parquet, llm)
        assert result.disposal_nature is None

    def test_parquet_fallback_normalizes_title_case(self):
        """Parquet fallback normalizes to title case when valid."""
        parquet = {"disposal_nature": "partly allowed"}
        llm = CaseMetadata(disposal_nature=None)
        result, prov = merge_metadata(parquet, llm)
        assert result.disposal_nature == "Partly Allowed"
        assert prov["disposal_nature"] == "parquet_fallback"

    def test_parquet_fallback_with_normalized_value(self):
        """Parquet value that maps via _DISPOSAL_MAP should be accepted as fallback."""
        parquet = {"disposal_nature": "Appeal(s) allowed"}
        llm = CaseMetadata(disposal_nature=None)
        from app.core.ingestion.metadata import validate_parquet_data
        cleaned = validate_parquet_data(parquet)
        result, prov = merge_metadata(cleaned, llm)
        assert result.disposal_nature == "Allowed"
        assert prov["disposal_nature"] == "parquet_fallback"


# ---------------------------------------------------------------------------
# Task 4: bench_type/coram_size inference + judge completion
# ---------------------------------------------------------------------------


class TestCoramBenchInference:
    """Tests for coram_size → bench_type inference (Task 4)."""

    def test_coram_1_infers_single(self):
        meta = CaseMetadata(coram_size=1, bench_type=None)
        result = validate_cross_fields(meta)
        assert result.bench_type == "single"

    def test_coram_2_infers_division(self):
        meta = CaseMetadata(coram_size=2, bench_type=None)
        result = validate_cross_fields(meta)
        assert result.bench_type == "division"

    def test_coram_3_infers_division(self):
        meta = CaseMetadata(coram_size=3, bench_type=None)
        result = validate_cross_fields(meta)
        assert result.bench_type == "division"

    def test_coram_4_infers_full(self):
        meta = CaseMetadata(coram_size=4, bench_type=None)
        result = validate_cross_fields(meta)
        assert result.bench_type == "full"

    def test_coram_5_infers_constitutional(self):
        meta = CaseMetadata(coram_size=5, bench_type=None)
        result = validate_cross_fields(meta)
        assert result.bench_type == "constitutional"

    def test_coram_overrides_conflicting_bench_type(self):
        meta = CaseMetadata(coram_size=2, bench_type="single")
        result = validate_cross_fields(meta)
        assert result.bench_type == "division"


class TestJudgeArrayCompletion:
    """Tests for judge array completion from author_judge (Task 4)."""

    def test_author_judge_appended_when_missing(self):
        meta = CaseMetadata(
            coram_size=3,
            judge=["A", "B"],
            author_judge="C",
        )
        result = validate_cross_fields(meta)
        assert "C" in result.judge
        assert len(result.judge) == 3

    def test_author_judge_not_appended_when_already_present(self):
        meta = CaseMetadata(
            coram_size=2,
            judge=["A"],
            author_judge="A",
        )
        result = validate_cross_fields(meta)
        assert result.judge == ["A"]

    def test_author_judge_not_appended_when_judge_count_matches_coram(self):
        meta = CaseMetadata(
            coram_size=2,
            judge=["A", "B"],
            author_judge="C",
        )
        result = validate_cross_fields(meta)
        # coram_size == len(judge), so no append
        assert len(result.judge) == 2

    def test_case_insensitive_match(self):
        meta = CaseMetadata(
            coram_size=3,
            judge=["D.Y. Chandrachud", "B"],
            author_judge="d.y. chandrachud",
        )
        result = validate_cross_fields(meta)
        # Author already in list (case-insensitive), should not duplicate
        assert len(result.judge) == 2


class TestIsReportableSCRInference:
    """Tests for is_reportable SCR citation inference (Task 6)."""

    def test_scr_citation_sets_reportable(self):
        meta = CaseMetadata(
            citation="[2023] 5 SCR 100",
            is_reportable=None,
        )
        result = validate_cross_fields(meta)
        assert result.is_reportable is True

    def test_scr_dotted_citation_sets_reportable(self):
        meta = CaseMetadata(
            citation="[2021] 3 S.C.R. 456",
            is_reportable=None,
        )
        result = validate_cross_fields(meta)
        assert result.is_reportable is True

    def test_non_scr_citation_stays_none(self):
        meta = CaseMetadata(
            citation="(2023) 5 SCC 100",
            is_reportable=None,
        )
        result = validate_cross_fields(meta)
        assert result.is_reportable is None

    def test_already_set_not_overridden(self):
        meta = CaseMetadata(
            citation="[2023] 5 SCR 100",
            is_reportable=False,
        )
        result = validate_cross_fields(meta)
        assert result.is_reportable is False


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


class TestMergeMetadataValidatedJudges:
    """Tests for the new validated judge merge logic."""

    def test_llm_judges_all_validated_uses_llm(self):
        """When all LLM judges appear in text, prefer LLM (fuller bench)."""
        header = "BEFORE HON'BLE D.Y. CHANDRACHUD AND SANJIV KHANNA, JJ.\n"
        full_text = header + "Body..." * 500
        parquet = {"judge": "D.Y. Chandrachud"}
        llm = CaseMetadata(judge=["D.Y. Chandrachud", "Sanjiv Khanna"])
        result, prov = merge_metadata(parquet, llm, full_text=full_text)
        assert len(result.judge) == 2
        assert "Sanjiv Khanna" in result.judge

    def test_hallucinated_llm_judges_fall_back_to_parquet(self):
        """When ALL LLM judges fail text validation, use parquet."""
        header = "BEFORE JUSTICE KRISHNA IYER AND JUSTICE DESAI\n"
        full_text = header + "Body..." * 500
        parquet = {"judge": "V.R. Krishna Iyer, D.A. Desai"}
        llm = CaseMetadata(judge=["P. Sathasivam", "B.S. Chauhan"])
        result, prov = merge_metadata(parquet, llm, full_text=full_text)
        assert "V.R. Krishna Iyer" in result.judge
        assert "P. Sathasivam" not in result.judge

    def test_partial_hallucination_unions_valid_with_parquet(self):
        """When some LLM judges fail, union validated LLM + parquet."""
        header = "BEFORE HON'BLE D.Y. CHANDRACHUD, SANJIV KHANNA AND C.T. RAVIKUMAR, JJ.\n"
        full_text = header + "Body..." * 500
        parquet = {"judge": "D.Y. Chandrachud"}
        llm = CaseMetadata(
            judge=["D.Y. Chandrachud", "Sanjiv Khanna", "P. Sathasivam"],
        )
        result, prov = merge_metadata(parquet, llm, full_text=full_text)
        assert "D.Y. Chandrachud" in result.judge
        assert "Sanjiv Khanna" in result.judge
        assert "P. Sathasivam" not in result.judge

    def test_no_full_text_falls_back_to_old_logic(self):
        """When full_text not provided, use count-based fallback."""
        parquet = {"judge": "D.Y. Chandrachud"}
        llm = CaseMetadata(judge=["D.Y. Chandrachud", "Sanjiv Khanna"])
        result, prov = merge_metadata(parquet, llm)
        # Without text validation, LLM wins by count
        assert len(result.judge) == 2


class TestStripUnreliableLlmFields:
    """Tests for confidence-based field stripping."""

    def test_strips_semantic_fields(self):
        meta = CaseMetadata(
            title="Correct Title",
            ratio_decidendi="Hallucinated ratio",
            keywords=["wrong", "keywords"],
            case_type="Criminal Appeal",
            jurisdiction="civil",
            bench_type="division",
            headnotes="Hallucinated headnotes",
            outcome_summary="Wrong summary",
        )
        result = _strip_unreliable_llm_fields(meta)
        assert result.title == "Correct Title"
        assert result.ratio_decidendi is None
        assert result.keywords is None
        assert result.case_type is None
        assert result.jurisdiction is None
        assert result.bench_type is None
        assert result.headnotes is None
        assert result.outcome_summary is None

    def test_preserves_parquet_sourced_fields(self):
        meta = CaseMetadata(
            title="Title",
            citation="(2023) 1 SCC 100",
            court="Supreme Court of India",
            year=2023,
            petitioner="A",
            respondent="B",
            judge=["Judge X"],
        )
        result = _strip_unreliable_llm_fields(meta)
        assert result.title == "Title"
        assert result.citation == "(2023) 1 SCC 100"
        assert result.court == "Supreme Court of India"
        assert result.year == 2023
        assert result.judge == ["Judge X"]
