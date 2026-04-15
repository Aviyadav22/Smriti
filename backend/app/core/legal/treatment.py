"""Citation treatment detection for Indian legal judgments.

Detects treatment language (overruled, distinguished, affirmed, followed)
in judgment text using regex patterns. This is used during ingestion to
build citation treatment metadata.

The LLM-based classifier (classify_treatment_llm) provides higher accuracy
for ambiguous cases. It is gated by the enable_treatment_llm_fallback config
flag and activated when regex confidence falls below treatment_llm_confidence_threshold.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.interfaces import LLMProvider

logger = logging.getLogger(__name__)


class CitationTreatment(str, Enum):
    """How a case treats a cited precedent."""

    REFERRED_TO = "referred_to"  # Neutral reference (default when no specific treatment detected)
    OVERRULED = "overruled"
    DISTINGUISHED = "distinguished"
    AFFIRMED = "affirmed"
    FOLLOWED = "followed"
    NOT_FOLLOWED = "not_followed"
    EXPLAINED = "explained"
    DOUBTED = "doubted"
    PER_INCURIAM = "per_incuriam"  # [E3] Declared as decided per incuriam


# Patterns that indicate treatment of a cited case
# Format: (treatment_type, regex_pattern)
# NOTE: NOT_FOLLOWED is listed before FOLLOWED so that negative treatment
# is detected first and those match spans are excluded from positive matching.
TREATMENT_PATTERNS: list[tuple[CitationTreatment, re.Pattern[str]]] = [
    (
        CitationTreatment.OVERRULED,
        re.compile(
            r"\b(?:overruled|overrule[sd]?\s+(?:by|in)|no\s+longer\s+good\s+law|per\s+incuriam|"
            r"expressly\s+overruled|impliedly\s+overruled|stood\s+overruled)\b",
            re.IGNORECASE,
        ),
    ),
    (
        CitationTreatment.DISTINGUISHED,
        re.compile(
            r"\b(?:distinguished|distinguishable|distinguish(?:ed|ing)\s+(?:from|in|on))\b",
            re.IGNORECASE,
        ),
    ),
    (
        CitationTreatment.AFFIRMED,
        re.compile(
            r"\b(?:affirmed|upheld|approved|endorsed|confirmed\s+(?:by|in))\b",
            re.IGNORECASE,
        ),
    ),
    (
        CitationTreatment.NOT_FOLLOWED,
        re.compile(
            r"\b(?:(?:not|never|declined\s+to|refused\s+to)\s+follow(?:ed|ing)?|"
            r"(?:not|never)\s+(?:been\s+)?followed)\b",
            re.IGNORECASE,
        ),
    ),
    (
        CitationTreatment.FOLLOWED,
        re.compile(
            r"\b(?:followed|applied|relied\s+upon|reiterated)\b",
            re.IGNORECASE,
        ),
    ),
    (
        CitationTreatment.EXPLAINED,
        re.compile(
            r"\b(?:explained|clarified|interpreted)\b",
            re.IGNORECASE,
        ),
    ),
    (
        CitationTreatment.DOUBTED,
        re.compile(
            r"\b(?:doubted|questioned|expressed\s+(?:doubt|reservation))\b",
            re.IGNORECASE,
        ),
    ),
]


@dataclass
class TreatmentResult:
    """Result of detecting citation treatment in text."""

    treatment: CitationTreatment
    cited_text: str  # The text around the treatment mention
    confidence: float  # 0.0 to 1.0


def detect_treatment_in_text(text: str) -> list[TreatmentResult]:
    """Detect citation treatment language in judgment text.

    Scans text for patterns indicating how one case treats another
    (overruled, distinguished, affirmed, etc.).

    Negative follow patterns ("not followed", "declined to follow") are
    detected first. Their match spans are then excluded from the positive
    FOLLOWED pattern to prevent false-positive classification.

    Returns list of TreatmentResult with the treatment type and
    surrounding context.
    """
    results: list[TreatmentResult] = []

    # Collect spans consumed by negative follow patterns so the positive
    # FOLLOWED pattern does not re-match the same text as a false positive.
    negative_spans: list[tuple[int, int]] = []

    for treatment, pattern in TREATMENT_PATTERNS:
        for match in pattern.finditer(text):
            # For positive FOLLOWED, skip matches that overlap a negative span
            if treatment == CitationTreatment.FOLLOWED and any(
                ns <= match.start() < ne or ns < match.end() <= ne for ns, ne in negative_spans
            ):
                continue

            # Record spans for NOT_FOLLOWED so FOLLOWED can be excluded later
            if treatment == CitationTreatment.NOT_FOLLOWED:
                negative_spans.append((match.start(), match.end()))

            # Extract surrounding context (100 chars before and after)
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end].strip()

            # Higher confidence for more specific patterns
            confidence = (
                0.7
                if treatment
                in (
                    CitationTreatment.OVERRULED,
                    CitationTreatment.DISTINGUISHED,
                    CitationTreatment.NOT_FOLLOWED,
                )
                else 0.5
            )

            results.append(
                TreatmentResult(
                    treatment=treatment,
                    cited_text=context,
                    confidence=confidence,
                )
            )

    return results


def has_overruling_language(text: str) -> bool:
    """Quick check if text contains overruling language."""
    pattern = TREATMENT_PATTERNS[0][1]  # OVERRULED pattern
    return bool(pattern.search(text))


# [E3] LLM-based treatment classification for higher accuracy
_TREATMENT_CLASSIFICATION_SYSTEM = """You are a legal citation analyst. Classify the treatment of a cited case.

