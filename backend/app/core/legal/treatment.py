"""Citation treatment detection for Indian legal judgments.

Detects treatment language (overruled, distinguished, affirmed, followed)
in judgment text using regex patterns. This is used during ingestion to
build citation treatment metadata.
"""
from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass


class CitationTreatment(str, Enum):
    """How a case treats a cited precedent."""
    OVERRULED = "overruled"
    DISTINGUISHED = "distinguished"
    AFFIRMED = "affirmed"
    FOLLOWED = "followed"
    NOT_FOLLOWED = "not_followed"
    EXPLAINED = "explained"
    DOUBTED = "doubted"


# Negative follow patterns — checked BEFORE positive FOLLOWED to avoid false positives
# e.g. "not followed", "declined to follow", "refused to follow", "never been followed"
NEGATIVE_FOLLOW_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"(?:not|never|declined\s+to|refused\s+to)\s+follow(?:ed|ing)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:not|never)\s+(?:been\s+)?followed",
        re.IGNORECASE,
    ),
]

# Patterns that indicate treatment of a cited case
# Format: (treatment_type, regex_pattern)
# NOTE: NOT_FOLLOWED is listed before FOLLOWED so that negative treatment
# is detected first and those match spans are excluded from positive matching.
TREATMENT_PATTERNS: list[tuple[CitationTreatment, re.Pattern[str]]] = [
    (CitationTreatment.OVERRULED, re.compile(
        r"(?:overruled|overrule[sd]?\s+(?:by|in)|no\s+longer\s+good\s+law|per\s+incuriam|"
        r"expressly\s+overruled|impliedly\s+overruled|stood\s+overruled)",
        re.IGNORECASE,
    )),
    (CitationTreatment.DISTINGUISHED, re.compile(
        r"(?:distinguished|distinguishable|distinguish(?:ed|ing)\s+(?:from|in|on))",
        re.IGNORECASE,
    )),
    (CitationTreatment.AFFIRMED, re.compile(
        r"(?:affirmed|upheld|approved|endorsed|confirmed\s+(?:by|in))",
        re.IGNORECASE,
    )),
    (CitationTreatment.NOT_FOLLOWED, re.compile(
        r"(?:(?:not|never|declined\s+to|refused\s+to)\s+follow(?:ed|ing)?|"
        r"(?:not|never)\s+(?:been\s+)?followed)",
        re.IGNORECASE,
    )),
    (CitationTreatment.FOLLOWED, re.compile(
        r"(?:followed|applied|relied\s+upon|reiterated)",
        re.IGNORECASE,
    )),
    (CitationTreatment.EXPLAINED, re.compile(
        r"(?:explained|clarified|interpreted)",
        re.IGNORECASE,
    )),
    (CitationTreatment.DOUBTED, re.compile(
        r"(?:doubted|questioned|expressed\s+(?:doubt|reservation))",
        re.IGNORECASE,
    )),
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
            if treatment == CitationTreatment.FOLLOWED:
                if any(
                    ns <= match.start() < ne or ns < match.end() <= ne
                    for ns, ne in negative_spans
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
            confidence = 0.7 if treatment in (
                CitationTreatment.OVERRULED,
                CitationTreatment.DISTINGUISHED,
                CitationTreatment.NOT_FOLLOWED,
            ) else 0.5

            results.append(TreatmentResult(
                treatment=treatment,
                cited_text=context,
                confidence=confidence,
            ))

    return results


def has_overruling_language(text: str) -> bool:
    """Quick check if text contains overruling language."""
    pattern = TREATMENT_PATTERNS[0][1]  # OVERRULED pattern
    return bool(pattern.search(text))
