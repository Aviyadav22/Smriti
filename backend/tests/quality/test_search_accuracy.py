"""Search accuracy benchmark tests.

These tests verify that the search pipeline returns relevant results
for common legal queries. Run against a populated database.

Usage:
    pytest tests/quality/test_search_accuracy.py -m integration --timeout=30
"""

from __future__ import annotations

import pytest

# Benchmark queries with expected results
# Each entry: (query, expected_keywords_in_top_5, expected_case_fragment)
CITATION_QUERIES = [
    (
        "K.S. Puttaswamy v. Union of India",
        ["privacy", "Puttaswamy"],
        "Puttaswamy",
    ),
    (
        "Kesavananda Bharati v. State of Kerala",
        ["basic structure", "Kesavananda"],
        "Kesavananda",
    ),
    (
        "Maneka Gandhi v. Union of India",
        ["Article 21", "Maneka Gandhi"],
        "Maneka",
    ),
    (
        "Vishaka v. State of Rajasthan",
        ["sexual harassment", "Vishaka"],
        "Vishaka",
    ),
    (
        "Shreya Singhal v. Union of India",
        ["Section 66A", "Shreya Singhal"],
        "Shreya",
    ),
]

TOPICAL_QUERIES = [
    (
        "right to privacy fundamental right",
        ["privacy", "Article 21"],
    ),
    (
        "anticipatory bail conditions Supreme Court",
        ["bail", "Section 438"],
    ),
    (
        "environmental protection public interest litigation",
        ["environment", "PIL"],
    ),
    (
        "freedom of speech reasonable restrictions",
        ["Article 19", "speech"],
    ),
    (
        "land acquisition compensation fair market value",
        ["acquisition", "compensation"],
    ),
    (
        "divorce mutual consent waiting period",
        ["divorce", "mutual consent"],
    ),
    (
        "motor accident claims tribunal compensation",
        ["accident", "compensation"],
    ),
    (
        "arbitration clause validity",
        ["arbitration", "clause"],
    ),
    (
        "dowry harassment Section 498A",
        ["dowry", "498A"],
    ),
    (
        "contempt of court scandalizing judiciary",
        ["contempt", "court"],
    ),
]

HINDI_QUERIES = [
    (
        "निजता का अधिकार",
        ["privacy", "right"],
    ),
    (
        "अग्रिम जमानत शर्तें",
        ["bail", "anticipatory"],
    ),
    (
        "अनुच्छेद 21 जीवन का अधिकार",
        ["Article 21", "life"],
    ),
]


@pytest.mark.integration
class TestCitationSearch:
    """Verify citation lookups return the exact case in top results."""

    @pytest.mark.parametrize("query,keywords,fragment", CITATION_QUERIES)
    async def test_citation_in_top_5(
        self,
        query: str,
        keywords: list[str],
        fragment: str,
        search_client,
    ) -> None:
        """Citation search should return the cited case in top 5 results."""
        results = await search_client.search(query, page_size=5)
        titles = " ".join(r.get("title", "") for r in results)
        assert fragment.lower() in titles.lower(), (
            f"Expected '{fragment}' in top 5 results for query '{query}', "
            f"got: {titles}"
        )


@pytest.mark.integration
class TestTopicalSearch:
    """Verify topical queries return results containing expected keywords."""

    @pytest.mark.parametrize("query,keywords", TOPICAL_QUERIES)
    async def test_keywords_in_results(
        self,
        query: str,
        keywords: list[str],
        search_client,
    ) -> None:
        """Topical search should return results with relevant keywords."""
        results = await search_client.search(query, page_size=10)
        all_text = " ".join(
            f"{r.get('title', '')} {r.get('snippet', '')}" for r in results
        ).lower()
        for kw in keywords:
            assert kw.lower() in all_text, (
                f"Expected keyword '{kw}' in results for query '{query}'"
            )


@pytest.mark.integration
class TestHindiSearch:
    """Verify Hindi queries return relevant English results."""

    @pytest.mark.parametrize("query,expected_keywords", HINDI_QUERIES)
    async def test_hindi_returns_results(
        self,
        query: str,
        expected_keywords: list[str],
        search_client,
    ) -> None:
        """Hindi query should be translated and return relevant results."""
        results = await search_client.search(query, language="hi", page_size=5)
        assert len(results) > 0, f"No results for Hindi query: {query}"