Given a text excerpt around a citation, determine how the citing case treats the cited case.

Valid treatments:
1. "referred_to" — cited case is merely mentioned/referenced without specific treatment
2. "overruled" — cited case is expressly or impliedly overruled
3. "distinguished" — cited case is distinguished on facts or law
4. "affirmed" — cited case is approved/upheld/endorsed
5. "followed" — cited case is followed as binding/persuasive
6. "not_followed" — cited case is declined to be followed
7. "explained" — cited case is explained/interpreted/clarified
8. "doubted" — cited case is questioned/doubted
9. "per_incuriam" — cited case is declared per incuriam (decided in ignorance of law)

Return ONLY a JSON object: {"treatment": "<type>", "confidence": <0.0-1.0>}"""


async def classify_treatment_llm(
    text_context: str,
    llm: LLMProvider,
) -> TreatmentResult | None:
    """Use Flash LLM for more accurate treatment classification.

    Best used for ambiguous cases where regex confidence is low.
    Gated by settings.enable_treatment_llm_fallback — callers should
    check the flag before invoking this function.

    Legal purpose: Indian courts frequently use nuanced language when
    distinguishing or doubting a precedent. Regex catches explicit patterns
    ("overruled", "distinguished") but misses contextual treatment like
    "the ratio in X does not apply to the facts of the present case".
    The LLM classifier handles these ambiguous cases more accurately.

    Returns None on any failure so callers can fall back to regex results.
    """
    try:
        raw = await llm.generate(
            prompt=f"Classify the citation treatment in this excerpt:\n\n{text_context[:1000]}",
            system=_TREATMENT_CLASSIFICATION_SYSTEM,
        )
        data = json.loads(raw.strip().strip("`").removeprefix("json"))
        treatment_str = data.get("treatment", "")
        confidence = float(data.get("confidence", 0.5))
        try:
            treatment = CitationTreatment(treatment_str)
        except ValueError:
            return None
        return TreatmentResult(
            treatment=treatment,
            cited_text=text_context[:200],
            confidence=confidence,
        )
    except (
        json.JSONDecodeError,
        KeyError,
        ValueError,
        ConnectionError,
        TimeoutError,
        RuntimeError,
    ) as exc:
        logger.debug("LLM treatment classification failed: %s", exc)
        return None
