"""Tests for citation treatment detection wired into the ingestion pipeline.

Verifies that _build_citation_graph calls detect_treatment_in_text for each
citation, stores the treatment property on CITES edges, and defaults to
"referred_to" when no treatment language is detected.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.core.ingestion.metadata import CaseMetadata
from app.core.ingestion.pipeline import _build_citation_graph
from app.core.legal.extractor import Citation
from app.core.legal.treatment import CitationTreatment, TreatmentResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_case_metadata(**overrides) -> CaseMetadata:
    defaults = {
        "title": "State v. Kumar",
        "citation": "(2023) 5 SCC 123",
        "court": "Supreme Court of India",
        "judge": ["Justice Sharma"],
        "author_judge": "Justice Sharma",
        "year": 2023,
        "decision_date": "2023-03-15",
        "case_type": "Civil Appeal",
        "bench_type": "Division Bench",
        "jurisdiction": "Civil",
        "petitioner": "State of Maharashtra",
        "respondent": "Rajesh Kumar",
        "ratio_decidendi": "Personal hearing is mandatory",
        "acts_cited": ["Land Acquisition Act, 2013"],
        "cases_cited": ["(2019) 5 SCC 234"],
        "keywords": ["land acquisition"],
        "disposal_nature": "Dismissed",
    }
    defaults.update(overrides)
    return CaseMetadata(**defaults)


def _make_citation(raw_text: str, reporter: str = "SCC") -> Citation:
    return Citation(
        reporter=reporter,
        year=2019,
        volume="5",
        page="234",
        court=None,
        raw_text=raw_text,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.ingestion.pipeline.extract_citations")
@patch("app.core.ingestion.pipeline.detect_treatment_in_text")
async def test_treatment_detected_for_each_citation(mock_detect, mock_extract):
    """detect_treatment_in_text is called once per citation found in the text."""
    cit1 = _make_citation("(2019) 5 SCC 234")
    cit2 = _make_citation("(2020) 3 SCC 456")
    mock_extract.return_value = [cit1, cit2]

    # Return treatment results for each call
    mock_detect.side_effect = [
        [TreatmentResult(CitationTreatment.AFFIRMED, "affirmed context", 0.5)],
        [TreatmentResult(CitationTreatment.OVERRULED, "overruled context", 0.7)],
    ]

    full_text = (
        "Some preamble text. "
        "The Court in (2019) 5 SCC 234 affirmed the principle. "
        "However, (2020) 3 SCC 456 was overruled in this matter."
    )

    graph_store = AsyncMock()
    metadata = _make_case_metadata()

    await _build_citation_graph("case-123", metadata, full_text, graph_store)

    assert mock_detect.call_count == 2


@pytest.mark.asyncio
@patch("app.core.ingestion.pipeline.extract_citations")
@patch("app.core.ingestion.pipeline.detect_treatment_in_text")
async def test_default_referred_to_when_no_treatment(mock_detect, mock_extract):
    """When detect_treatment_in_text returns empty list, treatment defaults to 'referred_to'."""
    cit = _make_citation("(2019) 5 SCC 234")
    mock_extract.return_value = [cit]
    mock_detect.return_value = []  # No treatment detected

    full_text = "The Court referred to (2019) 5 SCC 234 in passing."

    graph_store = AsyncMock()
    metadata = _make_case_metadata()

    await _build_citation_graph("case-123", metadata, full_text, graph_store)

    # With batched approach, the CITES edge query uses UNWIND with edges param
    cites_call = [
        c for c in graph_store.query.call_args_list
        if "r:CITES" in str(c.args[0])
    ]
    assert len(cites_call) == 1
    edges = cites_call[0].kwargs["params"]["edges"]
    assert edges[0]["treatment"] == "referred_to"


@pytest.mark.asyncio
@patch("app.core.ingestion.pipeline.extract_citations")
@patch("app.core.ingestion.pipeline.detect_treatment_in_text")
async def test_treatment_property_passed_to_graph_store(mock_detect, mock_extract):
    """The treatment value is passed as a parameter to the CITES edge MERGE query."""
    cit = _make_citation("(2019) 5 SCC 234")
    mock_extract.return_value = [cit]
    mock_detect.return_value = [
        TreatmentResult(CitationTreatment.DISTINGUISHED, "distinguished context", 0.7),
    ]

    full_text = "The Court distinguished (2019) 5 SCC 234 on facts."

    graph_store = AsyncMock()
    metadata = _make_case_metadata()

    await _build_citation_graph("case-123", metadata, full_text, graph_store)

    # Find the CITES edge call (uses UNWIND with edges param)
    cites_calls = [
        c for c in graph_store.query.call_args_list
        if "r:CITES" in str(c.args[0])
    ]
    assert len(cites_calls) == 1

    params = cites_calls[0].kwargs["params"]
    assert params["from_id"] == "case-123"
    edges = params["edges"]
    assert edges[0]["treatment"] == "distinguished"
    assert edges[0]["reporter"] == "SCC"


@pytest.mark.asyncio
@patch("app.core.ingestion.pipeline.extract_citations")
@patch("app.core.ingestion.pipeline.detect_treatment_in_text")
async def test_highest_confidence_treatment_picked(mock_detect, mock_extract):
    """When multiple treatments are detected, the highest confidence one wins."""
    cit = _make_citation("(2019) 5 SCC 234")
    mock_extract.return_value = [cit]
    mock_detect.return_value = [
        TreatmentResult(CitationTreatment.FOLLOWED, "followed context", 0.5),
        TreatmentResult(CitationTreatment.OVERRULED, "overruled context", 0.7),
        TreatmentResult(CitationTreatment.EXPLAINED, "explained context", 0.3),
    ]

    full_text = "Discussion of (2019) 5 SCC 234 with various references."

    graph_store = AsyncMock()
    metadata = _make_case_metadata()

    await _build_citation_graph("case-123", metadata, full_text, graph_store)

    cites_calls = [
        c for c in graph_store.query.call_args_list
        if "r:CITES" in str(c.args[0])
    ]
    edges = cites_calls[0].kwargs["params"]["edges"]
    assert edges[0]["treatment"] == "overruled"


@pytest.mark.asyncio
@patch("app.core.ingestion.pipeline.extract_citations")
@patch("app.core.ingestion.pipeline.detect_treatment_in_text")
async def test_citation_not_found_in_text_defaults_referred_to(mock_detect, mock_extract):
    """When citation raw_text is not found in full_text, treatment defaults to 'referred_to'."""
    cit = _make_citation("(2019) 5 SCC 234")
    mock_extract.return_value = [cit]

    # full_text does NOT contain the citation raw_text
    full_text = "Some text that does not contain the citation at all."

    graph_store = AsyncMock()
    metadata = _make_case_metadata()

    await _build_citation_graph("case-123", metadata, full_text, graph_store)

    # detect_treatment_in_text should NOT be called since citation not found
    mock_detect.assert_not_called()

    cites_calls = [
        c for c in graph_store.query.call_args_list
        if "r:CITES" in str(c.args[0])
    ]
    edges = cites_calls[0].kwargs["params"]["edges"]
    assert edges[0]["treatment"] == "referred_to"
