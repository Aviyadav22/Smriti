"""Tests for Case model V2 columns."""

import pytest

from app.models.case import Case


class TestCaseModelV2Columns:
    """Verify all 24 new columns exist on the Case model."""

    @pytest.mark.parametrize(
        "col",
        [
            "arguments_raised",
            "relief_granted",
            "relief_sought",
            "sentence_details",
            "damages_awarded",
            "judicial_tone",
            "key_observations",
            "hearing_count",
            "citation_treatments",
            "distinguished_cases",
            "overruled_cases",
            "legal_principles_applied",
            "procedural_history",
            "interim_orders",
            "filing_date",
            "urgency_indicators",
            "party_counsel",
            "issue_classification",
            "fact_pattern_tags",
            "operative_order",
            "conditions_imposed",
            "costs_awarded",
            "page_map",
            "enrichment_status",
        ],
    )
    def test_column_exists(self, col: str):
        assert hasattr(Case, col), f"Case model missing column: {col}"
