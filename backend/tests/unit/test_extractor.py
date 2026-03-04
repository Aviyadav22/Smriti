"""Unit tests for Indian legal citation and act reference extraction."""

import pytest

from app.core.legal.extractor import (
    Citation,
    ActReference,
    extract_citations,
    extract_acts_cited,
    normalize_citation,
)


class TestExtractCitations:
    """Tests for extract_citations()."""

    def test_scc_citation(self):
        text = "as held in (2020) 3 SCC 145"
        citations = extract_citations(text)
        assert len(citations) >= 1
        scc = [c for c in citations if c.reporter == "SCC"]
        assert len(scc) == 1
        assert scc[0].year == 2020
        assert scc[0].volume == "3"
        assert scc[0].page == "145"

    def test_air_citation(self):
        text = "reported in AIR 2019 SC 3452"
        citations = extract_citations(text)
        air = [c for c in citations if c.reporter == "AIR"]
        assert len(air) == 1
        assert air[0].year == 2019
        assert air[0].court == "Supreme Court of India"

    def test_insc_citation(self):
        text = "2023 INSC 789"
        citations = extract_citations(text)
        insc = [c for c in citations if c.reporter == "INSC"]
        assert len(insc) == 1
        assert insc[0].year == 2023
        assert insc[0].page == "789"

    def test_scc_online_citation(self):
        text = "2021 SCC OnLine SC 1234"
        citations = extract_citations(text)
        online = [c for c in citations if c.reporter == "SCC OnLine"]
        assert len(online) == 1
        assert online[0].year == 2021

    def test_scr_citation(self):
        text = "[2018] 5 SCR 200"
        citations = extract_citations(text)
        scr = [c for c in citations if c.reporter == "SCR"]
        assert len(scr) == 1
        assert scr[0].year == 2018

    def test_crlj_citation(self):
        text = "2022 CrLJ 567"
        citations = extract_citations(text)
        crlj = [c for c in citations if c.reporter == "CrLJ"]
        assert len(crlj) == 1

    def test_scale_citation(self):
        text = "(2019) 2 SCALE 300"
        citations = extract_citations(text)
        scale = [c for c in citations if c.reporter == "SCALE"]
        assert len(scale) == 1

    def test_multiple_citations_in_text(self):
        text = (
            "See (2020) 3 SCC 145 and AIR 2019 SC 3452. "
            "Also 2023 INSC 789."
        )
        citations = extract_citations(text)
        assert len(citations) >= 3

    def test_no_citations(self):
        text = "This text contains no legal citations at all."
        citations = extract_citations(text)
        assert len(citations) == 0

    def test_citation_raw_text_preserved(self):
        text = "(2020) 3 SCC 145"
        citations = extract_citations(text)
        assert citations[0].raw_text == "(2020) 3 SCC 145"


class TestExtractActsCited:
    """Tests for extract_acts_cited()."""

    def test_section_of_act(self):
        text = "under Section 302 of the Indian Penal Code, 1860"
        acts = extract_acts_cited(text)
        assert len(acts) >= 1
        assert any("302" in a.section for a in acts)

    def test_article_of_constitution(self):
        text = "Article 21 of the Constitution of India"
        acts = extract_acts_cited(text)
        assert len(acts) >= 1

    def test_no_acts(self):
        text = "This paragraph discusses facts only."
        acts = extract_acts_cited(text)
        assert len(acts) == 0


class TestNormalizeCitation:
    """Tests for normalize_citation()."""

    def test_normalizes_spaces(self):
        result = normalize_citation("(2020)  3  SCC  145")
        assert "  " not in result

    def test_returns_input_unchanged_if_no_match(self):
        result = normalize_citation("some random text")
        assert result == "some random text"
