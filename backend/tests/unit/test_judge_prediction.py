"""Tests for judge outcome prediction service."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.analytics.judge_prediction import (
    JudgePrediction,
    predict_outcome,
)


def _make_base_rows(
    counts: dict[str, int],
    decision_date: date | None = None,
) -> list:
    """Build mock rows matching (disposal_nature, decision_date) — one row per case."""
    rows = []
    for disposition, cnt in counts.items():
        for _ in range(cnt):
            row = MagicMock()
            row.disposal_nature = disposition
            row.decision_date = decision_date
            rows.append(row)
    return rows


def _make_act_rows(counts: dict[str, int]) -> list:
    """Build mock rows matching (disposal_nature, cnt)."""
    rows = []
    for disposition, cnt in counts.items():
        row = MagicMock()
        row.disposal_nature = disposition
        row.cnt = cnt
        rows.append(row)
    return rows


def _mock_db_execute(side_effects: list) -> AsyncMock:
    """Create an AsyncMock db session whose execute returns results in order."""
    db = AsyncMock()
    results = []
    for rows in side_effects:
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        results.append(result_mock)
    db.execute = AsyncMock(side_effect=results)
    return db


@pytest.mark.asyncio
async def test_predict_outcome_basic() -> None:
    """Basic prediction with sufficient data returns a JudgePrediction."""
    base_rows = _make_base_rows(
        {"Allowed": 15, "Dismissed": 5},
        decision_date=date.today() - timedelta(days=30),
    )
    db = _mock_db_execute([base_rows])

    result = await predict_outcome(
        db=db,
        judges=["Justice A"],
        case_type="Criminal Appeal",
    )

    assert result is not None
    assert isinstance(result, JudgePrediction)
    assert result.predicted_outcome == "Allowed"
    assert result.sample_size == 20
    assert result.outcome_probabilities["Allowed"] > result.outcome_probabilities["Dismissed"]
    assert len(result.caveats) >= 3


@pytest.mark.asyncio
async def test_predict_outcome_no_data_returns_none() -> None:
    """When no rows found, returns None."""
    db = _mock_db_execute([[]])

    result = await predict_outcome(
        db=db,
        judges=["Justice Unknown"],
        case_type="Civil Appeal",
    )

    assert result is None


@pytest.mark.asyncio
async def test_predict_outcome_low_sample_returns_none() -> None:
    """When total count < 3, returns None."""
    base_rows = _make_base_rows(
        {"Allowed": 1, "Dismissed": 1},
        decision_date=date.today(),
    )
    db = _mock_db_execute([base_rows])

    result = await predict_outcome(
        db=db,
        judges=["Justice Scarce"],
        case_type="Writ Petition",
    )

    assert result is None


@pytest.mark.asyncio
async def test_predict_outcome_low_sample_caps_confidence() -> None:
    """When sample_size < 10, confidence is capped at 0.4."""
    base_rows = _make_base_rows(
        {"Allowed": 3, "Dismissed": 2},
        decision_date=date.today(),
    )
    db = _mock_db_execute([base_rows])

    result = await predict_outcome(
        db=db,
        judges=["Justice Few"],
        case_type="Criminal Appeal",
    )

    assert result is not None
    assert result.confidence <= 0.4
    assert any("Low sample size" in c for c in result.caveats)


@pytest.mark.asyncio
async def test_predict_outcome_empty_judges_returns_none() -> None:
    """Empty judges list returns None."""
    db = AsyncMock()

    result = await predict_outcome(
        db=db,
        judges=[],
        case_type="Criminal Appeal",
    )

    assert result is None


@pytest.mark.asyncio
async def test_predict_outcome_act_factors() -> None:
    """When act data has enough cases, factors include act entries."""
    base_rows = _make_base_rows(
        {"Allowed": 20, "Dismissed": 10},
        decision_date=date.today() - timedelta(days=100),
    )
    # Act query returns sufficient data.
    act_rows = _make_act_rows({"Allowed": 8, "Dismissed": 2})

    db = _mock_db_execute([base_rows, act_rows])

    result = await predict_outcome(
        db=db,
        judges=["Justice B"],
        case_type="Criminal Appeal",
        acts=["Indian Penal Code"],
    )

    assert result is not None
    act_factors = [f for f in result.factors if f.name.startswith("Act:")]
    assert len(act_factors) == 1
    assert "Indian Penal Code" in act_factors[0].name
    assert act_factors[0].impact in ("strong", "moderate", "weak")


@pytest.mark.asyncio
async def test_predict_outcome_act_insufficient_data_no_factor() -> None:
    """When act data has < 5 cases, no factor is added."""
    base_rows = _make_base_rows(
        {"Allowed": 20, "Dismissed": 10},
        decision_date=date.today(),
    )
    # Act query returns insufficient data (< 5).
    act_rows = _make_act_rows({"Allowed": 2, "Dismissed": 1})

    db = _mock_db_execute([base_rows, act_rows])

    result = await predict_outcome(
        db=db,
        judges=["Justice C"],
        case_type="Civil Appeal",
        acts=["Some Act"],
    )

    assert result is not None
    act_factors = [f for f in result.factors if f.name.startswith("Act:")]
    assert len(act_factors) == 0


@pytest.mark.asyncio
async def test_predict_outcome_bench_factor() -> None:
    """When multiple judges have sufficient shared history, bench factor appears."""
    base_rows = _make_base_rows(
        {"Allowed": 25, "Dismissed": 15},
        decision_date=date.today() - timedelta(days=60),
    )
    # Bench composition query.
    bench_rows = _make_act_rows({"Allowed": 6, "Dismissed": 4})

    db = _mock_db_execute([base_rows, bench_rows])

    result = await predict_outcome(
        db=db,
        judges=["Justice D", "Justice E"],
        case_type="Criminal Appeal",
    )

    assert result is not None
    bench_factors = [f for f in result.factors if f.name == "Bench composition"]
    assert len(bench_factors) == 1
    assert "10 cases" in bench_factors[0].detail


@pytest.mark.asyncio
async def test_predict_outcome_bench_insufficient_no_factor() -> None:
    """When bench has < 5 cases together, no bench factor."""
    base_rows = _make_base_rows(
        {"Allowed": 20, "Dismissed": 10},
        decision_date=date.today(),
    )
    bench_rows = _make_act_rows({"Allowed": 2, "Dismissed": 1})

    db = _mock_db_execute([base_rows, bench_rows])

    result = await predict_outcome(
        db=db,
        judges=["Justice F", "Justice G"],
        case_type="Civil Appeal",
    )

    assert result is not None
    bench_factors = [f for f in result.factors if f.name == "Bench composition"]
    assert len(bench_factors) == 0


@pytest.mark.asyncio
async def test_predict_outcome_temporal_weighting() -> None:
    """Recent cases get higher weight in probability calculation."""
    recent_date = date.today() - timedelta(days=30)
    old_date = date.today() - timedelta(days=365 * 5)

    # Recent cases favor Allowed; old cases favor Dismissed.
    recent_rows = _make_base_rows({"Allowed": 10}, decision_date=recent_date)
    old_rows = _make_base_rows({"Dismissed": 10}, decision_date=old_date)

    all_rows = recent_rows + old_rows
    db = _mock_db_execute([all_rows])

    result = await predict_outcome(
        db=db,
        judges=["Justice Temporal"],
        case_type="Criminal Appeal",
    )

    assert result is not None
    # Allowed should have higher probability due to 2x weight on recent cases.
    assert result.outcome_probabilities["Allowed"] > result.outcome_probabilities["Dismissed"]
    assert result.predicted_outcome == "Allowed"


@pytest.mark.asyncio
async def test_predict_outcome_standard_caveats_always_present() -> None:
    """Standard caveats are always present in the result."""
    base_rows = _make_base_rows(
        {"Allowed": 30, "Dismissed": 20},
        decision_date=date.today(),
    )
    db = _mock_db_execute([base_rows])

    result = await predict_outcome(
        db=db,
        judges=["Justice Caveat"],
        case_type="Criminal Appeal",
    )

    assert result is not None
    caveat_text = " ".join(result.caveats)
    assert "historical cases" in caveat_text
    assert "not predict future outcomes" in caveat_text
    assert "not legal advice" in caveat_text
