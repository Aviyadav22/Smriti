"""Document templates for Indian legal drafting.

Each template defines the structure, required fields, and formatting
metadata for a specific type of legal document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class DocumentTemplate:
    """Immutable template defining the structure of a legal document.

    Attributes:
        doc_type: Machine-readable identifier (e.g. "bail_application").
        display_name: Human-readable name shown in the UI.
        sections: Ordered list of section names that compose the document.
        required_fields: Keys the user must provide in additional_context.
        statutory_basis: The statute or article authorising this document type.
        court_header: Template string for the court name header.
        prompt_key: Key to look up the drafting prompt constant name.
    """

    doc_type: str
    display_name: str
    sections: tuple[str, ...]
    required_fields: tuple[str, ...]
    statutory_basis: str
    court_header: str
    prompt_key: str


TEMPLATES: Final[dict[str, DocumentTemplate]] = {
    "bail_application": DocumentTemplate(
        doc_type="bail_application",
        display_name="Bail Application (S.439 CrPC)",
        sections=(
            "court_header",
            "case_details",
            "facts_of_the_case",
            "grounds_for_bail",
            "legal_provisions",
            "precedents_relied_upon",
            "prayer",
            "verification",
        ),
        required_fields=(
            "accused_name",
            "fir_number",
            "police_station",
            "offences_charged",
        ),
        statutory_basis="Section 439, Code of Criminal Procedure, 1973",
        court_header="IN THE HIGH COURT OF {court}",
        prompt_key="DRAFT_BAIL_APPLICATION_SYSTEM",
    ),
    "writ_petition_226": DocumentTemplate(
        doc_type="writ_petition_226",
        display_name="Writ Petition (Art.226)",
        sections=(
            "court_header",
            "parties",
            "facts",
            "grounds",
            "violation_of_rights",
            "precedents_relied_upon",
            "prayer",
            "verification",
        ),
        required_fields=(
            "petitioner_details",
            "respondent_details",
            "fundamental_right_violated",
        ),
        statutory_basis="Article 226, Constitution of India",
        court_header="IN THE HIGH COURT OF {court}",
        prompt_key="DRAFT_WRIT_PETITION_SYSTEM",
    ),
    "writ_petition_32": DocumentTemplate(
        doc_type="writ_petition_32",
        display_name="Writ Petition (Art.32)",
        sections=(
            "court_header",
            "parties",
            "facts",
            "grounds",
            "violation_of_rights",
            "precedents_relied_upon",
            "prayer",
            "verification",
        ),
        required_fields=(
            "petitioner_details",
            "respondent_details",
            "fundamental_right_violated",
        ),
        statutory_basis="Article 32, Constitution of India",
        court_header="IN THE HON'BLE SUPREME COURT OF INDIA",
        prompt_key="DRAFT_WRIT_PETITION_SYSTEM",
    ),
    "written_statement": DocumentTemplate(
        doc_type="written_statement",
        display_name="Written Statement (Order VIII CPC)",
        sections=(
            "court_header",
            "case_details",
            "preliminary_objections",
            "parawise_reply",
            "additional_facts",
            "legal_grounds",
            "prayer",
        ),
        required_fields=(
            "suit_number",
            "plaintiff_claims",
        ),
        statutory_basis="Order VIII, Code of Civil Procedure, 1908",
        court_header="IN THE COURT OF {court}",
        prompt_key="DRAFT_WRITTEN_STATEMENT_SYSTEM",
    ),
    "legal_notice": DocumentTemplate(
        doc_type="legal_notice",
        display_name="Legal Notice",
        sections=(
            "sender_details",
            "recipient_details",
            "facts",
            "legal_basis",
            "demand",
            "consequences",
            "signature",
        ),
        required_fields=(
            "sender_name",
            "sender_address",
            "recipient_name",
            "recipient_address",
        ),
        statutory_basis="Various",
        court_header="",
        prompt_key="DRAFT_LEGAL_NOTICE_SYSTEM",
    ),
    "appeal": DocumentTemplate(
        doc_type="appeal",
        display_name="Appeal (Civil/Criminal)",
        sections=(
            "court_header",
            "parties",
            "impugned_order",
            "facts",
            "grounds_of_appeal",
            "errors_in_impugned_order",
            "precedents_relied_upon",
            "prayer",
        ),
        required_fields=(
            "impugned_order_details",
            "lower_court_name",
        ),
        statutory_basis="Various",
        court_header="IN THE HIGH COURT OF {court}",
        prompt_key="DRAFT_APPEAL_SYSTEM",
    ),
    "interim_application": DocumentTemplate(
        doc_type="interim_application",
        display_name="Interim Application",
        sections=(
            "court_header",
            "case_details",
            "facts",
            "urgency",
            "grounds_for_relief",
            "legal_provisions",
            "precedents_relied_upon",
            "prayer",
            "verification",
        ),
        required_fields=(
            "main_case_number",
            "relief_sought",
        ),
        statutory_basis="Various",
        court_header="IN THE HIGH COURT OF {court}",
        prompt_key="DRAFT_APPLICATION_SYSTEM",
    ),
}


def get_template(doc_type: str) -> DocumentTemplate:
    """Get a document template by type.

    Args:
        doc_type: The document type identifier.

    Returns:
        The matching DocumentTemplate.

    Raises:
        ValueError: If the document type is not recognised.
    """
    template = TEMPLATES.get(doc_type)
    if template is None:
        valid = ", ".join(sorted(TEMPLATES.keys()))
        raise ValueError(f"Unknown document type '{doc_type}'. Valid types: {valid}")
    return template
