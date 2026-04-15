"""Judge outcome prediction service using statistical heuristics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.models.case import Case

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Temporal weighting threshold: cases within this many years get boosted.
_RECENT_YEARS = 3
_RECENT_WEIGHT = 2.0
_OLD_WEIGHT = 1.0

# Minimum cases required for base rate.
_MIN_CASES = 3

# Blend parameters for act-specific adjustment.
_ACT_MIN_CASES = 5
_ACT_MAX_BLEND = 0.4
_ACT_BLEND_DENOM = 30
_MAX_ACTS = 3

# Bench composition minimum.
_BENCH_MIN_CASES = 5

# Confidence parameters.
_LOW_SAMPLE_THRESHOLD = 10
_LOW_SAMPLE_CAP = 0.4
_SIZE_NORM = 50


@dataclass
class Factor:
    """A factor that influenced the prediction."""

    name: str
    impact: str  # "strong", "moderate", "weak"
    detail: str


@dataclass
class JudgePrediction:
    """Statistical outcome prediction for a judge + case configuration."""

    predicted_outcome: str
    outcome_probabilities: dict[str, float]
    confidence: float
    sample_size: int
    factors: list[Factor] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


def _impact_label(blend_weight: float) -> str:
    """Return impact label based on blend weight magnitude."""
    if blend_weight >= 0.3:
        return "strong"
    if blend_weight >= 0.15:
        return "moderate"
    return "weak"


async def predict_outcome(
    *,
    db: AsyncSession,
    judges: list[str],
    case_type: str,
    jurisdiction: str | None = None,
    acts: list[str] | None = None,
    bench_type: str | None = None,
) -> JudgePrediction | None:
    """Predict case outcome based on historical judicial patterns.

    Returns None if insufficient data (< 3 cases) for the primary judge
    and case type combination.
    """
    if not judges:
        return None

    primary_judge = judges[0]
    factors: list[Factor] = []

    # ------------------------------------------------------------------
    # 1. Base rate — disposal counts for primary judge + case_type
    # ------------------------------------------------------------------
    base_query = (
        select(
            Case.disposal_nature,
            Case.decision_date,
        )
        .where(Case.judge.any(primary_judge))
        .where(Case.case_type == case_type)
        .where(Case.disposal_nature.isnot(None))
    )
    if jurisdiction:
        base_query = base_query.where(Case.jurisdiction == jurisdiction)
    base_result = await db.execute(base_query)
    base_rows = base_result.all()

    if not base_rows:
        return None

    # ------------------------------------------------------------------
    # 2. Temporal weighting
    # ------------------------------------------------------------------
    cutoff_date = date.today() - timedelta(days=_RECENT_YEARS * 365)

    weighted_counts: dict[str, float] = {}
    total_weight = 0.0
    raw_total = 0

    for row in base_rows:
        disposition = row.disposal_nature
        raw_total += 1

        weight = _OLD_WEIGHT
        if row.decision_date is not None and row.decision_date >= cutoff_date:
            weight = _RECENT_WEIGHT

        weighted_counts[disposition] = weighted_counts.get(disposition, 0.0) + weight
        total_weight += weight

    if raw_total < _MIN_CASES:
        return None

    # Compute weighted probabilities.
    probabilities: dict[str, float] = {}
    if total_weight > 0:
        for disposition, w in weighted_counts.items():
            probabilities[disposition] = round(w / total_weight, 4)

    # ------------------------------------------------------------------
    # 3. Act-specific adjustment
    # ------------------------------------------------------------------
    if acts:
        for act in acts[:_MAX_ACTS]:
            act_query = (
                select(
                    Case.disposal_nature,
                    func.count().label("cnt"),
                )
                .where(Case.judge.any(primary_judge))
                .where(Case.acts_cited.any(act))
                .where(Case.disposal_nature.isnot(None))
                .group_by(Case.disposal_nature)
            )
            act_result = await db.execute(act_query)
            act_rows = act_result.all()

            act_total = sum(r.cnt for r in act_rows)
            if act_total < _ACT_MIN_CASES:
                continue

            blend_weight = min(act_total / _ACT_BLEND_DENOM, _ACT_MAX_BLEND)

            # Compute act-specific probabilities.
            act_probs: dict[str, float] = {}
            for r in act_rows:
                act_probs[r.disposal_nature] = r.cnt / act_total

            # Blend into main probabilities.
            all_dispositions = set(probabilities) | set(act_probs)
            for d in all_dispositions:
                base_p = probabilities.get(d, 0.0)
                act_p = act_probs.get(d, 0.0)
                probabilities[d] = round(
                    base_p * (1 - blend_weight) + act_p * blend_weight, 4
                )

            # Determine top act outcome for factor detail.
            top_act_outcome = max(act_probs, key=act_probs.get)  # type: ignore[arg-type]
            factors.append(
                Factor(
                    name=f"Act: {act}",
                    impact=_impact_label(blend_weight),
                    detail=(
                        f"{act_total} cases under this act; "
                        f"most common outcome: {top_act_outcome} "
                        f"({act_probs[top_act_outcome]:.0%})"
                    ),
                )
            )

    # ------------------------------------------------------------------
    # 4. Bench composition — multiple judges sitting together
    # ------------------------------------------------------------------
    if len(judges) > 1:
        bench_query = (
            select(
                Case.disposal_nature,
                func.count().label("cnt"),
            )
            .where(Case.judge.contains(judges))
            .where(Case.disposal_nature.isnot(None))
            .group_by(Case.disposal_nature)
        )
        bench_result = await db.execute(bench_query)
        bench_rows = bench_result.all()

        bench_total = sum(r.cnt for r in bench_rows)
        if bench_total >= _BENCH_MIN_CASES:
            bench_probs: dict[str, float] = {}
            for r in bench_rows:
                bench_probs[r.disposal_nature] = r.cnt / bench_total

            top_bench_outcome = max(bench_probs, key=bench_probs.get)  # type: ignore[arg-type]
            factors.append(
                Factor(
                    name="Bench composition",
                    impact="moderate" if bench_total >= 10 else "weak",
                    detail=(
                        f"This bench has sat together in {bench_total} cases; "
                        f"most common outcome: {top_bench_outcome} "
                        f"({bench_probs[top_bench_outcome]:.0%})"
                    ),
                )
            )

    # ------------------------------------------------------------------
    # 5. Confidence calculation
    # ------------------------------------------------------------------
    consistency = max(probabilities.values()) if probabilities else 0.0
    size_factor = min(raw_total / _SIZE_NORM, 1.0)
    confidence = round(consistency * 0.6 + size_factor * 0.4, 4)

    caveats: list[str] = []

    if raw_total < _LOW_SAMPLE_THRESHOLD:
        confidence = min(confidence, _LOW_SAMPLE_CAP)
        caveats.append(
            f"Low sample size ({raw_total} cases). Prediction reliability is limited."
        )

    # ------------------------------------------------------------------
    # 6. Standard caveats
    # ------------------------------------------------------------------
    caveats.extend([
        f"Based on {raw_total} historical cases from Supreme Court records.",
        "Past judicial patterns do not predict future outcomes.",
        "This is a statistical summary, not legal advice.",
    ])

    # Determine predicted outcome.
    predicted_outcome = max(probabilities, key=probabilities.get)  # type: ignore[arg-type]

    return JudgePrediction(
        predicted_outcome=predicted_outcome,
        outcome_probabilities=probabilities,
        confidence=confidence,
        sample_size=raw_total,
        factors=factors,
        caveats=caveats,
    )
