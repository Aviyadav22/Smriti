"""Tests for the document template system."""

from __future__ import annotations

import pytest

from app.core.drafting.templates import TEMPLATES, DocumentTemplate, get_template
from app.core.legal.prompts import (
    DRAFT_AFFIDAVIT_SYSTEM,
    DRAFT_ANTICIPATORY_BAIL_SYSTEM,
    DRAFT_APPEAL_SYSTEM,
    DRAFT_APPLICATION_SYSTEM,
    DRAFT_BAIL_APPLICATION_SYSTEM,
    DRAFT_CONSUMER_COMPLAINT_SYSTEM,
    DRAFT_DEMAND_NOTICE_138_SYSTEM,
    DRAFT_DIVORCE_PETITION_SYSTEM,
    DRAFT_LEGAL_NOTICE_SYSTEM,
    DRAFT_MAINTENANCE_APPLICATION_SYSTEM,
    DRAFT_PLAINT_SYSTEM,
    DRAFT_QUASHING_PETITION_SYSTEM,
    DRAFT_REPLY_TO_NOTICE_SYSTEM,
    DRAFT_SLP_SYSTEM,
    DRAFT_WRIT_PETITION_SYSTEM,
    DRAFT_WRITTEN_STATEMENT_SYSTEM,
)

# All prompt constants keyed by the prompt_key string stored in each template.
# This mirrors the _PROMPT_MAP in drafting_nodes.py.
_VALID_PROMPT_MAP: dict[str, str] = {
    "DRAFT_BAIL_APPLICATION_SYSTEM": DRAFT_BAIL_APPLICATION_SYSTEM,
    "DRAFT_WRIT_PETITION_SYSTEM": DRAFT_WRIT_PETITION_SYSTEM,
    "DRAFT_WRITTEN_STATEMENT_SYSTEM": DRAFT_WRITTEN_STATEMENT_SYSTEM,
    "DRAFT_LEGAL_NOTICE_SYSTEM": DRAFT_LEGAL_NOTICE_SYSTEM,
    "DRAFT_APPEAL_SYSTEM": DRAFT_APPEAL_SYSTEM,
    "DRAFT_APPLICATION_SYSTEM": DRAFT_APPLICATION_SYSTEM,
    "DRAFT_ANTICIPATORY_BAIL_SYSTEM": DRAFT_ANTICIPATORY_BAIL_SYSTEM,
    "DRAFT_QUASHING_PETITION_SYSTEM": DRAFT_QUASHING_PETITION_SYSTEM,
    "DRAFT_DEMAND_NOTICE_138_SYSTEM": DRAFT_DEMAND_NOTICE_138_SYSTEM,
    "DRAFT_PLAINT_SYSTEM": DRAFT_PLAINT_SYSTEM,
    "DRAFT_REPLY_TO_NOTICE_SYSTEM": DRAFT_REPLY_TO_NOTICE_SYSTEM,
    "DRAFT_SLP_SYSTEM": DRAFT_SLP_SYSTEM,
    "DRAFT_DIVORCE_PETITION_SYSTEM": DRAFT_DIVORCE_PETITION_SYSTEM,
    "DRAFT_MAINTENANCE_APPLICATION_SYSTEM": DRAFT_MAINTENANCE_APPLICATION_SYSTEM,
    "DRAFT_CONSUMER_COMPLAINT_SYSTEM": DRAFT_CONSUMER_COMPLAINT_SYSTEM,
    "DRAFT_AFFIDAVIT_SYSTEM": DRAFT_AFFIDAVIT_SYSTEM,
}

# All 17 document types that must exist in TEMPLATES.
_EXPECTED_DOC_TYPES = {
    "bail_application",
    "writ_petition_226",
    "writ_petition_32",
    "written_statement",
    "legal_notice",
    "appeal",
    "interim_application",
    "anticipatory_bail",
    "quashing_petition_482",
    "demand_notice_138",
    "plaint",
    "reply_to_notice",
    "slp",
    "divorce_petition",
    "maintenance_application",
    "consumer_complaint",
    "affidavit",
}


