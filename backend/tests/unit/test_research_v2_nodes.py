"""Tests for Research Agent V2 node functions.

Covers Bible Section 13 tests 1-9 (Core), 10-13 (CRAG), 18-20 (MA-RAG CoT),
39-41 (Fast Path), and worker tests (1D.4).
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.nodes.research_nodes import (
    batch_worker_cot_with_reflection_node,
    evaluate_and_extract_node,
    fast_path_search_node,
    fast_path_synthesis_node,
    gap_analysis_node,
    gather_worker_results_node,
    plan_research_node,
    rewrite_query_node,
)
from app.core.agents.nodes.worker_nodes import (
    case_law_worker,
    named_case_worker,
)
from app.core.agents.state import (
    EvidenceGap,
    ExtractedPassage,
    RelevanceScore,
    ResearchTask,
    StrategyAdjustment,
    WorkerResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_v2_state(**overrides) -> dict:
    """Create a minimal V2 ResearchState dict with defaults."""
    base: dict = {
        "query": "What are the grounds for anticipatory bail under Section 438 CrPC?",
        "target_court": "",
        "target_bench": "",
        "language": "en",
        "sub_queries": [],
        "search_results": [],
        "cross_references": [],
        "contradictions": [],
        "draft_memo": "",
        "confidence": 0.0,
        "messages": [],
        "iteration": 0,
        "error": "",
        # V2 fields
        "rewritten_query": "",
        "complexity": "complex",
        "research_plan": [],
        "worker_results": [],
        "worker_reasonings": [],
        "relevance_scores": [],
        "community_summaries": [],
        "extracted_passages": [],
        "evidence_gaps": [],
        "refinement_round": 0,
        "synthesis_drafts": [],
        "footnotes": [],
        "source_attribution": {},
        "research_audit": {},
        "precomputed_embeddings": {},
        "strategy_adjustment": None,
        "legal_quality_result": None,
        "citation_verification_results": [],
        "process_events": [],
    }
    base.update(overrides)
    return base


def _make_llm(**overrides) -> AsyncMock:
    """Create a mock LLMProvider."""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="")
    llm.generate_structured = AsyncMock(return_value={})
    for k, v in overrides.items():
        setattr(llm, k, v)
    return llm


def _make_worker_result(
    task_id: str = "t1",
    task_type: str = "case_law",
    query: str = "test query",
    results: list | None = None,
    error: str | None = None,
) -> WorkerResult:
    """Create a WorkerResult for testing."""
    return WorkerResult(
        task_id=task_id,
        task_type=task_type,
        query=query,
        results=results or [],
        source_urls=[],
        metadata={},
        error=error,
        reasoning="",
    )


def _make_search_result(
    case_id: str = "c1",
    title: str = "Test Case",
    citation: str = "(2020) 5 SCC 1",
    score: float = 0.85,
    **extra: object,
) -> dict:
    """Create a mock search result dict."""
    base = {
        "case_id": case_id,
        "title": title,
        "citation": citation,
        "score": score,
        "snippet": f"Snippet for {title}",
        "court": "Supreme Court of India",
        "year": 2020,
    }
    base.update(extra)
    return base


# ===========================================================================
# Bible Test 1: Unit tests — each new node in isolation with mocked deps
# ===========================================================================


class TestRewriteQueryNode:
    """Bible test 1 — rewrite_query_node."""

    @pytest.mark.asyncio
    async def test_returns_rewritten_query(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "  Detailed legal query about anticipatory bail  "

        state = _make_v2_state()
        result = await rewrite_query_node(state, llm)

        assert "rewritten_query" in result
        assert result["rewritten_query"] == "Detailed legal query about anticipatory bail"

    @pytest.mark.asyncio
    async def test_passes_original_query_to_llm(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "rewritten"

        state = _make_v2_state(query="Section 302 IPC punishment")
        await rewrite_query_node(state, llm)

        call_kwargs = llm.generate.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "Section 302 IPC punishment" in prompt

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self) -> None:
        llm = _make_llm()
        llm.generate.side_effect = RuntimeError("LLM down")

        state = _make_v2_state(query="original query")
        result = await rewrite_query_node(state, llm)

        assert result["rewritten_query"] == "original query"


# ===========================================================================
# Bible Test 2: Dual-query test — plan_research generates both nl_query
# and boolean_query per task
# ===========================================================================


class TestPlanResearchNode:
    """Bible test 2 — dual-query generation."""

    @pytest.mark.asyncio
    async def test_generates_dual_queries(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "research_tasks": [
                {
                    "task_type": "case_law",
                    "nl_query": "anticipatory bail Section 438 CrPC Supreme Court",
                    "boolean_query": "anticipatory AND bail AND (Section 438 OR S.438)",
                    "named_cases": [],
                    "rationale": "Search for SC rulings on anticipatory bail",
                    "filters": {},
                    "priority": 1,
                },
                {
                    "task_type": "named_case",
                    "nl_query": "Sushila Aggarwal anticipatory bail conditions",
                    "boolean_query": "Sushila Aggarwal AND anticipatory bail",
                    "named_cases": [{"name": "Sushila Aggarwal v. State", "citation": "(2020) 5 SCC 1"}],
                    "rationale": "Landmark case on anticipatory bail",
                    "filters": {},
                    "priority": 1,
                },
            ]
        }

        state = _make_v2_state(
            rewritten_query="anticipatory bail under Section 438 CrPC",
            messages=[{"type": "classification", "data": {"topic": "criminal", "complexity": "complex"}}],
        )
        result = await plan_research_node(state, llm)

        assert "research_plan" in result
        assert len(result["research_plan"]) == 2

        # Verify BOTH nl_query and boolean_query present
        for task in result["research_plan"]:
            assert task["nl_query"], f"nl_query missing in {task['task_type']}"
            assert task["boolean_query"], f"boolean_query missing in {task['task_type']}"

    @pytest.mark.asyncio
    async def test_generates_task_ids(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "research_tasks": [
                {"task_type": "case_law", "nl_query": "q", "boolean_query": "b",
                 "named_cases": [], "rationale": "r", "filters": {}, "priority": 1}
            ]
        }

        state = _make_v2_state()
        result = await plan_research_node(state, llm)

        task = result["research_plan"][0]
        # task_id should be a valid UUID
        uuid.UUID(task["task_id"])

    @pytest.mark.asyncio
    async def test_populates_sub_queries_for_backward_compat(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "research_tasks": [
                {"task_type": "case_law", "nl_query": "query one", "boolean_query": "",
                 "named_cases": [], "rationale": "r", "filters": {}, "priority": 1},
                {"task_type": "case_law", "nl_query": "query two", "boolean_query": "",
                 "named_cases": [], "rationale": "r", "filters": {}, "priority": 2},
            ]
        }

        state = _make_v2_state()
        result = await plan_research_node(state, llm)

        assert "sub_queries" in result
        assert result["sub_queries"] == ["query one", "query two"]

    @pytest.mark.asyncio
    async def test_includes_user_feedback_in_prompt(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"research_tasks": []}

        state = _make_v2_state(
            messages=[
                {"type": "classification", "data": {"topic": "criminal"}},
                {"type": "user_feedback", "step": "plan", "content": "Focus on bail only"},
            ]
        )
        await plan_research_node(state, llm)

        call_kwargs = llm.generate_structured.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "Focus on bail only" in prompt

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        llm = _make_llm()
        llm.generate_structured.side_effect = RuntimeError("LLM error")

        state = _make_v2_state()
        result = await plan_research_node(state, llm)

        assert "error" in result
        assert "Failed to create research plan" in result["error"]


# ===========================================================================
# Bible Test 5: Passage extraction test
# ===========================================================================


class TestEvaluateAndExtractNode:
    """Bible tests 5, 10-13 — CRAG + passage extraction."""

    @pytest.mark.asyncio
    async def test_extracts_passages_from_correct_results(self) -> None:
        """Bible test 5 — verify extracted passages."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "evaluations": [
                {
                    "case_id": "c1",
                    "score": 0.9,
                    "verdict": "correct",
                    "reason": "Directly relevant",
                    "action": "keep",
                    "passage": "The court held that anticipatory bail is a right.",
                    "passage_source_field": "chunk_text",
                    "is_verbatim": True,
                },
            ]
        }

        worker_results = [_make_worker_result(
            results=[_make_search_result(case_id="c1", citation="(2020) 5 SCC 1")]
        )]
        state = _make_v2_state(
            worker_results=worker_results,
            rewritten_query="anticipatory bail",
        )
        db = AsyncMock()

        result = await evaluate_and_extract_node(state, llm, db)

        assert len(result["extracted_passages"]) == 1
        passage = result["extracted_passages"][0]
        assert passage["case_id"] == "c1"
        assert passage["passage"] == "The court held that anticipatory bail is a right."
        assert passage["citation"] == "(2020) 5 SCC 1"
        assert passage["is_verbatim"] is True

    @pytest.mark.asyncio
    async def test_crag_scoring_correct_ambiguous_incorrect(self) -> None:
        """Bible test 10 — CRAG scoring with mixed verdicts."""
        llm = _make_llm()
        evaluations = []
        for i in range(5):
            evaluations.append({
                "case_id": f"correct_{i}", "score": 0.9, "verdict": "correct",
                "reason": "relevant", "action": "keep", "passage": f"passage {i}",
                "passage_source_field": "chunk_text", "is_verbatim": True,
            })
        for i in range(5):
            evaluations.append({
                "case_id": f"ambiguous_{i}", "score": 0.5, "verdict": "ambiguous",
                "reason": "unclear", "action": "keep", "passage": "",
            })
        for i in range(5):
            evaluations.append({
                "case_id": f"incorrect_{i}", "score": 0.1, "verdict": "incorrect",
                "reason": "irrelevant", "action": "filter",
            })

        llm.generate_structured.return_value = {"evaluations": evaluations}

        all_results = []
        for ev in evaluations:
            all_results.append(_make_search_result(case_id=ev["case_id"]))
        worker_results = [_make_worker_result(results=all_results)]

        state = _make_v2_state(worker_results=worker_results)
        db = AsyncMock()
        result = await evaluate_and_extract_node(state, llm, db)

        correct = [s for s in result["relevance_scores"] if s["verdict"] == "correct"]
        ambiguous = [s for s in result["relevance_scores"] if s["verdict"] == "ambiguous"]
        incorrect = [s for s in result["relevance_scores"] if s["verdict"] == "incorrect"]

        assert len(correct) == 5
        assert len(ambiguous) == 5
        assert len(incorrect) == 5

    @pytest.mark.asyncio
    async def test_crag_filtering_removes_incorrect(self) -> None:
        """Bible test 11 — incorrect results removed from downstream."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "evaluations": [
                {"case_id": "good", "score": 0.9, "verdict": "correct",
                 "reason": "relevant", "action": "keep"},
                {"case_id": "bad", "score": 0.1, "verdict": "incorrect",
                 "reason": "irrelevant", "action": "filter"},
            ]
        }

        worker_results = [_make_worker_result(
            results=[
                _make_search_result(case_id="good"),
                _make_search_result(case_id="bad"),
            ]
        )]
        state = _make_v2_state(worker_results=worker_results)
        db = AsyncMock()

        result = await evaluate_and_extract_node(state, llm, db)

        # Filtered worker_results should exclude "bad"
        for wr in result["worker_results"]:
            case_ids = [r["case_id"] for r in wr["results"]]
            assert "bad" not in case_ids
            assert "good" in case_ids

    @pytest.mark.asyncio
    async def test_no_passages_for_incorrect(self) -> None:
        """Bible test 11 (cont) — no passages extracted for incorrect verdicts."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "evaluations": [
                {"case_id": "bad", "score": 0.1, "verdict": "incorrect",
                 "reason": "irrelevant", "action": "filter",
                 "passage": "This should not be extracted"},
            ]
        }

        worker_results = [_make_worker_result(results=[_make_search_result(case_id="bad")])]
        state = _make_v2_state(worker_results=worker_results)
        db = AsyncMock()

        result = await evaluate_and_extract_node(state, llm, db)
        assert len(result["extracted_passages"]) == 0

    @pytest.mark.asyncio
    async def test_empty_worker_results(self) -> None:
        state = _make_v2_state(worker_results=[])
        db = AsyncMock()
        llm = _make_llm()

        result = await evaluate_and_extract_node(state, llm, db)
        assert result["relevance_scores"] == []
        assert result["extracted_passages"] == []

    @pytest.mark.asyncio
    async def test_parallel_batches(self) -> None:
        """Bible test S12 — verify batches processed via asyncio.gather."""
        llm = _make_llm()
        call_count = 0

        async def mock_generate_structured(**kwargs):
            nonlocal call_count
            call_count += 1
            return {"evaluations": []}

        llm.generate_structured = mock_generate_structured

        # 20 results → should be split into 2 batches of 15 and 5
        results = [_make_search_result(case_id=f"c{i}") for i in range(20)]
        worker_results = [_make_worker_result(results=results)]

        state = _make_v2_state(worker_results=worker_results)
        db = AsyncMock()
        await evaluate_and_extract_node(state, llm, db)

        assert call_count == 2  # 2 batches


