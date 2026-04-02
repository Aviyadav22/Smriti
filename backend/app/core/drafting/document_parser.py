"""LLM-powered structural extraction of opposing legal documents.

Parses uploaded PDFs into structured sections (facts, reliefs, legal grounds)
for auto-generating response documents.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Final

from app.core.interfaces import LLMProvider

logger = logging.getLogger(__name__)

# Maps an opposing document type to the appropriate response type
RESPONSE_TYPE_MAP: Final[dict[str, str]] = {
    "plaint": "written_statement",
    "legal_notice": "reply_to_notice",
    "order": "appeal",
    "bail_rejection_order": "bail_application",
    "charge_sheet": "quashing_petition_482",
    "show_cause_notice": "reply_to_notice",
    "demand_notice": "reply_to_notice",
}

_PARSE_SYSTEM_PROMPT = """\
You are an expert Indian legal document analyzer. Given the text of a legal \
document, extract its structure into JSON format.

Return a JSON object with these fields:
- "doc_type": the type of document (one of: "plaint", "legal_notice", "order", \
"bail_rejection_order", "charge_sheet", "show_cause_notice", "demand_notice", "unknown")
- "parties": {"petitioner": "...", "respondent": "..."}
- "court": name of the court
- "case_number": case/suit number if mentioned
- "date": date of the document
- "facts": list of numbered fact paragraphs (strings)
- "reliefs_claimed": list of reliefs/prayers sought
- "legal_provisions": list of statutory provisions cited
- "precedents_cited": list of case citations mentioned
- "key_arguments": list of main legal arguments made

Be precise. Extract only what is explicitly stated in the document. \
Do not infer or fabricate information.
"""


@dataclass
class OpposingDocAnalysis:
    """Structured analysis of an opposing legal document."""
    doc_type: str = "unknown"
    parties: dict = field(default_factory=dict)
    court: str = ""
    case_number: str = ""
    date: str = ""
    facts: list[str] = field(default_factory=list)
    reliefs_claimed: list[str] = field(default_factory=list)
    legal_provisions: list[str] = field(default_factory=list)
    precedents_cited: list[str] = field(default_factory=list)
    key_arguments: list[str] = field(default_factory=list)
    raw_text: str = ""
    suggested_response_type: str = ""


async def parse_opposing_document(
    text: str,
    llm: LLMProvider,
) -> OpposingDocAnalysis:
    """Parse an opposing legal document into structured sections.

    Args:
        text: Extracted text from the opposing document PDF.
        llm: LLM provider for structural extraction.

    Returns:
        OpposingDocAnalysis with extracted structure.
    """
    if not text.strip():
        return OpposingDocAnalysis()

    # Truncate to fit LLM context (keep first 30K + last 10K chars)
    if len(text) > 40000:
        text = text[:30000] + "\n\n[... truncated ...]\n\n" + text[-10000:]

    prompt = f"Analyze the following legal document and extract its structure:\n\n{text}"

    try:
        raw = await llm.generate(
            prompt=prompt,
            system=_PARSE_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=4096,
        )

        # Parse JSON response
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        data = json.loads(cleaned)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to parse opposing document: %s", e)
        return OpposingDocAnalysis(raw_text=text[:5000])

    doc_type = data.get("doc_type", "unknown")
    suggested = RESPONSE_TYPE_MAP.get(doc_type, "")

    return OpposingDocAnalysis(
        doc_type=doc_type,
        parties=data.get("parties", {}),
        court=data.get("court", ""),
        case_number=data.get("case_number", ""),
        date=data.get("date", ""),
        facts=data.get("facts", []),
        reliefs_claimed=data.get("reliefs_claimed", []),
        legal_provisions=data.get("legal_provisions", []),
        precedents_cited=data.get("precedents_cited", []),
        key_arguments=data.get("key_arguments", []),
        raw_text=text[:5000],  # Store first 5K chars for reference
        suggested_response_type=suggested,
    )


def build_response_context(analysis: OpposingDocAnalysis) -> dict:
    """Build additional_context for the drafting agent from parsed analysis.

    This maps the opposing document's structure into fields that the
    drafting templates expect.
    """
    context: dict[str, str] = {}

    # Map parties (swap roles for response)
    if analysis.parties.get("petitioner"):
        context["respondent_details"] = analysis.parties["petitioner"]
    if analysis.parties.get("respondent"):
        context["petitioner_details"] = analysis.parties["respondent"]

    # Court and case info
    if analysis.court:
        context["court_name"] = analysis.court
    if analysis.case_number:
        context["suit_number"] = analysis.case_number
        context["main_case_number"] = analysis.case_number

    # For written statements: plaintiff claims = opposing facts
    if analysis.facts:
        context["plaintiff_claims"] = "\n".join(
            f"{i+1}. {fact}" for i, fact in enumerate(analysis.facts)
        )

    # Opposing reliefs (to address in response)
    if analysis.reliefs_claimed:
        context["opposing_reliefs"] = "\n".join(analysis.reliefs_claimed)

    # Provisions cited by opposing side
    if analysis.legal_provisions:
        context["opposing_provisions"] = ", ".join(analysis.legal_provisions)

    # For appeals: impugned order details
    if analysis.doc_type == "order":
        context["impugned_order_details"] = (
            f"Order dated {analysis.date} in {analysis.case_number} "
            f"by {analysis.court}"
        )
        context["lower_court_name"] = analysis.court

    return context
