"""Tests for precedent strength classification based on Indian court hierarchy."""
import pytest
from app.core.legal.precedent_strength import classify_precedent_strength, PrecedentStrength


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