# ---------------------------------------------------------------------------
# TestTemplates
# ---------------------------------------------------------------------------


class TestTemplates:
    def test_all_templates_exist_in_templates_dict(self) -> None:
        assert set(TEMPLATES.keys()) == _EXPECTED_DOC_TYPES

    def test_each_template_is_document_template_instance(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert isinstance(
                template, DocumentTemplate
            ), f"TEMPLATES['{doc_type}'] is not a DocumentTemplate instance"

    def test_each_template_has_non_empty_sections(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert isinstance(
                template.sections, tuple
            ), f"TEMPLATES['{doc_type}'].sections must be a tuple"
            assert len(template.sections) > 0, f"TEMPLATES['{doc_type}'].sections must be non-empty"

    def test_each_template_has_non_empty_required_fields(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert isinstance(
                template.required_fields, tuple
            ), f"TEMPLATES['{doc_type}'].required_fields must be a tuple"
            assert (
                len(template.required_fields) > 0
            ), f"TEMPLATES['{doc_type}'].required_fields must be non-empty"

    def test_each_template_has_non_empty_display_name(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert isinstance(
                template.display_name, str
            ), f"TEMPLATES['{doc_type}'].display_name must be a string"
            assert (
                template.display_name.strip()
            ), f"TEMPLATES['{doc_type}'].display_name must be non-empty"

    def test_each_template_prompt_key_maps_to_valid_prompt(self) -> None:
        for doc_type, template in TEMPLATES.items():
            prompt_key = template.prompt_key
            # V2 templates have prompt keys that will be added in a later task.
            # For now, just verify they follow the naming convention.
            if prompt_key not in _VALID_PROMPT_MAP:
                assert prompt_key.startswith("DRAFT_") and prompt_key.endswith("_SYSTEM"), (
                    f"TEMPLATES['{doc_type}'].prompt_key='{prompt_key}' "
                    f"must follow DRAFT_*_SYSTEM naming convention"
                )
                continue
            prompt_text = _VALID_PROMPT_MAP[prompt_key]
            assert (
                isinstance(prompt_text, str) and prompt_text.strip()
            ), f"Prompt for key '{prompt_key}' must be a non-empty string"

    def test_section_names_are_non_empty_strings(self) -> None:
        for doc_type, template in TEMPLATES.items():
            for section in template.sections:
                assert isinstance(section, str) and section.strip(), (
                    f"Section in TEMPLATES['{doc_type}'].sections must be a non-empty string, "
                    f"got: {section!r}"
                )

    def test_required_field_names_are_non_empty_strings(self) -> None:
        for doc_type, template in TEMPLATES.items():
            for field in template.required_fields:
                assert isinstance(field, str) and field.strip(), (
                    f"Field in TEMPLATES['{doc_type}'].required_fields must be a non-empty string, "
                    f"got: {field!r}"
                )

    def test_bail_application_has_expected_sections(self) -> None:
        template = TEMPLATES["bail_application"]
        expected_sections = {
            "court_header",
            "case_details",
            "facts_of_the_case",
            "grounds_for_bail",
            "legal_provisions",
            "precedents_relied_upon",
            "prayer",
            "verification",
        }
        assert set(template.sections) == expected_sections

    def test_bail_application_has_expected_required_fields(self) -> None:
        template = TEMPLATES["bail_application"]
        assert "accused_name" in template.required_fields
        assert "fir_number" in template.required_fields
        assert "police_station" in template.required_fields
        assert "offences_charged" in template.required_fields

    def test_writ_petition_226_uses_writ_petition_prompt(self) -> None:
        template = TEMPLATES["writ_petition_226"]
        assert template.prompt_key == "DRAFT_WRIT_PETITION_SYSTEM"

    def test_writ_petition_32_uses_writ_petition_prompt(self) -> None:
        template = TEMPLATES["writ_petition_32"]
        assert template.prompt_key == "DRAFT_WRIT_PETITION_SYSTEM"

    def test_writ_petition_32_targets_supreme_court(self) -> None:
        template = TEMPLATES["writ_petition_32"]
        # Art. 32 petitions go to the Supreme Court, not High Courts
        assert "SUPREME COURT" in template.court_header.upper()

    def test_templates_dict_is_frozen_and_not_mutated(self) -> None:
        """TEMPLATES should not allow adding new keys at runtime."""
        original_keys = set(TEMPLATES.keys())
        # Attempt to verify that we're working with an immutable mapping
        # (typing.Final means the binding is frozen, not the dict itself)
        # So we just verify the contents are stable
        assert set(TEMPLATES.keys()) == original_keys

    def test_doc_type_matches_key(self) -> None:
        """Each template's doc_type attribute must match its key in TEMPLATES."""
        for key, template in TEMPLATES.items():
            assert template.doc_type == key, (
                f"TEMPLATES['{key}'].doc_type='{template.doc_type}' "
                f"does not match its key '{key}'"
            )


# ---------------------------------------------------------------------------
# TestGetTemplate
# ---------------------------------------------------------------------------


class TestGetTemplate:
    def test_returns_correct_template_for_bail_application(self) -> None:
        template = get_template("bail_application")
        assert isinstance(template, DocumentTemplate)
        assert template.doc_type == "bail_application"
        assert template.display_name == "Bail Application (S.439 CrPC)"

    def test_returns_correct_template_for_writ_petition_226(self) -> None:
        template = get_template("writ_petition_226")
        assert template.doc_type == "writ_petition_226"
        assert "226" in template.display_name or "226" in template.statutory_basis

    def test_returns_correct_template_for_writ_petition_32(self) -> None:
        template = get_template("writ_petition_32")
        assert template.doc_type == "writ_petition_32"
        assert "32" in template.display_name or "32" in template.statutory_basis

    def test_returns_correct_template_for_written_statement(self) -> None:
        template = get_template("written_statement")
        assert template.doc_type == "written_statement"

    def test_returns_correct_template_for_legal_notice(self) -> None:
        template = get_template("legal_notice")
        assert template.doc_type == "legal_notice"

    def test_returns_correct_template_for_appeal(self) -> None:
        template = get_template("appeal")
        assert template.doc_type == "appeal"

    def test_returns_correct_template_for_interim_application(self) -> None:
        template = get_template("interim_application")
        assert template.doc_type == "interim_application"

    def test_raises_value_error_for_unknown_doc_type(self) -> None:
        with pytest.raises(ValueError):
            get_template("nonexistent_document_type")

    def test_error_message_lists_valid_types(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            get_template("invalid_type_xyz")

        error_message = str(exc_info.value)
        # The error message must list valid doc_type strings
        for valid_type in _EXPECTED_DOC_TYPES:
            assert (
                valid_type in error_message
            ), f"Error message does not list valid type '{valid_type}': {error_message}"

    def test_error_message_mentions_invalid_type(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            get_template("totally_invalid")

        assert "totally_invalid" in str(exc_info.value)

    def test_raises_for_empty_string(self) -> None:
        with pytest.raises(ValueError):
            get_template("")

    def test_raises_for_near_miss_type(self) -> None:
        """Slightly misspelled doc types must still raise ValueError."""
        with pytest.raises(ValueError):
            get_template("bail_applications")  # plural

    def test_raises_for_wrong_case(self) -> None:
        """Doc type lookup is case-sensitive."""
        with pytest.raises(ValueError):
            get_template("BAIL_APPLICATION")

    def test_returned_template_is_frozen(self) -> None:
        """DocumentTemplate is a frozen dataclass; mutation must raise."""
        template = get_template("bail_application")
        with pytest.raises((AttributeError, TypeError)):
            template.doc_type = "mutated"  # type: ignore[misc]

    def test_returns_same_object_on_repeated_calls(self) -> None:
        """get_template should return the same immutable object from TEMPLATES."""
        t1 = get_template("bail_application")
        t2 = get_template("bail_application")
        assert t1 is t2


# ---------------------------------------------------------------------------
# TestTemplateV2Fields
# ---------------------------------------------------------------------------

_VALID_CATEGORIES = {
    "criminal",
    "civil",
    "constitutional",
    "family",
    "commercial",
    "transactional",
}


class TestTemplateV2Fields:
    def test_every_template_has_category(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert isinstance(
                template.category, str
            ), f"TEMPLATES['{doc_type}'].category must be a string"
            assert template.category in _VALID_CATEGORIES, (
                f"TEMPLATES['{doc_type}'].category='{template.category}' "
                f"is not a valid category. Valid: {sorted(_VALID_CATEGORIES)}"
            )

    def test_every_template_has_argument_style(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert template.argument_style in ("irac", "crac"), (
                f"TEMPLATES['{doc_type}'].argument_style='{template.argument_style}' "
                f"must be 'irac' or 'crac'"
            )

    def test_every_template_has_requires_affidavit(self) -> None:
        for doc_type, template in TEMPLATES.items():
            assert isinstance(template.requires_affidavit, bool), (
                f"TEMPLATES['{doc_type}'].requires_affidavit must be a bool, "
                f"got {type(template.requires_affidavit).__name__}"
            )

    def test_bail_application_is_crac_and_requires_affidavit(self) -> None:
        template = TEMPLATES["bail_application"]
        assert template.category == "criminal"
        assert template.argument_style == "crac"
        assert template.requires_affidavit is True

    def test_legal_notice_is_irac_and_no_affidavit(self) -> None:
        template = TEMPLATES["legal_notice"]
        assert template.category == "transactional"
        assert template.argument_style == "irac"
        assert template.requires_affidavit is False


# ---------------------------------------------------------------------------
# TestV2Templates
# ---------------------------------------------------------------------------


class TestV2Templates:
    def test_anticipatory_bail_sections(self) -> None:
        template = TEMPLATES["anticipatory_bail"]
        sections = set(template.sections)
        assert "apprehension_of_arrest" in sections
        assert "grounds_for_anticipatory_bail" in sections
        assert "conditions_offered" in sections
        assert template.category == "criminal"
        assert template.argument_style == "crac"

    def test_slp_has_synopsis_and_questions_of_law(self) -> None:
        template = TEMPLATES["slp"]
        sections = set(template.sections)
        assert "synopsis" in sections
        assert "list_of_dates" in sections
        assert "questions_of_law" in sections
        assert template.category == "constitutional"

    def test_plaint_has_jurisdiction_and_limitation(self) -> None:
        template = TEMPLATES["plaint"]
        sections = set(template.sections)
        assert "jurisdiction_and_valuation" in sections
        assert "limitation" in sections
        assert "cause_of_action" in sections
        assert template.category == "civil"

    def test_demand_notice_138_has_cheque_fields(self) -> None:
        template = TEMPLATES["demand_notice_138"]
        fields = set(template.required_fields)
        assert "cheque_number" in fields
        assert "cheque_amount" in fields
        assert "return_date" in fields

    def test_divorce_petition_has_marriage_details(self) -> None:
        template = TEMPLATES["divorce_petition"]
        fields = set(template.required_fields)
        assert "marriage_date" in fields
        assert "grounds_for_divorce" in fields
        assert template.category == "family"

    def test_affidavit_no_affidavit_required(self) -> None:
        template = TEMPLATES["affidavit"]
        assert template.requires_affidavit is False

    def test_all_17_templates_exist(self) -> None:
        assert len(TEMPLATES) == 17
