"""Unit tests for metadata extraction and validation."""

import pytest
from datetime import datetime

from app.core.ingestion.metadata import (
    CaseMetadata,
    merge_metadata,
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
        result = merge_metadata(parquet, llm)
        assert result.title == "Parquet Title"

    def test_llm_fallback_for_title(self):
        parquet = {"title": ""}
        llm = CaseMetadata(title="LLM Title")
        result = merge_metadata(parquet, llm)
        assert result.title == "LLM Title"

    def test_llm_wins_for_ratio(self):
        parquet = {}
        llm = CaseMetadata(ratio_decidendi="The court held that...")
        result = merge_metadata(parquet, llm)
        assert result.ratio_decidendi == "The court held that..."

    def test_judge_from_comma_string(self):
        parquet = {"judge": "Justice A, Justice B"}
        llm = CaseMetadata()
        result = merge_metadata(parquet, llm)
        assert result.judge == ["Justice A", "Justice B"]

    def test_nc_display_used_for_case_type(self):
        parquet = {"nc_display": "Criminal Appeal"}
        llm = CaseMetadata(case_type="Civil")
        result = merge_metadata(parquet, llm)
        assert result.case_type == "Criminal Appeal"

    def test_empty_parquet_and_llm(self):
        result = merge_metadata({}, CaseMetadata())
        assert result.title is None
        assert result.court is None
