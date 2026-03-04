"""Prompt templates for LLM-based legal document processing."""

from typing import Final

# ---------------------------------------------------------------------------
# Metadata extraction from Indian court judgments
# ---------------------------------------------------------------------------

METADATA_EXTRACTION_SYSTEM: Final[str] = """\
You are an expert Indian legal research assistant specializing in metadata \
extraction from court judgments. You extract structured metadata from judgment \
text with high accuracy. You never hallucinate or fabricate information that \
is not present in the source text.

Rules:
- Extract ONLY information explicitly stated in the judgment text.
- If a field cannot be determined from the text, return null for that field.
- For dates, use ISO 8601 format (YYYY-MM-DD).
- For citations, preserve the exact citation format used in the judgment.
- For judge names, use the format as it appears in the judgment (e.g., "Hon'ble Mr. Justice X").
- For acts cited, include section numbers where mentioned (e.g., "Section 302 of IPC").
- For cases cited, include the full citation as referenced in the judgment.
- The ratio_decidendi should be a concise 1-3 sentence summary of the core legal principle.
- bench_type should be one of: single, division, full, constitutional.
- jurisdiction should be one of: civil, criminal, constitutional, tax, labor, company, other.
- disposal_nature should be one of: Allowed, Dismissed, Partly Allowed, Withdrawn, Remanded, Other.
"""

METADATA_EXTRACTION_USER: Final[str] = """\
Extract structured metadata from the following Indian court judgment text. \
Return a JSON object with the following fields:

- title: Case title (e.g., "State of Maharashtra v. Xyz")
- citation: Official citation if present (e.g., "(2023) 5 SCC 123" or "AIR 2023 SC 456")
- court: Name of the court
- judge: List of judge names on the bench
- author_judge: Name of the judge who authored the judgment
- year: Year of the judgment (integer)
- decision_date: Date of the judgment in ISO format (YYYY-MM-DD)
- case_type: Type of case (e.g., "Civil Appeal", "Criminal Appeal", "Writ Petition")
- bench_type: Type of bench (single, division, full, constitutional)
- jurisdiction: Area of law (civil, criminal, constitutional, tax, labor, company, other)
- petitioner: Name of the petitioner/appellant
- respondent: Name of the respondent
- ratio_decidendi: Core legal principle decided (1-3 sentences)
- acts_cited: List of statutes/acts cited in the judgment
- cases_cited: List of case citations referenced in the judgment
- keywords: List of 5-10 relevant legal keywords/topics
- disposal_nature: How the case was disposed (Allowed, Dismissed, Partly Allowed, Withdrawn, Remanded, Other)

Judgment text:
{judgment_text}
"""

# ---------------------------------------------------------------------------
# JSON schema for structured output (used with LLM generate_structured)
# ---------------------------------------------------------------------------

METADATA_OUTPUT_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "title": {"type": ["string", "null"]},
        "citation": {"type": ["string", "null"]},
        "court": {"type": ["string", "null"]},
        "judge": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "author_judge": {"type": ["string", "null"]},
        "year": {"type": ["integer", "null"]},
        "decision_date": {"type": ["string", "null"]},
        "case_type": {"type": ["string", "null"]},
        "bench_type": {
            "type": ["string", "null"],
            "enum": ["single", "division", "full", "constitutional", None],
        },
        "jurisdiction": {
            "type": ["string", "null"],
            "enum": [
                "civil", "criminal", "constitutional",
                "tax", "labor", "company", "other", None,
            ],
        },
        "petitioner": {"type": ["string", "null"]},
        "respondent": {"type": ["string", "null"]},
        "ratio_decidendi": {"type": ["string", "null"]},
        "acts_cited": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "cases_cited": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "keywords": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "disposal_nature": {
            "type": ["string", "null"],
            "enum": [
                "Allowed", "Dismissed", "Partly Allowed",
                "Withdrawn", "Remanded", "Other", None,
            ],
        },
    },
    "required": [
        "title", "citation", "court", "judge", "author_judge", "year",
        "decision_date", "case_type", "bench_type", "jurisdiction",
        "petitioner", "respondent", "ratio_decidendi", "acts_cited",
        "cases_cited", "keywords", "disposal_nature",
    ],
}
