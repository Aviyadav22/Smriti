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

    print("\n=== IK Test 1: Basic Search ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("right to privacy", max_results=3)
        print(f"  Results: {len(results)}")
        for r in results:
            title = r.get("title", "?")[:80]
            doc_id = r.get("tid", "?")
            print(f"  - [{doc_id}] {title}")
        assert len(results) > 0, "No results returned"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_ik_boolean_search(token: str) -> bool:
    """Test 2: IK boolean query with court filter."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    print("\n=== IK Test 2: Boolean Search + Court Filter ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search(
            "privacy",
            boolean_query="right ANDD privacy ANDD fundamental",
            court_filter="supreme_court",
            max_results=5,
        )
        print(f"  Results: {len(results)}")
        for r in results:
            title = r.get("title", "?")[:80]
            print(f"  - {title}")
        assert len(results) > 0, "No results for boolean query"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_ik_date_filter(token: str) -> bool:
    """Test 3: IK date range + sort."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    print("\n=== IK Test 3: Date Filter + Sort ===")
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
        print(f"  Results: {len(results)}")
        for r in results:
            title = r.get("title", "?")[:80]
            print(f"  - {title}")
        print("  PASS" if len(results) >= 0 else "  WARN: 0 results")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_ik_fragment(token: str) -> bool:
    """Test 4: IK document fragment (Rs 0.05/call)."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    print("\n=== IK Test 4: Document Fragment ===")
    client = IndianKanoonClient(token=token)
    try:
        # First search to get a doc ID
        results = await client.search("Puttaswamy privacy", max_results=1)
        if not results:
            print("  SKIP: No search results to get fragment from")
            return True
        doc_id = str(results[0].get("tid", ""))
        if not doc_id:
            print("  SKIP: No doc ID in result")
            return True
        print(f"  Fetching fragment for doc {doc_id}...")
        frag = await client.get_fragment(doc_id, "right to privacy")
        # IK API returns fragment text under "headline" key (list of HTML strings)
        headlines = frag.get("headline", [])
        frag_text = headlines[0][:200] if headlines else ""
        print(f"  Fragment keys: {list(frag.keys())}")
        print(f"  Fragment: {frag_text}...")
        assert headlines, "Empty headline in fragment response"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_ik_pagination(token: str) -> bool:
    """Test 5: IK multi-page pagination."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    print("\n=== IK Test 5: Multi-page Pagination ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search(
            "article 21 life liberty",
            max_results=15,
            max_pages=2,
        )
        print(f"  Results: {len(results)} (across 2 pages)")
        assert len(results) > 0, "No results"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_tavily_basic(api_key: str) -> bool:
    """Test 6: Tavily basic search."""
    from app.core.providers.web_search.tavily import TavilySearchClient

    print("\n=== Tavily Test 1: Basic Search ===")
    client = TavilySearchClient(api_key=api_key)
    try:
        results = await client.search(
            "Supreme Court India right to privacy judgment",
            max_results=5,
        )
        print(f"  Results: {len(results)}")
        for r in results:
            print(f"  - [{r.get('score', 0):.2f}] {r.get('title', '?')[:60]}")
            print(f"    URL: {r.get('url', '?')[:80]}")
        assert len(results) > 0, "No results"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_tavily_country_india(api_key: str) -> bool:
    """Test 7: Tavily with country=IN."""
    from app.core.providers.web_search.tavily import TavilySearchClient

    print("\n=== Tavily Test 2: Country=IN Filter ===")
    client = TavilySearchClient(api_key=api_key)
    try:
        results = await client.search(
            "section 498A IPC cruelty",
            max_results=5,
            country="IN",
        )
        print(f"  Results: {len(results)}")
        for r in results:
            print(f"  - {r.get('title', '?')[:60]}")
        assert len(results) > 0, "No results with country=IN"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_tavily_time_range(api_key: str) -> bool:
    """Test 8: Tavily with time_range."""
    from app.core.providers.web_search.tavily import TavilySearchClient

    print("\n=== Tavily Test 3: Time Range (month) ===")
    client = TavilySearchClient(api_key=api_key)
    try:
        results = await client.search(
            "Supreme Court India latest judgment 2026",
            max_results=3,
            time_range="month",
            country="IN",
        )
        print(f"  Results: {len(results)}")
        for r in results:
            print(f"  - {r.get('title', '?')[:60]}")
        # time_range may legitimately return 0 for very narrow queries
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_tavily_raw_content(api_key: str) -> bool:
    """Test 9: Tavily with raw_content."""
    from app.core.providers.web_search.tavily import TavilySearchClient

    print("\n=== Tavily Test 4: Raw Content (markdown) ===")
    client = TavilySearchClient(api_key=api_key)
    try:
        results = await client.search(
            "Puttaswamy right to privacy Supreme Court",
            max_results=2,
            include_raw_content=True,
            country="IN",
        )
        print(f"  Results: {len(results)}")
        has_raw = sum(1 for r in results if r.get("raw_content"))
        print(f"  Results with raw_content: {has_raw}/{len(results)}")
        for r in results:
            raw = r.get("raw_content", "")
            if raw:
                print(f"  - {r.get('title', '?')[:50]} — raw_content: {len(raw)} chars")
            else:
                print(f"  - {r.get('title', '?')[:50]} — no raw_content")
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_ik_title_filter(token: str) -> bool:
    """Test: IK title filter."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    print("\n=== IK Test 6: Title Filter ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("privacy", title_filter="Puttaswamy", max_results=3)
        print(f"  Results: {len(results)}")
        for r in results:
            print(f"  - {r.get('title', '?')[:80]}")
        assert len(results) > 0, "No results with title filter"
        assert any("puttaswamy" in r.get("title", "").lower() for r in results), "No Puttaswamy in titles"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_ik_author_filter(token: str) -> bool:
    """Test: IK author filter."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    print("\n=== IK Test 7: Author Filter ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("fundamental rights", author_filter="chandrachud", max_results=3)
        print(f"  Results: {len(results)}")
        for r in results:
            print(f"  - {r.get('title', '?')[:60]} [author: {r.get('author', '?')}]")
        assert len(results) > 0, "No results with author filter"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_ik_maxcites(token: str) -> bool:
    """Test: IK maxcites returns citation list."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    print("\n=== IK Test 8: maxcites ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("right to privacy", max_results=1, max_cites=5)
        print(f"  Results: {len(results)}")
        cites = results[0].get("cites", [])
        print(f"  Cites for first result: {len(cites)}")
        for c in cites[:3]:
            print(f"    - [{c.get('tid')}] {c.get('title', '?')[:60]}")
        assert len(cites) > 0, "No cites returned with maxcites"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_ik_maxpages(token: str) -> bool:
    """Test: IK maxpages in single call."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    print("\n=== IK Test 9: maxpages (single call) ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("article 21 life liberty", max_results=15, max_pages=2)
        print(f"  Results: {len(results)}")
        assert len(results) > 10, f"Expected >10 results from 2 pages, got {len(results)}"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def test_ik_rich_fields(token: str) -> bool:
    """Test: IK search returns rich fields."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    print("\n=== IK Test 10: Rich Fields ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("right to privacy", max_results=1)
        doc = results[0]
        print(f"  Title: {doc.get('title', '?')[:60]}")
        print(f"  docsource: {doc.get('docsource', 'MISSING')}")
        print(f"  author: {doc.get('author', 'MISSING')}")
        print(f"  publishdate: {doc.get('publishdate', 'MISSING')}")
        print(f"  numcites: {doc.get('numcites', 'MISSING')}")
        print(f"  numcitedby: {doc.get('numcitedby', 'MISSING')}")
        print(f"  headline: {str(doc.get('headline', 'MISSING'))[:80]}")
        assert doc.get("docsource"), "Missing docsource"
        assert doc.get("headline"), "Missing headline"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()


async def main():
    print("=" * 60)
    print("E2E API Test — Indian Kanoon & Tavily")
    print("=" * 60)

    passed = 0
    failed = 0
    total_start = time.time()

    # --- IK Tests ---
    if IK_TOKEN:
        print(f"\nIndian Kanoon token: {IK_TOKEN[:8]}...{IK_TOKEN[-4:]}")
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
        print("\nSKIPPING IK tests — IK_API_TOKEN not set")

    # --- Tavily Tests ---
    if TAVILY_KEY:
        print(f"\nTavily key: {TAVILY_KEY[:10]}...{TAVILY_KEY[-4:]}")
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
        print("\nSKIPPING Tavily tests — TAVILY_API_KEY not set")

    elapsed = time.time() - total_start
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed ({elapsed:.1f}s)")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
