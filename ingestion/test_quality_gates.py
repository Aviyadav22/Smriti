"""Tests for quality_gates.validate_batch_metadata — ratio_decidendi uniqueness."""

from __future__ import annotations

import pytest

from quality_gates import validate_batch_metadata


class TestRatioUniqueness:
    def test_detects_duplicate_ratios(self):
        """Flag when too many cases share identical ratio_decidendi."""
        # 20 cases with only 3 unique ratios = should FAIL
        metadata = {}
        for i in range(20):
            metadata[f"case_{i}"] = {
                "title": f"Case Title {i}",
                "citation": f"2025 INSC {i}",
                "year": 2025,
                "court": "Supreme Court of India",
                "judge": f"Justice {i}",
                "ratio_decidendi": f"Ratio text {i % 3}",
            }
        result = validate_batch_metadata(metadata)
        assert not result.passed
        assert any("ratio" in f.lower() for f in result.failures)

    def test_accepts_unique_ratios(self):
        """All unique ratios should not trigger the check."""
        metadata = {}
        for i in range(20):
            metadata[f"case_{i}"] = {
                "title": f"Case Title {i}",
                "citation": f"2025 INSC {i}",
                "year": 2025,
                "court": "Supreme Court of India",
                "judge": f"Justice {i}",
                "ratio_decidendi": f"Unique ratio for case {i}",
            }
        result = validate_batch_metadata(metadata)
        assert not any("ratio" in f.lower() for f in result.failures)

    def test_skips_check_when_few_cases(self):
        """With <=10 cases, ratio uniqueness check should not trigger."""
        metadata = {}
        for i in range(8):
            metadata[f"case_{i}"] = {
                "title": f"Case Title {i}",
                "citation": f"2025 INSC {i}",
                "year": 2025,
                "court": "Supreme Court of India",
                "judge": f"Justice {i}",
                "ratio_decidendi": "Same ratio for all",
            }
        result = validate_batch_metadata(metadata)
        assert not any("ratio" in f.lower() for f in result.failures)

    def test_skips_check_when_no_ratios(self):
        """Cases without ratio_decidendi should not cause errors."""
        metadata = {}
        for i in range(20):
            metadata[f"case_{i}"] = {
                "title": f"Case Title {i}",
                "citation": f"2025 INSC {i}",
                "year": 2025,
                "court": "Supreme Court of India",
                "judge": f"Justice {i}",
            }
        result = validate_batch_metadata(metadata)
        assert not any("ratio" in f.lower() for f in result.failures)

    def test_borderline_passes_at_80_percent(self):
        """Exactly 80% unique ratios should pass (not less than)."""
        metadata = {}
        # 20 cases: 16 unique + 4 duplicates of the first = 16/20 = 80%
        for i in range(16):
            metadata[f"case_{i}"] = {
                "title": f"Case Title {i}",
                "citation": f"2025 INSC {i}",
                "year": 2025,
                "court": "Supreme Court of India",
                "judge": f"Justice {i}",
                "ratio_decidendi": f"Unique ratio {i}",
            }
        for i in range(16, 20):
            metadata[f"case_{i}"] = {
                "title": f"Case Title {i}",
                "citation": f"2025 INSC {i}",
                "year": 2025,
                "court": "Supreme Court of India",
                "judge": f"Justice {i}",
                "ratio_decidendi": "Unique ratio 0",  # duplicate of case_0
            }
        result = validate_batch_metadata(metadata)
        # 16 unique out of 20 = 80%, threshold is < 80%, so should pass
        assert not any("ratio" in f.lower() for f in result.failures)
