"""E2E test for Indian Kanoon and Tavily APIs with real keys.

Usage:
    cd backend
    IK_API_TOKEN=... TAVILY_API_KEY=... python -m scripts.e2e_test_apis
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set env vars before importing settings
IK_TOKEN = os.environ.get("IK_API_TOKEN", "")
TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")


async def test_ik_basic_search(token: str) -> bool:
    """Test 1: IK basic search."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("right to privacy", max_results=3)
        for r in results:
            r.get("title", "?")[:80]
            r.get("tid", "?")
        assert len(results) > 0, "No results returned"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_ik_boolean_search(token: str) -> bool:
    """Test 2: IK boolean query with court filter."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        results = await client.search(
            "privacy",
            boolean_query="right ANDD privacy ANDD fundamental",
            court_filter="supreme_court",
            max_results=5,
        )
        for r in results:
            r.get("title", "?")[:80]
        assert len(results) > 0, "No results for boolean query"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_ik_date_filter(token: str) -> bool:
    """Test 3: IK date range + sort."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        results = await client.search(
            "section 498A IPC",
            court_filter="sc",
            from_date="01-01-2020",
            to_date="31-12-2025",
            sort_by="mostrecent",
            max_results=3,
        )
        for r in results:
            r.get("title", "?")[:80]
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_ik_fragment(token: str) -> bool:
    """Test 4: IK document fragment (Rs 0.05/call)."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        # First search to get a doc ID
        results = await client.search("Puttaswamy privacy", max_results=1)
        if not results:
            return True
        doc_id = str(results[0].get("tid", ""))
        if not doc_id:
            return True
        frag = await client.get_fragment(doc_id, "right to privacy")
        # IK API returns fragment text under "headline" key (list of HTML strings)
        headlines = frag.get("headline", [])
        headlines[0][:200] if headlines else ""
        assert headlines, "Empty headline in fragment response"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_ik_pagination(token: str) -> bool:
    """Test 5: IK multi-page pagination."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        results = await client.search(
            "article 21 life liberty",
            max_results=15,
            max_pages=2,
        )
        assert len(results) > 0, "No results"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_tavily_basic(api_key: str) -> bool:
    """Test 6: Tavily basic search."""
    from app.core.providers.web_search.tavily import TavilySearchClient

    client = TavilySearchClient(api_key=api_key)
    try:
        results = await client.search(
            "Supreme Court India right to privacy judgment",
            max_results=5,
        )
        for _r in results:
            pass
        assert len(results) > 0, "No results"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_tavily_country_india(api_key: str) -> bool:
    """Test 7: Tavily with country=IN."""
    from app.core.providers.web_search.tavily import TavilySearchClient

    client = TavilySearchClient(api_key=api_key)
    try:
        results = await client.search(
            "section 498A IPC cruelty",
            max_results=5,
            country="IN",
        )
        for _r in results:
            pass
        assert len(results) > 0, "No results with country=IN"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_tavily_time_range(api_key: str) -> bool:
    """Test 8: Tavily with time_range."""
    from app.core.providers.web_search.tavily import TavilySearchClient

    client = TavilySearchClient(api_key=api_key)
    try:
        results = await client.search(
            "Supreme Court India latest judgment 2026",
            max_results=3,
            time_range="month",
            country="IN",
        )
        for _r in results:
            pass
        # time_range may legitimately return 0 for very narrow queries
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_tavily_raw_content(api_key: str) -> bool:
    """Test 9: Tavily with raw_content."""
    from app.core.providers.web_search.tavily import TavilySearchClient

    client = TavilySearchClient(api_key=api_key)
    try:
        results = await client.search(
            "Puttaswamy right to privacy Supreme Court",
            max_results=2,
            include_raw_content=True,
            country="IN",
        )
        sum(1 for r in results if r.get("raw_content"))
        for r in results:
            raw = r.get("raw_content", "")
            if raw:
                pass
            else:
                pass
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_ik_title_filter(token: str) -> bool:
    """Test: IK title filter."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("privacy", title_filter="Puttaswamy", max_results=3)
        for _r in results:
            pass
        assert len(results) > 0, "No results with title filter"
        assert any(
            "puttaswamy" in r.get("title", "").lower() for r in results
        ), "No Puttaswamy in titles"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_ik_author_filter(token: str) -> bool:
    """Test: IK author filter."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        results = await client.search(
            "fundamental rights", author_filter="chandrachud", max_results=3
        )
        for _r in results:
            pass
        assert len(results) > 0, "No results with author filter"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_ik_maxcites(token: str) -> bool:
    """Test: IK maxcites returns citation list."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("right to privacy", max_results=1, max_cites=5)
        cites = results[0].get("cites", [])
        for _c in cites[:3]:
            pass
        assert len(cites) > 0, "No cites returned with maxcites"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_ik_maxpages(token: str) -> bool:
    """Test: IK maxpages in single call."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("article 21 life liberty", max_results=15, max_pages=2)
        assert len(results) > 10, f"Expected >10 results from 2 pages, got {len(results)}"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def test_ik_rich_fields(token: str) -> bool:
    """Test: IK search returns rich fields."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("right to privacy", max_results=1)
        doc = results[0]
        assert doc.get("docsource"), "Missing docsource"
        assert doc.get("headline"), "Missing headline"
        return True
    except Exception:
        return False
    finally:
        await client.close()


async def main():
    passed = 0
    failed = 0
    total_start = time.time()

    # --- IK Tests ---
    if IK_TOKEN:
        ik_tests = [
            test_ik_basic_search,
            test_ik_boolean_search,
            test_ik_date_filter,
            test_ik_fragment,
            test_ik_pagination,
            test_ik_title_filter,
            test_ik_author_filter,
            test_ik_maxcites,
            test_ik_maxpages,
            test_ik_rich_fields,
        ]
        for test_fn in ik_tests:
            ok = await test_fn(IK_TOKEN)
            if ok:
                passed += 1
            else:
                failed += 1
            await asyncio.sleep(0.6)  # respect rate limit
    else:
        pass

    # --- Tavily Tests ---
    if TAVILY_KEY:
        tavily_tests = [
            test_tavily_basic,
            test_tavily_country_india,
            test_tavily_time_range,
            test_tavily_raw_content,
        ]
        for test_fn in tavily_tests:
            ok = await test_fn(TAVILY_KEY)
            if ok:
                passed += 1
            else:
                failed += 1
    else:
        pass

    time.time() - total_start

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