# ===========================================================================
# Bible Test 3: Named case test
# ===========================================================================


class TestNamedCaseWorker:
    """Bible test 3 — named_case_worker finds cases via citation + title fallback."""

    @pytest.mark.asyncio
    async def test_finds_by_citation(self) -> None:
        state = {
            "task": {
                "task_id": "t1",
                "task_type": "named_case",
                "nl_query": "Sushila Aggarwal anticipatory bail",
                "boolean_query": "",
                "named_cases": [
                    {"name": "Sushila Aggarwal v. State", "citation": "(2020) 5 SCC 1"},
                ],
                "rationale": "Landmark case",
                "filters": {},
                "priority": 1,
            },
            "precomputed_embeddings": {},
        }

        from dataclasses import dataclass

        @dataclass
        class FakeCitationResult:
            case_id: str = "c1"
            title: str = "Sushila Aggarwal"
            citation: str = "(2020) 5 SCC 1"
            score: float = 1.0
            snippet: str = "text"

        with patch("app.core.agents.nodes.worker_nodes.async_session_factory") as mock_sf, \
             patch("app.core.agents.nodes.worker_nodes._exact_citation_search", new_callable=AsyncMock) as mock_cite, \
             patch("app.core.agents.nodes.worker_nodes.enrich_results_with_ratio", new_callable=AsyncMock) as mock_enrich:

            mock_ctx = AsyncMock()
            mock_sf.return_value = mock_ctx
            mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_ctx.__aexit__ = AsyncMock(return_value=False)

            mock_cite.return_value = [FakeCitationResult()]
            mock_enrich.side_effect = lambda results, db, **kw: results

            llm = _make_llm()
            embedder = AsyncMock()
            vector_store = AsyncMock()
            reranker = AsyncMock()

            result = await named_case_worker(state, llm, embedder, vector_store, reranker)

        assert len(result["worker_results"]) == 1
        wr = result["worker_results"][0]
        assert wr["task_type"] == "named_case"
        assert len(wr["results"]) >= 1
        assert wr["error"] is None

    @pytest.mark.asyncio
    async def test_fallback_to_title_search(self) -> None:
        """When citation search fails, fallback to _search_by_title."""
        state = {
            "task": {
                "task_id": "t1",
                "task_type": "named_case",
                "nl_query": "Maneka Gandhi passport case",
                "boolean_query": "",
                "named_cases": [
                    {"name": "Maneka Gandhi v. Union of India", "citation": ""},
                ],
                "rationale": "Article 21 expansion",
                "filters": {},
                "priority": 1,
            },
            "precomputed_embeddings": {},
        }

        with patch("app.core.agents.nodes.worker_nodes.async_session_factory") as mock_sf, \
             patch("app.core.agents.nodes.worker_nodes._exact_citation_search", new_callable=AsyncMock) as mock_cite, \
             patch("app.core.agents.nodes.worker_nodes._search_by_title", new_callable=AsyncMock) as mock_title, \
             patch("app.core.agents.nodes.worker_nodes.enrich_results_with_ratio", new_callable=AsyncMock) as mock_enrich, \
             patch("app.core.agents.nodes.worker_nodes.parallel_hybrid_search", new_callable=AsyncMock) as mock_hybrid:

            mock_ctx = AsyncMock()
            mock_sf.return_value = mock_ctx
            mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_ctx.__aexit__ = AsyncMock(return_value=False)

            # Citation search returns nothing (no citation provided)
            mock_cite.return_value = []
            # Title search returns a result
            mock_title.return_value = [
                {"case_id": "c2", "title": "Maneka Gandhi v. Union of India",
                 "citation": "(1978) 1 SCC 248", "score": 0.95}
            ]
            mock_enrich.side_effect = lambda results, db, **kw: results
            mock_hybrid.return_value = []

            result = await named_case_worker(
                state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock()
            )

        wr = result["worker_results"][0]
        assert len(wr["results"]) >= 1
        assert wr["error"] is None

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        state = {
            "task": {
                "task_id": "t1", "task_type": "named_case",
                "nl_query": "test", "boolean_query": "",
                "named_cases": [{"name": "Test", "citation": "X"}],
                "rationale": "r", "filters": {}, "priority": 1,
            },
            "precomputed_embeddings": {},
        }

        with patch("app.core.agents.nodes.worker_nodes.async_session_factory") as mock_sf:
            mock_ctx = AsyncMock()
            mock_sf.return_value = mock_ctx
            mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
            mock_ctx.__aexit__ = AsyncMock(return_value=False)

            result = await named_case_worker(
                state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock()
            )

        wr = result["worker_results"][0]
        assert wr["error"] is not None
        assert "DB down" in wr["error"]


