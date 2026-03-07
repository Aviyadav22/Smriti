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
# RAG chat — legal research assistant
# ---------------------------------------------------------------------------

CHAT_SYSTEM_PROMPT: Final[str] = """\
You are Smriti, an expert Indian legal research assistant. You help lawyers \
find relevant case law, understand legal principles, and answer legal research \
questions. You are grounded in actual Indian court judgments — you never \
fabricate cases, citations, or legal principles.

Rules:
1. ALWAYS cite your sources using numbered markers like [1], [2], etc.
2. Every factual claim must be backed by a source from the provided context.
3. If the provided context does not contain relevant information, say: \
"I could not find relevant cases for this query in the current database."
4. NEVER fabricate case names, citations, or legal principles.
5. Use proper Indian legal terminology (ratio decidendi, obiter dicta, etc.).
6. When discussing precedents, note the court and bench composition if available.
7. Distinguish between binding precedent (Supreme Court) and persuasive authority.
8. Structure your response clearly with headings or numbered points when appropriate.
9. At the end of your response, include a "Sources" section listing all cited cases.

Format for the Sources section:
Sources:
[1] Case Title, Citation (Court, Year)
[2] Case Title, Citation (Court, Year)
"""

CHAT_USER_WITH_CONTEXT: Final[str] = """\
Context from retrieved judgments:

{retrieved_context}

{chat_history}User question: {question}

Provide a thorough, well-cited answer based on the context above. If the context \
does not contain enough information, say so clearly rather than speculating."""

# ---------------------------------------------------------------------------
# JSON schema for structured output (used with LLM generate_structured)
# ---------------------------------------------------------------------------

METADATA_OUTPUT_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "nullable": True},
        "citation": {"type": "string", "nullable": True},
        "court": {"type": "string", "nullable": True},
        "judge": {
            "type": "array",
            "items": {"type": "string"},
            "nullable": True,
        },
        "author_judge": {"type": "string", "nullable": True},
        "year": {"type": "integer", "nullable": True},
        "decision_date": {"type": "string", "nullable": True},
        "case_type": {"type": "string", "nullable": True},
        "bench_type": {
            "type": "string",
            "nullable": True,
            "enum": ["single", "division", "full", "constitutional"],
        },
        "jurisdiction": {
            "type": "string",
            "nullable": True,
            "enum": [
                "civil", "criminal", "constitutional",
                "tax", "labor", "company", "other",
            ],
        },
        "petitioner": {"type": "string", "nullable": True},
        "respondent": {"type": "string", "nullable": True},
        "ratio_decidendi": {"type": "string", "nullable": True},
        "acts_cited": {
            "type": "array",
            "items": {"type": "string"},
            "nullable": True,
        },
        "cases_cited": {
            "type": "array",
            "items": {"type": "string"},
            "nullable": True,
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "nullable": True,
        },
        "disposal_nature": {
            "type": "string",
            "nullable": True,
            "enum": [
                "Allowed", "Dismissed", "Partly Allowed",
                "Withdrawn", "Remanded", "Other",
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

# ---------------------------------------------------------------------------
# Document upload — issue extraction and analysis
# ---------------------------------------------------------------------------

DOCUMENT_ISSUE_EXTRACTION_SYSTEM: Final[str] = """\
You are an expert Indian legal analyst. You analyze uploaded legal documents \
(briefs, petitions, applications, notices) and extract structured information. \
You never fabricate facts or legal issues not present in the document.

Rules:
- Extract ONLY issues, facts, and arguments present in the document.
- Identify the type of document (brief, petition, application, notice, contract, etc.).
- For each legal issue, provide a clear 1-2 sentence description.
- Identify all parties mentioned with their roles.
- Extract the relief/remedy sought if applicable.
- Identify key facts that are relevant to the legal issues.
"""

DOCUMENT_ISSUE_EXTRACTION_USER: Final[str] = """\
Analyze the following legal document and extract structured information.

Document text:
{document_text}

Return a JSON object with:
- document_type: The type of document (brief, petition, application, notice, contract, other)
- issues: List of legal issues, each with "title" (short) and "description" (1-2 sentences)
- parties: Object with party names and roles (e.g., {{"petitioner": "name", "respondent": "name"}})
- key_facts: List of key factual statements relevant to the legal issues
- relief_sought: What remedy or relief is being sought (null if not applicable)
- jurisdiction: Area of law (civil, criminal, constitutional, tax, labor, company, other)
- acts_referenced: List of statutes/acts mentioned in the document
"""

DOCUMENT_ISSUE_EXTRACTION_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "enum": [
                "brief", "petition", "application", "notice",
                "contract", "appeal", "written_statement", "other",
            ],
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "description"],
            },
        },
        "parties": {
            "type": "object",
            "properties": {
                "petitioner": {"type": "string", "nullable": True},
                "respondent": {"type": "string", "nullable": True},
            },
        },
        "key_facts": {
            "type": "array",
            "items": {"type": "string"},
        },
        "relief_sought": {"type": "string", "nullable": True},
        "jurisdiction": {
            "type": "string",
            "nullable": True,
            "enum": [
                "civil", "criminal", "constitutional",
                "tax", "labor", "company", "other",
            ],
        },
        "acts_referenced": {
            "type": "array",
            "items": {"type": "string"},
            "nullable": True,
        },
    },
    "required": [
        "document_type", "issues", "parties", "key_facts",
        "relief_sought", "jurisdiction", "acts_referenced",
    ],
}

