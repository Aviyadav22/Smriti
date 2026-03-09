"""Precedent strength classification based on Indian court hierarchy.

Deterministic function — no LLM needed. Uses the doctrine of stare decisis
as applied in Indian courts:
- Supreme Court binds all courts
- High Court binds within its state/territory
- Larger bench overrides smaller bench of same court
- Constitution Bench > Full Bench > Division Bench > Single Judge
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Final

_CURRENT_YEAR: Final[int] = 2026

_STRENGTH_NUMERIC: Final[dict[str, float]] = {
    "BINDING": 1.0,
    "PERSUASIVE": 0.6,
    "DISTINGUISHABLE": 0.3,
    "OVERRULED": 0.0,
    "UNKNOWN": 0.4,
}

from app.core.legal.courts import get_court_level, normalize_court_name

logger = logging.getLogger(__name__)

BENCH_HIERARCHY: Final[dict[str, int]] = {
    "constitutional": 4,
    "full": 3,
    "division": 2,
    "single": 1,
}


class PrecedentStrength(str, Enum):
    """Classification of how strongly a precedent applies."""

    BINDING = "BINDING"
    PERSUASIVE = "PERSUASIVE"
    DISTINGUISHABLE = "DISTINGUISHABLE"
    OVERRULED = "OVERRULED"


def classify_precedent_strength(
    source_court: str,
    source_bench: str | None,
    target_court: str | None = None,
    target_bench: str | None = None,
    overruled: bool = False,
) -> PrecedentStrength:
    """Classify the binding strength of a precedent.

    Args:
        source_court: Court that decided the precedent.
        source_bench: Bench type of the source decision (single/division/full/constitutional).
        target_court: Court where the precedent is being cited. If None, uses general rules.
        target_bench: Bench type of the target court (for same-court comparisons).

    Returns:
        PrecedentStrength indicating how strongly the precedent applies.
    """
    # If the case is known to be overruled, return immediately
    if overruled:
        return PrecedentStrength.OVERRULED

    source_canonical = normalize_court_name(source_court)
    source_level = get_court_level(source_canonical)
    if source_level == "unknown":
        logger.warning("Unknown court level for: %s (normalized: %s)", source_court, source_canonical)

    # Supreme Court binds everything
    if source_level == "supreme":
        if target_court is None:
            return PrecedentStrength.BINDING

        target_canonical = normalize_court_name(target_court)
        target_level = get_court_level(target_canonical)
        if target_level == "unknown":
            logger.warning("Unknown court level for: %s (normalized: %s)", target_court, target_canonical)

        # SC citing SC — check bench strength
        if target_level == "supreme" and target_bench and source_bench:
            source_rank = BENCH_HIERARCHY.get(source_bench, 0)
            target_rank = BENCH_HIERARCHY.get(target_bench, 0)
            if source_rank >= target_rank:
                return PrecedentStrength.BINDING
            return PrecedentStrength.PERSUASIVE

        return PrecedentStrength.BINDING

    # High Court
    if source_level == "high":
        if target_court is None:
            return PrecedentStrength.PERSUASIVE

        target_canonical = normalize_court_name(target_court)
        target_level = get_court_level(target_canonical)
        if target_level == "unknown":
            logger.warning("Unknown court level for: %s (normalized: %s)", target_court, target_canonical)

        # Same High Court
        if source_canonical == target_canonical:
            if source_bench and target_bench:
                source_rank = BENCH_HIERARCHY.get(source_bench, 0)
                target_rank = BENCH_HIERARCHY.get(target_bench, 0)
                if source_rank >= target_rank:
                    return PrecedentStrength.BINDING
                return PrecedentStrength.PERSUASIVE
            # No bench info — assume binding within same HC
            return PrecedentStrength.BINDING

        # Different High Court
        return PrecedentStrength.PERSUASIVE

    # Tribunals, district courts, unknown — always persuasive
    return PrecedentStrength.PERSUASIVE


def recency_weight(year: int | None) -> float:
    """Compute a recency decay weight for a judgment year.

    Recent cases receive a weight close to 1.0; older cases decay gradually.
    Formula: ``1.0 / (1 + max(0, (current_year - year)) / 10)``

    Args:
        year: The year the judgment was decided. If *None*, returns 1.0
              (no penalty when year is unknown).

    Returns:
        A float between 0.0 and 1.0.
    """
    if year is None:
        return 1.0
    age = max(0, (_CURRENT_YEAR - year))
    return 1.0 / (1 + age / 10)


def compute_effective_strength(
    base_strength: PrecedentStrength,
    overruled: bool,
    treatment_confidence: float = 0.7,
    year: int | None = None,
) -> float:
    """Fuse precedent strength with treatment status and recency.

    A BINDING precedent that has been overruled will receive a heavy penalty,
    while a recent, non-overruled BINDING case retains a score close to 1.0.

    Args:
        base_strength: The structural strength from :func:`classify_precedent_strength`.
        overruled: Whether the case has been overruled.
        treatment_confidence: Confidence in the overruled detection (0-1).
            Only applied when *overruled* is True.
        year: Year the judgment was decided (for recency weighting).

    Returns:
        Effective strength score between 0.0 and 1.0.
    """
    base_value = _STRENGTH_NUMERIC.get(base_strength.value, 0.4)

    # Treatment penalty — scale the base value down by confidence
    if overruled:
        base_value = base_value * (1 - treatment_confidence)

    # Recency decay
    result = base_value * recency_weight(year)

    return min(1.0, max(0.0, result))
