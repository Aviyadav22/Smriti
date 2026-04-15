"""Gold-standard benchmark tests for metadata extraction accuracy.

Compares LLM extraction quality against curated ground truth for
landmark Indian Supreme Court cases. Uses compute_extraction_confidence
to verify confidence scores are reasonable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.ingestion.metadata import (
    CaseMetadata,
    compute_extraction_confidence,
    validate_with_regex,
)

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_gold_standard() -> list[dict]:
    path = _FIXTURES_DIR / "gold_standard_metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))


class TestGoldStandardFixture:
    """Verify the gold standard dataset itself is well-formed."""

    def test_fixture_loads(self):
        data = _load_gold_standard()
        assert len(data) >= 5

    def test_all_required_fields_present(self):
        required = {"title", "citation", "court", "year", "judge", "disposal_nature"}
        for case in _load_gold_standard():
            for field in required:
                assert case.get(field), (
                    f"Gold case {case['id']} missing {field}"
                )


class TestConfidenceOnGoldStandard:
    """Confidence scores on gold-standard metadata should be high."""

    @pytest.mark.parametrize(
        "case_data",
        _load_gold_standard(),
        ids=lambda c: c.get("id", "unknown"),
    )
    def test_gold_case_confidence_above_threshold(self, case_data: dict):
        """Gold standard cases should have confidence >= 0.85."""
        field_names = {f.name for f in CaseMetadata.__dataclass_fields__.values()}
        filtered = {k: v for k, v in case_data.items() if k in field_names}
        meta = CaseMetadata(**filtered)
        confidence = compute_extraction_confidence(meta)
        assert confidence >= 0.85, (
            f"Gold case {case_data['id']} has low confidence {confidence}"
        )


class TestValidationOnGoldStandard:
    """Gold-standard metadata should pass all validation without data loss."""

    @pytest.mark.parametrize(
        "case_data",
        _load_gold_standard(),
        ids=lambda c: c.get("id", "unknown"),
    )
    def test_validation_preserves_gold_data(self, case_data: dict):
        """validate_with_regex should not clear any gold-standard fields."""
        field_names = {f.name for f in CaseMetadata.__dataclass_fields__.values()}
        filtered = {k: v for k, v in case_data.items() if k in field_names}
        meta = CaseMetadata(**filtered)
        validated = validate_with_regex(meta)

        # Core fields should survive validation
        assert validated.title == case_data["title"]
        assert validated.year == case_data["year"]
        assert validated.court is not None
        assert validated.judge is not None and len(validated.judge) > 0
