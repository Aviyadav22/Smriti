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
        category: Document category (criminal, civil, constitutional, family, commercial, transactional).
        argument_style: "irac" (factual) or "crac" (advocacy, conclusion-first).
        requires_affidavit: Whether to auto-generate a companion affidavit.
    """

    doc_type: str
    display_name: str
    sections: tuple[str, ...]
    required_fields: tuple[str, ...]
    statutory_basis: str
    court_header: str
    prompt_key: str
    category: str
    argument_style: str
    requires_affidavit: bool


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
        category="criminal",
        argument_style="crac",
        requires_affidavit=True,
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
        category="constitutional",
        argument_style="crac",
        requires_affidavit=True,
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
        category="constitutional",
        argument_style="crac",
        requires_affidavit=True,
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
        category="civil",
        argument_style="irac",
        requires_affidavit=False,
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
        category="transactional",
        argument_style="irac",
        requires_affidavit=False,
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
        category="constitutional",
        argument_style="crac",
        requires_affidavit=True,
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
        category="civil",
        argument_style="crac",
        requires_affidavit=True,
    ),
    "anticipatory_bail": DocumentTemplate(
        doc_type="anticipatory_bail",
        display_name="Anticipatory Bail Application (S.438 CrPC)",
        sections=(
            "court_header", "case_details", "facts_of_the_case",
            "apprehension_of_arrest", "grounds_for_anticipatory_bail",
            "legal_provisions", "precedents_relied_upon",
            "conditions_offered", "prayer", "verification",
        ),
        required_fields=("accused_name", "fir_number", "police_station", "offences_charged", "apprehension_grounds"),
        statutory_basis="Section 438, Code of Criminal Procedure, 1973 / Section 482, BNSS, 2023",
        court_header="IN THE HIGH COURT OF {court}",
        prompt_key="DRAFT_ANTICIPATORY_BAIL_SYSTEM",
        category="criminal",
        argument_style="crac",
        requires_affidavit=True,
    ),
    "quashing_petition_482": DocumentTemplate(
        doc_type="quashing_petition_482",
        display_name="Quashing Petition (S.482 CrPC)",
        sections=(
            "court_header", "parties", "synopsis_and_list_of_dates",
            "facts", "grounds_for_quashing", "legal_provisions",
            "precedents_relied_upon", "prayer", "verification",
        ),
        required_fields=("fir_number", "police_station", "offences_charged", "quashing_grounds"),
        statutory_basis="Section 482, Code of Criminal Procedure, 1973 / Section 528, BNSS, 2023",
        court_header="IN THE HIGH COURT OF {court}",
        prompt_key="DRAFT_QUASHING_PETITION_SYSTEM",
        category="criminal",
        argument_style="crac",
        requires_affidavit=True,
    ),
    "demand_notice_138": DocumentTemplate(
        doc_type="demand_notice_138",
        display_name="Demand Notice (S.138 NI Act)",
        sections=(
            "header", "sender_details", "recipient_details", "reference",
            "transaction_details", "cheque_details", "dishonour_details",
            "demand", "consequences", "dispatch_clause", "signature",
        ),
        required_fields=(
            "drawer_name", "drawer_address", "cheque_number", "cheque_date",
            "cheque_amount", "bank_name", "return_date", "return_reason",
        ),
        statutory_basis="Section 138, Negotiable Instruments Act, 1881",
        court_header="",
        prompt_key="DRAFT_DEMAND_NOTICE_138_SYSTEM",
        category="commercial",
        argument_style="irac",
        requires_affidavit=False,
    ),
    "plaint": DocumentTemplate(
        doc_type="plaint",
        display_name="Plaint (Order VII CPC)",
        sections=(
            "court_header", "parties", "jurisdiction_and_valuation",
            "facts_of_the_case", "cause_of_action", "limitation",
            "legal_grounds", "precedents_relied_upon",
            "documents_relied_upon", "prayer", "verification",
        ),
        required_fields=("plaintiff_details", "defendant_details", "cause_of_action", "relief_sought", "suit_valuation"),
        statutory_basis="Order VII, Code of Civil Procedure, 1908",
        court_header="IN THE COURT OF {court}",
        prompt_key="DRAFT_PLAINT_SYSTEM",
        category="civil",
        argument_style="irac",
        requires_affidavit=False,
    ),
    "reply_to_notice": DocumentTemplate(
        doc_type="reply_to_notice",
        display_name="Reply to Legal Notice",
        sections=(
            "header", "recipient_details", "sender_details", "reference",
            "preliminary_objections", "para_wise_reply", "denial_of_claims",
            "counter_claims", "closing", "signature",
        ),
        required_fields=("original_notice_date", "sender_name", "sender_address", "recipient_name", "recipient_address"),
        statutory_basis="Various",
        court_header="",
        prompt_key="DRAFT_REPLY_TO_NOTICE_SYSTEM",
        category="transactional",
        argument_style="irac",
        requires_affidavit=False,
    ),
    "slp": DocumentTemplate(
        doc_type="slp",
        display_name="Special Leave Petition (Art.136)",
        sections=(
            "synopsis", "list_of_dates", "questions_of_law",
            "court_header", "parties", "impugned_order", "facts",
            "grounds_for_leave", "precedents_relied_upon",
            "prayer", "verification",
        ),
        required_fields=("impugned_order_details", "lower_court_name", "questions_of_law"),
        statutory_basis="Article 136, Constitution of India",
        court_header="IN THE HON'BLE SUPREME COURT OF INDIA",
        prompt_key="DRAFT_SLP_SYSTEM",
        category="constitutional",
        argument_style="crac",
        requires_affidavit=True,
    ),
    "divorce_petition": DocumentTemplate(
        doc_type="divorce_petition",
        display_name="Divorce Petition (S.13 HMA)",
        sections=(
            "court_header", "parties", "marriage_details",
            "facts_of_the_case", "grounds_for_divorce",
            "legal_provisions", "precedents_relied_upon",
            "prayer", "verification",
        ),
        required_fields=("petitioner_details", "respondent_details", "marriage_date", "marriage_place", "grounds_for_divorce"),
        statutory_basis="Section 13, Hindu Marriage Act, 1955",
        court_header="IN THE COURT OF {court}",
        prompt_key="DRAFT_DIVORCE_PETITION_SYSTEM",
        category="family",
        argument_style="crac",
        requires_affidavit=True,
    ),
    "maintenance_application": DocumentTemplate(
        doc_type="maintenance_application",
        display_name="Maintenance Application (S.125 CrPC)",
        sections=(
            "court_header", "parties", "relationship_details",
            "facts_of_the_case", "income_and_means",
            "grounds_for_maintenance", "legal_provisions",
            "precedents_relied_upon", "prayer", "verification",
        ),
        required_fields=("applicant_details", "respondent_details", "relationship", "income_details"),
        statutory_basis="Section 125, Code of Criminal Procedure, 1973 / Section 144, BNSS, 2023",
        court_header="IN THE COURT OF {court}",
        prompt_key="DRAFT_MAINTENANCE_APPLICATION_SYSTEM",
        category="family",
        argument_style="crac",
        requires_affidavit=True,
    ),
    "consumer_complaint": DocumentTemplate(
        doc_type="consumer_complaint",
        display_name="Consumer Complaint (CPA 2019)",
        sections=(
            "court_header", "parties", "facts_of_the_case",
            "deficiency_or_defect", "loss_or_damage",
            "legal_provisions", "precedents_relied_upon",
            "prayer", "verification",
        ),
        required_fields=("complainant_details", "opposite_party_details", "product_or_service", "deficiency_details", "compensation_sought"),
        statutory_basis="Section 35, Consumer Protection Act, 2019",
        court_header="BEFORE THE {court}",
        prompt_key="DRAFT_CONSUMER_COMPLAINT_SYSTEM",
        category="commercial",
        argument_style="irac",
        requires_affidavit=True,
    ),
    "affidavit": DocumentTemplate(
        doc_type="affidavit",
        display_name="General Affidavit",
        sections=(
            "deponent_identification", "oath_clause",
            "statement_of_facts", "verification", "notary_block",
        ),
        required_fields=("deponent_name", "deponent_address", "purpose", "facts_to_state"),
        statutory_basis="Various",
        court_header="",
        prompt_key="DRAFT_AFFIDAVIT_SYSTEM",
        category="transactional",
        argument_style="irac",
        requires_affidavit=False,
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
