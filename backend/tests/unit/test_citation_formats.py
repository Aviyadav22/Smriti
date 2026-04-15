"""Tests for Indian legal citation format extraction.

Covers the 5 key citation formats used in Indian legal practice:
1. SCC — Supreme Court Cases: (2024) 5 SCC 142
2. AIR — All India Reporter: AIR 2019 SC 2005
3. INSC Neutral — 2024:INSC:123
4. MANU — Manupatra: MANU/SC/1234/2020
5. LiveLaw — LiveLaw (SC) 123/2024

These formats are critical for citation verification and search — lawyers
cite cases in these formats in court filings and research memos.
"""

from app.core.legal.extractor import extract_citations, normalize_citation


class TestSCCCitations:
    """SCC (Supreme Court Cases) — most common Indian law reporter."""

    def test_standard_scc(self):
        """Standard format: (2024) 5 SCC 142."""
        citations = extract_citations("The court relied on (2024) 5 SCC 142.")
        assert len(citations) >= 1
        scc = [c for c in citations if c.reporter == "SCC"]
        assert len(scc) >= 1
        assert scc[0].year == 2024
        assert scc[0].page == "142"

    def test_scc_with_volume(self):
        """SCC with volume: (2023) 3 SCC 456."""
        citations = extract_citations("(2023) 3 SCC 456 was followed.")
        scc = [c for c in citations if c.reporter == "SCC"]
        assert len(scc) >= 1
        assert scc[0].volume == "3"

    def test_scc_online(self):
        """SCC OnLine format: 2024 SCC OnLine SC 789."""
        citations = extract_citations("2024 SCC OnLine SC 789")
        matches = [c for c in citations if "SCC" in c.reporter]
        assert len(matches) >= 1

    def test_scc_sub_reporter(self):
        """SCC sub-reporter: (2020) 4 SCC (Cri) 100."""
        citations = extract_citations("As held in (2020) 4 SCC (Cri) 100.")
        scc = [c for c in citations if "SCC" in c.reporter]
        assert len(scc) >= 1


class TestAIRCitations:
    """AIR (All India Reporter) — oldest Indian law reporter."""

    def test_air_supreme_court(self):
        """AIR SC: AIR 2019 SC 2005."""
        citations = extract_citations("AIR 2019 SC 2005 held that...")
        air = [c for c in citations if c.reporter == "AIR"]
        assert len(air) >= 1
        assert air[0].year == 2019
        # Court code may be expanded to full name
        assert air[0].court is not None
        assert "SC" in air[0].raw_text

    def test_air_high_court(self):
        """AIR HC: AIR 2020 Bom 145."""
        citations = extract_citations("Refer to AIR 2020 Bom 145.")
        air = [c for c in citations if c.reporter == "AIR"]
        assert len(air) >= 1
        assert air[0].court is not None

    def test_air_delhi(self):
        """AIR Delhi: AIR 2018 Del 302."""
        citations = extract_citations("AIR 2018 Del 302 is relevant.")
        air = [c for c in citations if c.reporter == "AIR"]
        assert len(air) >= 1


class TestINSCNeutralCitations:
    """INSC Neutral citations — 2024:INSC:123 format (post-2024 SC)."""

    def test_neutral_citation(self):
        """Standard neutral: 2024:INSC:123."""
        citations = extract_citations("The judgment at 2024:INSC:123 states...")
        neutral = [c for c in citations if c.reporter == "INSC"]
        assert len(neutral) >= 1
        assert neutral[0].year == 2024

    def test_neutral_with_spaces_after_normalization(self):
        """Neutral with spaces should be normalized then extracted."""
        text = "See 2023 : INSC : 456 for the ratio."
        normalized = normalize_citation(text)
        citations = extract_citations(normalized)
        neutral = [c for c in citations if c.reporter == "INSC" or "INSC" in c.raw_text]
        assert len(neutral) >= 1


class TestMANUCitations:
    """MANU (Manupatra) — major Indian legal database."""

    def test_manu_supreme_court(self):
        """MANU SC: MANU/SC/1234/2020."""
        citations = extract_citations("MANU/SC/1234/2020 is a landmark judgment.")
        manu = [c for c in citations if c.reporter == "MANU"]
        assert len(manu) >= 1
        assert manu[0].year == 2020
        assert manu[0].court == "SC"

    def test_manu_high_court(self):
        """MANU HC: MANU/DE/5678/2023 (Delhi HC)."""
        citations = extract_citations("See MANU/DE/5678/2023 for this point.")
        manu = [c for c in citations if c.reporter == "MANU"]
        assert len(manu) >= 1
        assert manu[0].court == "DE"
        assert manu[0].year == 2023

    def test_manu_with_spaces(self):
        """MANU with spaces should be normalized: MANU / SC / 1234 / 2020."""
        normalized = normalize_citation("MANU / SC / 1234 / 2020")
        assert "MANU/SC/1234/2020" in normalized


class TestLiveLawCitations:
    """LiveLaw — modern Indian legal news/case reporter."""

    def test_livelaw_sc(self):
        """LiveLaw SC: 2024 LiveLaw (SC) 123."""
        citations = extract_citations("2024 LiveLaw (SC) 123 was reported.")
        ll = [c for c in citations if "LiveLaw" in c.reporter or "LiveLaw" in c.raw_text]
        assert len(ll) >= 1

    def test_livelaw_hc(self):
        """LiveLaw HC: 2023 LiveLaw (Del) 456."""
        citations = extract_citations("2023 LiveLaw (Del) 456 discusses bail.")
        ll = [c for c in citations if "LiveLaw" in c.reporter or "LiveLaw" in c.raw_text]
        assert len(ll) >= 1


class TestNormalizeCitation:
    """normalize_citation() should standardize citation formats."""

    def test_normalize_scc_brackets(self):
        """Square brackets → round brackets for SCC: [2024] 5 SCC 142 → (2024) 5 SCC 142."""
        result = normalize_citation("[2024] 5 SCC 142")
        assert "(2024)" in result

    def test_normalize_neutral_separators(self):
        """Normalize colon separators: 2024 : INSC : 123 → 2024:INSC:123."""
        result = normalize_citation("2024 : INSC : 123")
        assert "2024:INSC:123" in result

    def test_normalize_manu_spaces(self):
        """Normalize MANU path: MANU / SC / 1234 / 2020 → MANU/SC/1234/2020."""
        result = normalize_citation("MANU / SC / 1234 / 2020")
        assert "MANU/SC/1234/2020" in result

    def test_normalize_versus(self):
        """Normalize party names: 'versus' → 'v.'."""
        result = normalize_citation("State versus Kumar")
        assert "v." in result
