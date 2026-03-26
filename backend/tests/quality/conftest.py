"""Shared fixtures for quality integration tests.

These fixtures use real providers (Gemini LLM/embedder, Pinecone, Cohere reranker,
PostgreSQL, Neo4j) to test actual end-to-end flows.

Run with:
    pytest tests/quality/ -m integration --timeout=120
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import (
    get_embedder,
    get_flash_llm,
    get_graph_store,
    get_llm,
    get_reranker,
    get_vector_store,
)
from app.core.search.hybrid import SearchResponse, hybrid_search
from app.db.postgres import async_session_factory


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session():
    """Real PostgreSQL async session."""
    async with async_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Search client
# ---------------------------------------------------------------------------


class SearchClient:
    """Thin async wrapper around hybrid_search for quality tests."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._llm = get_llm()
        self._embedder = get_embedder()
        self._vector_store = get_vector_store()
        self._reranker = get_reranker()

    async def search(
        self,
        query: str,
        page_size: int = 5,
        language: str = "en",
    ) -> list[dict[str, Any]]:
        response: SearchResponse = await hybrid_search(
            query=query,
            filters=None,
            page=1,
            page_size=page_size,
            llm=self._llm,
            embedder=self._embedder,
            vector_store=self._vector_store,
            reranker=self._reranker,
            db=self._db,
            redis_client=None,
            language=language,
        )
        return [
            {
                "case_id": r.case_id,
                "title": r.title or "",
                "snippet": r.snippet or r.chunk_text or "",
                "citation": r.citation,
                "score": round(r.score, 4),
                "court": r.court,
                "year": r.year,
            }
            for r in response.results
        ]


@pytest.fixture
async def search_client(db_session: AsyncSession) -> SearchClient:
    """Async search client backed by real providers."""
    return SearchClient(db_session)


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


class AgentRunner:
    """Facade wrapping research, strategy, and drafting LangGraph agents."""

    def __init__(self) -> None:
        self._llm = get_llm()
        self._flash_llm = get_flash_llm()
        self._embedder = get_embedder()
        self._vector_store = get_vector_store()
        self._reranker = get_reranker()
        self._graph_store = get_graph_store()

    async def run_research(self, query: str) -> dict[str, Any]:
        from app.core.agents.research import build_research_graph

        graph = build_research_graph(
            llm=self._llm,
            flash_llm=self._flash_llm,
            embedder=self._embedder,
            vector_store=self._vector_store,
            reranker=self._reranker,
            graph_store=self._graph_store,
            checkpointer=None,
            memo_stream_callback=None,
        )
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        state = await graph.ainvoke(
            {"query": query, "language": "en", "auto_approve": True},
            config=config,
        )
        return {
            "research_memo": state.get("draft_memo", ""),
            "confidence": state.get("confidence", 0.0),
            "footnotes": state.get("footnotes", []),
            "research_audit": state.get("research_audit", {}),
        }

    async def run_strategy(
        self, case_facts: str, desired_relief: str
    ) -> dict[str, Any]:
        from app.core.agents.strategy import build_strategy_graph

        graph = build_strategy_graph(
            llm=self._llm,
            flash_llm=self._flash_llm,
            embedder=self._embedder,
            vector_store=self._vector_store,
            reranker=self._reranker,
            graph_store=self._graph_store,
            checkpointer=None,
        )
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        state = await graph.ainvoke(
            {
                "case_facts": case_facts,
                "desired_relief": desired_relief,
                "language": "en",
            },
            config=config,
        )
        # strength_assessment is a dict {level, reasoning, score}
        sa = state.get("strength_assessment", {})
        return {
            "strategy_memo": state.get("strategy_memo", ""),
            "strength_assessment": sa.get("level", "") if isinstance(sa, dict) else sa,
            "confidence": state.get("confidence", 0.0),
        }

    async def run_drafting(
        self, doc_type: str, case_facts: str
    ) -> dict[str, Any]:
        from app.core.agents.drafting import build_drafting_graph

        graph = build_drafting_graph(
            llm=self._llm,
            flash_llm=self._flash_llm,
            embedder=self._embedder,
            vector_store=self._vector_store,
            reranker=self._reranker,
            checkpointer=None,
        )
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        state = await graph.ainvoke(
            {
                "doc_type": doc_type,
                "case_facts": case_facts,
                "language": "en",
                "relevant_precedents": [],
                "additional_context": {},
                "target_court": "",
            },
            config=config,
        )
        return {
            "full_draft": state.get("full_draft", ""),
            "section_drafts": state.get("section_drafts", {}),
        }


@pytest.fixture
async def agent_runner() -> AgentRunner:
    """Agent runner backed by real providers."""
    return AgentRunner()
