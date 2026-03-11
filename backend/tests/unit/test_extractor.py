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


# ---------------------------------------------------------------------------
# B7: Tightened AIR pattern — known court codes only
# ---------------------------------------------------------------------------


class TestAIRPatternTightened:
    """B7: AIR pattern should only match known court codes."""

    def test_air_known_court_code_matches(self):
        text = "AIR 2020 SC 145"
        citations = extract_citations(text)
        air = [c for c in citations if c.reporter == "AIR"]
        assert len(air) == 1
        assert air[0].year == 2020
        assert air[0].page == "145"
        assert air[0].court == "Supreme Court of India"

    def test_air_unknown_court_code_does_not_match(self):
        text = "AIR 2020 RANDOM 145"
        citations = extract_citations(text)
        air = [c for c in citations if c.reporter == "AIR"]
        assert len(air) == 0

    def test_air_with_dots_known_code(self):
        text = "A.I.R. 2020 Bom 300"
        citations = extract_citations(text)
        air = [c for c in citations if c.reporter == "AIR"]
        assert len(air) == 1
        assert air[0].court == "High Court of Bombay"


# ---------------------------------------------------------------------------
# B8: Section range parsing
# ---------------------------------------------------------------------------


class TestSectionRangeParsing:
    """B8: _parse_section_list should expand ranges."""

    def test_section_range_dash(self):
        text = "Sections 302-304 IPC"
        acts = extract_acts_cited(text)
        ipc = [a for a in acts if a.act_name == "Indian Penal Code"]
        sections = {a.section for a in ipc}
        assert "302" in sections
        assert "303" in sections
        assert "304" in sections

    def test_section_range_to(self):
        text = "Sections 302 to 307 IPC"
        acts = extract_acts_cited(text)
        ipc = [a for a in acts if a.act_name == "Indian Penal Code"]
        sections = {a.section for a in ipc}
        for i in range(302, 308):
            assert str(i) in sections, f"Section {i} missing"


# ---------------------------------------------------------------------------
# B9: "read with" / "r/w" pattern
# ---------------------------------------------------------------------------


class TestReadWithPattern:
    """B9: Section X read with Section Y should capture both."""

    def test_read_with_full(self):
        text = "Section 302 read with Section 34 IPC"
        acts = extract_acts_cited(text)
        ipc = [a for a in acts if a.act_name == "Indian Penal Code"]
        sections = {a.section for a in ipc}
        assert "302" in sections
        assert "34" in sections

    def test_rw_shorthand(self):
        text = "Section 120B r/w Section 34 IPC"
        acts = extract_acts_cited(text)
        ipc = [a for a in acts if a.act_name == "Indian Penal Code"]
        sections = {a.section for a in ipc}
        assert "120B" in sections
        assert "34" in sections

    def test_read_with_no_second_section_prefix(self):
        text = "Section 302 read with 34 IPC"
        acts = extract_acts_cited(text)
        ipc = [a for a in acts if a.act_name == "Indian Penal Code"]
        sections = {a.section for a in ipc}
        assert "302" in sections
        assert "34" in sections


# ---------------------------------------------------------------------------
# B10: Bare "Article N" defaults to Constitution for N <= 395
# ---------------------------------------------------------------------------


class TestBareArticleConstitution:
    """B10: Bare Article N for valid constitutional articles."""

    def test_bare_article_21_defaults_to_constitution(self):
        text = "The petitioner invoked Article 21."
        acts = extract_acts_cited(text)
        art21 = [a for a in acts if "Article 21" in a.section]
        assert len(art21) >= 1
        assert art21[0].act_name == "Constitution of India"
        assert art21[0].year == 1950

    def test_bare_article_500_defaults_to_unknown(self):
        text = "Article 500 of the Treaty"
        acts = extract_acts_cited(text)
        art500 = [a for a in acts if "Article 500" in a.section]
        assert len(art500) >= 1
        assert art500[0].act_name == "Unknown Act"

    def test_article_with_constitution_still_works(self):
        text = "Article 14 of the Constitution"
        acts = extract_acts_cited(text)
        art14 = [a for a in acts if "Article 14" in a.section]
        assert len(art14) >= 1
        assert art14[0].act_name == "Constitution of India"


