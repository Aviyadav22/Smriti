"""Tests for the improved confidence scoring formula."""
import pytest
from app.core.agents.confidence import calculate_confidence


class TestConfidenceScoring:
    def test_zero_results_gives_zero(self):
        result = calculate_confidence(
            reranker_scores=[], cross_ref_ratio=0.0,
            precedent_strengths=[], contradiction_count=0, total_results=0,
        )
        assert result == 0.0

    def test_strong_results_high_confidence(self):
        """High reranker scores + cross-refs + binding precedents = high confidence."""
        result = calculate_confidence(
            reranker_scores=[0.95, 0.92, 0.88, 0.85, 0.80],
            cross_ref_ratio=0.6,
            precedent_strengths=["BINDING", "BINDING", "PERSUASIVE"],
            contradiction_count=0,
            total_results=15,
        )
        assert result >= 0.8

    def test_contradictions_reduce_confidence(self):
        """Many contradictions should lower confidence."""
        base = calculate_confidence(
            reranker_scores=[0.9, 0.85],
            cross_ref_ratio=0.3,
            precedent_strengths=["BINDING"],
            contradiction_count=0,
            total_results=5,
        )
        with_contradictions = calculate_confidence(
            reranker_scores=[0.9, 0.85],
            cross_ref_ratio=0.3,
            precedent_strengths=["BINDING"],
            contradiction_count=3,
            total_results=5,
        )
        assert with_contradictions < base

    def test_confidence_capped_at_one(self):
        """Confidence should never exceed 1.0."""
        result = calculate_confidence(
            reranker_scores=[1.0, 1.0, 1.0, 1.0, 1.0],
            cross_ref_ratio=1.0,
            precedent_strengths=["BINDING"] * 10,
            contradiction_count=0,
            total_results=50,
        )
        assert result <= 1.0

    def test_only_persuasive_lower_than_binding(self):
        """All-persuasive sources should score lower than all-binding."""
        binding = calculate_confidence(
            reranker_scores=[0.9], cross_ref_ratio=0.3,
            precedent_strengths=["BINDING"], contradiction_count=0, total_results=5,
        )
        persuasive = calculate_confidence(
            reranker_scores=[0.9], cross_ref_ratio=0.3,
            precedent_strengths=["PERSUASIVE"], contradiction_count=0, total_results=5,
        )
        assert persuasive < binding
