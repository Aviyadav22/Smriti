"""Search accuracy tests against live database (796 cases, year 2024, Supreme Court of India).

These tests verify search quality by hitting the live API and checking that:
1. Citation lookups return the exact case
2. Topic searches return relevant results
3. Filtered searches narrow correctly

Run with: pytest tests/integration/test_search_accuracy.py -m "integration and search_accuracy"
Requires a running server (default http://localhost:8001).
"""

from __future__ import annotations

import os

import httpx
import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.getenv("SMRITI_TEST_BASE_URL", "http://localhost:8001")
SEARCH_ENDPOINT = f"{BASE_URL}/api/v1/search"
TIMEOUT = 30.0  # seconds per request — search involves LLM + vector + FTS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> httpx.AsyncClient:
    """Reusable async HTTP client for the test module."""
    return httpx.AsyncClient(timeout=TIMEOUT)


async def _search(
    client: httpx.AsyncClient,
    q: str,
    **kwargs,
) -> dict:
    """Helper to call the search endpoint and return parsed JSON."""
    params = {"q": q, **kwargs}
    resp = await client.get(SEARCH_ENDPOINT, params=params)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Citation Lookup Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.search_accuracy
class TestCitationLookup:
    """Verify that citation-style queries surface the correct case."""

    @pytest.mark.asyncio
    async def test_exact_citation_2024_insc_878(self, client: httpx.AsyncClient) -> None:
        """Search for '2024 INSC 878' should return that citation in top results."""
        data = await _search(client, "2024 INSC 878")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for exact citation lookup"
        citations = [r["citation"] for r in results if r.get("citation")]
        assert any(
            "2024 INSC 878" in c for c in citations
        ), f"Citation '2024 INSC 878' not found in top results. Got citations: {citations}"

    @pytest.mark.asyncio
    async def test_criminal_appeal_cases(self, client: httpx.AsyncClient) -> None:
        """Search for 'Criminal Appeal' should return criminal appeal cases."""
        data = await _search(client, "Criminal Appeal")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for 'Criminal Appeal'"
        has_criminal = any(
            "criminal" in (r.get("title") or "").lower()
            or "criminal" in (r.get("case_type") or "").lower()
            or "criminal appeal" in (r.get("title") or "").lower()
            for r in results
        )
        assert has_criminal, (
            "No result mentions 'criminal' in title or case_type. "
            f"Got: {[(r.get('title'), r.get('case_type')) for r in results[:5]]}"
        )

    @pytest.mark.asyncio
    async def test_civil_appeal_cases(self, client: httpx.AsyncClient) -> None:
        """Search for 'Civil Appeal' should return civil appeal cases."""
        data = await _search(client, "Civil Appeal")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for 'Civil Appeal'"
        has_civil = any(
            "civil" in (r.get("title") or "").lower()
            or "civil" in (r.get("case_type") or "").lower()
            for r in results
        )
        assert has_civil, (
            "No result mentions 'civil' in title or case_type. "
            f"Got: {[(r.get('title'), r.get('case_type')) for r in results[:5]]}"
        )

    @pytest.mark.asyncio
    async def test_slp_cases(self, client: httpx.AsyncClient) -> None:
        """Search for 'Special Leave Petition' should return SLP cases."""
        data = await _search(client, "Special Leave Petition")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for 'Special Leave Petition'"
        has_slp = any(
            "special leave" in (r.get("title") or "").lower()
            or "slp" in (r.get("case_type") or "").lower()
            or "special leave petition" in (r.get("case_type") or "").lower()
            for r in results
        )
        assert has_slp, (
            "No result mentions 'special leave' in title or case_type. "
            f"Got: {[(r.get('title'), r.get('case_type')) for r in results[:5]]}"
        )

    @pytest.mark.asyncio
    async def test_writ_petition_cases(self, client: httpx.AsyncClient) -> None:
        """Search for 'Writ Petition' should return writ petition cases."""
        data = await _search(client, "Writ Petition")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for 'Writ Petition'"
        has_writ = any(
            "writ" in (r.get("title") or "").lower()
            or "writ" in (r.get("case_type") or "").lower()
            for r in results
        )
        assert has_writ, (
            "No result mentions 'writ' in title or case_type. "
            f"Got: {[(r.get('title'), r.get('case_type')) for r in results[:5]]}"
        )


