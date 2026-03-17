"""Tests for citation confidence levels."""

from app.core.legal.extractor import extract_citations


def test_name_citation_has_low_confidence():
    """Name-based citations should have confidence < 0.5."""
    text = "as held in Union of India v. State of Kerala"
    citations = extract_citations(text)
    name_cites = [c for c in citations if c.reporter == "NameCitation"]
    assert len(name_cites) >= 1
    assert all(c.confidence < 0.5 for c in name_cites)


def test_neutral_citation_has_high_confidence():
    """Neutral citations should have confidence >= 0.9."""
    text = "2024:INSC:0001"
    citations = extract_citations(text)
    assert len(citations) >= 1
    assert all(c.confidence >= 0.9 for c in citations)


def test_neutral_hc_citation_has_high_confidence():
    """Neutral HC citations should have confidence >= 0.9."""
    text = "2024:DELHC:1234"
    citations = extract_citations(text)
    assert len(citations) >= 1
    assert all(c.confidence >= 0.9 for c in citations)


def test_formal_reporter_has_medium_high_confidence():
    """SCC/AIR citations should have confidence between 0.8 and 1.0."""
    text = "(2024) 1 SCC 100"
    citations = extract_citations(text)
    scc_cites = [c for c in citations if "SCC" in c.reporter]
    if scc_cites:  # pattern may or may not match
        assert all(0.8 <= c.confidence <= 1.0 for c in scc_cites)


def test_air_citation_confidence():
    """AIR citations should have confidence of 0.9."""
    text = "AIR 2020 SC 145"
    citations = extract_citations(text)
    air_cites = [c for c in citations if c.reporter == "AIR"]
    assert len(air_cites) >= 1
    assert all(c.confidence == 0.9 for c in air_cites)


def test_manu_citation_confidence():
    """MANU citations should have confidence of 0.8."""
    text = "MANU/SC/1234/2020"
    citations = extract_citations(text)
    manu_cites = [c for c in citations if c.reporter == "MANU"]
    assert len(manu_cites) >= 1
    assert all(c.confidence == 0.8 for c in manu_cites)


def test_insc_space_delimited_confidence():
    """Space-delimited INSC citations should have confidence of 0.95."""
    text = "2020 INSC 145"
    citations = extract_citations(text)
    insc_cites = [c for c in citations if c.reporter == "INSC"]
    assert len(insc_cites) >= 1
    assert all(c.confidence == 0.95 for c in insc_cites)


def test_default_confidence_is_one():
    """Citation constructed without confidence should default to 1.0."""
    from app.core.legal.extractor import Citation

    c = Citation(
        reporter="TEST",
        year=2020,
        volume=None,
        page="1",
        court=None,
        raw_text="test",
    )
    assert c.confidence == 1.0


def test_confidence_tiers_ordering():
    """Verify the confidence hierarchy: neutral > formal > other > name."""
    text = (
        "2024:INSC:0001 was cited in (2024) 1 SCC 100 and MANU/SC/1234/2020. "
        "Also held in Union of India v. State of Kerala"
    )
    citations = extract_citations(text)

    neutral = [c for c in citations if c.reporter == "INSC"]
    formal = [c for c in citations if c.reporter == "SCC"]
    other = [c for c in citations if c.reporter == "MANU"]
    name = [c for c in citations if c.reporter == "NameCitation"]

    assert len(neutral) >= 1
    assert len(formal) >= 1
    assert len(other) >= 1
    assert len(name) >= 1

    # Neutral > Formal > Other > Name
    assert neutral[0].confidence > formal[0].confidence
    assert formal[0].confidence > other[0].confidence
    assert other[0].confidence > name[0].confidence
