"""Canonical legal taxonomy for Indian case law.

Provides a structured taxonomy of 18 legal categories with subtopic tags,
normalization functions to map variant issue-classification tags to canonical
forms, and utility functions for taxonomy lookup and LLM prompt generation.

Usage::

    from app.core.legal.taxonomy import (
        normalize_issue_tags,
        get_category_for_tag,
        get_all_subtopics,
        get_categories,
        get_taxonomy_prompt_text,
    )

    # Normalize variant tags from existing data
    tags = normalize_issue_tags(["criminal.murder", "fundamental_rights.article_21"])
    # → ["criminal_law.murder", "constitutional_law.article_21"]

    # Look up category
    get_category_for_tag("criminal_law.bail")  # → "Criminal Law"
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Canonical Legal Taxonomy
# ---------------------------------------------------------------------------
# 18 categories, each with 4-16 subtopic tags covering the most common
# issues in Indian Supreme Court judgments.
# Structure: {category_display_name: {dot_separated_tag: display_label}}
# ---------------------------------------------------------------------------

LEGAL_TAXONOMY: Final[dict[str, dict[str, str]]] = {
    "Criminal Law": {
        "criminal_law.murder": "Murder",
        "criminal_law.bail": "Bail",
        "criminal_law.anticipatory_bail": "Anticipatory Bail",
        "criminal_law.quashing": "Quashing of FIR / Proceedings",
        "criminal_law.dowry_death": "Dowry Death",
        "criminal_law.cheating": "Cheating & Fraud",
        "criminal_law.kidnapping": "Kidnapping & Abduction",
        "criminal_law.robbery": "Robbery & Dacoity",
        "criminal_law.criminal_conspiracy": "Criminal Conspiracy",
        "criminal_law.narcotics": "Narcotics (NDPS Act)",
        "criminal_law.sexual_offences": "Sexual Offences",
        "criminal_law.cruelty": "Cruelty (Section 498A / BNS 85)",
        "criminal_law.criminal_appeal": "Criminal Appeal",
        "criminal_law.sentencing": "Sentencing & Death Penalty",
        "criminal_law.criminal_contempt": "Criminal Contempt",
        "criminal_law.prevention_of_corruption": "Prevention of Corruption",
    },
    "Constitutional Law": {
        "constitutional_law.article_14": "Article 14 — Equality",
        "constitutional_law.article_19": "Article 19 — Freedoms",
        "constitutional_law.article_21": "Article 21 — Right to Life",
        "constitutional_law.article_32": "Article 32 — Writ Jurisdiction (SC)",
        "constitutional_law.article_136": "Article 136 — Special Leave Petition",
        "constitutional_law.article_142": "Article 142 — Complete Justice",
        "constitutional_law.article_226": "Article 226 — Writ Jurisdiction (HC)",
        "constitutional_law.article_370": "Article 370 — J&K Special Status",
        "constitutional_law.reservation": "Reservation & Affirmative Action",
        "constitutional_law.federalism": "Centre-State Relations & Federalism",
        "constitutional_law.separation_of_powers": "Separation of Powers",
        "constitutional_law.pil": "Public Interest Litigation",
        "constitutional_law.freedom_of_speech": "Freedom of Speech & Expression",
        "constitutional_law.right_to_privacy": "Right to Privacy",
        "constitutional_law.constitutional_validity": "Constitutional Validity of Statutes",
    },
    "Civil Procedure": {
        "civil_procedure.res_judicata": "Res Judicata",
        "civil_procedure.limitation": "Limitation",
        "civil_procedure.injunction": "Injunction",
        "civil_procedure.order_7_rule_11": "Rejection of Plaint (O7 R11)",
        "civil_procedure.order_39": "Temporary Injunction (O39)",
        "civil_procedure.decree_execution": "Execution of Decree",
        "civil_procedure.appeal": "Civil Appeal",
        "civil_procedure.review": "Review & Revision",
        "civil_procedure.specific_performance": "Specific Performance",
        "civil_procedure.suit_valuation": "Suit Valuation & Court Fees",
        "civil_procedure.class_action": "Representative Suit / Class Action",
    },
    "Land & Property": {
        "land_property.land_acquisition": "Land Acquisition",
        "land_property.compensation": "Compensation & Solatium",
        "land_property.partition": "Partition",
        "land_property.tenancy": "Tenancy & Rent Control",
        "land_property.title_dispute": "Title Dispute",
        "land_property.ceiling": "Land Ceiling",
        "land_property.adverse_possession": "Adverse Possession",
        "land_property.transfer_of_property": "Transfer of Property",
        "land_property.registration": "Registration of Documents",
        "land_property.easement": "Easement",
        "land_property.specific_relief": "Specific Relief",
    },
    "Tax Law": {
        "tax_law.income_tax": "Income Tax",
        "tax_law.gst": "Goods & Services Tax (GST)",
        "tax_law.customs": "Customs Duty",
        "tax_law.excise": "Central Excise",
        "tax_law.transfer_pricing": "Transfer Pricing",
        "tax_law.reassessment": "Reassessment & Reopening",
        "tax_law.penalty": "Tax Penalty & Prosecution",
        "tax_law.exemption": "Tax Exemption & Deduction",
        "tax_law.stamp_duty": "Stamp Duty",
    },
    "Labour & Service": {
        "labour_service.recruitment": "Recruitment & Appointment",
        "labour_service.promotion": "Promotion & Seniority",
        "labour_service.disciplinary_proceedings": "Disciplinary Proceedings",
        "labour_service.termination": "Termination & Retrenchment",
        "labour_service.pension": "Pension & Retirement Benefits",
        "labour_service.industrial_dispute": "Industrial Disputes",
        "labour_service.wages": "Wages & Compensation",
        "labour_service.regularisation": "Regularisation & Contractual Labour",
        "labour_service.transfer": "Transfer & Posting",
        "labour_service.compassionate_appointment": "Compassionate Appointment",
    },
    "Arbitration": {
        "arbitration.section_11": "Appointment of Arbitrator (S.11)",
        "arbitration.section_34": "Setting Aside Award (S.34)",
        "arbitration.section_37": "Appeal Against Arbitral Order (S.37)",
        "arbitration.enforcement": "Enforcement of Award",
        "arbitration.international": "International Commercial Arbitration",
        "arbitration.interim_measures": "Interim Measures (S.9 / S.17)",
        "arbitration.public_policy": "Public Policy Exception",
        "arbitration.arbitrability": "Arbitrability of Disputes",
    },
    "Family Law": {
        "family_law.divorce": "Divorce",
        "family_law.maintenance": "Maintenance & Alimony",
        "family_law.custody": "Child Custody & Guardianship",
        "family_law.succession": "Succession & Inheritance",
        "family_law.domestic_violence": "Domestic Violence",
        "family_law.hindu_marriage": "Hindu Marriage Act",
        "family_law.muslim_personal_law": "Muslim Personal Law",
        "family_law.adoption": "Adoption",
        "family_law.restitution": "Restitution of Conjugal Rights",
    },
    "Insolvency": {
        "insolvency.cirp": "Corporate Insolvency (CIRP)",
        "insolvency.resolution_plan": "Resolution Plan",
        "insolvency.liquidation": "Liquidation",
        "insolvency.moratorium": "Moratorium (S.14)",
        "insolvency.operational_creditor": "Operational Creditor Disputes",
        "insolvency.financial_creditor": "Financial Creditor Disputes",
        "insolvency.personal_guarantor": "Personal Guarantor Insolvency",
        "insolvency.avoidance_transactions": "Avoidance Transactions",
    },
    "Company Law": {
        "company_law.oppression_mismanagement": "Oppression & Mismanagement",
        "company_law.winding_up": "Winding Up",
        "company_law.director_liability": "Director Liability",
        "company_law.merger_amalgamation": "Merger & Amalgamation",
        "company_law.shareholder_rights": "Shareholder Rights",
        "company_law.corporate_governance": "Corporate Governance",
        "company_law.sebi": "SEBI Regulations",
    },
    "Contract & Commercial": {
        "contract_commercial.breach": "Breach of Contract",
        "contract_commercial.damages": "Damages & Compensation",
        "contract_commercial.government_contract": "Government Contracts & Tenders",
        "contract_commercial.negotiable_instruments": "Negotiable Instruments (S.138)",
        "contract_commercial.partnership": "Partnership Disputes",
        "contract_commercial.agency": "Agency & Principal-Agent",
        "contract_commercial.indemnity_guarantee": "Indemnity & Guarantee",
        "contract_commercial.banking": "Banking & Financial Services",
    },
    "Environmental Law": {
        "environmental_law.pollution": "Pollution Control",
        "environmental_law.forest_conservation": "Forest Conservation",
        "environmental_law.eia": "Environmental Impact Assessment",
        "environmental_law.wildlife": "Wildlife Protection",
        "environmental_law.mining": "Mining & Quarrying",
        "environmental_law.coastal_regulation": "Coastal Regulation Zone",
        "environmental_law.ngt": "National Green Tribunal",
    },
    "Evidence": {
        "evidence.circumstantial": "Circumstantial Evidence",
        "evidence.dying_declaration": "Dying Declaration",
        "evidence.expert_opinion": "Expert Opinion",
        "evidence.electronic_evidence": "Electronic Evidence",
        "evidence.documentary": "Documentary Evidence",
        "evidence.witness_credibility": "Witness Credibility",
        "evidence.burden_of_proof": "Burden of Proof",
        "evidence.admissibility": "Admissibility",
        "evidence.confession": "Confession & Admission",
    },
    "Motor Accident & Tort": {
        "motor_accident_tort.compensation": "Motor Accident Compensation",
        "motor_accident_tort.negligence": "Negligence",
        "motor_accident_tort.strict_liability": "Strict Liability",
        "motor_accident_tort.medical_negligence": "Medical Negligence",
        "motor_accident_tort.vicarious_liability": "Vicarious Liability",
        "motor_accident_tort.defamation": "Defamation",
    },
    "Consumer Protection": {
        "consumer_protection.deficiency_of_service": "Deficiency of Service",
        "consumer_protection.unfair_trade_practice": "Unfair Trade Practice",
        "consumer_protection.medical": "Medical / Hospital Services",
        "consumer_protection.insurance": "Insurance Disputes",
        "consumer_protection.real_estate": "Real Estate (RERA)",
        "consumer_protection.banking": "Banking & Financial Products",
        "consumer_protection.product_liability": "Product Liability",
    },
    "Administrative Law": {
        "administrative_law.judicial_review": "Judicial Review",
        "administrative_law.natural_justice": "Natural Justice",
        "administrative_law.statutory_interpretation": "Statutory Interpretation",
        "administrative_law.delegated_legislation": "Delegated Legislation",
        "administrative_law.government_policy": "Government Policy Challenge",
        "administrative_law.tribunal": "Tribunal Jurisdiction",
        "administrative_law.legitimate_expectation": "Legitimate Expectation",
        "administrative_law.proportionality": "Proportionality",
    },
    "Election Law": {
        "election_law.disqualification": "Disqualification",
        "election_law.election_petition": "Election Petition",
        "election_law.corrupt_practices": "Corrupt Practices",
        "election_law.delimitation": "Delimitation",
        "election_law.nomination": "Nomination & Candidature",
        "election_law.evm": "EVM & Electoral Process",
    },
    "Regulatory Law": {
        "regulatory_law.telecom": "Telecom Regulation",
        "regulatory_law.electricity": "Electricity & Energy",
        "regulatory_law.competition": "Competition Law (CCI)",
        "regulatory_law.intellectual_property": "Intellectual Property",
        "regulatory_law.real_estate_regulation": "Real Estate Regulation (RERA)",
        "regulatory_law.food_safety": "Food Safety & Standards",
        "regulatory_law.information_technology": "Information Technology Act",
    },
}


# ---------------------------------------------------------------------------
# Normalization Map
# ---------------------------------------------------------------------------
# Maps ~50+ variant tags found in existing data to canonical tags.
# ---------------------------------------------------------------------------

NORMALIZATION_MAP: Final[dict[str, str]] = {
    # Criminal Law variants
    "criminal.murder": "criminal_law.murder",
    "criminal.bail": "criminal_law.bail",
    "criminal.anticipatory_bail": "criminal_law.anticipatory_bail",
    "criminal.quashing": "criminal_law.quashing",
    "criminal.dowry_death": "criminal_law.dowry_death",
    "criminal.narcotics": "criminal_law.narcotics",
    "criminal.sentencing": "criminal_law.sentencing",
    "criminal_procedure.bail": "criminal_law.bail",
    "criminal_procedure.quashing": "criminal_law.quashing",
    "criminal_procedure.anticipatory_bail": "criminal_law.anticipatory_bail",
    "criminal_law.bail.pre_arrest_bail": "criminal_law.anticipatory_bail",
    "criminal_law.bail.default_bail": "criminal_law.bail",
    "criminal_law.bail.regular_bail": "criminal_law.bail",
    # Constitutional Law variants
    "fundamental_rights.article_14": "constitutional_law.article_14",
    "fundamental_rights.article_19": "constitutional_law.article_19",
    "fundamental_rights.article_21": "constitutional_law.article_21",
    "fundamental_rights.article_32": "constitutional_law.article_32",
    "constitutional.article_14": "constitutional_law.article_14",
    "constitutional.article_19": "constitutional_law.article_19",
    "constitutional.article_21": "constitutional_law.article_21",
    "constitutional.article_32": "constitutional_law.article_32",
    "constitutional.article_136": "constitutional_law.article_136",
    "constitutional.article_142": "constitutional_law.article_142",
    "constitutional.article_226": "constitutional_law.article_226",
    "constitutional.article_370": "constitutional_law.article_370",
    "constitutional.pil": "constitutional_law.pil",
    "constitutional.reservation": "constitutional_law.reservation",
    # Service / Labour variants
    "service.appointment": "labour_service.recruitment",
    "service.promotion": "labour_service.promotion",
    "service.termination": "labour_service.termination",
    "service.pension": "labour_service.pension",
    "service.transfer": "labour_service.transfer",
    "service.disciplinary": "labour_service.disciplinary_proceedings",
    "service_law.recruitment": "labour_service.recruitment",
    "service_law.promotion": "labour_service.promotion",
    "service_law.termination": "labour_service.termination",
    "service_law.pension": "labour_service.pension",
    "service_law.disciplinary_proceedings": "labour_service.disciplinary_proceedings",
    "service_law.regularisation": "labour_service.regularisation",
    "service_law.compassionate_appointment": "labour_service.compassionate_appointment",
    "labour.industrial_dispute": "labour_service.industrial_dispute",
    "labour.wages": "labour_service.wages",
    # Land variants
    "land_acquisition.compensation": "land_property.compensation",
    "land_acquisition.lapse_of_proceedings": "land_property.land_acquisition",
    "land_acquisition.land_acquisition": "land_property.land_acquisition",
    "property.partition": "land_property.partition",
    "property.title_dispute": "land_property.title_dispute",
    "property.adverse_possession": "land_property.adverse_possession",
    "property.transfer": "land_property.transfer_of_property",
    # Evidence variants
    "evidence.circumstantial_evidence": "evidence.circumstantial",
    "evidence.dying_declaration_evidence": "evidence.dying_declaration",
    "evidence.electronic": "evidence.electronic_evidence",
    # Administrative / statutory interpretation
    "statutory_interpretation": "administrative_law.statutory_interpretation",
    "judicial_review": "administrative_law.judicial_review",
    "natural_justice": "administrative_law.natural_justice",
    # Election Law variants
    "election.disqualification": "election_law.disqualification",
    "election.election_petition": "election_law.election_petition",
    "election.corrupt_practices": "election_law.corrupt_practices",
    # Consumer protection variants
    "consumer_law.deficiency_of_service": "consumer_protection.deficiency_of_service",
    "consumer_law.unfair_trade_practice": "consumer_protection.unfair_trade_practice",
    "consumer_law.consumer_protection_act.definition_of_consumer": "consumer_protection.deficiency_of_service",
    "insurance_law.indemnity": "consumer_protection.insurance",
    "insurance_law.claim": "consumer_protection.insurance",
    "insurance.claim": "consumer_protection.insurance",
    # Tax variants
    "tax.income_tax": "tax_law.income_tax",
    "tax.gst": "tax_law.gst",
    "tax.customs": "tax_law.customs",
    "tax.excise": "tax_law.excise",
    # Family law variants
    "family.divorce": "family_law.divorce",
    "family.maintenance": "family_law.maintenance",
    "family.custody": "family_law.custody",
    "family.succession": "family_law.succession",
    "family.domestic_violence": "family_law.domestic_violence",
    # Contract variants
    "contract.breach": "contract_commercial.breach",
    "contract.damages": "contract_commercial.damages",
    "contract.government_contract": "contract_commercial.government_contract",
    "commercial.negotiable_instruments": "contract_commercial.negotiable_instruments",
    # Arbitration variants
    "arbitration.appointment": "arbitration.section_11",
    "arbitration.setting_aside": "arbitration.section_34",
    # Insolvency variants
    "insolvency.ibc": "insolvency.cirp",
    "insolvency.corporate_insolvency": "insolvency.cirp",
    # Environmental variants
    "environment.pollution": "environmental_law.pollution",
    "environment.forest": "environmental_law.forest_conservation",
    # Motor accident variants
    "motor_accident.compensation": "motor_accident_tort.compensation",
    "tort.negligence": "motor_accident_tort.negligence",
    "tort.medical_negligence": "motor_accident_tort.medical_negligence",
    "tort.defamation": "motor_accident_tort.defamation",
    # Civil procedure variants
    "civil.limitation": "civil_procedure.limitation",
    "civil.res_judicata": "civil_procedure.res_judicata",
    "civil.injunction": "civil_procedure.injunction",
    "civil.appeal": "civil_procedure.appeal",
    "civil.specific_performance": "civil_procedure.specific_performance",
}


# ---------------------------------------------------------------------------
# Internal lookup dicts (built at module load time)
# ---------------------------------------------------------------------------

_TAG_TO_CATEGORY: dict[str, str] = {}
_TAG_TO_LABEL: dict[str, str] = {}
_CATEGORY_KEY_TO_NAME: dict[str, str] = {}

for _cat_name, _subtopics in LEGAL_TAXONOMY.items():
    # Derive the category key from the first tag's prefix
    # e.g. "criminal_law.murder" → "criminal_law"
    for _tag, _label in _subtopics.items():
        _TAG_TO_CATEGORY[_tag] = _cat_name
        _TAG_TO_LABEL[_tag] = _label
        _prefix = _tag.rsplit(".", 1)[0]
        if _prefix not in _CATEGORY_KEY_TO_NAME:
            _CATEGORY_KEY_TO_NAME[_prefix] = _cat_name

# Clean up module-level loop variables
del _cat_name, _subtopics, _tag, _label, _prefix


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def normalize_issue_tags(tags: list[str] | None) -> list[str]:
    """Map variant tags to canonical forms, preserve unknown, deduplicate.

    Args:
        tags: List of issue-classification tags (may contain variants).
              ``None`` or empty list returns an empty list.

    Returns:
        Deduplicated list of canonical tags, preserving insertion order.
    """
    if not tags:
        return []

    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        canonical = NORMALIZATION_MAP.get(tag, tag)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def get_category_for_tag(tag: str) -> str | None:
    """Return the category display name for a tag.

    Attempts exact match first, then falls back to prefix matching
    (e.g. ``"criminal_law.some_new_topic"`` → ``"Criminal Law"``).

    Args:
        tag: A dot-separated issue tag.

    Returns:
        Category display name, or ``None`` if no match found.
    """
    # Exact match
    if tag in _TAG_TO_CATEGORY:
        return _TAG_TO_CATEGORY[tag]

    # Prefix match
    prefix = tag.rsplit(".", 1)[0] if "." in tag else tag
    return _CATEGORY_KEY_TO_NAME.get(prefix)


def get_all_subtopics(category: str) -> dict[str, str]:
    """Return ``{tag: label}`` for all subtopics in a category.

    Args:
        category: Category display name (e.g. ``"Criminal Law"``).

    Returns:
        Dict of tag → label, or empty dict if category not found.
    """
    return dict(LEGAL_TAXONOMY.get(category, {}))


def get_categories() -> list[str]:
    """Return all category display names in taxonomy order."""
    return list(LEGAL_TAXONOMY.keys())


def get_taxonomy_prompt_text() -> str:
    """Generate the taxonomy formatted for LLM prompt inclusion.

    Returns a multi-line string listing each category and its subtopics,
    suitable for embedding in a system prompt.

    Example output::

        ## Criminal Law
        - criminal_law.murder: Murder
        - criminal_law.bail: Bail
        ...

        ## Constitutional Law
        - constitutional_law.article_14: Article 14 — Equality
        ...
    """
    lines: list[str] = []
    for cat_name, subtopics in LEGAL_TAXONOMY.items():
        lines.append(f"## {cat_name}")
        for tag, label in subtopics.items():
            lines.append(f"- {tag}: {label}")
        lines.append("")  # blank line between categories
    return "\n".join(lines)
