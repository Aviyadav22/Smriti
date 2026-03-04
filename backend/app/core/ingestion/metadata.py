"""LLM-based metadata extraction with regex validation for Indian court judgments."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from datetime import datetime

from app.core.interfaces.llm import LLMProvider

logger = logging.getLogger(__name__)

# Maximum characters of judgment text sent to the LLM for metadata extraction.
_MAX_INPUT_CHARS: int = 50_000


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


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

async def extract_metadata_llm(text: str, llm: LLMProvider) -> CaseMetadata:
    """Use an LLM with structured output to extract metadata from judgment text.

    Args:
        text: Full judgment text (will be truncated to ``_MAX_INPUT_CHARS``).
        llm: An LLM provider implementing ``generate_structured``.

    Returns:
        A ``CaseMetadata`` instance populated from the LLM response.
    """
    from app.core.legal.prompts import (
        METADATA_EXTRACTION_SYSTEM,
        METADATA_EXTRACTION_USER,
        METADATA_OUTPUT_SCHEMA,
    )

    prompt = METADATA_EXTRACTION_USER.format(judgment_text=text[:_MAX_INPUT_CHARS])

    try:
        result = await llm.generate_structured(
            prompt,
            system=METADATA_EXTRACTION_SYSTEM,
            output_schema=METADATA_OUTPUT_SCHEMA,
            temperature=0.1,
        )
    except (ValueError, KeyError, ConnectionError, TimeoutError, RuntimeError) as exc:
        logger.error("LLM metadata extraction failed: %s", exc)
        return CaseMetadata()

    # Build CaseMetadata only from keys that match its fields.
    field_names = {f.name for f in fields(CaseMetadata)}
    filtered = {k: v for k, v in result.items() if k in field_names}
    return CaseMetadata(**filtered)


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
    # -- Year must be in [1800, current_year + 1] --
    current_year = datetime.now().year
    if metadata.year is not None and (metadata.year < 1800 or metadata.year > current_year + 1):
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
        except ValueError:
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
    valid_jurisdictions = {"civil", "criminal", "constitutional", "tax", "labor", "company", "other"}
    if metadata.jurisdiction and metadata.jurisdiction.lower() not in valid_jurisdictions:
        logger.warning("Unknown jurisdiction '%s', clearing field", metadata.jurisdiction)
        metadata.jurisdiction = None
    elif metadata.jurisdiction:
        metadata.jurisdiction = metadata.jurisdiction.lower()

    # -- Validate disposal_nature --
    valid_disposals = {"Allowed", "Dismissed", "Partly Allowed", "Withdrawn", "Remanded", "Other"}
    if metadata.disposal_nature and metadata.disposal_nature not in valid_disposals:
        # Try title-casing in case LLM returned lowercase
        title_cased = metadata.disposal_nature.title()
        if title_cased in valid_disposals:
            metadata.disposal_nature = title_cased
        else:
            logger.warning("Unknown disposal_nature '%s', clearing field", metadata.disposal_nature)
            metadata.disposal_nature = None

    # -- Ensure list fields are actually lists --
    for list_field in ("judge", "acts_cited", "cases_cited", "keywords"):
        val = getattr(metadata, list_field, None)
        if val is not None and not isinstance(val, list):
            logger.warning("Field '%s' is not a list, clearing field", list_field)
            setattr(metadata, list_field, None)

    return metadata


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
        # Use parquet value if it is truthy, otherwise fall back to LLM.
        setattr(result, field, parquet_val if parquet_val else llm_val)

    # -- Judge array (parquet may store as comma-separated string) --
    judge_raw = parquet_meta.get("judge", "")
    if isinstance(judge_raw, str) and judge_raw.strip():
        result.judge = [j.strip() for j in judge_raw.split(",")]
    elif isinstance(judge_raw, list) and judge_raw:
        result.judge = judge_raw
    elif llm_meta.judge:
        result.judge = llm_meta.judge

    # -- LLM-priority fields --
    llm_priority = (
        "ratio_decidendi", "acts_cited", "cases_cited",
        "keywords", "bench_type", "jurisdiction",
    )
    for field in llm_priority:
        setattr(result, field, getattr(llm_meta, field, None))

    # -- case_type: prefer parquet nc_display, fall back to LLM --
    result.case_type = parquet_meta.get("nc_display") or llm_meta.case_type

    return result
