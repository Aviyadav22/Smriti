"""LLM-based metadata extraction with regex validation for Indian court judgments."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, fields
from datetime import datetime

from app.core.interfaces.llm import LLMProvider

logger = logging.getLogger(__name__)

# Maximum characters of judgment text sent to the LLM for metadata extraction.
_MAX_INPUT_CHARS: int = 50_000

# Head+tail truncation: keeps beginning (parties, header) and end (order, disposition)
_HEAD_CHARS: int = 30_000
_TAIL_CHARS: int = 20_000


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
                       "Dr. Justice", "Mr. Justice", "Justice",
                       "Dr.", "Smt.", "Shri", "J."]:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
                break
        # Strip trailing ", J." or " J."
        if name.endswith(", J.") or name.endswith(" J."):
            name = name[:-4].strip() if name.endswith(", J.") else name[:-3].strip()
        if name:
            cleaned.append(name)

    return cleaned if cleaned else None


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
    keywords: list[str] | None = None
    disposal_nature: str | None = None
    case_number: str | None = None
    is_reportable: bool | None = None
    headnotes: str | None = None  # JSON string of structured headnotes array
    outcome_summary: str | None = None
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


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

async def extract_metadata_llm(
    text: str, llm: LLMProvider, *, max_retries: int = 3
) -> CaseMetadata:
    """Use an LLM with structured output to extract metadata from judgment text.

    Uses head+tail truncation to preserve both the header (parties, court info)
    and the disposition/order at the end.

    Retries up to max_retries times with exponential backoff on transient failures.
    """
    from app.core.legal.prompts import (
        METADATA_EXTRACTION_SYSTEM,
        METADATA_EXTRACTION_USER,
        METADATA_OUTPUT_SCHEMA,
    )

    # Truncation strategy for long judgments
    if len(text) <= _MAX_INPUT_CHARS:
        truncated = text
    else:
        # For very long texts (>50K chars), use 3-segment strategy:
        # head (20K) + middle sample (15K from 40-60% position) + tail (15K)
        # This preserves: parties/header (head), analysis/reasoning (middle),
        # and order/disposition (tail).
        head = text[:20_000]
        mid_start = int(len(text) * 0.4)
        mid_end = mid_start + 15_000
        middle = text[mid_start:mid_end]
        tail = text[-15_000:]
        truncated = (
            head
            + "\n\n[...EARLY MIDDLE OMITTED...]\n\n"
            + middle
            + "\n\n[...LATE MIDDLE OMITTED...]\n\n"
            + tail
        )

    prompt = METADATA_EXTRACTION_USER.format(judgment_text=truncated)

    for attempt in range(max_retries):
        try:
            result = await llm.generate_structured(
                prompt,
                system=METADATA_EXTRACTION_SYSTEM,
                output_schema=METADATA_OUTPUT_SCHEMA,
                temperature=0.1,
            )
            # Build CaseMetadata only from keys that match its fields.
            field_names = {f.name for f in fields(CaseMetadata)}
            filtered = {k: v for k, v in result.items() if k in field_names}
            # Convert structured headnotes list to JSON string for DB storage
            if isinstance(filtered.get("headnotes"), list):
                filtered["headnotes"] = json.dumps(filtered["headnotes"])
            return CaseMetadata(**filtered)
        except (ValueError, KeyError, RuntimeError) as exc:
            # Non-transient errors -- don't retry
            logger.error("LLM metadata extraction failed (non-retryable): %s", exc)
            return CaseMetadata()
        except Exception as exc:
            if attempt == max_retries - 1:
                logger.error(
                    "LLM metadata extraction failed after %d retries: %s",
                    max_retries, exc,
                )
                return CaseMetadata()
            wait = 2 ** attempt
            logger.warning(
                "LLM metadata extraction attempt %d/%d failed, retrying in %ds: %s",
                attempt + 1, max_retries, wait, exc,
            )
            await asyncio.sleep(wait)

    return CaseMetadata()


# ---------------------------------------------------------------------------
# Regex / heuristic validation
# ---------------------------------------------------------------------------

def validate_with_regex(metadata: CaseMetadata) -> CaseMetadata:
    """Validate and sanitize LLM-extracted metadata using deterministic checks.

    This catches common LLM hallucinations such as impossible dates, future
    years, or unrecognized court names.

    Args:
        metadata: Raw ``CaseMetadata`` from the LLM.

    Returns:
        The same instance with invalid fields set to ``None``.
    """
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

    # -- Clear empty-string enum fields --
    for field_name in ("bench_type", "jurisdiction", "disposal_nature"):
        val = getattr(metadata, field_name, None)
        if isinstance(val, str) and not val.strip():
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
            # Filter empty/whitespace strings, deduplicate, cap count
            cleaned = list(dict.fromkeys(
                item.strip() for item in val if isinstance(item, str) and item.strip()
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
        import re as _re
        if not _re.match(r'^\d+:\d+$', metadata.split_ratio):
            logger.warning("Invalid split_ratio '%s', clearing field", metadata.split_ratio)
            metadata.split_ratio = None

    # -- String length validation --
    _MAX_LENGTHS = {
        "title": 500, "citation": 200, "court": 200, "petitioner": 500,
        "respondent": 500, "ratio_decidendi": 3000,
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

def merge_metadata(parquet_meta: dict, llm_meta: CaseMetadata) -> CaseMetadata:
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
        A merged ``CaseMetadata`` instance.
    """
    result = CaseMetadata()

    # -- Parquet-priority fields --
    parquet_priority = (
        "title", "citation", "court", "year", "decision_date",
        "petitioner", "respondent", "author_judge", "disposal_nature",
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
        val = parquet_val if (parquet_val is not None and str(parquet_val).strip() != "") else llm_val
        setattr(result, field, val)

    # -- Judge array (parquet may store as comma-separated string) --
    judge_raw = parquet_meta.get("judge", "")
    if isinstance(judge_raw, str) and judge_raw.strip():
        result.judge = _parse_judge_names(judge_raw)
    elif isinstance(judge_raw, list) and judge_raw:
        result.judge = _parse_judge_names(judge_raw)
    elif llm_meta.judge:
        result.judge = _parse_judge_names(llm_meta.judge)

    # -- LLM-priority fields --
    llm_priority = (
        "ratio_decidendi", "acts_cited", "cases_cited",
        "keywords", "bench_type", "jurisdiction",
    )
    for field in llm_priority:
        setattr(result, field, getattr(llm_meta, field, None))

    # -- LLM-only fields (added in March 2026 ingestion overhaul) --
    llm_only_fields = (
        "case_number", "is_reportable", "headnotes", "outcome_summary",
        # Phase C: legal completeness fields
        "coram_size", "lower_court", "lower_court_case_number", "appeal_from",
        "opinion_type", "dissenting_judges", "concurring_judges", "split_ratio",
        "petitioner_type", "respondent_type", "is_pil", "companion_cases",
    )
    for field in llm_only_fields:
        llm_val = getattr(llm_meta, field, None)
        if llm_val is not None:
            setattr(result, field, llm_val)

    # -- case_type: prefer parquet nc_display, fall back to LLM --
    raw_case_type = parquet_meta.get("nc_display") or llm_meta.case_type
    result.case_type = normalize_case_type(raw_case_type) if raw_case_type else raw_case_type

    return result
