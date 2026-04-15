"""Tests for V2 metadata extraction prompts."""
import pytest

from app.core.legal.prompts import (
    METADATA_EXTRACTION_SYSTEM,
    METADATA_EXTRACTION_USER,
    METADATA_OUTPUT_SCHEMA,
)


class TestV2PromptFields:
    """Verify V2 fields are present in extraction prompts."""

    @pytest.mark.parametrize("field", [
        "arguments_raised", "relief_granted", "relief_sought",
        "judicial_tone", "operative_order", "citation_treatments",
        "party_counsel", "legal_principles_applied", "fact_pattern_tags",
        "issue_classification", "procedural_history", "filing_date",
        "sentence_details", "damages_awarded", "key_observations",
        "hearing_count", "distinguished_cases", "overruled_cases",
        "interim_orders", "urgency_indicators", "conditions_imposed",
        "costs_awarded",
    ])
    def test_field_in_schema(self, field: str):
        props = METADATA_OUTPUT_SCHEMA["properties"]
        assert field in props, f"Missing schema property: {field}"

    @pytest.mark.parametrize("field", [
        "arguments_raised", "relief_sought", "relief_granted",
        "sentence_details", "damages_awarded", "judicial_tone",
        "key_observations", "hearing_count", "citation_treatments",
        "distinguished_cases", "overruled_cases", "legal_principles_applied",
        "procedural_history", "interim_orders", "filing_date",
        "urgency_indicators", "party_counsel", "issue_classification",
        "fact_pattern_tags", "operative_order", "conditions_imposed",
        "costs_awarded",
    ])
    def test_field_in_required(self, field: str):
        assert field in METADATA_OUTPUT_SCHEMA["required"], f"Missing from required: {field}"

    def test_system_prompt_mentions_arguments(self):
        assert "ARGUMENTS" in METADATA_EXTRACTION_SYSTEM

    def test_system_prompt_mentions_operative_order(self):
        assert "OPERATIVE ORDER" in METADATA_EXTRACTION_SYSTEM

    def test_system_prompt_mentions_judicial_tone(self):
        assert "JUDICIAL TONE" in METADATA_EXTRACTION_SYSTEM

    def test_system_prompt_mentions_citation_treatments(self):
        assert "CITATION TREATMENTS" in METADATA_EXTRACTION_SYSTEM

    def test_user_prompt_mentions_v2_fields(self):
        assert "arguments_raised" in METADATA_EXTRACTION_USER
        assert "judicial_tone" in METADATA_EXTRACTION_USER
        assert "operative_order" in METADATA_EXTRACTION_USER
        assert "fact_pattern_tags" in METADATA_EXTRACTION_USER

    def test_schema_arguments_raised_is_array(self):
        prop = METADATA_OUTPUT_SCHEMA["properties"]["arguments_raised"]
        assert prop["type"] == "array"

    def test_schema_judicial_tone_has_enum(self):
        prop = METADATA_OUTPUT_SCHEMA["properties"]["judicial_tone"]
        assert "enum" in prop
        assert "neutral" in prop["enum"]
        assert "stern" in prop["enum"]
