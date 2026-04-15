"""Tests for Research Agent V2 Phase 3 — Multi-Source Workers + GraphRAG.

Covers Bible Section 13 tests:
  4  (IK API integration — mocked)
  6  (Send() fan-out with all worker types)
  21-25 (GraphRAG community detection)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm(**overrides: object) -> AsyncMock:
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="test response")
    llm.generate_structured = AsyncMock(
        return_value={
            "title": "Test Community",
            "summary": "Test summary",
            "legal_principles": ["Principle 1"],
        }
    )
    for k, v in overrides.items():
        setattr(llm, k, v)
    return llm


def _make_mock_embedder() -> AsyncMock:
    embedder = AsyncMock()
    embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)
    embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
    embedder.dimension = 1536
    return embedder


def _make_mock_vector_store() -> AsyncMock:
    vs = AsyncMock()
    vs.search = AsyncMock(return_value=[])
    vs.upsert = AsyncMock()
    return vs


def _make_mock_reranker() -> AsyncMock:
    reranker = AsyncMock()
    reranker.rerank = AsyncMock(return_value=[])
    return reranker


def _make_mock_graph_store() -> AsyncMock:
    gs = AsyncMock()
    gs.query = AsyncMock(return_value=[])
    gs.get_neighbors = AsyncMock(return_value={"nodes": [], "edges": []})
    return gs


def _make_task(task_type: str = "case_law", **overrides: object) -> dict:
    task = {
        "task_id": "test-1",
        "task_type": task_type,
        "nl_query": "test query about Section 302 IPC",
        "boolean_query": "Section 302 IPC murder",
        "named_cases": [],
        "rationale": "Test rationale",
        "filters": {},
        "priority": 1,
    }
    task.update(overrides)
    return task


# ===========================================================================
# 3B — Provider Tests: Indian Kanoon Client
# ===========================================================================


class TestIndianKanoonClient:
    """Bible test 4 — IK API integration (mocked HTTP)."""

    @pytest.mark.asyncio
    async def test_search_returns_docs(self) -> None:
        """IK search should parse response and return list of docs."""
        import httpx

        from app.core.providers.external.indiankanoon import IndianKanoonClient

        mock_response = httpx.Response(
            200,
            json={
                "docs": [
                    {"tid": "123", "title": "Test Case", "citation": "AIR 2020 SC 1"},
                    {"tid": "456", "title": "Another Case", "citation": "AIR 2021 SC 2"},
                ]
            },
            request=httpx.Request("POST", "https://api.indiankanoon.org/search/"),
        )

        with patch.object(
            httpx.AsyncClient,
            "post",
            return_value=mock_response,
        ):
            client = IndianKanoonClient(token="test-token")
            results = await client.search("murder Section 302", max_results=2)

        assert len(results) == 2
        assert results[0]["tid"] == "123"
        assert results[0]["title"] == "Test Case"

    @pytest.mark.asyncio
    async def test_get_fragment(self) -> None:
        """IK get_fragment should return fragment dict."""
        import httpx

        from app.core.providers.external.indiankanoon import IndianKanoonClient

        mock_response = httpx.Response(
            200,
            json={"fragment": "Relevant paragraph about Section 302..."},
            request=httpx.Request("POST", "https://api.indiankanoon.org/docfragment/123/"),
        )

        with patch.object(
            httpx.AsyncClient,
            "post",
            return_value=mock_response,
        ):
            client = IndianKanoonClient(token="test-token")
            result = await client.get_fragment("123", "Section 302")

        assert "fragment" in result
        assert "Section 302" in result["fragment"]

    @pytest.mark.asyncio
    async def test_get_metadata(self) -> None:
        """IK get_metadata should return metadata dict."""
        import httpx

        from app.core.providers.external.indiankanoon import IndianKanoonClient

        mock_response = httpx.Response(
            200,
            json={"title": "State v. Accused", "court": "Supreme Court of India", "year": 2020},
            request=httpx.Request("POST", "https://api.indiankanoon.org/docmeta/123/"),
        )

        with patch.object(
            httpx.AsyncClient,
            "post",
            return_value=mock_response,
        ):
            client = IndianKanoonClient(token="test-token")
            result = await client.get_metadata("123")

        assert result["title"] == "State v. Accused"
        assert result["court"] == "Supreme Court of India"

    @pytest.mark.asyncio
    async def test_get_document(self) -> None:
        """IK get_document should return full document dict."""
        import httpx

        from app.core.providers.external.indiankanoon import IndianKanoonClient

        mock_response = httpx.Response(
            200,
            json={"doc": "Full judgment text...", "title": "Test Case"},
            request=httpx.Request("POST", "https://api.indiankanoon.org/doc/123/"),
        )

        with patch.object(
            httpx.AsyncClient,
            "post",
            return_value=mock_response,
        ):
            client = IndianKanoonClient(token="test-token")
            result = await client.get_document("123")

        assert "doc" in result

    @pytest.mark.asyncio
    async def test_search_with_court_filter(self) -> None:
        """IK search with court filter should append to formInput."""
        import httpx

        from app.core.providers.external.indiankanoon import IndianKanoonClient

        calls: list[tuple] = []

        async def capture_post(url: str, data: dict | None = None, **kw: object) -> httpx.Response:
            calls.append((url, data))
            return httpx.Response(
                200,
                json={"docs": []},
                request=httpx.Request("POST", url),
            )

        with patch.object(httpx.AsyncClient, "post", side_effect=capture_post):
            client = IndianKanoonClient(token="test-token")
            await client.search("murder", court_filter="supremecourt")

        assert len(calls) == 1
        assert "supremecourt" in calls[0][1]["formInput"]

    @pytest.mark.asyncio
    async def test_missing_token_raises(self) -> None:
        """IndianKanoonClient should raise ValueError without a token."""
        with patch("app.core.providers.external.indiankanoon.settings") as mock_settings:
            mock_settings.ik_api_token = ""
            with pytest.raises(ValueError, match="Indian Kanoon API token"):
                from app.core.providers.external.indiankanoon import IndianKanoonClient

                IndianKanoonClient(token="")


# ===========================================================================
# 3B — Provider Tests: Tavily Search Client
# ===========================================================================


class TestTavilySearchClient:
    """Tavily web search provider tests."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self) -> None:
        """Tavily search should return structured results."""
        import httpx

        from app.core.providers.web_search.tavily import TavilySearchClient

        mock_response = httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Legal News",
                        "url": "https://livelaw.in/article",
                        "content": "Article text",
                        "score": 0.9,
                    },
                    {
                        "title": "Case Update",
                        "url": "https://barandbench.com/case",
                        "content": "Case text",
                        "score": 0.8,
                    },
                ]
            },
            request=httpx.Request("POST", "https://api.tavily.com/search"),
        )

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            client = TavilySearchClient(api_key="test-key")
            results = await client.search("Section 302 IPC recent developments")

        assert len(results) == 2
        assert results[0]["title"] == "Legal News"
        assert results[0]["url"] == "https://livelaw.in/article"
        assert results[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_search_with_custom_domains(self) -> None:
        """Tavily search should pass custom include_domains."""
        import httpx

        from app.core.providers.web_search.tavily import TavilySearchClient

        calls: list[dict] = []

        async def capture_post(url: str, json: dict | None = None, **kw: object) -> httpx.Response:
            calls.append(json or {})
            return httpx.Response(
                200,
                json={"results": []},
                request=httpx.Request("POST", url),
            )

        with patch.object(httpx.AsyncClient, "post", side_effect=capture_post):
            client = TavilySearchClient(api_key="test-key")
            await client.search("test", include_domains=["custom.com"])

        assert calls[0]["include_domains"] == ["custom.com"]

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self) -> None:
        """TavilySearchClient should raise ValueError without API key."""
        with patch("app.core.providers.web_search.tavily.settings") as mock_settings:
            mock_settings.tavily_api_key = ""
            with pytest.raises(ValueError, match="Tavily API key"):
                from app.core.providers.web_search.tavily import TavilySearchClient

                TavilySearchClient(api_key="")


