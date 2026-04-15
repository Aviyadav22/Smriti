"""LLM-based metadata extraction with regex validation for Indian court judgments."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, fields
from datetime import datetime

from app.core.interfaces.llm import LLMProvider
from app.core.legal.taxonomy import normalize_issue_tags

logger = logging.getLogger(__name__)

_HEAD_CHARS = 30_000
_TAIL_CHARS = 20_000


def _truncate_for_llm(text: str) -> str:
    """Head+tail truncation to stay within LLM context budget."""
    if len(text) <= _HEAD_CHARS + _TAIL_CHARS:
        return text
    return (
        text[:_HEAD_CHARS]
        + "\n\n[...middle section truncated for length...]\n\n"
        + text[-_TAIL_CHARS:]
    )


def _normalize_judge_name(name: str) -> str:
    """Normalize judge name spacing and known variants.

    Fixes:
    - Inconsistent spacing after initials: "D.Y." → "D.Y.", "D. Y." → "D.Y."
    - Multiple spaces
    - Known SC judge name variants (OCR/LLM inconsistencies)
    """
    # Collapse multiple spaces
    name = re.sub(r"\s{2,}", " ", name).strip()

    # Normalize initials: "D. Y. " → "D.Y." (letter-dot-space before uppercase)
    # This handles "D. Y. Chandrachud" → "D.Y. Chandrachud"
    name = re.sub(r"\b([A-Z])\.\s+(?=[A-Z]\.)", r"\1.", name)

    # Remove trailing dot after last initial before surname
    # "D.Y. Chandrachud" stays as is (dot followed by space+lowercase-start word is fine)

    # Strip leading/trailing dots or commas left from OCR
    name = re.sub(r"^[.,\s]+|[.,\s]+$", "", name)

    return name


# Known SC judge canonical names — maps common variants to canonical form.
# Only includes judges with frequently observed OCR/LLM inconsistencies.
_JUDGE_CANONICAL: dict[str, str] = {
    # Modern era (most common in our corpus)
    "dhananjaya y chandrachud": "D.Y. Chandrachud",
    "dy chandrachud": "D.Y. Chandrachud",
    "d y chandrachud": "D.Y. Chandrachud",
    "chandrachud": "D.Y. Chandrachud",
    "sanjiv khanna": "Sanjiv Khanna",
    "b r gavai": "B.R. Gavai",
    "br gavai": "B.R. Gavai",
    "bhushan ramkrishna gavai": "B.R. Gavai",
    "surya kant": "Surya Kant",
    "suryakant": "Surya Kant",
    "hrishikesh roy": "Hrishikesh Roy",
    "j b pardiwala": "J.B. Pardiwala",
    "jb pardiwala": "J.B. Pardiwala",
    "j.b pardiwala": "J.B. Pardiwala",
    "pamidighantam sri narasimha": "P.S. Narasimha",
    "ps narasimha": "P.S. Narasimha",
    "p s narasimha": "P.S. Narasimha",
    "manoj misra": "Manoj Misra",
    "ujjal bhuyan": "Ujjal Bhuyan",
    "s c sharma": "S.C. Sharma",
    "sc sharma": "S.C. Sharma",
    "augustine george masih": "Augustine George Masih",
    "a g masih": "Augustine George Masih",
    # Recent CJIs
    "n v ramana": "N.V. Ramana",
    "nv ramana": "N.V. Ramana",
    "nuthalapati venkata ramana": "N.V. Ramana",
    "u u lalit": "U.U. Lalit",
    "uu lalit": "U.U. Lalit",
    "uday umesh lalit": "U.U. Lalit",
    "s a bobde": "S.A. Bobde",
    "sa bobde": "S.A. Bobde",
    "sharad arvind bobde": "S.A. Bobde",
    "ranjan gogoi": "Ranjan Gogoi",
    "dipak misra": "Dipak Misra",
    # Historical (frequent in 1950s-2000s corpus)
    "b p sinha": "B.P. Sinha",
    "bp sinha": "B.P. Sinha",
    "s r das": "S.R. Das",
    "sr das": "S.R. Das",
    "k subba rao": "K. Subba Rao",
    "k n wanchoo": "K.N. Wanchoo",
    "kn wanchoo": "K.N. Wanchoo",
    "p n bhagwati": "P.N. Bhagwati",
    "pn bhagwati": "P.N. Bhagwati",
    "y v chandrachud": "Y.V. Chandrachud",
    "yv chandrachud": "Y.V. Chandrachud",
    "yeshwant vishnu chandrachud": "Y.V. Chandrachud",
    "v r krishna iyer": "V.R. Krishna Iyer",
    "vr krishna iyer": "V.R. Krishna Iyer",
}


def _apply_judge_canonical(name: str) -> str:
    """Look up canonical form for known SC judges."""
    # Normalize for lookup: lowercase, strip dots/periods, collapse spaces
    key = re.sub(r"[.\-']", "", name.lower()).strip()
    key = re.sub(r"\s+", " ", key)
    return _JUDGE_CANONICAL.get(key, name)


def _validate_judges_against_text(
    judges: list[str] | None,
    full_text: str,
    header_chars: int = 2000,
) -> tuple[list[str], list[str]]:
    """Validate judge names by checking they appear in the judgment header.

    The bench composition is always listed in the first ~2000 chars of
    an Indian court judgment. For each judge, we check whether the surname
    (longest word with 4+ chars) appears case-insensitively in the header.

    Args:
        judges: List of judge names to validate.
        full_text: Full judgment text (only first ``header_chars`` are scanned).
        header_chars: How many chars from the start to scan.

    Returns:
        Tuple of (validated_judges, rejected_judges).
    """
    if not judges:
        return [], []

    # If text is too short to contain a reliable header, skip validation
    if len(full_text) < 200:
        return list(judges), []

    header = full_text[:header_chars].upper()
    validated: list[str] = []
    rejected: list[str] = []

    for judge in judges:
        # Extract surname: longest word with 4+ alpha chars
        words = [w.strip(".,'") for w in judge.split()]
        surname_candidates = [w for w in words if len(w) >= 4 and w.isalpha()]
        if not surname_candidates:
            # Fallback: use last word regardless
            surname_candidates = [words[-1].strip(".,'") if words else ""]

        surname = max(surname_candidates, key=len) if surname_candidates else ""

        if surname and surname.upper() in header:
            validated.append(judge)
        else:
            rejected.append(judge)

    return validated, rejected


# Supreme Court judge tenure lookup — (appointment_year, retirement_year).
# Only includes judges with frequently observed hallucination in audit.
# Source: Supreme Court of India official records.
_JUDGE_TENURE: dict[str, tuple[int, int]] = {
    "sathasivam": (2007, 2014),
    "kapadia": (2003, 2012),
    "pasayat": (2001, 2009),
    "gogoi": (2012, 2019),
    "chandrachud d.y.": (2016, 2024),
    "chandrachud y.v.": (1972, 1985),
    "krishna iyer": (1973, 1980),
    "bhagwati": (1973, 1986),
    "fazal ali": (1950, 1952),
    "mukherjea": (1950, 1955),
    "das": (1950, 1956),
    "ramana": (2014, 2022),
    "misra dipak": (2011, 2018),
    "bobde": (2013, 2021),
    "lalit": (2014, 2022),
    "nariman": (2014, 2020),
    "khanna sanjiv": (2019, 2025),
    "kaul": (2017, 2025),
    "bhat": (2019, 2025),
    "maheshwari": (2019, 2024),
    "nazeer": (2017, 2023),
    "trivedi": (2021, 2025),
    "oka": (2021, 2026),
    "rajendra babu": (1997, 2004),
    "venkatarama reddi": (2000, 2006),
    "arun kumar": (2000, 2005),
    "kania": (1987, 1992),
    "kuldip singh": (1988, 1996),
    "ramaswamy k.": (1989, 1995),
    "venkatachala": (1995, 1999),
    "phukan": (1999, 2004),
    "sen a.p.": (1978, 1985),
    "dutt murari": (2007, 2009),
    "chauhan b.s.": (2009, 2014),
    "bharucha": (1995, 2002),
}


def _validate_judge_tenure(
    judges: list[str],
    year: int | None,
) -> list[str]:
    """Filter out judges who couldn't have sat on the bench in the given year.

    Uses a lightweight lookup of SC judge tenure ranges. Judges not found
    in the lookup are passed through (benefit of the doubt).

    Args:
        judges: List of judge names.
        year: Case decision year.

    Returns:
        Filtered list with only temporally plausible judges.
    """
    if not judges or year is None:
        return list(judges) if judges else []

    valid: list[str] = []
    for judge in judges:
        # Build lookup key: try surname, then "surname initial"
        words = [w.strip(".,'") for w in judge.split()]
        surname_candidates = [w for w in words if len(w) >= 3 and w.isalpha()]
        surname = max(surname_candidates, key=len).lower() if surname_candidates else ""

        tenure = _JUDGE_TENURE.get(surname)

        # Try with first initial for disambiguation (e.g., "chandrachud d.y.")
        if tenure is None and len(words) >= 2:
            initial = words[0].strip(".").lower()
            tenure = _JUDGE_TENURE.get(f"{surname} {initial}")

        if tenure is None:
            # Unknown judge — pass through
            valid.append(judge)
        elif tenure[0] <= year <= tenure[1] + 1:
            # +1 grace: retirement mid-year means they may have sat in that year
            valid.append(judge)
        else:
            logger.warning(
                "Temporal judge mismatch: %s (tenure %d-%d) on %d case — rejected",
                judge, tenure[0], tenure[1], year,
            )

    return valid


# Common English stopwords to exclude from token matching
_STOPWORDS = frozenset({
    "the", "a", "an", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "must", "and", "but", "or",
    "nor", "not", "no", "so", "if", "then", "than", "that", "this",
    "which", "who", "whom", "what", "where", "when", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "only",
    "own", "same", "too", "very", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "into", "through", "during", "before",
    "after", "above", "below", "between", "under", "upon", "about",
    "it", "its", "he", "she", "they", "them", "his", "her", "their",
    "case", "court", "judgment", "order", "act", "section", "india",
    "supreme", "high", "appeal", "petition", "respondent", "appellant",
})


def _validate_metadata_against_text(
    metadata: CaseMetadata,
    full_text: str,
    min_text_len: int = 200,
) -> CaseMetadata:
    """Post-extraction sanity checks — remove fields that contradict the text.

    Validates:
    - Keywords: each keyword must have at least one non-stopword token in full_text.
    - Ratio decidendi: must share >=3 non-stopword tokens with full_text.

    Args:
        metadata: Extracted metadata to validate.
        full_text: Full judgment text.
        min_text_len: Skip validation if text is shorter than this.

    Returns:
        Metadata with invalidated fields nulled out.
    """
    if len(full_text) < min_text_len:
        return metadata

    text_lower = full_text.lower()

    # --- Validate keywords ---
    if metadata.keywords:
        validated_kw: list[str] = []
        for kw in metadata.keywords:
            # Check if any non-stopword token (4+ chars) from the keyword appears in text
            tokens = [t for t in re.split(r"\W+", kw.lower()) if len(t) >= 3 and t not in _STOPWORDS]
            if not tokens:
                # Short keyword — keep it (e.g., "PIL", "bail")
                validated_kw.append(kw)
            elif any(token in text_lower for token in tokens):
                validated_kw.append(kw)
            else:
                logger.warning("Keyword not found in text, removing: %s", kw)
        metadata.keywords = validated_kw if validated_kw else None

    # --- Validate ratio_decidendi ---
    if metadata.ratio_decidendi:
        ratio_tokens = [
            t for t in re.split(r"\W+", metadata.ratio_decidendi.lower())
            if len(t) >= 4 and t not in _STOPWORDS
        ]
        matching = sum(1 for t in ratio_tokens if t in text_lower)
        if ratio_tokens and matching < 2:
            logger.warning(
                "Ratio decidendi shares only %d/%d tokens with text — nulling",
                matching, len(ratio_tokens),
            )
            metadata.ratio_decidendi = None

    return metadata


# Fields to null out when confidence is very low
_UNRELIABLE_LLM_FIELDS = (
    "ratio_decidendi", "keywords", "case_type", "jurisdiction",
    "bench_type", "headnotes", "outcome_summary",
    "legal_principles_applied", "issue_classification", "fact_pattern_tags",
    "opinion_type", "judicial_tone", "key_observations",
    "arguments_raised", "fact_pattern_summary",
)


def _strip_unreliable_llm_fields(metadata: CaseMetadata) -> CaseMetadata:
    """Null out LLM-only semantic fields when extraction confidence is very low.

    Preserves Parquet-sourced fields (title, citation, court, year, judge, etc.)
    and structured fields (decision_date, petitioner, respondent).
    """
    for field_name in _UNRELIABLE_LLM_FIELDS:
        if hasattr(metadata, field_name):
            setattr(metadata, field_name, None)
    return metadata


def synthesize_case_description(metadata: CaseMetadata) -> str | None:
    """Build a case description from already-extracted structured fields.

    Returns None if insufficient data (title-only is too thin).
    Pure function — no LLM call.
    """
    if not metadata.title:
        return None

    parts: list[str] = []

    # Lead with case type if available
    if metadata.case_type:
        parts.append(f"{metadata.case_type} — {metadata.title}.")
    else:
        parts.append(f"{metadata.title}.")

    # Add first sentence of ratio if available
    if metadata.ratio_decidendi:
        first_sentence = metadata.ratio_decidendi.split(". ")[0].strip()
        if len(first_sentence) > 200:
            first_sentence = first_sentence[:200].rsplit(" ", 1)[0]
        parts.append(f"The court held that {first_sentence}.")
    elif metadata.headnotes:
        # Fallback: first headnote proposition
        try:
            hn_list = json.loads(metadata.headnotes) if isinstance(metadata.headnotes, str) else []
            if hn_list and isinstance(hn_list[0], dict):
                prop = hn_list[0].get("proposition", "")[:150]
                if prop:
                    parts.append(f"Key issue: {prop}.")
        except (json.JSONDecodeError, TypeError, IndexError):
            pass

    # Add disposal
    if metadata.disposal_nature:
        parts.append(f"The case was {metadata.disposal_nature.lower()}.")

    description = " ".join(parts)

    # Only title was used — too thin to be useful
    if len(parts) <= 1:
        return None

    return description[:500]


# Regex for extracting operative outcome from judgment tail
_OUTCOME_RE = re.compile(
    r"(?:the\s+)?(?:appeal|petition|writ(?:\s+petition)?|suit|case|"
    r"special\s+leave\s+petition|criminal\s+appeal|civil\s+appeal)"
    r"\s+(?:is|are|stands?|shall\s+stand)\s+"
    r"(allowed|dismissed|partly\s+allowed|disposed\s+of|"
    r"remanded|transferred|withdrawn)",
    re.IGNORECASE,
)


def synthesize_outcome_summary(
    metadata: CaseMetadata, full_text: str,
) -> str | None:
    """Build an outcome summary from disposal_nature or regex on the operative order.

    Path A: template from disposal_nature + ratio first sentence.
    Path B: regex extraction from last 3000 chars of judgment text.
    Returns None if neither path yields a result.
    """
    # Path A: structured fields
    if metadata.disposal_nature:
        case_label = metadata.case_type or "case"
        summary = f"The {case_label.lower()} was {metadata.disposal_nature.lower()}."

        # Append first sentence of ratio for richer context
        if metadata.ratio_decidendi:
            first_sentence = metadata.ratio_decidendi.split(". ")[0].strip()
            if len(first_sentence) > 150:
                first_sentence = first_sentence[:150].rsplit(" ", 1)[0]
            summary += f" {first_sentence}."

        return summary[:300]

    # Path B: regex from text tail
    if full_text:
        tail = full_text[-3000:]
        match = _OUTCOME_RE.search(tail)
        if match:
            # Extract the sentence containing the match
            start = tail.rfind(".", 0, match.start())
            start = start + 1 if start != -1 else max(0, match.start() - 50)
            end = tail.find(".", match.end())
            end = end + 1 if end != -1 else min(len(tail), match.end() + 50)
            sentence = tail[start:end].strip()
            if sentence:
                return sentence[:200]

    return None


async def reextract_missing_fields(
    metadata: CaseMetadata,
    full_text: str,
    llm: LLMProvider,
    fields_needed: list[str],
) -> CaseMetadata:
    """Targeted re-extraction of specific missing fields with a minimal LLM call.

    Only called when confidence < 0.6 and deterministic synthesis failed.
    Uses a focused prompt with minimal text (5K chars) to reduce cost.
    Never overwrites existing non-None fields.
    """
    from app.core.legal.prompts import REEXTRACTION_SYSTEM_PROMPT

    # Build minimal schema with only requested fields
    field_schemas: dict[str, dict] = {
        "outcome_summary": {
            "type": "string",
            "nullable": True,
            "description": "1-2 sentence description of the specific outcome of the case",
        },
        "case_description": {
            "type": "string",
            "nullable": True,
            "description": "2-4 sentence summary: what the dispute is about, what was decided, key legal issue",
        },
    }
    schema = {
        "type": "object",
        "properties": {k: v for k, v in field_schemas.items() if k in fields_needed},
    }

    # Use targeted text slice: tail for outcome, head for description
    if fields_needed == ["outcome_summary"]:
        text_slice = full_text[-5000:] if len(full_text) > 5000 else full_text
    elif fields_needed == ["case_description"]:
        text_slice = full_text[:5000] if len(full_text) > 5000 else full_text
    else:
        # Both needed: head + tail
        text_slice = full_text[:3000] + "\n\n[...]\n\n" + full_text[-3000:] if len(full_text) > 6000 else full_text

    prompt = f"Extract the following fields from this Indian court judgment:\n\n{text_slice}"

    try:
        result = await llm.generate_structured(
            prompt,
            system=REEXTRACTION_SYSTEM_PROMPT,
            output_schema=schema,
            temperature=0.0,
        )
        for field in fields_needed:
            value = result.get(field)
            if value and getattr(metadata, field, None) is None:
                setattr(metadata, field, value)
                logger.info("Re-extracted %s successfully", field)
    except Exception:
        logger.warning("Targeted re-extraction failed for %s — proceeding without", fields_needed, exc_info=True)

    return metadata


def _parse_judge_names(raw: str | list | None) -> list[str] | None:
    """Parse judge names from various formats.

    Handles:
    - Pipe-delimited: "Justice A | Justice B"
    - Semicolon-delimited: "Justice A; Justice B"
    - Comma-delimited: "Justice A, Justice B"
    - Strips common prefixes: "Hon'ble", "Justice", "Mr. Justice", "J."
    """
    if raw is None:
        return None

    if isinstance(raw, list):
        names = raw
    elif isinstance(raw, str):
        # Try delimiters in order of specificity
        if "|" in raw:
            names = raw.split("|")
        elif ";" in raw:
            names = raw.split(";")
        else:
            names = raw.split(",")
    else:
        return None

    cleaned = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        # Strip common honorific prefixes (order matters: most specific first)
        for prefix in ["Hon'ble Mr. Justice", "Hon'ble Justice", "Hon'ble",
                       "Dr. Justice", "Mr. Justice", "Mrs. Justice",
                       "Ms. Justice", "Justice",
                       "Dr.", "Smt.", "Shri", "Mrs.", "Ms.", "J."]:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
                break
        # Strip trailing ", JJ." / " JJ." (plural judges) — must check before ", J."
        if name.endswith(", JJ.") or name.endswith(" JJ."):
            name = name[:-5].strip() if name.endswith(", JJ.") else name[:-4].strip()
        elif name.endswith(", JJ") or name.endswith(" JJ"):
            name = name[:-4].strip() if name.endswith(", JJ") else name[:-3].strip()
        elif name.endswith("JJ.") and len(name) > 3:
            name = name[:-3].strip().rstrip(",").strip()
        # Strip trailing ", J." or " J."
        elif name.endswith(", J.") or name.endswith(" J."):
            name = name[:-4].strip() if name.endswith(", J.") else name[:-3].strip()
        if name:
            name = _normalize_judge_name(name)
            name = _apply_judge_canonical(name)
            if name:
                cleaned.append(name)

    # Deduplicate while preserving order (after normalization, variants merge)
    seen: set[str] = set()
    deduped = []
    for n in cleaned:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(n)

    return deduped if deduped else None


@dataclass
class CaseMetadata:
    """Structured metadata extracted from an Indian court judgment."""

    title: str | None = None
    citation: str | None = None
    court: str | None = None
    judge: list[str] | None = None
    author_judge: str | None = None
    year: int | None = None
    decision_date: str | None = None  # ISO 8601 (YYYY-MM-DD)
    case_type: str | None = None
    bench_type: str | None = None
    jurisdiction: str | None = None
    petitioner: str | None = None
    respondent: str | None = None
    ratio_decidendi: str | None = None
    acts_cited: list[str] | None = None
    cases_cited: list[str] | None = None
    citation_refs: list[str] | None = None  # Bare reporter refs (no case names) for graph linking
    keywords: list[str] | None = None
    disposal_nature: str | None = None
    case_number: str | None = None
    is_reportable: bool | None = None
    headnotes: str | None = None  # JSON string of structured headnotes array
    outcome_summary: str | None = None
    case_description: str | None = None  # LLM-generated case summary (fallback for Parquet)
    # Phase C: Legal completeness fields
    coram_size: int | None = None
    lower_court: str | None = None
    lower_court_case_number: str | None = None
    appeal_from: str | None = None
    opinion_type: str | None = None  # unanimous, majority, plurality, per_curiam
    dissenting_judges: list[str] | None = None
    concurring_judges: list[str] | None = None
    split_ratio: str | None = None  # e.g., "3:2"
    petitioner_type: str | None = None
    respondent_type: str | None = None
    is_pil: bool | None = None
    companion_cases: list[str] | None = None
    # U4: Anonymization tracking
    is_anonymized: bool = False
    anonymization_flags: list[str] | None = None

    # --- Ingestion V2 fields ---
    # Group A: Judge Behavior Modeling
    arguments_raised: list[dict] | None = None
    relief_granted: str | None = None
    relief_sought: str | None = None
    sentence_details: dict | None = None
    damages_awarded: dict | None = None
    judicial_tone: str | None = None
    key_observations: list[str] | None = None
    hearing_count: int | None = None
    # Group B: Citation Intelligence
    citation_treatments: list[dict] | None = None
    distinguished_cases: list[str] | None = None
    overruled_cases: list[str] | None = None
    legal_principles_applied: list[str] | None = None
    # Group C: Procedural Intelligence
    procedural_history: list[dict] | None = None
    interim_orders: list[str] | None = None
    filing_date: str | None = None
    urgency_indicators: list[str] | None = None
    # Group D: Party & Case Intelligence
    party_counsel: list[dict] | None = None
    issue_classification: list[str] | None = None
    fact_pattern_tags: list[str] | None = None
    # Group E: Output Quality
    operative_order: str | None = None
    conditions_imposed: list[str] | None = None
    costs_awarded: dict | None = None
    # Enrichment tracking
    enrichment_status: str = "flash_only"

    # --- Ingestion V3 fields ---
    source_dataset: str = "aws_open_data_sc"
    legal_propositions: list[dict] | None = None  # [{proposition_text, paragraph_number, is_novel, related_section}]
    statute_sections_interpreted: list[dict] | None = None  # [{section, act, interpretation_summary}]
    fact_pattern_summary: str | None = None


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

async def extract_metadata_llm(
    text: str,
    llm: LLMProvider,
    *,
    pdf_path: str | None = None,
    hint_year: int | None = None,
) -> CaseMetadata:
    """Use an LLM with structured output to extract metadata from judgment text.

    V3: Prefers Gemini PDF multimodal when pdf_path is provided (better layout
    understanding, no pdfplumber artifacts). Falls back to text-only for
    non-Gemini providers or when pdf_path is unavailable.

    Single-attempt function — retries are handled by the pipeline's tenacity
    decorator (3 attempts) and the Gemini provider's own retry (5 attempts).
    """
    from app.core.legal.prompts import (
        METADATA_EXTRACTION_SYSTEM,
        METADATA_EXTRACTION_USER,
        METADATA_OUTPUT_SCHEMA,
        get_era_preamble,
    )

    era_preamble = get_era_preamble(hint_year)
    system_prompt = METADATA_EXTRACTION_SYSTEM + era_preamble

    # Determine whether to use PDF multimodal or text-only
    can_use_pdf = bool(pdf_path and hasattr(llm, "generate_structured_from_pdf"))

    try:
        result: dict = {}

        if can_use_pdf:
            # PDF multimodal: Gemini sees actual PDF layout
            try:
                prompt = METADATA_EXTRACTION_USER.format(
                    judgment_text="[See attached PDF document]"
                )
                result = await llm.generate_structured_from_pdf(
                    pdf_path,
                    prompt=prompt,
                    system=system_prompt,
                    output_schema=METADATA_OUTPUT_SCHEMA,
                    temperature=0.1,
                )
            except Exception as pdf_exc:
                logger.warning(
                    "PDF multimodal extraction failed, falling back to text: %s",
                    pdf_exc,
                )
                result = {}  # Trigger text fallback below

        if not result:
            # Text fallback: send extracted text (for tests, non-Gemini, PDF failure)
            truncated = _truncate_for_llm(text)
            prompt = METADATA_EXTRACTION_USER.format(judgment_text=truncated)
            result = await llm.generate_structured(
                prompt,
                system=system_prompt,
                output_schema=METADATA_OUTPUT_SCHEMA,
                temperature=0.1,
            )

        # Empty or all-null result means LLM returned no useful data — retry
        if not result or all(v is None for v in result.values()):
            raise RuntimeError("LLM returned empty/all-null structured output")

        # Build CaseMetadata only from keys that match its fields.
        field_names = {f.name for f in fields(CaseMetadata)}
        filtered = {k: v for k, v in result.items() if k in field_names}
        # Convert structured headnotes list to JSON string for DB storage
        if isinstance(filtered.get("headnotes"), list):
            filtered["headnotes"] = json.dumps(filtered["headnotes"])
        return CaseMetadata(**filtered)
    except (ValueError, KeyError) as exc:
        # Non-transient errors -- don't retry
        logger.error("LLM metadata extraction failed (non-retryable): %s", exc)
        return CaseMetadata()


# ---------------------------------------------------------------------------
# Regex / heuristic validation
# ---------------------------------------------------------------------------

def compute_extraction_confidence(metadata: CaseMetadata) -> float:
    """Compute a confidence score (0.0-1.0) for the LLM extraction quality.

    Weights critical fields more heavily: title, citation, court, year, judge,
    and ratio_decidendi are high-value; optional fields contribute less.

    Returns a float between 0.0 (no fields extracted) and 1.0 (all key fields present).
    """
    weighted_fields: list[tuple[str, float]] = [
        ("title", 0.12),
        ("citation", 0.12),
        ("court", 0.10),
        ("year", 0.10),
        ("judge", 0.08),
        ("decision_date", 0.06),
        ("petitioner", 0.05),
        ("respondent", 0.05),
        ("ratio_decidendi", 0.08),
        ("acts_cited", 0.05),
        ("cases_cited", 0.05),
        ("keywords", 0.04),
        ("case_type", 0.03),
        ("disposal_nature", 0.03),
        ("bench_type", 0.02),
        ("jurisdiction", 0.02),
    ]
    score = 0.0
    for field_name, weight in weighted_fields:
        val = getattr(metadata, field_name, None)
        if val is not None:
            # Lists must be non-empty to count
            if isinstance(val, list) and len(val) == 0:
                continue
            # Empty strings don't count
            if isinstance(val, str) and not val.strip():
                continue
            score += weight
    return round(min(score, 1.0), 3)


def validate_with_regex(metadata: CaseMetadata) -> CaseMetadata:
    """Validate and sanitize LLM-extracted metadata using deterministic checks.

    This catches common LLM hallucinations such as impossible dates, future
    years, or unrecognized court names.

    Args:
        metadata: Raw ``CaseMetadata`` from the LLM.

    Returns:
        The same instance with invalid fields set to ``None``.
    """
    # -- Title cleanup: strip OCR header/footer garbage --
    if metadata.title:
        # "G H " prefix is OCR header leakage (seen in 2019 PDFs)
        if metadata.title.startswith("G H "):
            metadata.title = metadata.title[4:]
        # Strip leading/trailing punctuation artifacts from OCR
        metadata.title = re.sub(r"^[.\s,;:]+", "", metadata.title).strip()

    # -- Petitioner/Respondent cleanup: strip OCR artifacts --
    for party_field in ("petitioner", "respondent"):
        val = getattr(metadata, party_field, None)
        if val and isinstance(val, str):
            # Strip leading dots, commas, colons (OCR artifacts)
            cleaned = re.sub(r"^[.\s,;:]+", "", val).strip()
            if cleaned != val:
                setattr(metadata, party_field, cleaned)

    # -- Year must be in [1800, current_year] --
    current_year = datetime.now().year
    if metadata.year is not None and (metadata.year < 1800 or metadata.year > current_year):
        logger.warning("Invalid year %d detected, clearing field", metadata.year)
        metadata.year = None

    # -- decision_date must be valid ISO 8601 --
    if metadata.decision_date is not None:
        try:
            parsed_date = datetime.fromisoformat(metadata.decision_date)
            # Also reject future dates
            if parsed_date.date() > datetime.now().date():
                logger.warning("Future decision_date %s, clearing field", metadata.decision_date)
                metadata.decision_date = None
        except (ValueError, TypeError):
            logger.warning("Invalid decision_date format '%s', clearing field", metadata.decision_date)
            metadata.decision_date = None

    # -- Normalize court name via courts.py --
    if metadata.court:
        from app.core.legal.courts import normalize_court_name

        metadata.court = normalize_court_name(metadata.court)

    # -- Validate bench_type against known values --
    valid_bench_types = {"single", "division", "full", "constitutional"}
    if metadata.bench_type and metadata.bench_type.lower() not in valid_bench_types:
        logger.warning("Unknown bench_type '%s', clearing field", metadata.bench_type)
        metadata.bench_type = None
    elif metadata.bench_type:
        metadata.bench_type = metadata.bench_type.lower()

    # -- Validate jurisdiction --
    valid_jurisdictions = {
        "civil", "criminal", "constitutional", "tax", "labor", "company",
        "family", "environmental", "arbitration", "consumer", "election",
        "service", "ip/commercial", "other",
    }
    # Alias normalization
    _jurisdiction_aliases = {
        "ip": "ip/commercial",
    }
    if metadata.jurisdiction:
        normalized = metadata.jurisdiction.lower()
        normalized = _jurisdiction_aliases.get(normalized, normalized)
        if normalized not in valid_jurisdictions:
            logger.warning("Unknown jurisdiction '%s', clearing field", metadata.jurisdiction)
            metadata.jurisdiction = None
        else:
            metadata.jurisdiction = normalized

    # -- Validate disposal_nature --
    valid_disposals = {
        "Allowed", "Dismissed", "Partly Allowed", "Withdrawn", "Remanded",
        "Disposed Of", "Settled", "Transferred", "Modified", "Other",
        "Referred to Larger Bench", "Abated", "Not Pressed",
    }
    if metadata.disposal_nature and metadata.disposal_nature not in valid_disposals:
        # Try title-casing in case LLM returned lowercase
        title_cased = metadata.disposal_nature.title()
        if title_cased in valid_disposals:
            metadata.disposal_nature = title_cased
        else:
            logger.warning("Unknown disposal_nature '%s', clearing field", metadata.disposal_nature)
            metadata.disposal_nature = None

    # -- Clear empty-string and literal "None" enum fields --
    for field_name in ("bench_type", "jurisdiction", "disposal_nature"):
        val = getattr(metadata, field_name, None)
        if isinstance(val, str) and (not val.strip() or val.strip().lower() == "none"):
            setattr(metadata, field_name, None)

    # -- Ensure list fields are actually lists --
    _ALL_LIST_FIELDS = (
        "judge", "acts_cited", "cases_cited", "keywords",
        "dissenting_judges", "concurring_judges", "companion_cases",
    )
    for list_field in _ALL_LIST_FIELDS:
        val = getattr(metadata, list_field, None)
        if val is not None and not isinstance(val, list):
            logger.warning("Field '%s' is not a list, clearing field", list_field)
            setattr(metadata, list_field, None)

    # -- List content quality: deduplicate, strip, cap count --
    _MAX_LIST_ITEMS = {
        "judge": 20, "acts_cited": 50, "cases_cited": 100, "keywords": 15,
        "dissenting_judges": 10, "concurring_judges": 10, "companion_cases": 50,
    }
    for list_field, max_items in _MAX_LIST_ITEMS.items():
        val = getattr(metadata, list_field, None)
        if isinstance(val, list):
            # Strip newlines, collapse double-spaces, deduplicate, cap count
            def _clean_item(item: str) -> str:
                item = item.replace("\n", " ").replace("\r", " ")
                return re.sub(r"\s{2,}", " ", item).strip()

            cleaned = list(dict.fromkeys(
                _clean_item(item) for item in val
                if isinstance(item, str) and item.strip()
            ))
            if len(cleaned) > max_items:
                cleaned = cleaned[:max_items]
            setattr(metadata, list_field, cleaned if cleaned else None)

    # -- Validate opinion_type --
    valid_opinion_types = {"unanimous", "majority", "plurality", "per_curiam"}
    if metadata.opinion_type and metadata.opinion_type.lower() not in valid_opinion_types:
        logger.warning("Unknown opinion_type '%s', clearing field", metadata.opinion_type)
        metadata.opinion_type = None
    elif metadata.opinion_type:
        metadata.opinion_type = metadata.opinion_type.lower()

    # -- Validate party types --
    valid_party_types = {
        "individual", "government_central", "government_state", "PSU",
        "company", "NGO", "statutory_body", "other",
    }
    for party_field in ("petitioner_type", "respondent_type"):
        val = getattr(metadata, party_field, None)
        if val and val not in valid_party_types:
            # Try lowercase match
            lower_val = val.lower()
            match = next((v for v in valid_party_types if v.lower() == lower_val), None)
            if match:
                setattr(metadata, party_field, match)
            else:
                logger.warning("Unknown %s '%s', clearing field", party_field, val)
                setattr(metadata, party_field, None)

    # -- Validate coram_size --
    if metadata.coram_size is not None:
        if not isinstance(metadata.coram_size, int) or metadata.coram_size < 1 or metadata.coram_size > 15:
            logger.warning("Invalid coram_size %s, clearing field", metadata.coram_size)
            metadata.coram_size = None

    # -- Validate split_ratio format (e.g., "3:2", "4:1") --
    if metadata.split_ratio is not None:
        if not re.match(r'^\d+:\d+$', metadata.split_ratio):
            logger.warning("Invalid split_ratio '%s', clearing field", metadata.split_ratio)
            metadata.split_ratio = None

    # -- String length validation --
    _MAX_LENGTHS = {
        "title": 500, "citation": 200, "court": 200, "petitioner": 500,
        "respondent": 500, "ratio_decidendi": 1500,
        "outcome_summary": 500, "author_judge": 200, "case_type": 100,
        "disposal_nature": 50, "case_number": 200,
        "lower_court": 200, "lower_court_case_number": 200, "appeal_from": 200,
        "split_ratio": 20,
    }
    for field_name, max_len in _MAX_LENGTHS.items():
        val = getattr(metadata, field_name, None)
        if isinstance(val, str) and len(val) > max_len:
            logger.warning(
                "Field '%s' exceeds max length %d (has %d), truncating",
                field_name, max_len, len(val),
            )
            setattr(metadata, field_name, val[:max_len])

    # --- Headnotes structural validation (editorial contamination defense) ---
    _EDITORIAL_MARKER_PATTERNS = [
        re.compile(r"result\s+of\s+the\s+case\s*:", re.IGNORECASE),
        re.compile(r"catchwords?\s*:", re.IGNORECASE),
        re.compile(r"cases?\s+referred\s*:", re.IGNORECASE),
        re.compile(r"legislation\s+cited\s*:", re.IGNORECASE),
        re.compile(r"headnotes?\s+prepared\s+by", re.IGNORECASE),
        re.compile(r"reporter'?s?\s+note", re.IGNORECASE),
    ]
    # SCR lettered margin markers (A-H standalone on a line)
    _LETTERED_MARGIN_RE = re.compile(r"^\s*[A-H]\s*$", re.MULTILINE)

    # Reporter summarization prefixes to strip from proposition text.
    # These are editorial framing phrases, not judicial holdings.
    _REPORTER_PREFIX_RE = re.compile(
        r"^\s*(?:"
        r"Held\s*[-–—:,]\s*|"                          # "Held - ", "Held:"
        r"Held\s+that\s+the\s+Court\s+(?:reiterated|observed|held|noted)\s+(?:that\s+)?|"
        r"Per\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s*,?\s*(?:J\.?\s*)?[-–—:,]\s*|"  # "Per Misra, J. -"
        r"It\s+was\s+(?:contended|submitted|argued|urged)\s+(?:by\s+(?:the\s+)?(?:appellant|respondent|petitioner|counsel)\s+)?that\s+|"
        r"The\s+(?:Supreme\s+)?Court\s+(?:reiterated|observed|held|noted|stated)\s+that\s+|"
        r"(?:†\s*)|"                                    # Dagger symbol prefix
        r"\[Ed\.\s*:?\s*\]?\s*"                         # [Ed.:] or [Ed.]
        r")",
        re.IGNORECASE,
    )

    if metadata.headnotes:
        try:
            hn_list = json.loads(metadata.headnotes) if isinstance(metadata.headnotes, str) else metadata.headnotes
            if isinstance(hn_list, list):
                cleaned_hn: list[dict] = []
                total_prop_len = 0
                for item in hn_list[:6]:  # Cap at 6 propositions
                    if isinstance(item, dict) and item.get("proposition"):
                        prop = item["proposition"]
                        # Check for editorial contamination in each proposition
                        contaminated = False
                        for marker_re in _EDITORIAL_MARKER_PATTERNS:
                            if marker_re.search(prop):
                                contaminated = True
                                break
                        if _LETTERED_MARGIN_RE.search(prop):
                            contaminated = True
                        if contaminated:
                            logger.warning(
                                "Headnote proposition contains editorial markers, skipping"
                            )
                            continue
                        # Strip reporter summarization prefixes
                        cleaned_prop = _REPORTER_PREFIX_RE.sub("", prop).strip()
                        if cleaned_prop and cleaned_prop != prop:
                            logger.info(
                                "Stripped reporter prefix from headnote proposition "
                                "(%d -> %d chars)", len(prop), len(cleaned_prop),
                            )
                            prop = cleaned_prop
                        # Cap individual proposition length
                        if len(prop) > 500:
                            prop = prop[:500]
                            logger.warning("Headnote proposition truncated from %d chars", len(item["proposition"]))
                        total_prop_len += len(prop)
                        cleaned_hn.append({**item, "proposition": prop})
                    elif isinstance(item, str) and item.strip():
                        cleaned_item = _REPORTER_PREFIX_RE.sub("", item).strip()
                        if cleaned_item and len(cleaned_item) <= 500:
                            cleaned_hn.append({"proposition": cleaned_item, "acts_sections": None})
                            total_prop_len += len(cleaned_item)
                if cleaned_hn and total_prop_len <= 3000:
                    metadata.headnotes = json.dumps(cleaned_hn)
                elif total_prop_len > 3000:
                    logger.warning(
                        "Headnotes total length %d > 3000, likely editorial — nulling",
                        total_prop_len,
                    )
                    metadata.headnotes = None
                else:
                    metadata.headnotes = None
            else:
                metadata.headnotes = None
        except (json.JSONDecodeError, TypeError):
            # Raw string, not valid JSON — check if it's editorial garbage
            if len(metadata.headnotes) > 3000:
                logger.warning(
                    "Headnotes is non-JSON string of %d chars, likely editorial — nulling",
                    len(metadata.headnotes),
                )
                metadata.headnotes = None

    # --- Ratio decidendi verbosity check ---
    # Sentence count check: ratio should be 2-5 sentences per prompt guidance.
    # If it has >8 sentences, truncate to 5 at sentence boundaries first.
    if metadata.ratio_decidendi:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', metadata.ratio_decidendi) if s.strip()]
        if len(sentences) > 8:
            logger.warning(
                "ratio_decidendi has %d sentences (>8), truncating to first 5",
                len(sentences),
            )
            metadata.ratio_decidendi = " ".join(sentences[:5])

    # Hard length cap at 1500 chars (lowered from 2000)
    if metadata.ratio_decidendi and len(metadata.ratio_decidendi) > 1500:
        logger.warning(
            "ratio_decidendi is %d chars (>1500), likely contains editorial content — truncating",
            len(metadata.ratio_decidendi),
        )
        truncated = metadata.ratio_decidendi[:1500]
        last_period = truncated.rfind(". ")
        if last_period > 800:
            metadata.ratio_decidendi = truncated[:last_period + 1]
        else:
            metadata.ratio_decidendi = truncated

    # --- Fact pattern summary length cap ---
    if metadata.fact_pattern_summary and len(metadata.fact_pattern_summary) > 1000:
        truncated = metadata.fact_pattern_summary[:1000]
        last_period = truncated.rfind(". ")
        if last_period > 500:
            metadata.fact_pattern_summary = truncated[:last_period + 1]
        else:
            metadata.fact_pattern_summary = truncated

    # --- V2 Field Validation ---

    # judicial_tone enum
    valid_tones = {"formal", "assertive", "sympathetic", "critical", "neutral", "analytical"}
    if metadata.judicial_tone and metadata.judicial_tone.lower() not in valid_tones:
        metadata.judicial_tone = None

    # filing_date — validate ISO format
    if metadata.filing_date:
        try:
            datetime.fromisoformat(metadata.filing_date)
        except (ValueError, TypeError):
            metadata.filing_date = None

    # hearing_count — sanity range
    if metadata.hearing_count is not None and (metadata.hearing_count < 0 or metadata.hearing_count > 500):
        metadata.hearing_count = None

    # operative_order length cap
    if metadata.operative_order and len(metadata.operative_order) > 10_000:
        metadata.operative_order = metadata.operative_order[:10_000]

    # V2 list fields — ensure lists, dedup, cap length
    _V2_LIST_FIELDS = {
        "arguments_raised": 50, "key_observations": 30, "citation_treatments": 100,
        "distinguished_cases": 50, "overruled_cases": 50, "legal_principles_applied": 30,
        "procedural_history": 30, "interim_orders": 20, "urgency_indicators": 10,
        "party_counsel": 30, "issue_classification": 20, "fact_pattern_tags": 20,
        "conditions_imposed": 20,
    }
    for field_name, max_items in _V2_LIST_FIELDS.items():
        val = getattr(metadata, field_name, None)
        if val is not None:
            if not isinstance(val, list):
                setattr(metadata, field_name, [val] if val else [])
                val = getattr(metadata, field_name)
            if len(val) > max_items:
                setattr(metadata, field_name, val[:max_items])

    # citation_treatments — validate dict structure
    if metadata.citation_treatments:
        valid_treatments = []
        for ct in metadata.citation_treatments:
            if isinstance(ct, dict) and ct.get("cited_case"):
                valid_treatments.append(ct)
        metadata.citation_treatments = valid_treatments

    # party_counsel — validate dict structure
    if metadata.party_counsel:
        valid_counsel = []
        for pc in metadata.party_counsel:
            if isinstance(pc, dict) and pc.get("name"):
                valid_counsel.append(pc)
        metadata.party_counsel = valid_counsel

    return metadata


def cross_validate_propositions(metadata: CaseMetadata) -> CaseMetadata:
    """Cross-reference legal_propositions against ratio_decidendi.

    - If ratio is empty but propositions exist, synthesize ratio from top 3.
    - If propositions empty but ratio exists, create a single proposition from ratio.
    """
    props = metadata.legal_propositions or []
    ratio = metadata.ratio_decidendi or ""

    if not ratio.strip() and props:
        # Synthesize ratio from top propositions (non-novel first, then novel)
        sorted_props = sorted(props, key=lambda p: (p.get("is_novel", False),))
        top = sorted_props[:3]
        metadata.ratio_decidendi = " ".join(p["proposition_text"] for p in top)

    if ratio.strip() and not props:
        # Create a single proposition from ratio
        metadata.legal_propositions = [{
            "proposition_text": ratio.strip(),
            "paragraph_number": None,
            "is_novel": False,
            "related_section": None,
        }]

    # If still no propositions, try to derive from headnotes
    if not metadata.legal_propositions:
        headnotes_raw = metadata.headnotes or ""
        if headnotes_raw.strip():
            try:
                headnotes = json.loads(headnotes_raw) if isinstance(headnotes_raw, str) else headnotes_raw
                if isinstance(headnotes, list):
                    metadata.legal_propositions = [
                        {
                            "proposition_text": (h.get("text", "") or h.get("proposition", "")).strip(),
                            "paragraph_number": None,
                            "is_novel": False,
                            "related_section": None,
                        }
                        for h in headnotes
                        if (h.get("text", "") or h.get("proposition", "")).strip()
                    ]
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                logger.debug("Headnote JSON parse failed: %s", e)

    return metadata


def validate_cross_fields(metadata: CaseMetadata) -> CaseMetadata:
    """Cross-validate fields against each other to catch inconsistencies."""
    # Year must match decision_date year if both present
    if metadata.year and metadata.decision_date:
        try:
            date_year = datetime.fromisoformat(metadata.decision_date).year
            if metadata.year != date_year:
                logger.warning(
                    "Year %d doesn't match decision_date year %d, using decision_date",
                    metadata.year, date_year,
                )
                metadata.year = date_year
        except (ValueError, TypeError):
            pass

    # bench_type vs judge count: single bench shouldn't have 3+ judges
    if metadata.bench_type == "single" and metadata.judge and len(metadata.judge) >= 3:
        logger.warning(
            "bench_type is 'single' but %d judges listed, clearing bench_type",
            len(metadata.judge),
        )
        metadata.bench_type = None

    # coram_size → bench_type inference (override mismatches)
    # SC terminology: 1=single, 2-3=division, 4+=full, 5+=constitutional
    if metadata.coram_size and isinstance(metadata.coram_size, int):
        inferred_bench = None
        if metadata.coram_size == 1:
            inferred_bench = "single"
        elif metadata.coram_size in (2, 3):
            inferred_bench = "division"
        elif metadata.coram_size == 4:
            inferred_bench = "full"
        elif metadata.coram_size >= 5:
            inferred_bench = "constitutional"
        if inferred_bench and metadata.bench_type != inferred_bench:
            if metadata.bench_type is not None:
                logger.warning(
                    "bench_type '%s' conflicts with coram_size %d (expected '%s'), overriding",
                    metadata.bench_type, metadata.coram_size, inferred_bench,
                )
            metadata.bench_type = inferred_bench

    # Normalize author_judge (same pipeline as judge list names)
    if metadata.author_judge and isinstance(metadata.author_judge, str):
        normalized = _normalize_judge_name(metadata.author_judge.strip())
        normalized = _apply_judge_canonical(normalized)
        if normalized:
            metadata.author_judge = normalized

    # Judge array completion: if author_judge exists but not in judge list, append
    if (metadata.coram_size and metadata.judge and metadata.author_judge
            and isinstance(metadata.coram_size, int)
            and metadata.coram_size > len(metadata.judge)):
        author_lower = metadata.author_judge.lower()
        if author_lower not in [j.lower() for j in metadata.judge]:
            metadata.judge.append(metadata.author_judge)

    # author_judge should appear in judge list
    if metadata.author_judge and metadata.judge:
        author_lower = metadata.author_judge.lower()
        judge_names_lower = [j.lower() for j in metadata.judge]
        if author_lower not in judge_names_lower:
            logger.warning(
                "author_judge '%s' not found in judge list %s",
                metadata.author_judge, metadata.judge,
            )

    # petitioner != respondent
    if metadata.petitioner and metadata.respondent:
        if metadata.petitioner.strip().lower() == metadata.respondent.strip().lower():
            logger.warning(
                "petitioner and respondent are the same ('%s'), clearing respondent",
                metadata.petitioner,
            )
            metadata.respondent = None

    # case_type vs jurisdiction consistency
    if metadata.case_type == "Writ Petition" and metadata.jurisdiction == "criminal":
        logger.warning(
            "case_type 'Writ Petition' with jurisdiction 'criminal' is unusual"
        )

    # case_type vs case_number: the case number is authoritative for civil/criminal
    if metadata.case_number and metadata.case_type:
        cn_lower = metadata.case_number.lower()
        if "civil appeal" in cn_lower and metadata.case_type == "Criminal Appeal":
            logger.warning(
                "case_number '%s' says Civil but case_type is Criminal — correcting",
                metadata.case_number,
            )
            metadata.case_type = "Civil Appeal"
            metadata.case_number = metadata.case_number.replace(
                "Criminal Appeal", "Civil Appeal"
            ).replace("criminal appeal", "Civil Appeal")
        elif "criminal appeal" in cn_lower and metadata.case_type == "Civil Appeal":
            logger.warning(
                "case_number '%s' says Criminal but case_type is Civil — correcting",
                metadata.case_number,
            )
            metadata.case_type = "Criminal Appeal"
        elif re.search(r"slp\s*\(\s*c\s*\)", cn_lower) or "w.p.(c)" in cn_lower:
            # SLP(C) and W.P.(C) are civil — case_type should not be Criminal Appeal
            if metadata.case_type == "Criminal Appeal":
                logger.warning(
                    "case_number '%s' is civil but case_type is Criminal Appeal — correcting",
                    metadata.case_number,
                )
                if "slp" in cn_lower:
                    metadata.case_type = "Special Leave Petition"
                else:
                    metadata.case_type = "Writ Petition"

    # -- cases_cited cleanup: remove self-citations, then run GAN discriminator --
    if metadata.cases_cited and metadata.citation:
        own_normalized = re.sub(r"\s+", " ", metadata.citation.strip().lower())
        metadata.cases_cited = [
            c for c in metadata.cases_cited
            if re.sub(r"\s+", " ", c.strip().lower()) != own_normalized
        ]
    if metadata.cases_cited:
        # GAN Discriminator: classify into named citations vs bare refs
        from app.core.legal.extractor import classify_case_citations
        named, bare_refs = classify_case_citations(metadata.cases_cited)
        metadata.cases_cited = named if named else None
        # Preserve bare refs for later graph linking
        if bare_refs:
            existing_refs = getattr(metadata, "citation_refs", None) or []
            all_refs = sorted(set(existing_refs + bare_refs))
            metadata.citation_refs = all_refs

    # -- is_reportable: infer from SCR citation --
    if metadata.is_reportable is None and metadata.citation:
        if re.search(r'\[\d{4}\]\s+\d+\s+S\.?C\.?R\.?\s+\d+', metadata.citation):
            metadata.is_reportable = True

    return metadata


# ---------------------------------------------------------------------------
# Case type normalization
# ---------------------------------------------------------------------------

_CASE_TYPE_MAP: dict[str, str] = {
    "criminal appeal": "Criminal Appeal",
    "civil appeal": "Civil Appeal",
    "special leave petition": "Special Leave Petition",
    "slp": "Special Leave Petition",
    "slp(crl)": "Special Leave Petition",
    "slp(crl.)": "Special Leave Petition",
    "slp(c)": "Special Leave Petition",
    "w.p.(c)": "Writ Petition",
    "w.p.(crl)": "Writ Petition",
    "w.p.(crl.)": "Writ Petition",
    "writ petition": "Writ Petition",
    "writ petition (civil)": "Writ Petition",
    "writ petition (criminal)": "Writ Petition",
    "transfer petition": "Transfer Petition",
    "transfer petition (civil)": "Transfer Petition",
    "transfer petition (criminal)": "Transfer Petition",
    "t.p.(c)": "Transfer Petition",
    "t.p.(crl)": "Transfer Petition",
    "review petition": "Review Petition",
    "r.p.": "Review Petition",
    "contempt petition": "Contempt Petition",
    "conmt.pet.": "Contempt Petition",
    "original suit": "Original Suit",
    "reference": "Reference",
    "curative petition": "Curative Petition",
    "cur.pet.": "Curative Petition",
    "miscellaneous application": "Miscellaneous Application",
    "m.a.": "Miscellaneous Application",
    "arbitration petition": "Arbitration Petition",
    "arb.p.": "Arbitration Petition",
    "suo motu": "Suo Motu",
    "election petition": "Election Petition",
    "slp (civil)": "Special Leave Petition",
    "slp (criminal)": "Special Leave Petition",
    "c.a.": "Civil Appeal",
    "crl.a.": "Criminal Appeal",
    "i.a.": "Interlocutory Application",
    "interlocutory application": "Interlocutory Application",
    "l.p.a.": "Letters Patent Appeal",
    "letters patent appeal": "Letters Patent Appeal",
}


def normalize_case_type(raw: str) -> str:
    """Map abbreviations and variants to canonical case type names."""
    if not raw:
        return raw
    key = raw.strip().lower()
    return _CASE_TYPE_MAP.get(key, raw.strip().title())


# ---------------------------------------------------------------------------
# Merge Parquet ground truth with LLM extraction
# ---------------------------------------------------------------------------

def validate_parquet_data(parquet_meta: dict) -> dict:
    """Validate and sanitize Parquet metadata before merge.

    Catches common data issues: NaN values, extreme years, truncated titles,
    invalid date formats. Returns a cleaned copy.
    """
    import math

    cleaned = {}
    for key, val in parquet_meta.items():
        # Convert NaN/inf to None
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            cleaned[key] = None
            continue
        # Convert pandas NaT/None-like strings
        if isinstance(val, str) and val.strip().lower() in ("nan", "nat", "none", "null", ""):
            cleaned[key] = None
            continue
        cleaned[key] = val

    # Validate year range
    year = cleaned.get("year")
    if year is not None:
        try:
            year_int = int(year)
            if year_int < 1800 or year_int > datetime.now().year:
                logger.warning("Parquet year %d out of range, clearing", year_int)
                cleaned["year"] = None
            else:
                cleaned["year"] = year_int
        except (ValueError, TypeError):
            cleaned["year"] = None

    # Validate decision_date format
    date_val = cleaned.get("decision_date")
    if date_val is not None and isinstance(date_val, str):
        try:
            datetime.fromisoformat(date_val)
        except (ValueError, TypeError):
            # Try common date formats
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(date_val, fmt)
                    cleaned["decision_date"] = parsed.date().isoformat()
                    break
                except ValueError:
                    continue
            else:
                logger.warning("Invalid parquet date format '%s', clearing", date_val)
                cleaned["decision_date"] = None

    # Truncate excessively long titles (likely data corruption)
    title = cleaned.get("title")
    if isinstance(title, str) and len(title) > 1000:
        cleaned["title"] = title[:500]
        logger.warning("Parquet title truncated from %d chars", len(title))

    # Normalize Parquet disposal_nature to standard enum values
    _DISPOSAL_MAP = {
        "appeal(s) allowed": "Allowed",
        "appeals allowed": "Allowed",
        "appeal allowed": "Allowed",
        "case allowed": "Allowed",
        "leave granted & allowed": "Allowed",
        "dismissed": "Dismissed",
        "disposed off": "Disposed Of",
        "disposed of": "Disposed Of",
        "case partly allowed": "Partly Allowed",
        "partly allowed": "Partly Allowed",
        "directions issued": "Disposed Of",
        "leave granted & dismissed": "Dismissed",
        "leave granted & disposed off": "Disposed Of",
        "matter referred to larger bench": "Referred to Larger Bench",
        "referred to larger bench": "Referred to Larger Bench",
        "remitted to lower court": "Remanded",
        "rejected": "Dismissed",
        "withdrawn": "Withdrawn",
        "settled": "Settled",
        "transferred": "Transferred",
        "modified": "Modified",
        "abated": "Abated",
        "not pressed": "Not Pressed",
    }
    raw_disposal = cleaned.get("disposal_nature")
    if isinstance(raw_disposal, str) and raw_disposal.strip():
        normalized = _DISPOSAL_MAP.get(raw_disposal.strip().lower())
        if normalized:
            cleaned["disposal_nature"] = normalized
        # else: leave as-is for downstream validation to handle

    return cleaned


def merge_metadata(
    parquet_meta: dict,
    llm_meta: CaseMetadata,
    full_text: str = "",
) -> tuple[CaseMetadata, dict[str, str]]:
    """Merge Parquet ground-truth metadata with LLM-extracted metadata.

    Strategy:
    - **Parquet wins** for structured fields that are reliably present in the
      dataset (title, citation, court, year, decision_date, petitioner,
      respondent, judge, author_judge, disposal_nature).
    - **LLM wins** for semantic fields the LLM excels at extracting from
      unstructured text (ratio_decidendi, acts_cited, cases_cited, keywords,
      bench_type, jurisdiction).

    Args:
        parquet_meta: Dictionary of metadata from the Parquet file.
        llm_meta: ``CaseMetadata`` from the LLM.

    Returns:
        A tuple of (merged CaseMetadata, provenance dict mapping field -> source).
    """
    result = CaseMetadata()
    provenance: dict[str, str] = {}

    # -- Parquet-priority fields --
    parquet_priority = (
        "title", "citation", "court", "year", "decision_date",
        "petitioner", "respondent",
    )
    for field in parquet_priority:
        parquet_val = parquet_meta.get(field)
        llm_val = getattr(llm_meta, field, None)
        # Convert date objects to ISO string before merging
        if field == "decision_date" and parquet_val is not None:
            if hasattr(parquet_val, 'isoformat'):
                parquet_val = parquet_val.isoformat()
            elif not isinstance(parquet_val, str):
                parquet_val = str(parquet_val)
        # Use parquet value if non-None and non-empty, otherwise fall back to LLM.
        # Truthiness fix: empty strings from parquet should not override LLM values.
        if parquet_val is not None and str(parquet_val).strip() != "":
            val = parquet_val
            provenance[field] = "parquet"
        elif llm_val is not None:
            val = llm_val
            provenance[field] = "llm"
        else:
            val = None
        setattr(result, field, val)

    # -- disposal_nature: LLM priority (Parquet has 67-81% NULLs; LLM reads
    # the operative portion which always states disposal explicitly) --
    _valid_disposals = {
        "Allowed", "Dismissed", "Partly Allowed", "Withdrawn", "Remanded",
        "Disposed Of", "Settled", "Transferred", "Modified", "Other",
        "Referred to Larger Bench", "Abated", "Not Pressed",
    }
    llm_disposal = getattr(llm_meta, "disposal_nature", None)
    parquet_disposal = parquet_meta.get("disposal_nature")
    if llm_disposal and str(llm_disposal).strip():
        result.disposal_nature = llm_disposal
        provenance["disposal_nature"] = "llm"
    elif parquet_disposal and str(parquet_disposal).strip():
        # Normalize Parquet value if needed
        if parquet_disposal in _valid_disposals:
            result.disposal_nature = parquet_disposal
        elif parquet_disposal.title() in _valid_disposals:
            result.disposal_nature = parquet_disposal.title()
        else:
            result.disposal_nature = parquet_disposal
        provenance["disposal_nature"] = "parquet_fallback"

    # -- author_judge: LLM priority (Parquet has 0% for un-enriched cases;
    # LLM extracts from judgment header with 99% success rate) --
    llm_author = getattr(llm_meta, "author_judge", None)
    parquet_author = parquet_meta.get("author_judge")
    if llm_author and str(llm_author).strip():
        result.author_judge = llm_author
        provenance["author_judge"] = "llm"
    elif parquet_author and str(parquet_author).strip():
        result.author_judge = parquet_author
        provenance["author_judge"] = "parquet_fallback"

    # -- Judge array: Validated LLM with Parquet anchor --
    # Parquet typically only has 1 author judge. LLM extracts full bench.
    # But LLM can hallucinate judges, so we validate against the judgment text.
    judge_raw = parquet_meta.get("judge", "")
    parquet_judges: list[str] | None = None
    if (isinstance(judge_raw, str) and judge_raw.strip()) or (isinstance(judge_raw, list) and judge_raw):
        parquet_judges = _parse_judge_names(judge_raw)

    llm_judges: list[str] | None = None
    if llm_meta.judge:
        llm_judges = _parse_judge_names(llm_meta.judge)

    llm_coram = getattr(llm_meta, "coram_size", None)
    _needs_review = False

    if llm_judges and full_text:
        # Validate LLM judges against judgment header text
        validated_llm, rejected_llm = _validate_judges_against_text(
            llm_judges, full_text,
        )
        # Also apply temporal validation if year is known
        case_year = (
            parquet_meta.get("year")
            or getattr(llm_meta, "year", None)
        )
        if case_year and validated_llm:
            validated_llm = _validate_judge_tenure(validated_llm, case_year)

        if rejected_llm:
            logger.warning(
                "Judge text validation rejected %d/%d LLM judges: %s",
                len(rejected_llm), len(llm_judges), rejected_llm,
            )

        if validated_llm and not rejected_llm:
            # All LLM judges validated — use full LLM list
            result.judge = validated_llm
            provenance["judge"] = "llm_validated"
        elif validated_llm:
            # Partial validation — union validated LLM + parquet (deduped)
            merged_set: dict[str, str] = {}  # lowercase -> original
            for j in validated_llm:
                merged_set.setdefault(j.lower(), j)
            if parquet_judges:
                for j in parquet_judges:
                    merged_set.setdefault(j.lower(), j)
            result.judge = list(merged_set.values())
            provenance["judge"] = "llm_partial+parquet"
        else:
            # All LLM judges failed — fall back to parquet
            result.judge = parquet_judges
            provenance["judge"] = "parquet_llm_rejected"
            _needs_review = True
    elif llm_judges and parquet_judges:
        # No full_text for validation — fall back to count-based logic
        if len(llm_judges) > len(parquet_judges) or (llm_coram and isinstance(llm_coram, int) and llm_coram > len(parquet_judges)):
            result.judge = llm_judges
            provenance["judge"] = "llm_unvalidated"
        else:
            result.judge = parquet_judges
            provenance["judge"] = "parquet"
    elif llm_judges:
        # Only LLM — validate if text available
        if full_text:
            validated_llm, _ = _validate_judges_against_text(llm_judges, full_text)
            case_year = parquet_meta.get("year") or getattr(llm_meta, "year", None)
            if case_year and validated_llm:
                validated_llm = _validate_judge_tenure(validated_llm, case_year)
            result.judge = validated_llm or llm_judges
            provenance["judge"] = "llm_validated" if validated_llm else "llm_unvalidated"
        else:
            result.judge = llm_judges
            provenance["judge"] = "llm"
    elif parquet_judges:
        result.judge = parquet_judges
        provenance["judge"] = "parquet"

    if _needs_review:
        provenance["_needs_review"] = "all_llm_judges_rejected"

    # -- LLM-priority fields --
    llm_priority = (
        "ratio_decidendi", "acts_cited", "cases_cited",
        "keywords", "bench_type", "jurisdiction",
    )
    for field in llm_priority:
        val = getattr(llm_meta, field, None)
        setattr(result, field, val)
        if val is not None:
            provenance[field] = "llm"

    # -- LLM-only fields (added in March 2026 ingestion overhaul) --
    llm_only_fields = (
        "case_number", "is_reportable", "headnotes", "outcome_summary",
        # Phase C: legal completeness fields
        "coram_size", "lower_court", "lower_court_case_number", "appeal_from",
        "opinion_type", "dissenting_judges", "concurring_judges", "split_ratio",
        "petitioner_type", "respondent_type", "is_pil", "companion_cases",
        # V2 fields
        "arguments_raised", "relief_granted", "relief_sought", "sentence_details",
        "damages_awarded", "judicial_tone", "key_observations", "hearing_count",
        "citation_treatments", "distinguished_cases", "overruled_cases",
        "legal_principles_applied", "procedural_history", "interim_orders",
        "filing_date", "urgency_indicators", "party_counsel", "issue_classification",
        "fact_pattern_tags", "operative_order", "conditions_imposed", "costs_awarded",
        # V3 fields
        "legal_propositions", "statute_sections_interpreted", "fact_pattern_summary",
        "primary_legal_issue",
    )
    for field in llm_only_fields:
        llm_val = getattr(llm_meta, field, None)
        if llm_val is not None:
            setattr(result, field, llm_val)
            provenance[field] = "llm"

    # Normalize issue classification tags to canonical taxonomy
    if result.issue_classification:
        result.issue_classification = normalize_issue_tags(result.issue_classification)

    # -- case_type: LLM extraction only (parquet nc_display is a case ID, not a type) --
    # Store nc_display as case_id field instead
    nc_display = parquet_meta.get("nc_display")
    if nc_display and not result.case_number:
        result.case_number = nc_display
        provenance["case_number"] = provenance.get("case_number", "parquet_nc_display")
    raw_case_type = llm_meta.case_type
    result.case_type = normalize_case_type(raw_case_type) if raw_case_type else raw_case_type
    if llm_meta.case_type:
        provenance["case_type"] = "llm"

    return result, provenance