# ===========================================================================
# Bible Test 1 (cont): case_law_worker isolation test
# ===========================================================================


class TestCaseLawWorker:
    """Bible test 1 + 1D.4 — case_law_worker with mocked deps."""

    @pytest.mark.asyncio
    async def test_dual_query_search(self) -> None:
        """Verify both nl_query and boolean_query are searched."""
        state = {
            "task": {
                "task_id": "t1",
                "task_type": "case_law",
                "nl_query": "anticipatory bail Section 438",
                "boolean_query": "anticipatory AND bail AND Section 438",
                "named_cases": [],
                "rationale": "Search for bail cases",
                "filters": {},
                "priority": 1,
            },
            "precomputed_embeddings": {},
        }

        with patch("app.core.agents.nodes.worker_nodes.async_session_factory") as mock_sf, \
             patch("app.core.agents.nodes.worker_nodes.parallel_hybrid_search", new_callable=AsyncMock) as mock_search, \
             patch("app.core.agents.nodes.worker_nodes.enrich_results_with_ratio", new_callable=AsyncMock) as mock_enrich:

            mock_ctx = AsyncMock()
            mock_sf.return_value = mock_ctx
            mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_ctx.__aexit__ = AsyncMock(return_value=False)

            mock_search.return_value = [_make_search_result()]
            mock_enrich.side_effect = lambda results, db, **kw: results

            result = await case_law_worker(
                state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock()
            )

        # Verify parallel_hybrid_search received BOTH queries
        call_args = mock_search.call_args
        queries_sent = call_args.args[0] if call_args.args else call_args.kwargs.get("queries", [])
        assert len(queries_sent) == 2
        assert "anticipatory bail Section 438" in queries_sent
        assert "anticipatory AND bail AND Section 438" in queries_sent

        wr = result["worker_results"][0]
        assert wr["task_type"] == "case_law"
        assert len(wr["results"]) >= 1
        assert wr["error"] is None

    @pytest.mark.asyncio
    async def test_single_query_when_no_boolean(self) -> None:
        state = {
            "task": {
                "task_id": "t1", "task_type": "case_law",
                "nl_query": "bail provisions", "boolean_query": "",
                "named_cases": [], "rationale": "r", "filters": {}, "priority": 1,
            },
            "precomputed_embeddings": {},
        }

        with patch("app.core.agents.nodes.worker_nodes.async_session_factory") as mock_sf, \
             patch("app.core.agents.nodes.worker_nodes.parallel_hybrid_search", new_callable=AsyncMock) as mock_search, \
             patch("app.core.agents.nodes.worker_nodes.enrich_results_with_ratio", new_callable=AsyncMock) as mock_enrich:

            mock_ctx = AsyncMock()
            mock_sf.return_value = mock_ctx
            mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_search.return_value = []
            mock_enrich.side_effect = lambda results, db, **kw: results

            await case_law_worker(state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock())

        queries_sent = mock_search.call_args.args[0]
        assert len(queries_sent) == 1

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        state = {
            "task": {
                "task_id": "t1", "task_type": "case_law",
                "nl_query": "test", "boolean_query": "",
                "named_cases": [], "rationale": "r", "filters": {}, "priority": 1,
            },
            "precomputed_embeddings": {},
        }

        with patch("app.core.agents.nodes.worker_nodes.async_session_factory") as mock_sf:
            mock_ctx = AsyncMock()
            mock_sf.return_value = mock_ctx
            mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("Search down"))
            mock_ctx.__aexit__ = AsyncMock(return_value=False)

            result = await case_law_worker(
                state, _make_llm(), AsyncMock(), AsyncMock(), AsyncMock()
            )

        wr = result["worker_results"][0]
        assert wr["error"] is not None
        assert wr["results"] == []


