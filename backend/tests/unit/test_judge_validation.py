"""Tests for judge name validation against judgment text and tenure."""

import pytest

from app.core.ingestion.metadata import (
    _validate_judges_against_text,
    _validate_judge_tenure,
)


class TestValidateJudgesAgainstText:
    """Tests for _validate_judges_against_text()."""

    def test_all_judges_found_in_header(self):
        header = (
            "IN THE SUPREME COURT OF INDIA\n"
            "BEFORE: HON'BLE MR. JUSTICE D.Y. CHANDRACHUD\n"
            "HON'BLE MR. JUSTICE SANJIV KHANNA\n"
            "Civil Appeal No. 1234 of 2023\n"
        )
        full_text = header + "\n" * 10 + "Some judgment body text..." * 100
        judges = ["D.Y. Chandrachud", "Sanjiv Khanna"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert validated == ["D.Y. Chandrachud", "Sanjiv Khanna"]
        assert rejected == []

    def test_hallucinated_judge_rejected(self):
        header = (
            "IN THE SUPREME COURT OF INDIA\n"
            "BEFORE: HON'BLE MR. JUSTICE V.R. KRISHNA IYER\n"
            "HON'BLE MR. JUSTICE D.A. DESAI\n"
        )
        full_text = header + "\n" * 10 + "Body text..." * 100
        judges = ["V.R. Krishna Iyer", "D.A. Desai", "P. Sathasivam"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert validated == ["V.R. Krishna Iyer", "D.A. Desai"]
        assert rejected == ["P. Sathasivam"]

    def test_all_judges_hallucinated(self):
        header = (
            "IN THE SUPREME COURT OF INDIA\n"
            "BEFORE: HON'BLE MR. JUSTICE RANJAN GOGOI\n"
        )
        full_text = header + "\n" * 10 + "Body..." * 100
        judges = ["P. Sathasivam", "B.S. Chauhan"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert validated == []
        assert rejected == ["P. Sathasivam", "B.S. Chauhan"]

    def test_surname_match_with_different_initials(self):
        header = "JUSTICE DHANANJAYA Y. CHANDRACHUD AND JUSTICE SURYA KANT\n"
        full_text = header + "Body..." * 100
        judges = ["D.Y. Chandrachud", "Surya Kant"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert "D.Y. Chandrachud" in validated
        assert "Surya Kant" in validated

    def test_empty_judges_list(self):
        validated, rejected = _validate_judges_against_text([], "some text")
        assert validated == []
        assert rejected == []

    def test_none_judges(self):
        validated, rejected = _validate_judges_against_text(None, "some text")
        assert validated == []
        assert rejected == []

    def test_short_text_skips_validation(self):
        judges = ["D.Y. Chandrachud"]
        validated, rejected = _validate_judges_against_text(judges, "Short.")
        assert validated == ["D.Y. Chandrachud"]
        assert rejected == []

    def test_case_insensitive_match(self):
        header = "BEFORE: JUSTICE CHANDRACHUD AND JUSTICE SANJIV KHANNA\n"
        full_text = header + "Body..." * 100
        judges = ["D.Y. Chandrachud", "Sanjiv Khanna"]
        validated, rejected = _validate_judges_against_text(judges, full_text)
        assert len(validated) == 2
        assert len(rejected) == 0


class TestValidateJudgeTenure:
    """Tests for temporal judge validation."""

    def test_valid_judge_in_tenure(self):
        valid = _validate_judge_tenure(["P. Sathasivam"], 2010)
        assert valid == ["P. Sathasivam"]

    def test_judge_before_appointment(self):
        valid = _validate_judge_tenure(["P. Sathasivam"], 1978)
        assert valid == []

    def test_judge_after_retirement(self):
        valid = _validate_judge_tenure(["P. Sathasivam"], 2020)
        assert valid == []

    def test_unknown_judge_passes(self):
        valid = _validate_judge_tenure(["Unknown Judge Name"], 2000)
        assert valid == ["Unknown Judge Name"]

    def test_mixed_valid_and_invalid(self):
        valid = _validate_judge_tenure(
            ["V.R. Krishna Iyer", "P. Sathasivam"], 1978,
        )
        assert "V.R. Krishna Iyer" in valid
        assert "P. Sathasivam" not in valid

    def test_no_year_skips_validation(self):
        valid = _validate_judge_tenure(["P. Sathasivam"], None)
        assert valid == ["P. Sathasivam"]

    def test_empty_list(self):
        valid = _validate_judge_tenure([], 2000)
        assert valid == []
