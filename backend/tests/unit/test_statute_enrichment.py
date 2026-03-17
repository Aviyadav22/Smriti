"""Tests for ingestion-time statute cross-reference enrichment."""

import pytest

from app.core.legal.statute_enrichment import enrich_statute_cross_references


class TestEnrichStatuteCrossReferences:
    """Test bidirectional IPC<->BNS, CrPC<->BNSS, IEA<->BSA enrichment."""

    def test_ipc_302_adds_bns_103(self):
        acts = ["Indian Penal Code, Section 302"]
        result = enrich_statute_cross_references(acts)
        assert "Indian Penal Code, Section 302" in result
        assert "Bharatiya Nyaya Sanhita, Section 103" in result

    def test_bns_103_adds_ipc_302(self):
        acts = ["Bharatiya Nyaya Sanhita, Section 103"]
        result = enrich_statute_cross_references(acts)
        assert "Bharatiya Nyaya Sanhita, Section 103" in result
        assert "Indian Penal Code, Section 302" in result

    def test_crpc_438_adds_bnss_482(self):
        acts = ["Code of Criminal Procedure, Section 438"]
        result = enrich_statute_cross_references(acts)
        assert "Code of Criminal Procedure, Section 438" in result
        assert "Bharatiya Nagarik Suraksha Sanhita, Section 482" in result

    def test_bnss_482_adds_crpc_438(self):
        acts = ["Bharatiya Nagarik Suraksha Sanhita, Section 482"]
        result = enrich_statute_cross_references(acts)
        assert "Code of Criminal Procedure, Section 438" in result

    def test_evidence_65b_adds_bsa_63(self):
        acts = ["Indian Evidence Act, Section 65B"]
        result = enrich_statute_cross_references(acts)
        assert "Bharatiya Sakshya Adhiniyam, Section 63" in result

    def test_bsa_63_adds_evidence_65b(self):
        acts = ["Bharatiya Sakshya Adhiniyam, Section 63"]
        result = enrich_statute_cross_references(acts)
        assert "Indian Evidence Act, Section 65B" in result

    def test_non_criminal_acts_unchanged(self):
        acts = ["Constitution of India, Article 21", "Arbitration and Conciliation Act"]
        result = enrich_statute_cross_references(acts)
        assert result == sorted(acts)

    def test_empty_list(self):
        assert enrich_statute_cross_references([]) == []

    def test_no_duplicates(self):
        acts = [
            "Indian Penal Code, Section 302",
            "Bharatiya Nyaya Sanhita, Section 103",
        ]
        result = enrich_statute_cross_references(acts)
        assert len(result) == len(set(result))

    def test_multiple_sections_enriched(self):
        acts = [
            "Indian Penal Code, Section 302",
            "Indian Penal Code, Section 376",
            "Code of Criminal Procedure, Section 482",
        ]
        result = enrich_statute_cross_references(acts)
        assert "Bharatiya Nyaya Sanhita, Section 103" in result
        assert "Bharatiya Nagarik Suraksha Sanhita, Section 528" in result

    def test_with_year_suffix_passthrough(self):
        acts = ["Indian Penal Code, 1860"]
        result = enrich_statute_cross_references(acts)
        assert "Indian Penal Code, 1860" in result

    def test_short_name_ipc(self):
        acts = ["IPC, Section 420"]
        result = enrich_statute_cross_references(acts)
        assert any("BNS" in a or "Bharatiya Nyaya Sanhita" in a for a in result)