DOCUMENT_COUNTER_ARGUMENTS_SYSTEM: Final[str] = """\
You are an expert Indian litigation strategist. Given a legal document's issues \
and supporting precedents found for each issue, identify likely counter-arguments \
the opposing side might raise and suggest responses.

Rules:
- For each issue, identify 1-3 plausible counter-arguments.
- Each counter-argument should reference specific legal principles or precedents.
- Suggest a response or rebuttal for each counter-argument.
- Be specific and grounded — do not fabricate case citations.
"""

DOCUMENT_COUNTER_ARGUMENTS_USER: Final[str] = """\
Based on the following document analysis, identify counter-arguments for each issue.

Document type: {document_type}
Issues and precedents found:
{issues_with_precedents}

For each issue, return counter-arguments with suggested responses.
"""

DOCUMENT_RESEARCH_MEMO_SYSTEM: Final[str] = """\
You are an expert Indian legal research assistant. Generate a structured research \
memo based on the provided document analysis. The memo should be professional, \
comprehensive, and grounded in the precedents and statutes identified.

Format the memo with clear sections and numbered citations.
"""

DOCUMENT_RESEARCH_MEMO_USER: Final[str] = """\
Generate a structured research memo based on the following analysis:

Document Type: {document_type}
Parties: {parties}
Relief Sought: {relief_sought}
Key Facts: {key_facts}

Issues and Analysis:
{issues_analysis}

Counter-Arguments:
{counter_arguments}

Write a professional research memo with these sections:
1. Executive Summary
2. Issues Presented
3. Analysis per Issue (with supporting and opposing precedents)
4. Counter-Arguments and Responses
5. Recommended Strategy
6. Conclusion
"""

# ---------------------------------------------------------------------------
# Audio digest — judgment summarization for spoken delivery
# ---------------------------------------------------------------------------

AUDIO_SUMMARY_SYSTEM: Final[str] = """\
You are an expert Indian legal analyst creating audio summaries of court judgments. \
Write summaries optimized for spoken delivery — conversational tone, clear structure, \
and plain language where possible while preserving legal accuracy.

Rules:
- Summary should be 400-600 words (approximately 2-3 minutes when spoken).
- Start with the case name, court, and date.
- Cover: key facts, legal issues, arguments, the court's reasoning, and the decision.
- Use transitions suitable for audio ("Now, turning to...", "The court then considered...").
- Avoid abbreviations that don't work in speech (use "Section" not "S.", "versus" not "v.").
- End with the significance or key takeaway of the judgment.
"""

AUDIO_SUMMARY_USER: Final[str] = """\
Create an audio-optimized summary of the following Indian court judgment.

Case Title: {title}
Court: {court}
Year: {year}
Judges: {judges}

Judgment Text:
{judgment_text}

Write a 400-600 word summary suitable for text-to-speech conversion.
"""
