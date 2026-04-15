"""Tests for follow-up conversation graph nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.nodes.follow_up_nodes import (
    _format_conversation_history,
    _format_footnotes,
    _format_search_results,
    reformulate_with_context_node,
    synthesize_follow_up_node,
    targeted_search_node,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FakeSearchResultItem:
    """Minimal stand-in for SearchResultItem."""

    case_id: str
    score: float = 0.9
    title: str | None = None
    citation: str | None = None
    court: str | None = None
    year: int | None = None
    snippet: str | None = None


@dataclass(slots=True)
class FakeSearchResponse:
    """Minimal stand-in for SearchResponse."""

    results: list[FakeSearchResultItem] = field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 5
    query_understanding: object = None
    facets: dict = field(default_factory=dict)


def _make_state(**overrides: object) -> dict:
    """Build a minimal FollowUpState dict with sensible defaults."""
    base: dict = {
        "follow_up_query": "What about the dissenting opinion?",
        "prior_memo": "The court in Sharma v. State held that...",
        "prior_footnotes": [
            {
                "number": 1,
                "citation": "(2023) 5 SCC 100",
                "title": "Sharma v. State",
                "court": "Supreme Court of India",
                "year": 2023,
            }
        ],
        "conversation_history": [
            {"role": "user", "content": "Tell me about right to privacy"},
            {"role": "assistant", "content": "The right to privacy was..."},
        ],
        "reformulated_query": "",
        "search_results": [],
    }
    base.update(overrides)
    return base


def _make_search_results(n: int = 2) -> list[FakeSearchResultItem]:
    return [
        FakeSearchResultItem(
            case_id=f"case-{i}",
            score=0.95 - i * 0.05,
            title=f"Test Case {i}",
            citation=f"(2023) {i} SCC {100 + i}",
            court="Supreme Court of India",
            year=2023,
            snippet=f"Snippet for case {i}",
        )
        for i in range(1, n + 1)
    ]


# ---------------------------------------------------------------------------
# reformulate_with_context_node
# ---------------------------------------------------------------------------


class TestReformulateWithContextNode:
    @pytest.mark.asyncio
    async def test_basic_reformulation(self) -> None:
        flash_llm = AsyncMock()
        flash_llm.generate.return_value = "  What was the dissenting opinion in Sharma v. State?  "

        state = _make_state()
        result = await reformulate_with_context_node(state, flash_llm)

        assert result["reformulated_query"] == "What was the dissenting opinion in Sharma v. State?"
        assert len(result["process_events"]) == 1
        assert result["process_events"][0]["type"] == "progress"
        assert result["process_events"][0]["stage"] == "Reformulating"
        assert result["process_events"][0]["progress"] == 0.2

    @pytest.mark.asyncio
    async def test_strips_quotes_from_llm_response(self) -> None:
        flash_llm = AsyncMock()
        flash_llm.generate.return_value = '"reformulated query with quotes"'

        result = await reformulate_with_context_node(_make_state(), flash_llm)
        assert result["reformulated_query"] == "reformulated query with quotes"

    @pytest.mark.asyncio
    async def test_single_quotes_stripped(self) -> None:
        flash_llm = AsyncMock()
        flash_llm.generate.return_value = "'single quoted'"

        result = await reformulate_with_context_node(_make_state(), flash_llm)
        assert result["reformulated_query"] == "single quoted"

    @pytest.mark.asyncio
    async def test_llm_called_with_correct_params(self) -> None:
        flash_llm = AsyncMock()
        flash_llm.generate.return_value = "reformulated"

        await reformulate_with_context_node(_make_state(), flash_llm)

        flash_llm.generate.assert_awaited_once()
        call_kwargs = flash_llm.generate.call_args
        assert call_kwargs.kwargs["temperature"] == 0.0
        assert call_kwargs.kwargs["max_tokens"] == 200
        assert "follow_up_query" not in call_kwargs.kwargs  # passed as prompt string

    @pytest.mark.asyncio
    async def test_long_memo_truncated_for_reformulation(self) -> None:
        flash_llm = AsyncMock()
        flash_llm.generate.return_value = "reformulated"
        long_memo = "A" * 5000

        state = _make_state(prior_memo=long_memo)
        await reformulate_with_context_node(state, flash_llm)

        prompt_arg = flash_llm.generate.call_args.kwargs["prompt"]
        # The prompt should contain the truncated memo (3000 chars + truncation marker)
        assert "A" * 3000 in prompt_arg
        assert "... [truncated]" in prompt_arg
        # Should NOT contain the full 5000 chars
        assert "A" * 5000 not in prompt_arg

    @pytest.mark.asyncio
    async def test_empty_conversation_history(self) -> None:
        flash_llm = AsyncMock()
        flash_llm.generate.return_value = "reformulated"

        state = _make_state(conversation_history=[])
        await reformulate_with_context_node(state, flash_llm)

        prompt_arg = flash_llm.generate.call_args.kwargs["prompt"]
        assert "(No prior conversation)" in prompt_arg

    @pytest.mark.asyncio
    async def test_empty_prior_memo(self) -> None:
        flash_llm = AsyncMock()
        flash_llm.generate.return_value = "reformulated"

        state = _make_state(prior_memo="")
        result = await reformulate_with_context_node(state, flash_llm)
        assert result["reformulated_query"] == "reformulated"

    @pytest.mark.asyncio
    async def test_llm_failure_propagates(self) -> None:
        flash_llm = AsyncMock()
        flash_llm.generate.side_effect = RuntimeError("LLM unavailable")

        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await reformulate_with_context_node(_make_state(), flash_llm)

    @pytest.mark.asyncio
    async def test_detail_truncated_to_100_chars(self) -> None:
        flash_llm = AsyncMock()
        long_reformulation = "X" * 200
        flash_llm.generate.return_value = long_reformulation

        result = await reformulate_with_context_node(_make_state(), flash_llm)

        detail = result["process_events"][0]["detail"]
        # "Reformulated query: " prefix + first 100 chars
        assert len(detail) == len("Reformulated query: ") + 100


# ---------------------------------------------------------------------------
# targeted_search_node
# ---------------------------------------------------------------------------


class TestTargetedSearchNode:
    def _make_deps(
        self,
        search_results: list[FakeSearchResultItem] | None = None,
    ) -> dict:
        """Build mocked dependency dict for targeted_search_node."""
        if search_results is None:
            search_results = _make_search_results(2)

        fake_response = FakeSearchResponse(
            results=search_results,
            total_count=len(search_results),
        )

        embedder = AsyncMock()
        vector_store = AsyncMock()
        reranker = AsyncMock()
        redis_client = AsyncMock()
        llm = AsyncMock()

        # db_session_factory is an async context manager factory
        db_session = AsyncMock()
        db_cm = AsyncMock()
        db_cm.__aenter__ = AsyncMock(return_value=db_session)
        db_cm.__aexit__ = AsyncMock(return_value=False)
        db_session_factory = MagicMock(return_value=db_cm)

        return {
            "embedder": embedder,
            "vector_store": vector_store,
            "reranker": reranker,
            "db_session_factory": db_session_factory,
            "redis_client": redis_client,
            "llm": llm,
            "fake_response": fake_response,
        }

    @pytest.mark.asyncio
    async def test_basic_search_returns_results(self) -> None:
        deps = self._make_deps()
        state = _make_state(reformulated_query="dissenting opinion in Sharma v. State")

        with patch(
            "app.core.agents.nodes.follow_up_nodes.hybrid_search",
            new_callable=AsyncMock,
            return_value=deps["fake_response"],
        ):
            result = await targeted_search_node(
                state,
                embedder=deps["embedder"],
                vector_store=deps["vector_store"],
                reranker=deps["reranker"],
                db_session_factory=deps["db_session_factory"],
                redis_client=deps["redis_client"],
                llm=deps["llm"],
            )

        assert len(result["search_results"]) == 2
        assert result["search_results"][0]["case_id"] == "case-1"
        assert result["search_results"][0]["title"] == "Test Case 1"
        assert result["search_results"][0]["citation"] == "(2023) 1 SCC 101"
        assert result["search_results"][0]["court"] == "Supreme Court of India"
        assert result["search_results"][0]["year"] == 2023
        assert result["search_results"][0]["snippet"] == "Snippet for case 1"
        assert result["search_results"][0]["score"] == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_progress_event_emitted(self) -> None:
        deps = self._make_deps()
        state = _make_state(reformulated_query="test query")

        with patch(
            "app.core.agents.nodes.follow_up_nodes.hybrid_search",
            new_callable=AsyncMock,
            return_value=deps["fake_response"],
        ):
            result = await targeted_search_node(
                state,
                embedder=deps["embedder"],
                vector_store=deps["vector_store"],
                reranker=deps["reranker"],
                db_session_factory=deps["db_session_factory"],
                redis_client=deps["redis_client"],
                llm=deps["llm"],
            )

        assert len(result["process_events"]) == 1
        evt = result["process_events"][0]
        assert evt["type"] == "progress"
        assert evt["stage"] == "Searching"
        assert evt["progress"] == 0.5
        assert "2 results" in evt["detail"]

    @pytest.mark.asyncio
    async def test_falls_back_to_follow_up_query_when_no_reformulated(self) -> None:
        deps = self._make_deps()
        state = _make_state(reformulated_query="", follow_up_query="original question")

        with patch(
            "app.core.agents.nodes.follow_up_nodes.hybrid_search",
            new_callable=AsyncMock,
            return_value=deps["fake_response"],
        ) as mock_search:
            await targeted_search_node(
                state,
                embedder=deps["embedder"],
                vector_store=deps["vector_store"],
                reranker=deps["reranker"],
                db_session_factory=deps["db_session_factory"],
                redis_client=deps["redis_client"],
                llm=deps["llm"],
            )

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["query"] == "original question"

    @pytest.mark.asyncio
    async def test_uses_reformulated_query_when_present(self) -> None:
        deps = self._make_deps()
        state = _make_state(reformulated_query="refined question")

        with patch(
            "app.core.agents.nodes.follow_up_nodes.hybrid_search",
            new_callable=AsyncMock,
            return_value=deps["fake_response"],
        ) as mock_search:
            await targeted_search_node(
                state,
                embedder=deps["embedder"],
                vector_store=deps["vector_store"],
                reranker=deps["reranker"],
                db_session_factory=deps["db_session_factory"],
                redis_client=deps["redis_client"],
                llm=deps["llm"],
            )

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["query"] == "refined question"

    @pytest.mark.asyncio
    async def test_passes_settings_max_results(self) -> None:
        deps = self._make_deps()
        state = _make_state(reformulated_query="query")

        with (
            patch(
                "app.core.agents.nodes.follow_up_nodes.hybrid_search",
                new_callable=AsyncMock,
                return_value=deps["fake_response"],
            ) as mock_search,
            patch("app.core.agents.nodes.follow_up_nodes.settings") as mock_settings,
        ):
            mock_settings.agent_followup_max_results = 7
            await targeted_search_node(
                state,
                embedder=deps["embedder"],
                vector_store=deps["vector_store"],
                reranker=deps["reranker"],
                db_session_factory=deps["db_session_factory"],
                redis_client=deps["redis_client"],
                llm=deps["llm"],
            )

        assert mock_search.call_args.kwargs["page_size"] == 7

    @pytest.mark.asyncio
    async def test_empty_search_results(self) -> None:
        deps = self._make_deps(search_results=[])
        state = _make_state(reformulated_query="obscure query")

        with patch(
            "app.core.agents.nodes.follow_up_nodes.hybrid_search",
            new_callable=AsyncMock,
            return_value=deps["fake_response"],
        ):
            result = await targeted_search_node(
                state,
                embedder=deps["embedder"],
                vector_store=deps["vector_store"],
                reranker=deps["reranker"],
                db_session_factory=deps["db_session_factory"],
                redis_client=deps["redis_client"],
                llm=deps["llm"],
            )

        assert result["search_results"] == []
        assert "0 results" in result["process_events"][0]["detail"]

    @pytest.mark.asyncio
    async def test_hybrid_search_failure_propagates(self) -> None:
        deps = self._make_deps()
        state = _make_state(reformulated_query="query")

        with (
            patch(
                "app.core.agents.nodes.follow_up_nodes.hybrid_search",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Search failed"),
            ),
            pytest.raises(RuntimeError, match="Search failed"),
        ):
            await targeted_search_node(
                state,
                embedder=deps["embedder"],
                vector_store=deps["vector_store"],
                reranker=deps["reranker"],
                db_session_factory=deps["db_session_factory"],
                redis_client=deps["redis_client"],
                llm=deps["llm"],
            )

    @pytest.mark.asyncio
    async def test_redis_client_none_accepted(self) -> None:
        deps = self._make_deps()
        state = _make_state(reformulated_query="query")

        with patch(
            "app.core.agents.nodes.follow_up_nodes.hybrid_search",
            new_callable=AsyncMock,
            return_value=deps["fake_response"],
        ) as mock_search:
            await targeted_search_node(
                state,
                embedder=deps["embedder"],
                vector_store=deps["vector_store"],
                reranker=deps["reranker"],
                db_session_factory=deps["db_session_factory"],
                redis_client=None,
                llm=deps["llm"],
            )

        assert mock_search.call_args.kwargs["redis_client"] is None


# ---------------------------------------------------------------------------
# synthesize_follow_up_node
# ---------------------------------------------------------------------------


class TestSynthesizeFollowUpNode:
    @pytest.mark.asyncio
    async def test_basic_synthesis_without_streaming(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "The dissenting opinion by Justice X held that..."

        state = _make_state(
            search_results=[
                {
                    "case_id": "case-1",
                    "title": "Sharma v. State",
                    "citation": "(2023) 5 SCC 100",
                    "court": "Supreme Court of India",
                    "year": 2023,
                    "snippet": "Justice X dissented on the ground...",
                    "score": 0.9,
                },
            ],
        )

        result = await synthesize_follow_up_node(state, llm)

        assert result["response"] == "The dissenting opinion by Justice X held that..."
        assert result["confidence"] == 0.7
        assert len(result["footnotes"]) == 1
        assert result["footnotes"][0]["citation"] == "(2023) 5 SCC 100"
        assert result["footnotes"][0]["case_id"] == "case-1"
        assert result["footnotes"][0]["number"] == 1
        assert result["footnotes"][0]["source_type"] == "case"
        assert result["footnotes"][0]["verification_status"] == "unverified"
        assert result["footnotes"][0]["is_used"] is True

    @pytest.mark.asyncio
    async def test_llm_called_with_correct_params(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "response"

        state = _make_state(search_results=[])
        await synthesize_follow_up_node(state, llm)

        llm.generate.assert_awaited_once()
        call_kwargs = llm.generate.call_args.kwargs
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["max_tokens"] == 4096
        assert "system" in call_kwargs

    @pytest.mark.asyncio
    async def test_streaming_with_callback(self) -> None:
        llm = AsyncMock()

        async def fake_stream(**kwargs: object):
            for chunk in ["The ", "dissenting ", "opinion ", "was..."]:
                yield chunk

        llm.stream = fake_stream
        callback = AsyncMock()

        state = _make_state(search_results=[])
        result = await synthesize_follow_up_node(state, llm, memo_stream_callback=callback)

        assert result["response"] == "The dissenting opinion was..."
        assert callback.await_count == 4
        # Verify each chunk was passed to callback
        callback.assert_any_await("The ")
        callback.assert_any_await("dissenting ")
        callback.assert_any_await("opinion ")
        callback.assert_any_await("was...")

    @pytest.mark.asyncio
    async def test_progress_event_emitted(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "response"

        state = _make_state(search_results=[])
        result = await synthesize_follow_up_node(state, llm)

        assert len(result["process_events"]) == 1
        evt = result["process_events"][0]
        assert evt["type"] == "progress"
        assert evt["stage"] == "Synthesizing"
        assert evt["progress"] == 1.0

    @pytest.mark.asyncio
    async def test_footnotes_from_multiple_search_results(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "synthesized"

        search_results = [
            {
                "case_id": f"case-{i}",
                "title": f"Case {i}",
                "citation": f"(2023) {i} SCC {i}",
                "court": "SC",
                "year": 2023,
                "snippet": f"Snippet {i}",
                "score": 0.5,
            }
            for i in range(1, 4)
        ]
        state = _make_state(search_results=search_results)
        result = await synthesize_follow_up_node(state, llm)

        assert len(result["footnotes"]) == 3
        for i, fn in enumerate(result["footnotes"], 1):
            assert fn["number"] == i
            assert fn["case_id"] == f"case-{i}"
            assert fn["citation"] == f"(2023) {i} SCC {i}"

    @pytest.mark.asyncio
    async def test_long_snippet_truncated_in_footnote(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "synthesized"

        long_snippet = "Z" * 500
        state = _make_state(
            search_results=[
                {
                    "case_id": "c1",
                    "title": "T",
                    "citation": "cite",
                    "court": "SC",
                    "year": 2023,
                    "snippet": long_snippet,
                    "score": 0.5,
                }
            ],
        )
        result = await synthesize_follow_up_node(state, llm)

        assert len(result["footnotes"][0]["excerpt"]) == 300

    @pytest.mark.asyncio
    async def test_long_memo_truncated_per_settings(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "synthesized"

        long_memo = "M" * 20000
        state = _make_state(prior_memo=long_memo, search_results=[])

        with patch("app.core.agents.nodes.follow_up_nodes.settings") as mock_settings:
            mock_settings.agent_followup_memo_chars = 15000
            await synthesize_follow_up_node(state, llm)

        prompt_arg = llm.generate.call_args.kwargs["prompt"]
        assert "M" * 15000 in prompt_arg
        assert "... [memo truncated for context]" in prompt_arg
        assert "M" * 20000 not in prompt_arg

    @pytest.mark.asyncio
    async def test_empty_search_results_and_footnotes(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "Based on the prior memo..."

        state = _make_state(
            search_results=[],
            prior_footnotes=[],
        )
        result = await synthesize_follow_up_node(state, llm)

        assert result["footnotes"] == []
        prompt_arg = llm.generate.call_args.kwargs["prompt"]
        assert "(No prior footnotes)" in prompt_arg
        assert "(No new search results found)" in prompt_arg

    @pytest.mark.asyncio
    async def test_llm_failure_propagates(self) -> None:
        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM down")

        state = _make_state(search_results=[])
        with pytest.raises(RuntimeError, match="LLM down"):
            await synthesize_follow_up_node(state, llm)

    @pytest.mark.asyncio
    async def test_streaming_error_propagates(self) -> None:
        llm = AsyncMock()

        async def failing_stream(**kwargs: object):
            yield "partial "
            raise RuntimeError("Stream interrupted")

        llm.stream = failing_stream
        callback = AsyncMock()

        state = _make_state(search_results=[])
        with pytest.raises(RuntimeError, match="Stream interrupted"):
            await synthesize_follow_up_node(state, llm, memo_stream_callback=callback)

    @pytest.mark.asyncio
    async def test_footnote_missing_fields_default_gracefully(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "synthesized"

        state = _make_state(
            search_results=[{"case_id": "c1"}],  # minimal — missing most fields
        )
        result = await synthesize_follow_up_node(state, llm)

        fn = result["footnotes"][0]
        assert fn["citation"] == ""
        assert fn["title"] == ""
        assert fn["court"] == ""
        assert fn["year"] is None
        assert fn["excerpt"] == ""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestFormatConversationHistory:
    def test_empty_history(self) -> None:
        assert _format_conversation_history([]) == "(No prior conversation)"

    def test_single_message(self) -> None:
        history = [{"role": "user", "content": "Hello"}]
        result = _format_conversation_history(history)
        assert "User: Hello" in result

    def test_role_title_cased(self) -> None:
        history = [{"role": "assistant", "content": "Hi"}]
        result = _format_conversation_history(history)
        assert "Assistant: Hi" in result

    def test_max_messages_limits_output(self) -> None:
        history = [{"role": "user", "content": f"msg-{i}"} for i in range(10)]
        result = _format_conversation_history(history, max_messages=3)
        # Only last 3 messages should appear
        assert "msg-7" in result
        assert "msg-8" in result
        assert "msg-9" in result
        assert "msg-0" not in result

    def test_content_truncated_to_500_chars(self) -> None:
        long_content = "W" * 1000
        history = [{"role": "user", "content": long_content}]
        result = _format_conversation_history(history)
        assert "W" * 500 in result
        assert "W" * 501 not in result

    def test_missing_role_defaults_to_user(self) -> None:
        history = [{"content": "no role"}]
        result = _format_conversation_history(history)
        assert "User: no role" in result

    def test_missing_content_defaults_to_empty(self) -> None:
        history = [{"role": "user"}]
        result = _format_conversation_history(history)
        assert "User: " in result


class TestFormatFootnotes:
    def test_empty_footnotes(self) -> None:
        assert _format_footnotes([]) == "(No prior footnotes)"

    def test_single_footnote(self) -> None:
        footnotes = [
            {
                "number": 1,
                "citation": "(2023) 5 SCC 100",
                "title": "Sharma v. State",
                "court": "SC",
                "year": 2023,
            }
        ]
        result = _format_footnotes(footnotes)
        assert "[^1]" in result
        assert "(2023) 5 SCC 100" in result
        assert "Sharma v. State" in result
        assert "SC" in result
        assert "2023" in result

    def test_max_footnotes_limit(self) -> None:
        footnotes = [
            {"number": i, "citation": f"cite-{i}", "title": f"T-{i}", "court": "SC", "year": 2020}
            for i in range(30)
        ]
        result = _format_footnotes(footnotes, max_footnotes=5)
        assert "cite-4" in result
        assert "cite-5" not in result  # 0-indexed, so footnotes[5] is the 6th

    def test_missing_fields_use_defaults(self) -> None:
        footnotes = [{}]
        result = _format_footnotes(footnotes)
        assert "[^?]" in result
        assert "Unknown" in result


class TestFormatSearchResults:
    def test_empty_results(self) -> None:
        assert _format_search_results([]) == "(No new search results found)"

    def test_single_result(self) -> None:
        results = [
            {
                "title": "Test Case",
                "citation": "(2023) 1 SCC 1",
                "court": "SC",
                "year": 2023,
                "snippet": "The court held...",
            }
        ]
        result = _format_search_results(results)
        assert "[1]" in result
        assert "Test Case" in result
        assert "(2023) 1 SCC 1" in result
        assert "SC" in result
        assert "2023" in result
        assert "The court held..." in result

    def test_snippet_truncated_to_500(self) -> None:
        results = [{"title": "T", "snippet": "S" * 1000}]
        result = _format_search_results(results)
        assert "S" * 500 in result
        assert "S" * 501 not in result

    def test_missing_fields_use_defaults(self) -> None:
        results = [{}]
        result = _format_search_results(results)
        assert "Unknown" in result
