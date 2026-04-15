"""Tests for precedent strength classification based on Indian court hierarchy."""

import pytest

from app.core.legal.precedent_strength import (
    PrecedentStrength,
    classify_precedent_strength,
    compute_effective_strength,
    recency_weight,
)


class TestPrecedentStrength:
    def test_sc_is_binding_everywhere(self):
        """Supreme Court decisions bind all courts."""
        result = classify_precedent_strength(
            source_court="Supreme Court of India",
            source_bench="division",
            target_court="High Court of Delhi",
        )
        assert result == PrecedentStrength.BINDING

    def test_same_hc_equal_bench_is_binding(self):
        """Same HC, equal or larger bench is binding."""
        result = classify_precedent_strength(
            source_court="High Court of Delhi",
            source_bench="division",
            target_court="High Court of Delhi",
        )
        assert result == PrecedentStrength.BINDING

    def test_same_hc_smaller_bench_is_persuasive(self):
        """Same HC, smaller source bench is persuasive only."""
        result = classify_precedent_strength(
            source_court="High Court of Delhi",
            source_bench="single",
            target_court="High Court of Delhi",
            target_bench="division",
        )
        assert result == PrecedentStrength.PERSUASIVE

    def test_different_hc_is_persuasive(self):
        """Different High Court is always persuasive."""
        result = classify_precedent_strength(
            source_court="High Court of Bombay",
            source_bench="division",
            target_court="High Court of Delhi",
        )
        assert result == PrecedentStrength.PERSUASIVE

    def test_tribunal_is_persuasive(self):
        """Tribunal decisions are persuasive."""
        result = classify_precedent_strength(
            source_court="National Green Tribunal",
            source_bench=None,
            target_court="High Court of Delhi",
        )
        assert result == PrecedentStrength.PERSUASIVE

    def test_constitution_bench_binds_division_bench(self):
        """Constitution bench binds all smaller benches of same court."""
        result = classify_precedent_strength(
            source_court="Supreme Court of India",
            source_bench="constitutional",
            target_court="Supreme Court of India",
            target_bench="division",
        )
        assert result == PrecedentStrength.BINDING

    def test_no_target_defaults_to_general(self):
        """When no target court specified, SC is binding, HC is persuasive."""
        sc_result = classify_precedent_strength(
            source_court="Supreme Court of India",
            source_bench="division",
        )
        assert sc_result == PrecedentStrength.BINDING

        hc_result = classify_precedent_strength(
            source_court="High Court of Bombay",
            source_bench="division",
        )
        assert hc_result == PrecedentStrength.PERSUASIVE

    def test_unknown_court_returns_persuasive(self):
        """Unknown courts default to persuasive."""
        result = classify_precedent_strength(
            source_court="Some Unknown Court",
            source_bench=None,
        )
        assert result == PrecedentStrength.PERSUASIVE


class TestRecencyWeight:
    """Tests for the recency_weight function."""

    def test_none_year_returns_one(self):
        """Unknown year should not penalise — returns 1.0."""
        assert recency_weight(None) == 1.0

    def test_current_year_returns_one(self):
        """A case from the current year has no decay."""
        assert recency_weight(2026) == 1.0

    def test_recent_year_high_weight(self):
        """A 5-year-old case should still have a high weight."""
        w = recency_weight(2021)
        assert 0.6 < w < 0.8  # 1/(1+5/10) = 1/1.5 ≈ 0.667

    def test_old_year_low_weight(self):
        """A 50-year-old case should have a low weight."""
        w = recency_weight(1976)
        assert 0.1 < w < 0.2  # 1/(1+50/10) = 1/6 ≈ 0.167

    def test_future_year_returns_one(self):
        """A future year (edge case) should clamp age to 0."""
        assert recency_weight(2030) == 1.0


class TestComputeEffectiveStrength:
    """Tests for compute_effective_strength fusion function."""

    def test_binding_not_overruled_recent(self):
        """Binding + not overruled + current year -> ~1.0."""
        score = compute_effective_strength(PrecedentStrength.BINDING, overruled=False, year=2026)
        assert score == pytest.approx(1.0)

    def test_binding_overruled_heavy_penalty(self):
        """Binding + overruled should produce a very low score."""
        score = compute_effective_strength(
            PrecedentStrength.BINDING, overruled=True, treatment_confidence=0.7, year=2026
        )
        # 1.0 * (1 - 0.7) * 1.0 = 0.3
        assert score == pytest.approx(0.3)

    def test_binding_overruled_full_confidence(self):
        """Binding + overruled with confidence=1.0 -> 0.0."""
        score = compute_effective_strength(
            PrecedentStrength.BINDING, overruled=True, treatment_confidence=1.0, year=2026
        )
        assert score == pytest.approx(0.0)

    def test_persuasive_not_overruled(self):
        """Persuasive + not overruled + current year -> 0.6."""
        score = compute_effective_strength(PrecedentStrength.PERSUASIVE, overruled=False, year=2026)
        assert score == pytest.approx(0.6)

    def test_distinguishable_not_overruled_old(self):
        """Distinguishable + not overruled + old year -> low score."""
        score = compute_effective_strength(
            PrecedentStrength.DISTINGUISHABLE, overruled=False, year=1976
        )
        # 0.3 * (1/(1+50/10)) = 0.3 * (1/6) = 0.05
        assert score == pytest.approx(0.05)

    def test_overruled_enum_value(self):
        """OVERRULED base strength gives 0.0 regardless."""
        score = compute_effective_strength(PrecedentStrength.OVERRULED, overruled=False, year=2026)
        assert score == pytest.approx(0.0)

    def test_none_year_no_recency_penalty(self):
        """When year is None, no recency penalty applied."""
        score = compute_effective_strength(PrecedentStrength.BINDING, overruled=False, year=None)
        assert score == pytest.approx(1.0)

    def test_result_clamped_to_zero_one(self):
        """Result is always between 0.0 and 1.0."""
        score = compute_effective_strength(
            PrecedentStrength.BINDING, overruled=True, treatment_confidence=1.0, year=1950
        )
        assert 0.0 <= score <= 1.0
