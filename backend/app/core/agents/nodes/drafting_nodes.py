"""Drafting Agent node functions for LangGraph.

Each node function takes the DraftingState as its first argument plus
injected dependencies, performs a single focused operation, and returns
a partial state dict for LangGraph to merge.  Dependencies (llm, db, etc.)
are passed via closures when the graph is built.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.nodes.citation_verifier import verify_citations_against_db
from app.core.agents.nodes.common import (
    apply_language_suffix,
    check_citation_density,
    collect_grounding_citations,
    get_latest_feedback,
    safe_json_parse_list,
    verify_memo_citations,
)
from app.core.agents.state import DraftingState
from app.core.drafting.court_profiles import get_court_profile
from app.core.drafting.templates import get_template
from app.core.interfaces import LLMProvider
from app.core.legal.prompts import (
    DRAFT_AFFIDAVIT_COMPANION_SYSTEM,
    DRAFT_AFFIDAVIT_SYSTEM,
    DRAFT_ANTICIPATORY_BAIL_SYSTEM,
    DRAFT_APPEAL_SYSTEM,
    DRAFT_APPLICATION_SYSTEM,
    DRAFT_ASSEMBLE_SYSTEM,
    DRAFT_BAIL_APPLICATION_SYSTEM,
    DRAFT_CONSUMER_COMPLAINT_SYSTEM,
    DRAFT_DEMAND_NOTICE_138_SYSTEM,
    DRAFT_DIVORCE_PETITION_SYSTEM,
    DRAFT_LEGAL_NOTICE_SYSTEM,
    DRAFT_MAINTENANCE_APPLICATION_SYSTEM,
    DRAFT_PLAINT_SYSTEM,
    DRAFT_QUASHING_PETITION_SYSTEM,
    DRAFT_REPLY_TO_NOTICE_SYSTEM,
    DRAFT_REVISE_SECTION_SYSTEM,
    DRAFT_SLP_SYSTEM,
    DRAFT_VERIFY_PROVISIONS_SYSTEM,
    DRAFT_WRIT_PETITION_SYSTEM,
    DRAFT_WRITTEN_STATEMENT_SYSTEM,
    LEGAL_DISCLAIMER,
)
from app.security.sanitizer import sanitize_search_query

logger = logging.getLogger(__name__)

MAX_RESULTS_FOR_LLM = 30


# ---------------------------------------------------------------------------
# Node 0: parse_opposing_document_node (V3)
# ---------------------------------------------------------------------------


async def parse_opposing_document_node(
    state: DraftingState,
    llm: LLMProvider,
) -> dict:
    """Parse an uploaded opposing document into structured sections.

    Only runs when opposing_document_text is present in state.
    """
    text = state.get("opposing_document_text", "")
    if not text:
        return {}

    from app.core.drafting.document_parser import (
        build_response_context,
        parse_opposing_document,
    )

    analysis = await parse_opposing_document(text, llm)

    # Build context for the response document
    response_context = build_response_context(analysis)

    # Merge with any user-provided additional_context (user overrides)
    existing_context = state.get("additional_context", {}) or {}
    merged_context = {**response_context, **existing_context}

    result: dict = {
        "opposing_document_analysis": {
            "doc_type": analysis.doc_type,
            "parties": analysis.parties,
            "court": analysis.court,
            "case_number": analysis.case_number,
            "facts": analysis.facts,
            "reliefs_claimed": analysis.reliefs_claimed,
            "legal_provisions": analysis.legal_provisions,
            "precedents_cited": analysis.precedents_cited,
            "key_arguments": analysis.key_arguments,
            "suggested_response_type": analysis.suggested_response_type,
        },
        "additional_context": merged_context,
    }

    # Auto-set doc_type if not already set and we have a suggestion
    if not state.get("doc_type") and analysis.suggested_response_type:
        result["doc_type"] = analysis.suggested_response_type

    # Auto-set target_court from opposing doc
    if not state.get("target_court") and analysis.court:
        result["target_court"] = analysis.court

    # Convert opposing precedents to relevant_precedents format
    if analysis.precedents_cited and not state.get("relevant_precedents"):
        result["relevant_precedents"] = [
            {"citation": cite, "title": cite} for cite in analysis.precedents_cited[:10]
        ]

    return result

# Mapping from template prompt_key strings to the actual prompt constants
_PROMPT_MAP: dict[str, str] = {
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _determine_primary_code(case_facts: str, additional_context: dict) -> str:
    """Return 'old' or 'new' based on FIR/filing date vs July 1 2024 cutoff."""
    from datetime import date, datetime

    cutoff = date(2024, 7, 1)
    for key in ("fir_date", "filing_date", "offence_date"):
        raw = additional_context.get(key, "")
        if not raw:
            continue
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
            try:
                parsed = datetime.strptime(raw, fmt).date()
                if parsed < cutoff:
                    return "old"
                return "new"
            except ValueError:
                continue
    return "new"


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

    court_profile = get_court_profile(state.get("target_court", ""))
    primary_code = _determine_primary_code(
        state.get("case_facts", ""),
        state.get("additional_context", {}) or {},
    )
    # V3: Judge-aware context
    judge_context: dict = {}
    bench = state.get("bench_composition", []) or []
    if bench:
        try:
            from app.core.analytics.judge_analytics import JudgeAnalyticsService
            from app.db.postgres import async_session_factory
            async with async_session_factory() as judge_db:
                svc = JudgeAnalyticsService(judge_db)
                profiles = []
                for judge_name in bench[:3]:  # Limit to 3 judges
                    profile = await svc.get_judge_profile(judge_name)
                    if profile:
                        profiles.append({
                            "name": judge_name,
                            "total_cases": profile.get("total_cases", 0),
                            "disposal_patterns": profile.get("disposal_patterns", {}),
                            "top_cited_judgments": profile.get("top_cited_judgments", [])[:5],
                            "acts_frequency": dict(list(profile.get("acts_frequency", {}).items())[:10]),
                        })
                judge_context = {"profiles": profiles}
        except Exception:
            logger.warning("Failed to fetch judge analytics", exc_info=True)

    return {
        "template": asdict(template),
        "court_profile": asdict(court_profile),
        "primary_code": primary_code,
        "judge_context": judge_context,
    }


# ---------------------------------------------------------------------------
# Node 2: gather_provisions_node
# ---------------------------------------------------------------------------


async def gather_provisions_node(
    state: DraftingState,
    llm: LLMProvider,
    db: AsyncSession,
    graph_store: Any | None = None,
) -> dict:
    """Identify relevant statutory provisions from case facts and template basis."""
    template = state.get("template", {})
    case_facts = sanitize_search_query(state.get("case_facts", ""))
    statutory_basis = template.get("statutory_basis", "")

    if not case_facts:
        return {"statutory_provisions": []}

    # Query PostgreSQL for related acts cited in cases with similar statutory basis
    related_acts: list[str] = []
    # Extract the first act name from statutory_basis for fuzzy matching
    act_name = statutory_basis.split(",")[0].strip() if statutory_basis else ""
    if act_name:
        try:
            result = await db.execute(
                text(
                    "SELECT DISTINCT unnest(acts_cited) AS act "
                    "FROM cases "
                    "WHERE array_to_string(acts_cited, ' ') ILIKE :pattern "
                    "LIMIT 20"
                ),
                {"pattern": f"%{act_name}%"},
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

    try:
        raw = await llm.generate(
            prompt=prompt,
            system=DRAFT_VERIFY_PROVISIONS_SYSTEM,
            temperature=0.1,
        )
    except Exception as e:
        logger.warning("LLM call failed in gather_provisions_node: %s", e)
        raw = ""

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

    # Post-process: attach old↔new code mappings
    from app.core.legal.amendment_service import build_lookup_from_constants

    old_to_new, new_to_old = build_lookup_from_constants()
    _act_to_new = {"IPC": "BNS", "CrPC": "BNSS", "IEA": "BSA"}
    _act_to_old = {"BNS": "IPC", "BNSS": "CrPC", "BSA": "IEA"}

    for prov in validated:
        act = prov.get("act", "")
        sec = prov.get("section", "")
        key_old = (act, sec)
        key_new = (act, sec)
        if key_old in old_to_new:
            prov["new_code_section"] = old_to_new[key_old][0]
            prov["new_code_act"] = _act_to_new.get(act, "")
        elif key_new in new_to_old:
            prov["old_code_section"] = new_to_old[key_new][0]
            prov["old_code_act"] = _act_to_old.get(act, "")

    # V2: Suggest related precedents from citation graph
    suggested_precedents: list[dict] = []
    if graph_store:
        user_precedents = state.get("relevant_precedents", []) or []
        seen_ids: set[str] = set()
        top_results: list[dict] = []
        for prec in user_precedents[:5]:  # Limit to first 5
            case_id = prec.get("case_id", "")
            if case_id:
                top_results.append({"case_id": case_id})
                seen_ids.add(case_id)
        if top_results:
            try:
                from app.core.agents.nodes.common import get_citation_neighbors

                neighbors = await get_citation_neighbors(
                    graph_store, top_results, seen_ids, max_results=5
                )
                for n in neighbors:
                    suggested_precedents.append({
                        "case_id": n.get("case_id", ""),
                        "title": n.get("title", ""),
                        "citation": n.get("citation", ""),
                        "source": "citation_graph",
                    })
            except Exception:
                logger.warning("Failed to get citation graph suggestions", exc_info=True)

    result = {"statutory_provisions": validated}
    if suggested_precedents:
        result["suggested_precedents"] = suggested_precedents
    return result


# ---------------------------------------------------------------------------
# Node 3: verify_precedents_node
# ---------------------------------------------------------------------------


async def verify_precedents_node(
    state: DraftingState,
    db: AsyncSession,
    graph_store: Any | None = None,
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

    # V2: Detect overruled/distinguished treatment via graph + text analysis
    if graph_store:
        from app.core.legal.treatment import has_overruling_language

        for prec in verified_precedents:
            # Default to good_law
            prec["treatment"] = "good_law"
            case_id = prec.get("case_id", "")
            if not case_id:
                continue
            try:
                neighbors = await graph_store.get_neighbors(
                    case_id, relationship="CITES", direction="both", depth=1
                )
                neighbor_nodes = neighbors.get("nodes", [])
                for node in neighbor_nodes:
                    node_text = node.get("text", "") or node.get("snippet", "") or ""
                    if node_text and has_overruling_language(node_text):
                        prec["treatment"] = "overruled"
                        break
            except Exception:
                logger.warning("Failed treatment check for %s", case_id, exc_info=True)
    else:
        for prec in verified_precedents:
            prec.setdefault("treatment", "good_law")

    return {"verified_precedents": verified_precedents}


# ---------------------------------------------------------------------------
# Node 4: draft_sections_node
# ---------------------------------------------------------------------------


async def draft_sections_node(
    state: DraftingState,
    llm: LLMProvider,
    vector_store: Any | None = None,
    embedder: Any | None = None,
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

    # Inject user feedback from sources checkpoint if re-running after HITL
    feedback = get_latest_feedback(state.get("messages", []), "sources")
    feedback_text = ""
    if feedback:
        sanitized_fb = sanitize_search_query(feedback)
        feedback_text = f"\n\nUser Feedback on Sources:\n{sanitized_fb}\n"

    # Determine argument structure (IRAC vs CRAC)
    argument_style = template.get("argument_style", "irac")
    if argument_style == "crac":
        structure_instruction = (
            "For substantive legal sections (grounds, legal provisions, "
            "precedents, analysis), structure each key point using CRAC: "
            "Lead with your CONCLUSION (your position), then state the RULE "
            "(statute/precedent), APPLY it to these facts, restate your CONCLUSION."
        )
    else:
        structure_instruction = (
            "For substantive legal sections (grounds, legal provisions, "
            "precedents, analysis), structure each key point using IRAC: "
            "ISSUE (legal question), RULE (statute/precedent), APPLICATION "
            "(to these facts), CONCLUSION (your position)."
        )

    # V3: Judge-aware context text
    judge_ctx = state.get("judge_context", {})
    judge_text = ""
    if judge_ctx.get("profiles"):
        parts = ["Judge Context (calibrate argument emphasis, do NOT mention this context in the draft):"]
        for jp in judge_ctx["profiles"]:
            top_cited = ", ".join(c.get("title", "") for c in jp.get("top_cited_judgments", [])[:3])
            parts.append(
                f"- {jp['name']}: {jp.get('total_cases', 0)} cases. "
                f"Disposal patterns: {jp.get('disposal_patterns', {})}. "
                f"Frequently cites: {top_cited}"
            )
        judge_text = "\n".join(parts) + "\n"

    # Build amendment / code context
    primary_code = state.get("primary_code", "new")
    if primary_code == "new":
        code_context = (
            "\n\nStatute Code Context:\n"
            "- Primary codes: BNS/BNSS/BSA (post-1 July 2024)\n"
            "- Cite new code as primary, old code in parentheses\n"
            "- Example: 'Section 482 BNSS (corresponding to Section 438 CrPC)'\n"
        )
    else:
        code_context = (
            "\n\nStatute Code Context:\n"
            "- Primary codes: IPC/CrPC/Indian Evidence Act (pre-1 July 2024)\n"
            "- Cite old code as primary, new code in parentheses for reference\n"
            "- Example: 'Section 438 CrPC (now Section 482 BNSS)'\n"
        )

    sem = asyncio.Semaphore(3)

    async def _draft_one(section_name: str) -> tuple[str, str]:
        async with sem:
            prompt = (
                f"Draft ONLY the '{section_name}' section of a "
                f"{template.get('display_name', 'legal document')}.\n\n"
                f"Case Facts:\n{case_facts}\n\n"
                f"Additional Context:\n{context_text}\n\n"
                f"Target Court: {target_court or 'Not specified'}\n\n"
                f"Statutory Provisions:\n{provisions_text}\n\n"
                f"Precedents (verified status included):\n{precedents_text}\n\n"
                f"{feedback_text}"
                f"Generate ONLY the content for the '{section_name}' section. "
                f"Do not include other sections.\n\n"
                f"{structure_instruction}"
                f"{code_context}"
                f"{judge_text}"
            )
            try:
                draft = await llm.generate(
                    prompt=prompt,
                    system=system_prompt,
                    temperature=0.2,
                    max_tokens=4096,
                )
                draft = draft.strip()

                # V2: Inject actual statute text for substantive sections
                substantive_sections = {
                    "legal_provisions", "grounds", "grounds_for_bail",
                    "grounds_for_anticipatory_bail", "grounds_for_quashing",
                    "grounds_for_leave", "grounds_for_divorce",
                    "grounds_for_maintenance", "legal_grounds",
                }
                if vector_store and embedder and section_name in substantive_sections:
                    try:
                        from app.core.legal.extractor import extract_acts_cited

                        acts_refs = extract_acts_cited(draft)
                        if acts_refs:
                            # Query for statute text (limit to 3 to avoid bloat)
                            for act_ref in list(acts_refs)[:3]:
                                query_text = f"{act_ref.raw_text} section text"
                                embedding = await embedder.embed(
                                    query_text, task_type="RETRIEVAL_QUERY"
                                )
                                results = await vector_store.search(
                                    embedding,
                                    top_k=1,
                                    filter={"vector_type": "statute"},
                                )
                                if results:
                                    statute_text = results[0].get("text", "")
                                    if statute_text and len(statute_text) < 2000:
                                        draft = draft + f"\n\n> **{act_ref.raw_text}**: {statute_text}"
                    except Exception:
                        logger.warning(
                            "Statute text injection failed for %s",
                            section_name,
                            exc_info=True,
                        )

                return section_name, draft
            except Exception as e:
                logger.warning("Failed to draft section %s: %s", section_name, e)
                return section_name, f"[Error drafting {section_name}: {e}]"

    tasks = [_draft_one(name) for name in sections]
    results = await asyncio.gather(*tasks)
    section_drafts: dict[str, str] = {}
    for name, draft_text in results:
        # Validate citation density for substantive sections
        warning = check_citation_density(draft_text, name)
        if warning:
            draft_text = draft_text + warning
            logger.info("Low citation density in section '%s'", name)
        section_drafts[name] = draft_text

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
    assemble_system = apply_language_suffix(DRAFT_ASSEMBLE_SYSTEM, state.get("language", "en"))

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

    # Append legal disclaimer to assembled document
    full_draft = full_draft.strip() + LEGAL_DISCLAIMER

    return {"full_draft": full_draft}


# ---------------------------------------------------------------------------
# Node 6: revise_section_node
# ---------------------------------------------------------------------------


async def revise_section_node(
    state: DraftingState,
    llm: LLMProvider,
) -> dict:
    """Revise a specific section based on user feedback."""
    revision_feedback = state.get("revision_feedback", "")
    section_drafts = state.get("section_drafts", {})
    template = state.get("template", {})

    if not revision_feedback:
        return {"section_drafts": section_drafts}

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
        return {"section_drafts": section_drafts}

    # Get the current draft of the target section
    current_draft = section_drafts.get(target_section, "")

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
        revised_text = revised.strip()

        # V3: Store revision snapshot
        import time
        snapshot = {
            "version": len(state.get("revision_history", []) or []) + 1,
            "timestamp": time.time(),
            "section": target_section,
            "old_text": current_draft,
            "new_text": revised_text,
            "feedback": feedback_text,
        }
        history = list(state.get("revision_history", []) or [])
        history.append(snapshot)

        section_drafts = {**section_drafts, target_section: revised_text}
    except Exception:
        logger.warning(
            "Failed to revise section '%s'", target_section, exc_info=True
        )
        return {"section_drafts": section_drafts}

    return {"section_drafts": section_drafts, "revision_history": history}


# ---------------------------------------------------------------------------
# Node 7: verify_final_node
# ---------------------------------------------------------------------------


async def verify_final_node(
    state: DraftingState,
    db: AsyncSession,
) -> dict:
    """Verify citations in the final draft using shared 3-layer verification."""
    memo = state.get("full_draft", "")
    if not memo:
        return {"full_draft": memo}

    grounding_citations = collect_grounding_citations(
        state.get("verified_precedents", [])
    )
    memo = await verify_memo_citations(memo, db, grounding_citations)
    return {"full_draft": memo}


# ---------------------------------------------------------------------------
# Node 8: generate_affidavit_node
# ---------------------------------------------------------------------------


async def generate_affidavit_node(
    state: DraftingState,
    llm: LLMProvider,
) -> dict:
    """Generate a companion affidavit if the template requires one."""
    template = state.get("template", {})
    if not template.get("requires_affidavit", False):
        return {"affidavit_draft": ""}

    case_facts = sanitize_search_query(state.get("case_facts", ""))
    additional_context = state.get("additional_context", {}) or {}
    target_court = state.get("target_court", "")

    deponent_name = (
        additional_context.get("accused_name", "")
        or additional_context.get("petitioner_details", "")
        or additional_context.get("applicant_details", "")
        or additional_context.get("complainant_details", "")
        or additional_context.get("deponent_name", "")
        or "[DEPONENT NAME]"
    )

    prompt = (
        f"Generate a supporting affidavit for a {template.get('display_name', 'legal document')}.\n\n"
        f"Deponent: {deponent_name}\n"
        f"Court: {target_court or 'Not specified'}\n\n"
        f"Case Facts:\n{case_facts}\n\n"
        "Follow standard Indian affidavit format:\n"
        "1. Deponent identification (name, age, S/o or D/o, address, occupation)\n"
        "2. 'I do hereby solemnly affirm and state on oath as follows:'\n"
        "3. Numbered paragraphs of facts\n"
        "4. Knowledge vs. belief distinction\n"
        "5. Verification clause with place and date\n"
        "6. Deponent signature line\n"
        "7. 'BEFORE ME' notary/oath commissioner block\n"
    )

    try:
        affidavit = await llm.generate(
            prompt=prompt,
            system=DRAFT_AFFIDAVIT_COMPANION_SYSTEM,
            temperature=0.1,
            max_tokens=4096,
        )
        return {"affidavit_draft": affidavit.strip()}
    except Exception:
        logger.warning("Failed to generate companion affidavit", exc_info=True)
        return {"affidavit_draft": ""}