# ---------------------------------------------------------------------------
# Topic Search Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.search_accuracy
class TestTopicSearch:
    """Verify that topic-based queries return semantically relevant results."""

    @pytest.mark.asyncio
    async def test_right_to_privacy(self, client: httpx.AsyncClient) -> None:
        """Search for 'right to privacy' should return results mentioning privacy."""
        data = await _search(client, "right to privacy")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for 'right to privacy'"
        has_privacy = any(
            "privacy" in (r.get("title") or "").lower()
            or "privacy" in (r.get("snippet") or "").lower()
            or "right to privacy" in (r.get("snippet") or "").lower()
            for r in results
        )
        assert has_privacy, (
            "No result mentions 'privacy' in title or snippet. "
            f"Got titles: {[r.get('title') for r in results[:5]]}"
        )

    @pytest.mark.asyncio
    async def test_murder_section_302(self, client: httpx.AsyncClient) -> None:
        """Search for 'murder section 302' should return criminal cases."""
        data = await _search(client, "murder section 302")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for 'murder section 302'"
        criminal_keywords = {"murder", "criminal", "302", "ipc", "penal", "homicide", "death"}
        has_criminal = any(
            any(
                kw in (r.get("title") or "").lower()
                or kw in (r.get("snippet") or "").lower()
                or kw in (r.get("case_type") or "").lower()
                for kw in criminal_keywords
            )
            for r in results
        )
        assert has_criminal, (
            "No result relates to criminal/murder law. "
            f"Got titles: {[r.get('title') for r in results[:5]]}"
        )

    @pytest.mark.asyncio
    async def test_land_acquisition_compensation(self, client: httpx.AsyncClient) -> None:
        """Search for 'land acquisition compensation' should return property/land cases."""
        data = await _search(client, "land acquisition compensation")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for 'land acquisition compensation'"
        land_keywords = {"land", "acquisition", "compensation", "property", "estate", "immovable"}
        has_land = any(
            any(
                kw in (r.get("title") or "").lower()
                or kw in (r.get("snippet") or "").lower()
                for kw in land_keywords
            )
            for r in results
        )
        assert has_land, (
            "No result relates to land/property law. "
            f"Got titles: {[r.get('title') for r in results[:5]]}"
        )

    @pytest.mark.asyncio
    async def test_bail_conditions(self, client: httpx.AsyncClient) -> None:
        """Search for 'bail conditions' should return bail-related cases."""
        data = await _search(client, "bail conditions")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for 'bail conditions'"
        bail_keywords = {"bail", "anticipatory", "criminal", "custody", "remand", "surety"}
        has_bail = any(
            any(
                kw in (r.get("title") or "").lower()
                or kw in (r.get("snippet") or "").lower()
                or kw in (r.get("case_type") or "").lower()
                for kw in bail_keywords
            )
            for r in results
        )
        assert has_bail, (
            "No result relates to bail/criminal law. "
            f"Got titles: {[r.get('title') for r in results[:5]]}"
        )

    @pytest.mark.asyncio
    async def test_constitutional_validity(self, client: httpx.AsyncClient) -> None:
        """Search for 'constitutional validity' should return constitutional law cases."""
        data = await _search(client, "constitutional validity")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for 'constitutional validity'"
        const_keywords = {
            "constitution", "constitutional", "article", "fundamental",
            "validity", "writ", "ultra vires", "vires",
        }
        has_constitutional = any(
            any(
                kw in (r.get("title") or "").lower()
                or kw in (r.get("snippet") or "").lower()
                for kw in const_keywords
            )
            for r in results
        )
        assert has_constitutional, (
            "No result relates to constitutional law. "
            f"Got titles: {[r.get('title') for r in results[:5]]}"
        )


# ---------------------------------------------------------------------------
# Filtered Search Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.search_accuracy
class TestFilteredSearch:
    """Verify that search filters narrow results correctly."""

    @pytest.mark.asyncio
    async def test_court_filter_supreme_court(self, client: httpx.AsyncClient) -> None:
        """Filter by court='Supreme Court of India' should return only SC cases."""
        data = await _search(client, "judgment", court="Supreme Court of India")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result with court filter"
        for r in results:
            assert r.get("court") == "Supreme Court of India", (
                f"Expected court 'Supreme Court of India', got '{r.get('court')}' "
                f"for case {r.get('title')}"
            )

    @pytest.mark.asyncio
    async def test_year_filter_2024(self, client: httpx.AsyncClient) -> None:
        """Filter by year_from=2024 should return only 2024 cases."""
        data = await _search(client, "appeal", year_from=2024)
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result with year filter"
        for r in results:
            assert r.get("year") is not None, f"Year missing for case {r.get('title')}"
            assert r["year"] >= 2024, (
                f"Expected year >= 2024, got {r['year']} for case {r.get('title')}"
            )

    @pytest.mark.asyncio
    async def test_case_type_filter_criminal_appeal(self, client: httpx.AsyncClient) -> None:
        """Filter by case_type='Criminal Appeal' should return only Criminal Appeal cases."""
        data = await _search(client, "murder", case_type="Criminal Appeal")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result with case_type filter"
        for r in results:
            assert r.get("case_type") is not None, (
                f"Case type missing for case {r.get('title')}"
            )
            assert "criminal" in r["case_type"].lower(), (
                f"Expected case_type containing 'criminal', got '{r['case_type']}' "
                f"for case {r.get('title')}"
            )

    @pytest.mark.asyncio
    async def test_combined_topic_and_case_type(self, client: httpx.AsyncClient) -> None:
        """Combined: topic 'murder' + case_type='Criminal Appeal' should intersect."""
        data = await _search(client, "murder", case_type="Criminal Appeal")
        results = data["results"]

        assert len(results) >= 1, "Expected at least 1 result for combined filter"

        # All results should be Criminal Appeal type
        for r in results:
            assert "criminal" in (r.get("case_type") or "").lower(), (
                f"Expected criminal case_type, got '{r.get('case_type')}'"
            )

        # At least one result should relate to murder in title or snippet
        murder_keywords = {"murder", "302", "homicide", "killing", "death"}
        has_murder = any(
            any(
                kw in (r.get("title") or "").lower()
                or kw in (r.get("snippet") or "").lower()
                for kw in murder_keywords
            )
            for r in results
        )
        assert has_murder, (
            "No result in Criminal Appeal cases relates to murder. "
            f"Got titles: {[r.get('title') for r in results[:5]]}"
        )

    @pytest.mark.asyncio
    async def test_page_size_limit(self, client: httpx.AsyncClient) -> None:
        """Search with page_size=3 should return at most 3 results."""
        data = await _search(client, "appeal", page_size=3)
        results = data["results"]

        assert len(results) <= 3, (
            f"Expected at most 3 results with page_size=3, got {len(results)}"
        )
        assert len(results) >= 1, "Expected at least 1 result"
        assert data["page_size"] == 3, (
            f"Expected page_size=3 in response, got {data['page_size']}"
        )