# ---------------------------------------------------------------------------
# B15: New short act names
# ---------------------------------------------------------------------------


class TestNewShortActNames:
    """B15: New short act name codes resolve correctly."""

    @pytest.mark.parametrize("code,expected", [
        ("RERA", "Real Estate (Regulation and Development) Act"),
        ("POSH ACT", "Prevention of Sexual Harassment at Workplace Act"),
        ("JJ ACT", "Juvenile Justice (Care and Protection of Children) Act"),
        ("MCOCA", "Maharashtra Control of Organised Crime Act"),
        ("COFEPOSA", "Conservation of Foreign Exchange and Prevention of Smuggling Activities Act"),
        ("ESI ACT", "Employees' State Insurance Act"),
        ("ID ACT", "Industrial Disputes Act"),
        ("COMPETITION ACT", "Competition Act"),
        ("CUSTOMS ACT", "Customs Act"),
        ("RBI ACT", "Reserve Bank of India Act"),
    ])
    def test_short_act_resolves(self, code, expected):
        text = f"Section 5 {code}"
        acts = extract_acts_cited(text)
        matching = [a for a in acts if a.act_name == expected]
        assert len(matching) >= 1, f"Expected act '{expected}' for code '{code}'"


# ---------------------------------------------------------------------------
# B15 dedup: Semantic dedup (act_name + section)
# ---------------------------------------------------------------------------


class TestActSemanticDedup:
    """B15 dedup: Same act+section from different raw_text is deduplicated."""

    def test_duplicate_act_section_deduped(self):
        text = "Section 302 IPC and also S. 302 IPC"
        acts = extract_acts_cited(text)
        sec302 = [a for a in acts if a.section == "302" and a.act_name == "Indian Penal Code"]
        assert len(sec302) == 1


# ---------------------------------------------------------------------------
# B16: New citation reporter patterns
# ---------------------------------------------------------------------------


class TestNewCitationReporters:
    """B16: LiveLaw, ITR, Taxmann, CompCas, LLJ patterns."""

    def test_livelaw_citation(self):
        text = "2024 LiveLaw (SC) 123"
        citations = extract_citations(text)
        ll = [c for c in citations if c.reporter == "LiveLaw"]
        assert len(ll) == 1
        assert ll[0].year == 2024
        assert ll[0].page == "123"
        assert ll[0].court == "SC"

    def test_itr_citation(self):
        text = "[2020] 123 ITR 456"
        citations = extract_citations(text)
        itr = [c for c in citations if c.reporter == "ITR"]
        assert len(itr) == 1
        assert itr[0].year == 2020
        assert itr[0].volume == "123"
        assert itr[0].page == "456"

    def test_taxmann_citation(self):
        text = "[2020] 123 taxmann.com 456"
        citations = extract_citations(text)
        tx = [c for c in citations if c.reporter == "Taxmann"]
        assert len(tx) == 1
        assert tx[0].year == 2020
        assert tx[0].volume == "123"
        assert tx[0].page == "456"

    def test_compcas_citation(self):
        text = "(2020) 123 CompCas 456"
        citations = extract_citations(text)
        cc = [c for c in citations if c.reporter == "CompCas"]
        assert len(cc) == 1
        assert cc[0].year == 2020
        assert cc[0].volume == "123"
        assert cc[0].page == "456"

    def test_llj_citation(self):
        text = "2020 LLJ 123"
        citations = extract_citations(text)
        llj = [c for c in citations if c.reporter == "LLJ"]
        assert len(llj) == 1
        assert llj[0].year == 2020
        assert llj[0].page == "123"

    def test_itr_with_parens(self):
        text = "(2021) 456 ITR 789"
        citations = extract_citations(text)
        itr = [c for c in citations if c.reporter == "ITR"]
        assert len(itr) == 1
        assert itr[0].year == 2021