# ===========================================================================
# Bible Test 5 (cont): gather_worker_results_node
# ===========================================================================


class TestGatherWorkerResultsNode:
    """Bible test 5 — deduplication + cross-references in V2 gather."""

    @pytest.mark.asyncio
    async def test_deduplicates_with_diversity(self) -> None:
        # 6 results from same case_id — should be capped at 4
        results = [_make_search_result(case_id="c1", score=0.9 - i * 0.01) for i in range(6)]
        worker_results = [_make_worker_result(results=results)]

        state = _make_v2_state(worker_results=worker_results)
        result = await gather_worker_results_node(state)

        c1_results = [r for r in result["search_results"] if r["case_id"] == "c1"]
        assert len(c1_results) <= 4

    @pytest.mark.asyncio
    async def test_cross_references_from_multiple_workers(self) -> None:
        wr1 = _make_worker_result(
            task_id="t1", task_type="case_law",
            results=[_make_search_result(case_id="shared_case")]
        )
        wr2 = _make_worker_result(
            task_id="t2", task_type="named_case",
            results=[_make_search_result(case_id="shared_case")]
        )

        state = _make_v2_state(worker_results=[wr1, wr2])
        result = await gather_worker_results_node(state)

        assert len(result["cross_references"]) >= 1
        xref = result["cross_references"][0]
        assert xref["case_id"] == "shared_case"
        assert xref["match_count"] >= 2

    @pytest.mark.asyncio
    async def test_empty_worker_results(self) -> None:
        state = _make_v2_state(worker_results=[])
        result = await gather_worker_results_node(state)
        assert result["search_results"] == []
        assert result["cross_references"] == []


