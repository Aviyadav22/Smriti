"""Unit tests for Indian legal citation and act reference extraction."""

import pytest

from app.core.legal.extractor import (
    extract_acts_cited,
    extract_citations,
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
# A2: Article sub-clause and read-with patterns
# ---------------------------------------------------------------------------


class TestArticleSubClauses:
    """A2: Article regex handles sub-clauses, suffixes, and read-with."""

    def test_article_19_1_a(self):
        text = "The right under Article 19(1)(a) is fundamental."
        acts = extract_acts_cited(text)
        art = [a for a in acts if "19(1)(a)" in a.section]
        assert len(art) >= 1
        assert art[0].act_name == "Constitution of India"

    def test_article_226_1(self):
        text = "The High Court under Article 226(1) may issue writs."
        acts = extract_acts_cited(text)
        art = [a for a in acts if "226(1)" in a.section]
        assert len(art) >= 1
        assert art[0].act_name == "Constitution of India"

    def test_article_368A(self):
        text = "Article 368A was considered."
        acts = extract_acts_cited(text)
        art = [a for a in acts if "368A" in a.section]
        assert len(art) >= 1
        assert art[0].act_name == "Constitution of India"

    def test_article_21_read_with_14(self):
        text = "Article 21 read with Article 14 of the Constitution"
        acts = extract_acts_cited(text)
        art21 = [a for a in acts if a.section == "Article 21"]
        art14 = [a for a in acts if a.section == "Article 14"]
        assert len(art21) >= 1
        assert len(art14) >= 1
        assert art21[0].act_name == "Constitution of India"
        assert art14[0].act_name == "Constitution of India"

    def test_article_rw_shorthand(self):
        text = "Art. 19(1)(a) r/w Art. 21"
        acts = extract_acts_cited(text)
        art19 = [a for a in acts if "19(1)(a)" in a.section]
        art21 = [a for a in acts if "21" in a.section and "19" not in a.section]
        assert len(art19) >= 1
        assert len(art21) >= 1


# ---------------------------------------------------------------------------
# A10: Regulation, Clause, Schedule, Form patterns
# ---------------------------------------------------------------------------


class TestRegulationClausePatterns:
    """A10: Order/Rule/Regulation/Schedule/Clause/Form reference extraction."""

    def test_regulation_sebi(self):
        text = "Regulation 3 of SEBI Act Regulations, 2015"
        acts = extract_acts_cited(text)
        reg = [a for a in acts if "Regulation 3" in a.section]
        assert len(reg) >= 1

    def test_clause_pattern(self):
        text = "Clause 49 of SEBI Act"
        acts = extract_acts_cited(text)
        clause = [a for a in acts if "Clause 49" in a.section]
        assert len(clause) >= 1

    def test_order_rule_cpc(self):
        text = "Order 39 Rule 1 CPC"
        acts = extract_acts_cited(text)
        order = [a for a in acts if "Order 39 Rule 1" in a.section]
        assert len(order) >= 1
        assert order[0].act_name == "Code of Civil Procedure"

    def test_order_rule_without_cpc(self):
        text = "Order VII Rule 11 of the Code of Civil Procedure"
        acts = extract_acts_cited(text)
        order = [a for a in acts if "Order VII Rule 11" in a.section]
        assert len(order) >= 1


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


class TestExpandedHCReporters:
    """Test newly added HC reporter patterns."""

    def test_lnind_citation(self):
        text = "2020 LNIND 145"
        citations = extract_citations(text)
        assert any(c.reporter == "LNIND" and c.year == 2020 for c in citations)

    def test_cdj_citation(self):
        text = "(2021) CDJ 300"
        citations = extract_citations(text)
        assert any(c.reporter == "CDJ" and c.year == 2021 for c in citations)

    def test_bomlr_citation(self):
        text = "2019 BomLR 450"
        citations = extract_citations(text)
        assert any(c.reporter.upper() == "BOMLR" and c.year == 2019 for c in citations)

    def test_calwn_citation(self):
        text = "(2022) CalWN 120"
        citations = extract_citations(text)
        assert any(c.reporter.upper() == "CALWN" and c.year == 2022 for c in citations)

    def test_wlr_citation(self):
        text = "2023 WLR 88"
        citations = extract_citations(text)
        assert any(c.reporter == "WLR" and c.year == 2023 for c in citations)

    def test_mplj_citation(self):
        text = "(2020) 2 MPLJ 300"
        citations = extract_citations(text)
        assert any(c.reporter == "MPLJ" and c.year == 2020 for c in citations)


class TestGenericReporterCatchAll:
    """Test catch-all pattern for unknown reporter formats."""

    def test_unknown_reporter_caught(self):
        text = "2023 XYZLR 456"
        citations = extract_citations(text)
        assert any(c.reporter == "Unknown" and c.year == 2023 for c in citations)

    def test_catch_all_does_not_duplicate_known(self):
        """Known reporters should NOT produce an extra Unknown citation."""
        text = "(2020) 3 SCC 145"
        citations = extract_citations(text)
        assert not any(c.reporter == "Unknown" for c in citations)

    def test_catch_all_capped_at_10(self):
        """At most 10 catch-all matches per document."""
        lines = [f"2020 XREP{chr(65+i)} {100 + i}" for i in range(20)]
        text = "\n".join(lines)
        citations = extract_citations(text)
        unknown_count = sum(1 for c in citations if c.reporter == "Unknown")
        assert unknown_count <= 10

    def test_catch_all_skips_common_words(self):
        """Common English words should not be caught."""
        text = "2020 Court 145 and 2020 State 200"
        citations = extract_citations(text)
        assert not any(c.reporter == "Unknown" for c in citations)


# ---------------------------------------------------------------------------
# Garbage filter: _is_valid_act_citation() hardening
# ---------------------------------------------------------------------------

from app.core.legal.extractor import _is_valid_act_citation, normalize_acts_cited_list


class TestActsCitedGarbageFilter:
    """Test that sentence fragments and garbage are rejected by _is_valid_act_citation."""

    @pytest.mark.parametrize("garbage", [
        "those candidates who went ahead",
        "Erstwhile Act which governed the field",
        "empowers the resolution professional",
        "how accused",
        "how the accused",
        "Act of",
        "Act plainly",
        "society",
        "subsequently",
        "new Act so as to include even a petitioner",
        "2013 Act deals with a scenario wherein",
        "Erstwhile Act before the High Court",
        "Erstwhile Act to the appellant company",
        "an offence punishable under Section 4 of the PMLA",
        "deposit of cash amount of Rs",
        "PMLA punishable under Section 4",
        "IBC by any of the petitioners",
        "1963 Act as well",
        "Act may be compared with Sections 4",
    ])
    def test_rejects_sentence_fragments(self, garbage):
        assert not _is_valid_act_citation(garbage), f"Should reject: {garbage!r}"

    @pytest.mark.parametrize("garbage", [
        "Section 95",
        "Section 302",
        "Article 21",
        "Section 313CrPC",
        "Chapter III of Part III",
        "Part II",
        "Section 18",
        "Sections 4 and 5",
    ])
    def test_rejects_standalone_section_article_references(self, garbage):
        assert not _is_valid_act_citation(garbage), f"Should reject: {garbage!r}"

    @pytest.mark.parametrize("garbage", [
        "Madras5",
        "Part III 57",
    ])
    def test_rejects_digit_glued_to_text(self, garbage):
        assert not _is_valid_act_citation(garbage), f"Should reject: {garbage!r}"

    @pytest.mark.parametrize("valid", [
        "IPC",
        "CrPC",
        "CRPC",
        "COI",
        "BNS",
        "NDPS ACT",
        "Indian Penal Code",
        "Motor Vehicles Act",
        "Limitation Act",
        "CA2013",
        "Transfer of Property Act",
        "Right to Fair Compensation Act",
        "RFCTLARR ACT",
    ])
    def test_accepts_legitimate_act_names(self, valid):
        assert _is_valid_act_citation(valid), f"Should accept: {valid!r}"


class TestActsCitedCanonicalDedup:
    """Test that normalize_acts_cited_list deduplicates variant short codes."""

    def test_crpc_variants_collapse(self):
        result = normalize_acts_cited_list(["CRPC", "CR.P.C.", "CrPC"])
        # All variants of Code of Criminal Procedure should collapse to one entry
        assert len(result) == 1

    def test_ipc_variants_collapse(self):
        result = normalize_acts_cited_list(["IPC", "I.P.C."])
        assert len(result) == 1

    def test_garbage_filtered_before_dedup(self):
        result = normalize_acts_cited_list([
            "IPC",
            "those candidates who went ahead",
            "Section 95",
            "Madras5",
        ])
        assert "IPC" in result or any("Penal" in r for r in result)
        assert len(result) == 1  # Only IPC survives
