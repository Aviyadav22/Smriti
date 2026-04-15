"""Tests for CaseMetadata V2 fields."""
from app.core.ingestion.metadata import CaseMetadata


class TestCaseMetadataV2Fields:
    """Verify new fields exist and have correct defaults."""

    def test_new_fields_have_none_defaults(self):
        meta = CaseMetadata()
        assert meta.arguments_raised is None
        assert meta.relief_granted is None
        assert meta.relief_sought is None
        assert meta.sentence_details is None
        assert meta.damages_awarded is None
        assert meta.judicial_tone is None
        assert meta.key_observations is None
        assert meta.hearing_count is None
        assert meta.citation_treatments is None
        assert meta.distinguished_cases is None
        assert meta.overruled_cases is None
        assert meta.legal_principles_applied is None
        assert meta.procedural_history is None
        assert meta.interim_orders is None
        assert meta.filing_date is None
        assert meta.urgency_indicators is None
        assert meta.party_counsel is None
        assert meta.issue_classification is None
        assert meta.fact_pattern_tags is None
        assert meta.operative_order is None
        assert meta.conditions_imposed is None
        assert meta.costs_awarded is None

    def test_enrichment_status_defaults_to_flash_only(self):
        meta = CaseMetadata()
        assert meta.enrichment_status == "flash_only"

    def test_arguments_raised_can_store_structured_data(self):
        meta = CaseMetadata(
            arguments_raised=[
                {
                    "party": "petitioner",
                    "argument_type": "constitutional",
                    "argument_summary": "Violation of Article 21",
                    "statutory_basis": "Article 21",
                    "accepted": True,
                }
            ]
        )
        assert len(meta.arguments_raised) == 1
        assert meta.arguments_raised[0]["accepted"] is True

    def test_citation_treatments_structure(self):
        meta = CaseMetadata(
            citation_treatments=[
                {
                    "cited_case": "AIR 1973 SC 1461",
                    "treatment": "followed",
                    "context": "Applied the basic structure doctrine",
                    "paragraph": 42,
                }
            ]
        )
        assert meta.citation_treatments[0]["treatment"] == "followed"
