"""Drafting Agent node functions for LangGraph.

Each node function takes the DraftingState as its first argument plus
injected dependencies, performs a single focused operation, and returns
a partial state dict for LangGraph to merge.  Dependencies (llm, db, etc.)
are passed via closures when the graph is built.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.nodes.citation_verifier import (
    check_grounding,
    extract_citations_from_text,
    verify_citations_against_db,
)
from app.core.agents.nodes.common import (
    UUID_RE,
    safe_json_parse_list,
    verify_case_ids,
)
from app.core.agents.state import DraftingState
from app.core.drafting.templates import get_template
from app.core.interfaces import LLMProvider
from app.core.legal.prompts import (
    DRAFT_APPEAL_SYSTEM,
    DRAFT_APPLICATION_SYSTEM,
    DRAFT_ASSEMBLE_SYSTEM,
    DRAFT_BAIL_APPLICATION_SYSTEM,
    DRAFT_LEGAL_NOTICE_SYSTEM,
    DRAFT_REVISE_SECTION_SYSTEM,
    DRAFT_VERIFY_PROVISIONS_SYSTEM,
    DRAFT_WRIT_PETITION_SYSTEM,
    DRAFT_WRITTEN_STATEMENT_SYSTEM,
)
from app.security.sanitizer import sanitize_search_query

logger = logging.getLogger(__name__)

MAX_RESULTS_FOR_LLM = 30

# Mapping from template prompt_key strings to the actual prompt constants
_PROMPT_MAP: dict[str, str] = {
    "DRAFT_BAIL_APPLICATION_SYSTEM": DRAFT_BAIL_APPLICATION_SYSTEM,
    "DRAFT_WRIT_PETITION_SYSTEM": DRAFT_WRIT_PETITION_SYSTEM,
    "DRAFT_WRITTEN_STATEMENT_SYSTEM": DRAFT_WRITTEN_STATEMENT_SYSTEM,
    "DRAFT_LEGAL_NOTICE_SYSTEM": DRAFT_LEGAL_NOTICE_SYSTEM,
    "DRAFT_APPEAL_SYSTEM": DRAFT_APPEAL_SYSTEM,
    "DRAFT_APPLICATION_SYSTEM": DRAFT_APPLICATION_SYSTEM,
}


# ---------------------------------------------------------------------------
# Node 1: resolve_template_node
# ---------------------------------------------------------------------------


async def resolve_template_node(state: DraftingState) -> dict:
    """Look up the document template and validate required fields are present."""
    doc_type = state.get("doc_type", "")
    additional_context = state.get("additional_context", {}) or {}

    if not doc_type:
        return {"error": "Missing required field: doc_type"}

    try:
        template = get_template(doc_type)
    except ValueError:
        return {"error": f"Unknown document type: {doc_type}"}

    # Validate that all required_fields are present in additional_context
    missing = [
        field for field in template.required_fields
        if field not in additional_context or not additional_context[field]
    ]
    if missing:
        return {"error": f"Missing required fields: {', '.join(missing)}"}

    return {"template": asdict(template)}


# ---------------------------------------------------------------------------
# Node 2: gather_provisions_node
# ---------------------------------------------------------------------------


async def gather_provisions_node(
    state: DraftingState,
    llm: LLMProvider,
    db: AsyncSession,
) -> dict:
    """Identify relevant statutory provisions from case facts and template basis."""
    template = state.get("template", {})
    case_facts = sanitize_search_query(state.get("case_facts", ""))
    statutory_basis = template.get("statutory_basis", "")

    if not case_facts:
        return {"statutory_provisions": []}

    # Query PostgreSQL for related acts cited in cases with similar statutory basis
    related_acts: list[str] = []
    if statutory_basis:
        try:
            result = await db.execute(
                text(
                    "SELECT DISTINCT unnest(acts_cited) as act "
                    "FROM cases "
                    "WHERE acts_cited && ARRAY[:statutory_basis] "
                    "LIMIT 20"
                ),
                {"statutory_basis": statutory_basis},
            )
            related_acts = [row[0] for row in result.fetchall()]
        except Exception:
            logger.warning(
                "Failed to query related acts for statutory_basis='%s'",
                statutory_basis,
                exc_info=True,
            )

    # Build prompt for LLM to identify all relevant provisions
    related_acts_text = (
        "\n".join(f"- {act}" for act in related_acts) if related_acts
        else "No related acts found in database."
    )

    prompt = (
        "Identify all relevant statutory provisions for drafting a legal document.\n\n"
        f"Document Type: {template.get('display_name', 'Unknown')}\n"
        f"Statutory Basis: {statutory_basis}\n\n"
        f"Case Facts:\n{case_facts}\n\n"
        f"Related Acts from Database:\n{related_acts_text}\n\n"
        "Return a JSON array where each element has:\n"
        '- "act": name of the act/statute\n'
        '- "section": specific section/article number\n'
        '- "description": brief description of relevance\n'
        '- "current": true if the provision is currently in force, false otherwise\n'
    )

    raw = await llm.generate(
        prompt=prompt,
        system=DRAFT_VERIFY_PROVISIONS_SYSTEM,
        temperature=0.1,
    )

    provisions = safe_json_parse_list(raw)

    # Ensure each provision has the expected keys
    validated: list[dict] = []
    for prov in provisions:
        if isinstance(prov, dict):
            validated.append({
                "act": prov.get("act", ""),
                "section": prov.get("section", ""),
                "description": prov.get("description", ""),
                "current": prov.get("current", True),
            })

    return {"statutory_provisions": validated}


# ---------------------------------------------------------------------------
# Node 3: verify_precedents_node
# ---------------------------------------------------------------------------


async def verify_precedents_node(
    state: DraftingState,
    db: AsyncSession,
) -> dict:
    """Verify user-provided precedents against the database."""
    relevant_precedents = state.get("relevant_precedents", []) or []

    if not relevant_precedents:
        return {"verified_precedents": []}

    # Extract citation strings from the precedents
    citation_strings: list[str] = []
    for prec in relevant_precedents:
        if isinstance(prec, dict):
            citation = prec.get("citation", "")
            if citation:
                citation_strings.append(citation)

    # Verify citations against DB
    verified_set: set[str] = set()
    if citation_strings:
        try:
            verified_list, _unverified = await verify_citations_against_db(
                citation_strings, db
            )
            verified_set = set(verified_list)
        except Exception:
            logger.warning(
                "Failed to verify precedent citations against DB",
                exc_info=True,
            )

    # Tag each precedent as verified or unverified
    verified_precedents: list[dict] = []
    for prec in relevant_precedents:
        if not isinstance(prec, dict):
            continue
        citation = prec.get("citation", "")
        entry = {**prec, "verified": citation in verified_set}
        verified_precedents.append(entry)

    return {"verified_precedents": verified_precedents}


# ---------------------------------------------------------------------------
# Node 4: draft_sections_node
# ---------------------------------------------------------------------------


async def draft_sections_node(
    state: DraftingState,
    llm: LLMProvider,
) -> dict:
    """Draft each section of the document individually using the LLM."""
    template = state.get("template", {})
    sections = template.get("sections", [])
    case_facts = sanitize_search_query(state.get("case_facts", ""))
    verified_precedents = state.get("verified_precedents", [])
    statutory_provisions = state.get("statutory_provisions", [])
    additional_context = state.get("additional_context", {}) or {}
    target_court = state.get("target_court", "")

    if not sections:
        return {"section_drafts": {}}

    # Look up the document-type-specific prompt
    prompt_key = template.get("prompt_key", "")
    system_prompt = _PROMPT_MAP.get(prompt_key, "")
    if not system_prompt:
        # Fallback: use a generic instruction
        system_prompt = (
            "You are an expert Indian legal drafter. Draft the requested "
            "section of the legal document with proper legal language, "
            "formatting, and citations."
        )

    # Build shared context for all sections
    precedents_text = json.dumps(
        verified_precedents[:MAX_RESULTS_FOR_LLM], indent=2
    ) if verified_precedents else "None provided."
    provisions_text = json.dumps(
        statutory_provisions[:MAX_RESULTS_FOR_LLM], indent=2
    ) if statutory_provisions else "None identified."
    context_text = json.dumps(additional_context, indent=2)

    section_drafts: dict[str, str] = {}

    for section_name in sections:
        prompt = (
            f"Draft ONLY the '{section_name}' section of a "
            f"{template.get('display_name', 'legal document')}.\n\n"
            f"Case Facts:\n{case_facts}\n\n"
            f"Additional Context:\n{context_text}\n\n"
            f"Target Court: {target_court or 'Not specified'}\n\n"
            f"Statutory Provisions:\n{provisions_text}\n\n"
            f"Precedents (verified status included):\n{precedents_text}\n\n"
            f"Generate ONLY the content for the '{section_name}' section. "
            f"Do not include other sections."
        )

        try:
            draft = await llm.generate(
                prompt=prompt,
                system=system_prompt,
                temperature=0.2,
                max_tokens=4096,
            )
            section_drafts[section_name] = draft.strip()
        except Exception:
            logger.warning(
                "Failed to draft section '%s'", section_name, exc_info=True
            )
            section_drafts[section_name] = f"[Error: Failed to draft section '{section_name}']"

    return {"section_drafts": section_drafts}


# ---------------------------------------------------------------------------
# Node 5: assemble_document_node
# ---------------------------------------------------------------------------


async def assemble_document_node(
    state: DraftingState,
    llm: LLMProvider,
) -> dict:
    """Assemble all section drafts into a coherent full document."""
    template = state.get("template", {})
    section_drafts = state.get("section_drafts", {})
    target_court = state.get("target_court", "")

    if not section_drafts:
        return {"full_draft": ""}

    # Build the court header from the template
    court_header_template = template.get("court_header", "")
    court_header = ""
    if court_header_template and target_court:
        try:
            court_header = court_header_template.format(court=target_court)
        except (KeyError, IndexError):
            court_header = court_header_template

    # Build the raw assembled text with sections in template order
    sections = template.get("sections", [])
    raw_parts: list[str] = []
    for section_name in sections:
        draft = section_drafts.get(section_name, "")
        if draft:
            raw_parts.append(f"## {section_name.upper().replace('_', ' ')}\n\n{draft}")

    raw_assembled = "\n\n---\n\n".join(raw_parts)

    # Use LLM to format with proper numbering and headers
    prompt = (
        "Assemble the following sections into a properly formatted Indian legal document.\n\n"
        f"Document Type: {template.get('display_name', 'Legal Document')}\n"
        f"Court Header: {court_header}\n\n"
        f"Sections:\n\n{raw_assembled}\n\n"
        "Format with proper paragraph numbering, headers, and legal formatting conventions. "
        "Preserve all citations and legal references exactly as written. "
        "Do not add any new substantive content."
    )

    # If language is Hindi, append instruction to write in Devanagari
    assemble_system = DRAFT_ASSEMBLE_SYSTEM
    if state.get("language", "en") == "hi":
        assemble_system += (
            "\n\nIMPORTANT: Write your entire response in Hindi (Devanagari script). "
            "Keep case names, citations, statute names, and section numbers in English."
        )

    try:
        full_draft = await llm.generate(
            prompt=prompt,
            system=assemble_system,
            temperature=0.1,
            max_tokens=8192,
        )
    except Exception:
        logger.warning("Failed to assemble document", exc_info=True)
        # Fall back to the raw assembled text
        return {"full_draft": raw_assembled}

    return {"full_draft": full_draft.strip()}


# ---------------------------------------------------------------------------
# Node 6: revise_section_node
# ---------------------------------------------------------------------------


async def revise_section_node(
    state: DraftingState,
    llm: LLMProvider,
) -> dict:
    """Revise a specific section based on user feedback and reassemble."""
    revision_feedback = state.get("revision_feedback", "")
    section_drafts = state.get("section_drafts", {})
    template = state.get("template", {})

    if not revision_feedback:
        return {"section_drafts": section_drafts, "full_draft": state.get("full_draft", ""), "revision_feedback": ""}

    sanitized_feedback = sanitize_search_query(revision_feedback)

    # Parse which section to revise from the feedback
    # Expected format: "section_name: feedback text" or just feedback text
    target_section = ""
    feedback_text = sanitized_feedback

    # Try to extract section name from feedback
    sections = template.get("sections", [])
    for section_name in sections:
        # Check if feedback starts with or mentions the section name
        lower_feedback = sanitized_feedback.lower()
        lower_section = section_name.lower().replace("_", " ")
        if lower_feedback.startswith(section_name.lower() + ":"):
            target_section = section_name
            feedback_text = sanitized_feedback[len(section_name) + 1:].strip()
            break
        if lower_feedback.startswith(lower_section + ":"):
            target_section = section_name
            feedback_text = sanitized_feedback[len(lower_section) + 1:].strip()
            break
        if section_name.lower() in lower_feedback:
            target_section = section_name
            break

    if not target_section and sections:
        # Default to first section if we cannot determine the target
        target_section = sections[0]
        logger.warning(
            "Could not determine target section from feedback, defaulting to '%s'",
            target_section,
        )

    if not target_section:
        return {"section_drafts": section_drafts, "full_draft": state.get("full_draft", ""), "revision_feedback": ""}

    # Get the current draft of the target section
    current_draft = section_drafts.get(target_section, "")

    # Look up the document-type-specific prompt
    prompt_key = template.get("prompt_key", "")
    base_prompt = _PROMPT_MAP.get(prompt_key, "")

    prompt = (
        f"Revise the '{target_section}' section of a "
        f"{template.get('display_name', 'legal document')}.\n\n"
        f"Current Draft:\n{current_draft}\n\n"
        f"User Feedback:\n{feedback_text}\n\n"
        "Incorporate the feedback and generate an improved version of this section only."
    )

    try:
        revised = await llm.generate(
            prompt=prompt,
            system=DRAFT_REVISE_SECTION_SYSTEM,
            temperature=0.2,
            max_tokens=4096,
        )
        section_drafts = {**section_drafts, target_section: revised.strip()}
    except Exception:
        logger.warning(
            "Failed to revise section '%s'", target_section, exc_info=True
        )
        return {"section_drafts": section_drafts, "full_draft": state.get("full_draft", ""), "revision_feedback": ""}

    # Reassemble the full draft with the revised section
    target_court = state.get("target_court", "")
    court_header_template = template.get("court_header", "")
    court_header = ""
    if court_header_template and target_court:
        try:
            court_header = court_header_template.format(court=target_court)
        except (KeyError, IndexError):
            court_header = court_header_template

    all_sections = template.get("sections", [])
    raw_parts: list[str] = []
    for section_name in all_sections:
        draft = section_drafts.get(section_name, "")
        if draft:
            raw_parts.append(f"## {section_name.upper().replace('_', ' ')}\n\n{draft}")

    raw_assembled = "\n\n---\n\n".join(raw_parts)

    reassemble_prompt = (
        "Assemble the following sections into a properly formatted Indian legal document.\n\n"
        f"Document Type: {template.get('display_name', 'Legal Document')}\n"
        f"Court Header: {court_header}\n\n"
        f"Sections:\n\n{raw_assembled}\n\n"
        "Format with proper paragraph numbering, headers, and legal formatting conventions. "
        "Preserve all citations and legal references exactly as written. "
        "Do not add any new substantive content."
    )

    try:
        full_draft = await llm.generate(
            prompt=reassemble_prompt,
            system=DRAFT_ASSEMBLE_SYSTEM,
            temperature=0.1,
            max_tokens=8192,
        )
    except Exception:
        logger.warning("Failed to reassemble document after revision", exc_info=True)
        full_draft = state.get("full_draft", "")

    return {
        "section_drafts": section_drafts,
        "full_draft": full_draft.strip() if isinstance(full_draft, str) else full_draft,
        "revision_feedback": "",
    }


# ---------------------------------------------------------------------------
# Node 7: verify_final_node
# ---------------------------------------------------------------------------


async def verify_final_node(
    state: DraftingState,
    db: AsyncSession,
) -> dict:
    """Verify citations in the full draft using 3-layer verification.

    Performs the same three-layer verification as research_nodes and strategy_nodes:
    1. UUID-based verification -- checks case IDs against the DB.
    2. Human-readable citation verification -- checks SCC/AIR/etc. citations
       against ``cases.citation`` and ``case_citation_equivalents.citation_text``.
    3. Grounding check -- flags citations in the draft that were NOT in the
       verified precedents (potentially hallucinated from LLM training data).
    """
    full_draft = state.get("full_draft", "")
    if not full_draft:
        return {"full_draft": full_draft}

    # --- Step 1: UUID verification ---
    found_ids = list(set(UUID_RE.findall(full_draft)))
    if found_ids:
        try:
            valid_ids = await verify_case_ids(found_ids, db)
            invalid_ids = [uid for uid in found_ids if uid not in valid_ids]

            if invalid_ids:
                warning = (
                    "\n\n---\n"
                    "**Citation Verification Warning**\n"
                    "The following case identifiers referenced in this document could not "
                    "be verified against the database:\n"
                )
                for uid in invalid_ids:
                    warning += f"- {uid}\n"
                warning += (
                    "These references may be hallucinated or refer to cases not yet "
                    "ingested. Please verify independently.\n"
                )
                full_draft += warning
        except Exception:
            logger.warning("UUID verification failed", exc_info=True)

    # --- Step 2: Human-readable citation verification ---
    draft_citations = extract_citations_from_text(full_draft)
    if draft_citations:
        try:
            _verified, unverified = await verify_citations_against_db(
                draft_citations, db
            )

            if unverified:
                warning = (
                    "\n\n---\n"
                    "**Human-Readable Citation Warning**\n"
                    "The following citations could not be verified against the database:\n"
                )
                for cite in unverified:
                    warning += f"- {cite}\n"
                warning += (
                    "These may be fabricated citations. Please verify independently "
                    "before relying on them.\n"
                )
                full_draft += warning
        except Exception:
            logger.warning(
                "Human-readable citation verification failed", exc_info=True
            )

    # --- Step 3: Grounding check ---
    if draft_citations:
        # Build grounding set from verified_precedents
        verified_precedents = state.get("verified_precedents", [])
        grounding_citation_strings: list[str] = []
        for prec in verified_precedents:
            if isinstance(prec, dict):
                citation = prec.get("citation", "")
                if citation:
                    grounding_citation_strings.append(citation)

        # Also extract citations from precedent text fields
        for prec in verified_precedents:
            if isinstance(prec, dict):
                for field in ("snippet", "ratio", "text"):
                    text_val = prec.get(field, "")
                    if text_val:
                        grounding_citation_strings.extend(
                            extract_citations_from_text(text_val)
                        )

        ungrounded = check_grounding(draft_citations, grounding_citation_strings)
        if ungrounded:
            warning = (
                "\n\n---\n"
                "**Ungrounded Citation Warning**\n"
                "The following citations appear in the document but were NOT found "
                "in the provided precedents. They may have been hallucinated from "
                "the LLM's training data:\n"
            )
            for cite in ungrounded:
                warning += f"- {cite}\n"
            warning += (
                "Exercise extra caution with these citations and verify them "
                "against primary sources.\n"
            )
            full_draft += warning

    return {"full_draft": full_draft}
