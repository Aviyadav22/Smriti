"""Precedent strength classification based on Indian court hierarchy.

Deterministic function — no LLM needed. Uses the doctrine of stare decisis
as applied in Indian courts:
- Supreme Court binds all courts
- High Court binds within its state/territory
- Larger bench overrides smaller bench of same court
- Constitution Bench > Full Bench > Division Bench > Single Judge
"""
from __future__ import annotations

from enum import Enum
from typing import Final

from app.core.legal.courts import get_court_level, normalize_court_name

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
    source_canonical = normalize_court_name(source_court)
    source_level = get_court_level(source_canonical)

    # Supreme Court binds everything
    if source_level == "supreme":
        if target_court is None:
            return PrecedentStrength.BINDING

        target_canonical = normalize_court_name(target_court)
        target_level = get_court_level(target_canonical)

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