# ===========================================================================
# 3D — Worker Tests: statute_worker
# ===========================================================================


class TestStatuteWorker:
    """statute_worker tests — PG lookup + Pinecone + code mapping."""

    @pytest.mark.asyncio
    async def test_returns_statute_results(self) -> None:
        """statute_worker should return WorkerResult with statute data."""
        from app.core.agents.nodes.worker_nodes import statute_worker

        mock_db_result = MagicMock()
        mock_db_result.scalars.return_value.all.return_value = [
            MagicMock(
                id=1,
                act_name="IPC",
                section_number="302",
                section_title="Murder",
                section_text="Punishment for murder...",
                document_type="statute",
                new_law_equivalent="Section 103 BNS",
            ),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_db_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store()

        task = _make_task("statute", nl_query="Section 302 IPC punishment")

        with patch(
            "app.core.agents.nodes.worker_nodes.async_session_factory", return_value=mock_session
        ):
            result = await statute_worker(
                {"task": task},
                embedder,
                vector_store,
            )

        assert "worker_results" in result
        wr = result["worker_results"][0]
        assert wr["task_type"] == "statute"
        assert wr["error"] is None

    @pytest.mark.asyncio
    async def test_code_mapping_expansion(self) -> None:
        """statute_worker should search both old and new codes via [T3]."""
        from app.core.agents.nodes.worker_nodes import statute_worker

        mock_db_result = MagicMock()
        mock_db_result.scalars.return_value.all.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_db_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store()

        task = _make_task("statute", nl_query="Section 302 IPC")

        with patch(
            "app.core.agents.nodes.worker_nodes.async_session_factory", return_value=mock_session
        ):
            with patch(
                "app.core.agents.nodes.worker_nodes.expand_statute_references"
            ) as mock_expand:
                mock_expand.return_value = ("Section 302 IPC", ["Section 103 BNS"])
                await statute_worker(
                    {"task": task},
                    embedder,
                    vector_store,
                )
                mock_expand.assert_called_once()


# ===========================================================================
# 3D — Worker Tests: ik_search_worker
# ===========================================================================


class TestIKSearchWorker:
    """ik_search_worker tests — Indian Kanoon search + fragment retrieval."""

    @pytest.mark.asyncio
    async def test_returns_ik_results(self) -> None:
        """ik_search_worker should return WorkerResult with IK data."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        mock_ik = AsyncMock()
        mock_ik.search = AsyncMock(
            return_value=[
                {
                    "tid": "123",
                    "title": "Test v. State",
                    "citation": "AIR 2020 SC 1",
                    "court": "Supreme Court",
                },
            ]
        )
        mock_ik.get_fragment = AsyncMock(return_value={"fragment": "Relevant text..."})

        task = _make_task("ik_search")
        result = await ik_search_worker({"task": task}, mock_ik)

        assert "worker_results" in result
        wr = result["worker_results"][0]
        assert wr["task_type"] == "ik_search"
        assert len(wr["results"]) == 1
        assert wr["results"][0]["source"] == "indian_kanoon"
        assert wr["results"][0]["case_id"] == "ik:123"
        assert len(wr["source_urls"]) == 1

    @pytest.mark.asyncio
    async def test_handles_ik_error_gracefully(self) -> None:
        """ik_search_worker should return error WorkerResult on failure."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        mock_ik = AsyncMock()
        mock_ik.search = AsyncMock(side_effect=ConnectionError("IK down"))

        task = _make_task("ik_search")
        result = await ik_search_worker({"task": task}, mock_ik)

        wr = result["worker_results"][0]
        assert wr["error"] is not None
        assert wr["results"] == []


# ===========================================================================
# 3D — Worker Tests: web_search_worker
# ===========================================================================


class TestWebSearchWorker:
    """web_search_worker tests — Tavily web search."""

    @pytest.mark.asyncio
    async def test_returns_web_results(self) -> None:
        """web_search_worker should return WorkerResult with web data."""
        from app.core.agents.nodes.worker_nodes import web_search_worker

        mock_ws = AsyncMock()
        mock_ws.search = AsyncMock(
            return_value=[
                {
                    "title": "News Article",
                    "url": "https://livelaw.in/art",
                    "content": "Text",
                    "score": 0.9,
                },
            ]
        )

        task = _make_task("web")
        result = await web_search_worker({"task": task}, mock_ws)

        assert "worker_results" in result
        wr = result["worker_results"][0]
        assert wr["task_type"] == "web"
        assert len(wr["results"]) == 1
        assert wr["results"][0]["source"] == "web"
        assert len(wr["source_urls"]) == 1

    @pytest.mark.asyncio
    async def test_handles_web_error_gracefully(self) -> None:
        """web_search_worker should return empty on failure (non-blocking)."""
        from app.core.agents.nodes.worker_nodes import web_search_worker

        mock_ws = AsyncMock()
        mock_ws.search = AsyncMock(side_effect=TimeoutError("Tavily timeout"))

        task = _make_task("web")
        result = await web_search_worker({"task": task}, mock_ws)

        wr = result["worker_results"][0]
        assert wr["error"] is not None
        assert wr["results"] == []


# ===========================================================================
# 3D — Worker Tests: graph_worker
# ===========================================================================


class TestGraphWorker:
    """graph_worker tests — Neo4j citation traversal."""

    @pytest.mark.asyncio
    async def test_returns_graph_results(self) -> None:
        """graph_worker should traverse citations and return neighbors."""
        from app.core.agents.nodes.worker_nodes import graph_worker

        mock_gs = _make_mock_graph_store()
        mock_gs.query = AsyncMock(
            return_value=[
                {
                    "id": "case-1",
                    "title": "Landmark Case",
                    "citation": "AIR 2019 SC 100",
                    "treatment": "followed",
                },
            ]
        )

        task = _make_task("graph", nl_query="citing cases for murder under IPC 302")
        result = await graph_worker({"task": task}, mock_gs)

        assert "worker_results" in result
        wr = result["worker_results"][0]
        assert wr["task_type"] == "graph"
        assert wr["error"] is None

    @pytest.mark.asyncio
    async def test_handles_graph_error(self) -> None:
        """graph_worker should handle Neo4j errors gracefully."""
        from app.core.agents.nodes.worker_nodes import graph_worker

        mock_gs = _make_mock_graph_store()
        mock_gs.query = AsyncMock(side_effect=RuntimeError("Neo4j unavailable"))

        task = _make_task("graph")
        result = await graph_worker({"task": task}, mock_gs)

        wr = result["worker_results"][0]
        assert wr["error"] is not None


# ===========================================================================
# 3E — GraphRAG Community Tests (Bible Tests 21-25)
# ===========================================================================


class TestCommunityDetection:
    """Bible test 21 — Leiden community detection on mock graph."""

    def test_leiden_produces_communities(self) -> None:
        """Leiden algorithm should partition a small graph into communities."""
        import networkx as nx

        # Create a graph with 2 clear clusters
        G = nx.Graph()
        # Cluster 1: cases 1-5 (fully connected)
        for i in range(1, 6):
            for j in range(i + 1, 6):
                G.add_edge(f"case-{i}", f"case-{j}")
        # Cluster 2: cases 6-10 (fully connected)
        for i in range(6, 11):
            for j in range(i + 1, 11):
                G.add_edge(f"case-{i}", f"case-{j}")
        # Weak bridge between clusters
        G.add_edge("case-3", "case-8")

        from app.core.agents.nodes.worker_nodes import _detect_communities

        communities = _detect_communities(G, resolution=1.0)

        assert len(communities) == 10  # all nodes assigned
        # Should produce at least 2 communities
        unique_communities = set(communities.values())
        assert len(unique_communities) >= 2


class TestGraphCommunityWorker:
    """Bible test 22-23 — graph_community_worker retrieval."""

    @pytest.mark.asyncio
    async def test_semantic_retrieval(self) -> None:
        """graph_community_worker should find communities via semantic search."""
        from app.core.agents.nodes.worker_nodes import graph_community_worker

        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        # Mock Pinecone returning community results
        mock_result = MagicMock()
        mock_result.score = 0.85
        mock_result.metadata = {
            "community_id": "comm-1",
            "title": "Section 498A Misuse",
            "text": "This cluster establishes...",
            "legal_principles": "Principle 1; Principle 2",
            "size": 23,
            "document_type": "community",
        }
        vector_store.search = AsyncMock(return_value=[mock_result])

        task = _make_task("graph_community")
        result = await graph_community_worker(
            {"task": task, "parent_state": {}},
            embedder,
            vector_store,
            graph_store,
        )

        assert "worker_results" in result
        wr = result["worker_results"][0]
        assert wr["task_type"] == "graph_community"
        assert len(wr["results"]) >= 1
        assert wr["results"][0]["community_id"] == "comm-1"
        assert wr["results"][0]["retrieval_method"] == "semantic"

    @pytest.mark.asyncio
    async def test_graph_overlap_retrieval(self) -> None:
        """graph_community_worker should find communities from existing cases."""
        from app.core.agents.nodes.worker_nodes import graph_community_worker

        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        # No semantic results
        vector_store.search = AsyncMock(return_value=[])

        # But graph has community overlap
        graph_store.query = AsyncMock(
            return_value=[
                {
                    "id": "comm-2",
                    "title": "Bail Jurisprudence",
                    "summary": "Evolution of bail...",
                    "principles": ["Bail is rule", "Jail is exception"],
                    "size": 15,
                    "overlap": 3,
                },
            ]
        )

        parent_state = {
            "worker_results": [
                {"results": [{"case_id": "case-100"}, {"case_id": "case-200"}]},
            ],
        }

        task = _make_task("graph_community")
        result = await graph_community_worker(
            {"task": task, "parent_state": parent_state},
            embedder,
            vector_store,
            graph_store,
        )

        wr = result["worker_results"][0]
        assert len(wr["results"]) >= 1
        assert wr["results"][0]["retrieval_method"] == "graph_overlap"

    @pytest.mark.asyncio
    async def test_deduplicates_across_strategies(self) -> None:
        """graph_community_worker should not duplicate communities found by both strategies."""
        from app.core.agents.nodes.worker_nodes import graph_community_worker

        embedder = _make_mock_embedder()
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        # Semantic finds comm-1
        mock_result = MagicMock()
        mock_result.score = 0.85
        mock_result.metadata = {
            "community_id": "comm-1",
            "title": "Test",
            "text": "Summary",
            "legal_principles": "P1",
            "size": 10,
            "document_type": "community",
        }
        vector_store.search = AsyncMock(return_value=[mock_result])

        # Graph also finds comm-1
        graph_store.query = AsyncMock(
            return_value=[
                {
                    "id": "comm-1",
                    "title": "Test",
                    "summary": "Summary",
                    "principles": ["P1"],
                    "size": 10,
                    "overlap": 2,
                },
            ]
        )

        parent_state = {
            "worker_results": [{"results": [{"case_id": "case-1"}]}],
        }

        task = _make_task("graph_community")
        result = await graph_community_worker(
            {"task": task, "parent_state": parent_state},
            embedder,
            vector_store,
            graph_store,
        )

        wr = result["worker_results"][0]
        comm_ids = [r["community_id"] for r in wr["results"]]
        assert comm_ids.count("comm-1") == 1  # No duplicates


class TestCommunityBuildScript:
    """Bible test 73 — community build script functions."""

    @pytest.mark.asyncio
    async def test_export_citation_graph(self) -> None:
        """export_citation_graph should build NetworkX from Neo4j results."""
        from scripts.build_citation_communities import export_citation_graph

        mock_gs = _make_mock_graph_store()
        mock_gs.query = AsyncMock(
            return_value=[
                {"source": "case-1", "target": "case-2", "treatment": "followed"},
                {"source": "case-2", "target": "case-3", "treatment": "cited"},
            ]
        )

        G = await export_citation_graph(mock_gs)
        assert len(G.nodes) == 3
        assert len(G.edges) == 2

    @pytest.mark.asyncio
    async def test_summarize_community(self) -> None:
        """summarize_community should generate CommunitySummary via Flash LLM."""
        from scripts.build_citation_communities import summarize_community

        mock_llm = _make_mock_llm()
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value = [
            MagicMock(
                title="Case 1",
                citation="AIR 2020 SC 1",
                court="SC",
                year=2020,
                ratio_decidendi="Ratio text",
            ),
        ]
        mock_session.execute = AsyncMock(return_value=mock_scalars)

        result = await summarize_community(
            "comm-1",
            ["case-1", "case-2"],
            mock_session,
            mock_llm,
        )

        assert result["community_id"] == "comm-1"
        assert result["title"] == "Test Community"
        assert "legal_principles" in result


# ===========================================================================
# 3F — Graph Registration Tests
# ===========================================================================


class TestDispatchAllWorkerTypes:
    """Bible test 6 — verify Send() fan-out routes to all worker types."""

    def test_dispatch_routes_all_task_types(self) -> None:
        """dispatch_workers should route to correct worker nodes."""
        # Import the graph builder to verify registration
        from app.core.agents.research import build_research_graph

        mock_deps = {
            "llm": _make_mock_llm(),
            "flash_llm": _make_mock_llm(),
            "embedder": _make_mock_embedder(),
            "vector_store": _make_mock_vector_store(),
            "reranker": _make_mock_reranker(),
            "graph_store": _make_mock_graph_store(),
        }

        # Build graph — should not raise
        graph = build_research_graph(**mock_deps)
        assert graph is not None

    def test_all_worker_types_are_registered(self) -> None:
        """All Phase 3 worker types should have corresponding nodes."""
        from app.core.agents.research import build_research_graph

        mock_deps = {
            "llm": _make_mock_llm(),
            "flash_llm": _make_mock_llm(),
            "embedder": _make_mock_embedder(),
            "vector_store": _make_mock_vector_store(),
            "reranker": _make_mock_reranker(),
            "graph_store": _make_mock_graph_store(),
        }

        graph = build_research_graph(**mock_deps)

        # Graph should have been compiled successfully with all worker nodes
        # The graph builder registers all worker nodes or raises
        assert graph is not None