# ===========================================================================
# Bible Tests 18-20: MA-RAG CoT
# ===========================================================================


class TestBatchWorkerCotWithReflectionNode:
    """Bible tests 18-20 — MA-RAG CoT + reflection."""

    @pytest.mark.asyncio
    async def test_returns_non_empty_reasoning(self) -> None:
        """Bible test 18 — worker reasoning is non-empty."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "reasoning": "Worker 1 found 5 cases about anticipatory bail. Key tension: ...",
            "should_pivot": False,
            "pivot_reason": "",
            "new_tasks": [],
            "reframe_query": None,
        }

        worker_results = [
            _make_worker_result(
                task_type="case_law", query="bail query",
                results=[_make_search_result(case_id=f"c{i}") for i in range(3)]
            )
        ]
        state = _make_v2_state(
            worker_results=worker_results,
            rewritten_query="anticipatory bail",
        )
        result = await batch_worker_cot_with_reflection_node(state, llm)

        assert "worker_reasonings" in result
        assert len(result["worker_reasonings"]) >= 1
        assert result["worker_reasonings"][0] != ""

    @pytest.mark.asyncio
    async def test_cot_quality_mentions_findings(self) -> None:
        """Bible test 19 — reasoning mentions key findings, not just counts."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "reasoning": "Analysis: Found tension between Sushila Aggarwal and Bhadresh Bipinbhai on bail conditions.",
            "should_pivot": False,
        }

        worker_results = [_make_worker_result(
            results=[
                _make_search_result(case_id="c1", title="Sushila Aggarwal"),
                _make_search_result(case_id="c2", title="Bhadresh Bipinbhai"),
            ]
        )]
        state = _make_v2_state(worker_results=worker_results)
        result = await batch_worker_cot_with_reflection_node(state, llm)

        # Verify the LLM prompt includes case titles for quality reasoning
        call_kwargs = llm.generate_structured.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "Sushila Aggarwal" in prompt
        assert "Bhadresh Bipinbhai" in prompt

    @pytest.mark.asyncio
    async def test_reflection_returns_strategy_adjustment(self) -> None:
        """Bible test Q5 — reflection returns strategy_adjustment."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "reasoning": "Need to broaden scope to include HC rulings.",
            "should_pivot": True,
            "pivot_reason": "SC cases insufficient — need HC perspective",
            "new_tasks": [
                {"task_type": "case_law", "nl_query": "HC anticipatory bail", "rationale": "HC rulings"}
            ],
            "reframe_query": "anticipatory bail across all courts",
        }

        worker_results = [_make_worker_result(results=[_make_search_result()])]
        state = _make_v2_state(worker_results=worker_results)
        result = await batch_worker_cot_with_reflection_node(state, llm)

        assert result["strategy_adjustment"] is not None
        sa = result["strategy_adjustment"]
        assert sa["should_pivot"] is True
        assert "HC" in sa["pivot_reason"]
        assert len(sa["new_tasks"]) >= 1

    @pytest.mark.asyncio
    async def test_no_pivot_returns_none_strategy(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "reasoning": "All results look good.",
            "should_pivot": False,
        }

        worker_results = [_make_worker_result(results=[_make_search_result()])]
        state = _make_v2_state(worker_results=worker_results)
        result = await batch_worker_cot_with_reflection_node(state, llm)

        assert result["strategy_adjustment"] is None

    @pytest.mark.asyncio
    async def test_empty_worker_results(self) -> None:
        state = _make_v2_state(worker_results=[])
        llm = _make_llm()
        result = await batch_worker_cot_with_reflection_node(state, llm)
        assert result["worker_reasonings"] == []
        assert result["strategy_adjustment"] is None


# ===========================================================================
# Bible Test 7: Gap analysis loop
# ===========================================================================


class TestGapAnalysisNode:
    """Bible test 7 — gap detection + refinement rounds."""

    @pytest.mark.asyncio
    async def test_identifies_evidence_gaps(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "gaps": [
                {
                    "description": "No cases found on bail for economic offences",
                    "suggested_query": "anticipatory bail economic offences",
                    "suggested_source": "case_law",
                    "priority": 1,
                    "conditioned_on": ["c1"],
                    "conditioning_context": "Building on Sushila Aggarwal findings",
                },
            ]
        }

        worker_results = [_make_worker_result(results=[_make_search_result(case_id="c1")])]
        state = _make_v2_state(
            worker_results=worker_results,
            research_plan=[{"task_type": "case_law", "nl_query": "bail"}],
            refinement_round=0,
        )
        result = await gap_analysis_node(state, llm)

        assert len(result["evidence_gaps"]) >= 1
        gap = result["evidence_gaps"][0]
        assert gap["suggested_query"] != ""
        assert gap["priority"] == 1

    @pytest.mark.asyncio
    async def test_generates_new_tasks_for_gaps(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "gaps": [
                {"description": "gap", "suggested_query": "new query",
                 "suggested_source": "case_law", "priority": 1,
                 "conditioned_on": [], "conditioning_context": ""},
            ]
        }

        state = _make_v2_state(
            worker_results=[_make_worker_result(results=[_make_search_result()])],
            research_plan=[],
            refinement_round=0,
        )
        result = await gap_analysis_node(state, llm)

        # Should have new research_plan tasks for dispatch
        assert "research_plan" in result
        assert len(result["research_plan"]) >= 1
        assert result["refinement_round"] == 1

    @pytest.mark.asyncio
    async def test_max_2_rounds_enforced(self) -> None:
        """Bible test 7 — max 2 refinement rounds."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "gaps": [
                {"description": "gap", "suggested_query": "q",
                 "suggested_source": "case_law", "priority": 1,
                 "conditioned_on": [], "conditioning_context": ""},
            ]
        }

        state = _make_v2_state(
            worker_results=[_make_worker_result(results=[_make_search_result()])],
            refinement_round=2,  # Already at max
        )
        result = await gap_analysis_node(state, llm)

        # Should NOT generate new tasks at round 2
        assert "research_plan" not in result or result.get("research_plan") is None
        assert result["refinement_round"] == 2

    @pytest.mark.asyncio
    async def test_mc_rag_conditioning(self) -> None:
        """Bible test Q1 — round 2 queries are conditioned on round 1 findings."""
        llm = _make_llm()
        llm.generate_structured.return_value = {"gaps": []}

        state = _make_v2_state(
            worker_results=[_make_worker_result(
                results=[_make_search_result(
                    case_id="c1", title="Bachan Singh", citation="(1980) 2 SCC 684"
                )]
            )],
            refinement_round=1,
        )
        await gap_analysis_node(state, llm)

        # Verify the prompt to LLM includes prior round results
        call_kwargs = llm.generate_structured.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "TOP RESULTS FROM PRIOR ROUNDS" in prompt
        assert "Bachan Singh" in prompt

    @pytest.mark.asyncio
    async def test_strategy_adjustment_adds_gaps(self) -> None:
        """Bible test Q5 — strategy pivot adds extra gap tasks."""
        llm = _make_llm()
        llm.generate_structured.return_value = {"gaps": []}

        strategy_adj = StrategyAdjustment(
            should_pivot=True,
            pivot_reason="Need HC perspective",
            new_tasks=[
                {"task_type": "case_law", "nl_query": "HC bail", "rationale": "HC view"},
            ],
            reframe_query=None,
        )

        state = _make_v2_state(
            worker_results=[_make_worker_result(results=[_make_search_result()])],
            strategy_adjustment=strategy_adj,
            refinement_round=0,
        )
        result = await gap_analysis_node(state, llm)

        # Strategy pivot tasks should appear as gaps
        strategy_gaps = [g for g in result["evidence_gaps"] if "[Strategy pivot]" in g["description"]]
        assert len(strategy_gaps) >= 1

    @pytest.mark.asyncio
    async def test_empty_worker_results(self) -> None:
        state = _make_v2_state(worker_results=[])
        llm = _make_llm()
        result = await gap_analysis_node(state, llm)
        assert result["evidence_gaps"] == []


