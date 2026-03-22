"""Tests for ingestion-time statute cross-reference enrichment.

Now tests act-level short-code enrichment (post-normalization).
"""

import pytest

from app.core.legal.statute_enrichment import enrich_statute_cross_references


class TestEnrichStatuteCrossReferences:
    """Test bidirectional IPC<->BNS, CrPC<->BNSS, IEA<->BSA enrichment."""

    def test_enrich_adds_bns_for_ipc(self):
        result = enrich_statute_cross_references(["IPC"])
        assert "BNS" in result
        assert "IPC" in result

    def test_enrich_adds_ipc_for_bns(self):
        result = enrich_statute_cross_references(["BNS"])
        assert "IPC" in result
        assert "BNS" in result

    def test_enrich_bidirectional_crpc(self):
        result = enrich_statute_cross_references(["CrPC"])
        assert "BNSS" in result
        assert "CrPC" in result

    def test_enrich_bidirectional_crpc_reverse(self):
        result = enrich_statute_cross_references(["BNSS"])
        assert "CrPC" in result
        assert "BNSS" in result

    def test_enrich_bidirectional_iea(self):
        result = enrich_statute_cross_references(["IEA"])
        assert "BSA" in result
        assert "IEA" in result

    def test_enrich_bidirectional_iea_reverse(self):
        result = enrich_statute_cross_references(["BSA"])
        assert "IEA" in result
        assert "BSA" in result

    def test_enrich_no_duplicates(self):
        result = enrich_statute_cross_references(["IPC", "BNS"])
        assert result == ["BNS", "IPC"]
        assert len(result) == len(set(result))

    def test_enrich_preserves_other_acts(self):
        result = enrich_statute_cross_references(["IPC", "ACA"])
        assert result == ["ACA", "BNS", "IPC"]

    def test_enrich_empty_list(self):
        assert enrich_statute_cross_references([]) == []

    def test_enrich_multiple_old_codes(self):
        result = enrich_statute_cross_references(["IPC", "CrPC"])
        assert "BNS" in result
        assert "BNSS" in result
        assert "IPC" in result
        assert "CrPC" in result

    def test_enrich_multiple_new_codes(self):
        result = enrich_statute_cross_references(["BNS", "BNSS"])
        assert "IPC" in result
        assert "CrPC" in result

    def test_non_criminal_acts_unchanged(self):
        acts = ["COI", "ACA", "MVA"]
        result = enrich_statute_cross_references(acts)
        assert result == sorted(acts)

    def test_enrich_uppercase_crpc(self):
        """CRPC (uppercase variant from normalizer) also gets enriched."""
        result = enrich_statute_cross_references(["CRPC"])
        assert "BNSS" in result

    def test_result_is_sorted(self):
        result = enrich_statute_cross_references(["IEA", "IPC", "CrPC"])
        assert result == sorted(result)