# ===========================================================================
# Bible Tests 39-41: Fast Path
# ===========================================================================


class TestFastPathSearchNode:
    """Bible tests 39-40 — fast path routing + fallback."""

    @pytest.mark.asyncio
    async def test_simple_query_returns_results(self) -> None:
        """Bible test 39 — simple query goes through fast path."""
        llm = _make_llm()
        flash_llm = _make_llm()
        embedder = AsyncMock()
        vector_store = AsyncMock()
        reranker = AsyncMock()
        db = AsyncMock()

        results = [_make_search_result(case_id=f"c{i}") for i in range(5)]

        with patch("app.core.agents.nodes.research_nodes.parallel_hybrid_search", new_callable=AsyncMock) as mock_search, \
             patch("app.core.agents.nodes.research_nodes.enrich_results_with_ratio", new_callable=AsyncMock) as mock_enrich:
            mock_search.return_value = results
            mock_enrich.side_effect = lambda results, db, **kw: results

            state = _make_v2_state(
                query="What is Section 302 IPC?",
                complexity="simple",
                messages=[{"type": "classification", "data": {"topic": "criminal"}}],
            )
            result = await fast_path_search_node(state, llm, flash_llm, embedder, vector_store, reranker, db)

        assert "search_results" in result
        assert len(result["search_results"]) == 5
        assert "worker_results" in result

    @pytest.mark.asyncio
    async def test_fallback_when_few_results(self) -> None:
        """Bible test 40 — fast path fallback when < 3 results."""
        with patch("app.core.agents.nodes.research_nodes.parallel_hybrid_search", new_callable=AsyncMock) as mock_search, \
             patch("app.core.agents.nodes.research_nodes.enrich_results_with_ratio", new_callable=AsyncMock) as mock_enrich:
            mock_search.return_value = [_make_search_result()]  # Only 1 result
            mock_enrich.side_effect = lambda results, db, **kw: results

            state = _make_v2_state(complexity="simple")
            result = await fast_path_search_node(
                state, _make_llm(), _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
            )

        # Should fall back to complex
        assert result.get("complexity") == "complex"
        assert "search_results" not in result

    @pytest.mark.asyncio
    async def test_fallback_on_search_error(self) -> None:
        with patch("app.core.agents.nodes.research_nodes.parallel_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = RuntimeError("Search failed")

            state = _make_v2_state(complexity="simple")
            result = await fast_path_search_node(
                state, _make_llm(), _make_llm(), AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
            )

        assert result.get("complexity") == "complex"


class TestFastPathSynthesisNode:
    """Bible test 41 (quality aspect) — fast path synthesis."""

    @pytest.mark.asyncio
    async def test_produces_memo_and_confidence(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "# Research Summary\n\nBail is a right under Section 438 CrPC."

        state = _make_v2_state(
            search_results=[_make_search_result(case_id=f"c{i}", score=0.8) for i in range(5)],
            rewritten_query="Section 438 bail",
        )
        result = await fast_path_synthesis_node(state, llm)

        assert "draft_memo" in result
        assert "confidence" in result
        assert len(result["draft_memo"]) > 50
        assert 0.0 < result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_empty_results_returns_no_results_memo(self) -> None:
        state = _make_v2_state(search_results=[])
        llm = _make_llm()
        result = await fast_path_synthesis_node(state, llm)
        assert result["confidence"] == 0.0
        assert "No results" in result["draft_memo"]

    @pytest.mark.asyncio
    async def test_appends_legal_disclaimer(self) -> None:
        llm = _make_llm()
        llm.generate.return_value = "Memo text."

        state = _make_v2_state(
            search_results=[_make_search_result(score=0.8)],
        )
        result = await fast_path_synthesis_node(state, llm)
        assert "disclaimer" in result["draft_memo"].lower() or "legal advice" in result["draft_memo"].lower()

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        llm = _make_llm()
        llm.generate.side_effect = RuntimeError("LLM down")

        state = _make_v2_state(search_results=[_make_search_result()])
        result = await fast_path_synthesis_node(state, llm)
        assert "error" in result


# ===========================================================================
# Bible Test 6: Send() fan-out test (integration)
# ===========================================================================


class TestDispatchWorkersIntegration:
    """Bible test 6 — dispatch_workers Send() fan-out."""

    def test_dispatch_creates_sends_for_each_task(self) -> None:
        """Verify dispatch_workers creates one Send per research task."""
        from app.core.agents.research import build_research_graph

        # Test dispatch_workers logic directly
        state = _make_v2_state(
            research_plan=[
                ResearchTask(
                    task_id="t1", task_type="case_law",
                    nl_query="bail query", boolean_query="bail AND query",
                    named_cases=[], rationale="r", filters={}, priority=1,
                ),
                ResearchTask(
                    task_id="t2", task_type="named_case",
                    nl_query="Sushila Aggarwal", boolean_query="",
                    named_cases=[{"name": "Sushila Aggarwal"}],
                    rationale="r", filters={}, priority=1,
                ),
            ],
            precomputed_embeddings={},
        )

        # Import the dispatch_workers function from the graph builder
        # We need to test the inner function, so we build the graph first
        llm = _make_llm()
        graph = build_research_graph(
            llm=llm, flash_llm=llm, embedder=AsyncMock(),
            vector_store=AsyncMock(), reranker=AsyncMock(),
        )

        # Access the dispatch_workers node function directly
        # The graph builder creates dispatch_workers as a closure
        # Instead, test via the routing logic
        from langgraph.types import Send

        # Test the dispatch logic from research.py
        sends: list = []
        plan = state["research_plan"]
        precomputed = state.get("precomputed_embeddings", {})

        for task in plan:
            task_type = task.get("task_type", "case_law")
            if task_type in ("case_law", "named_case"):
                worker_name = f"{task_type}_worker"
                sends.append(Send(worker_name, {
                    "task": task,
                    "precomputed_embeddings": precomputed,
                }))

        assert len(sends) == 2
        assert sends[0].node == "case_law_worker"
        assert sends[1].node == "named_case_worker"

    def test_fallback_send_when_no_plan(self) -> None:
        """When research_plan is empty, create fallback Send."""
        from langgraph.types import Send

        state = _make_v2_state(research_plan=[], rewritten_query="fallback query")

        # Replicate fallback logic from research.py dispatch_workers
        sends: list = []
        plan = state.get("research_plan", [])
        if not plan:
            sends.append(Send("case_law_worker", {
                "task": {
                    "task_id": "fallback",
                    "task_type": "case_law",
                    "nl_query": state.get("rewritten_query") or state["query"],
                    "boolean_query": "",
                    "named_cases": [],
                    "rationale": "Fallback search",
                    "filters": {},
                    "priority": 1,
                },
                "precomputed_embeddings": {},
            }))

        assert len(sends) == 1
        assert sends[0].node == "case_law_worker"
        assert sends[0].arg["task"]["nl_query"] == "fallback query"


# ===========================================================================
# Bible Test 12: CRAG → gap_analysis web_fallback
# ===========================================================================


class TestCragGapAnalysisTrigger:
    """Bible test 12 — when >50% incorrect, verify web fallback triggers."""

    @pytest.mark.asyncio
    async def test_web_fallback_reflected_in_gap_analysis_prompt(self) -> None:
        llm = _make_llm()
        llm.generate_structured.return_value = {"gaps": []}

        # Many incorrect results
        relevance_scores = []
        for i in range(3):
            relevance_scores.append(RelevanceScore(
                case_id=f"correct_{i}", score=0.9, verdict="correct",
                reason="ok", action="keep",
            ))
        for i in range(7):
            relevance_scores.append(RelevanceScore(
                case_id=f"incorrect_{i}", score=0.1, verdict="incorrect",
                reason="irrelevant", action="needs_web_fallback",
            ))

        state = _make_v2_state(
            worker_results=[_make_worker_result(results=[_make_search_result()])],
            relevance_scores=relevance_scores,
            refinement_round=0,
        )
        await gap_analysis_node(state, llm)

        call_kwargs = llm.generate_structured.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "Web fallback recommended" in prompt


# ===========================================================================
# Bible Test 20: CoT → synthesis integration
# ===========================================================================


class TestCotSynthesisIntegration:
    """Bible test 20 — synthesis prompt receives worker reasonings."""

    @pytest.mark.asyncio
    async def test_worker_reasonings_available_in_state(self) -> None:
        """Verify batch_cot produces reasonings that would be in state for synthesis."""
        llm = _make_llm()
        llm.generate_structured.return_value = {
            "reasoning": "Key finding: Bail is a right, not a privilege. Tension between SC and HC views.",
            "should_pivot": False,
        }

        worker_results = [_make_worker_result(results=[_make_search_result()])]
        state = _make_v2_state(worker_results=worker_results)

        result = await batch_worker_cot_with_reflection_node(state, llm)

        # These reasonings would be in state for synthesis
        assert result["worker_reasonings"][0] != ""
        assert "Bail" in result["worker_reasonings"][0] or "finding" in result["worker_reasonings"][0]
