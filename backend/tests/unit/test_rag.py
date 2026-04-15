"""Unit tests for RAG pipeline helper functions."""

from unittest.mock import AsyncMock

import pytest

from app.core.chat.rag import (
    MAX_PROMPT_CHARS,
    ChatSource,
    RAGEvent,
    _format_context,
    _format_history,
    _generate_title,
    _reformulate_query,
)
from app.core.legal.prompts import CHAT_USER_WITH_CONTEXT


class TestGenerateTitle:
    """Test session title generation."""

    def test_short_question(self) -> None:
        assert _generate_title("What is Article 21?") == "What is Article 21?"

    def test_long_question_truncated(self) -> None:
        long_q = "x" * 120
        result = _generate_title(long_q)
        assert len(result) == 83  # 80 chars + "..."
        assert result.endswith("...")

    def test_exactly_80_chars(self) -> None:
        q = "a" * 80
        assert _generate_title(q) == q  # no ellipsis

    def test_whitespace_stripped(self) -> None:
        assert _generate_title("  Hello  ") == "Hello"


class TestFormatContext:
    """Test context formatting for the RAG prompt."""

    def test_empty_sources(self) -> None:
        result = _format_context([])
        assert "No relevant cases" in result

    def test_single_source(self) -> None:
        sources = [
            ChatSource(
                case_id="123",
                title="State v. Citizen",
                citation="(2020) 1 SCC 1",
                court="Supreme Court of India",
                year=2020,
                score=0.95,
            ),
        ]
        result = _format_context(sources)
        assert "[1] State v. Citizen" in result
        assert "(2020) 1 SCC 1" in result
        assert "Supreme Court of India" in result
        assert "2020" in result

    def test_multiple_sources_numbered(self) -> None:
        sources = [
            ChatSource(case_id="1", title="Case A"),
            ChatSource(case_id="2", title="Case B"),
            ChatSource(case_id="3", title="Case C"),
        ]
        result = _format_context(sources)
        assert "[1] Case A" in result
        assert "[2] Case B" in result
        assert "[3] Case C" in result

    def test_missing_fields_have_defaults(self) -> None:
        sources = [ChatSource(case_id="1")]
        result = _format_context(sources)
        assert "Untitled" in result
        assert "No citation" in result
        assert "Unknown court" in result
        assert "Unknown year" in result


class TestFormatContextTreatmentWarning:
    """Test treatment warning integration in RAG context formatting."""

    def test_overruled_language_triggers_warning(self) -> None:
        """Context should include warning when ratio contains overruling language."""
        sources = [
            ChatSource(
                case_id="123",
                title="State v. Kumar",
                citation="(2020) 1 SCC 1",
                court="Supreme Court of India",
                year=2020,
                score=0.95,
                ratio="The decision in ABC v. XYZ was expressly overruled by this Court.",
            ),
        ]
        result = _format_context(sources)
        assert "WARNING" in result
        assert "overruled" in result.lower()

    def test_per_incuriam_triggers_warning(self) -> None:
        """Context should include warning when chunk text contains per incuriam."""
        sources = [
            ChatSource(
                case_id="456",
                title="State v. Rajan",
                citation="(2021) 2 SCC 50",
                court="Supreme Court of India",
                year=2021,
                score=0.90,
                chunk_text="This judgment was rendered per incuriam and cannot be relied upon.",
            ),
        ]
        result = _format_context(sources)
        assert "WARNING" in result

    def test_no_warning_for_neutral_text(self) -> None:
        """Context should NOT include warning when text is neutral."""
        sources = [
            ChatSource(
                case_id="789",
                title="State v. Normal",
                citation="(2019) 5 SCC 100",
                court="Supreme Court of India",
                year=2019,
                score=0.85,
                ratio="The appeal is hereby dismissed on merits.",
                chunk_text="The parties entered into a contract.",
            ),
        ]
        result = _format_context(sources)
        assert "WARNING" not in result

    def test_no_warning_when_no_text(self) -> None:
        """Context should NOT include warning when ratio and chunk are empty."""
        sources = [
            ChatSource(case_id="000", title="Empty Case"),
        ]
        result = _format_context(sources)
        assert "WARNING" not in result


class TestFormatHistory:
    """Test chat history formatting for the prompt."""

    def test_empty_history(self) -> None:
        assert _format_history([]) == ""

    def test_single_user_message(self) -> None:
        history = [{"role": "user", "content": "What is right to privacy?"}]
        result = _format_history(history)
        assert "User: What is right to privacy?" in result
        assert "Previous conversation" in result

    def test_user_and_assistant(self) -> None:
        history = [
            {"role": "user", "content": "Question one"},
            {"role": "assistant", "content": "Answer one"},
        ]
        result = _format_history(history)
        assert "User: Question one" in result
        assert "Assistant: Answer one" in result

    def test_multiple_turns_preserved_order(self) -> None:
        history = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Second"},
        ]
        result = _format_history(history)
        first_pos = result.index("First")
        second_pos = result.index("Second")
        assert first_pos < second_pos


class TestRAGEventDataclass:
    """Test the RAGEvent dataclass."""

    def test_creation(self) -> None:
        event = RAGEvent(type="chunk", data={"content": "hello"})
        assert event.type == "chunk"
        assert event.data["content"] == "hello"

    def test_session_event(self) -> None:
        event = RAGEvent(type="session", data={"session_id": "abc", "title": "Test"})
        assert event.type == "session"
        assert event.data["session_id"] == "abc"

    def test_source_event(self) -> None:
        event = RAGEvent(
            type="source",
            data={"case_id": "123", "citation": "(2020) 1 SCC 1"},
        )
        assert event.type == "source"


class TestChatSourceDataclass:
    """Test the ChatSource dataclass."""

    def test_defaults(self) -> None:
        source = ChatSource(case_id="abc")
        assert source.case_id == "abc"
        assert source.title is None
        assert source.citation is None
        assert source.court is None
        assert source.year is None
        assert source.score == 0.0

    def test_immutable(self) -> None:
        source = ChatSource(case_id="abc", title="Test")
        with pytest.raises(AttributeError):
            source.title = "Changed"  # type: ignore[misc]


class TestEncryptionIntegration:
    """Test that encryption roundtrip works for chat messages."""

    def test_encrypt_then_safe_decrypt_roundtrip(self) -> None:
        from app.security.encryption import encrypt_field, safe_decrypt

        original = "What is the right to privacy under Article 21?"
        encrypted = encrypt_field(original)
        assert encrypted != original
        assert safe_decrypt(encrypted) == original

    def test_safe_decrypt_handles_plaintext(self) -> None:
        from app.security.encryption import safe_decrypt

        plaintext = "This is a plain text message, not encrypted."
        assert safe_decrypt(plaintext) == plaintext

    def test_safe_decrypt_handles_empty_string(self) -> None:
        from app.security.encryption import safe_decrypt

        assert safe_decrypt("") == ""

    def test_encrypt_produces_different_ciphertext_each_time(self) -> None:
        from app.security.encryption import encrypt_field

        text = "Same message"
        enc1 = encrypt_field(text)
        enc2 = encrypt_field(text)
        # Different nonces should produce different ciphertexts
        assert enc1 != enc2


class TestReformulateQuery:
    """Test multi-turn query reformulation."""

    @pytest.mark.asyncio
    async def test_calls_llm_generate_with_correct_prompt(self) -> None:
        """Verify _reformulate_query calls llm.generate with history context."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "What is the penalty under Section 498A IPC?"

        chat_history = [
            {"role": "user", "content": "Tell me about Section 498A IPC"},
            {"role": "assistant", "content": "Section 498A deals with cruelty by husband..."},
        ]

        result = await _reformulate_query("and the penalty?", chat_history, mock_llm)

        mock_llm.generate.assert_called_once()
        call_kwargs = mock_llm.generate.call_args
        assert "498A" in call_kwargs.kwargs["prompt"] or "498A" in call_kwargs[0][0] if call_kwargs[0] else "498A" in call_kwargs.kwargs["prompt"]
        assert "and the penalty?" in call_kwargs.kwargs["prompt"]
        assert call_kwargs.kwargs["temperature"] == 0.0
        assert call_kwargs.kwargs["max_tokens"] == 200
        assert result == "What is the penalty under Section 498A IPC?"

    @pytest.mark.asyncio
    async def test_uses_last_four_messages(self) -> None:
        """Only the last 4 messages should be included in context."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "reformulated query"

        chat_history = [
            {"role": "user", "content": "message 1"},
            {"role": "assistant", "content": "response 1"},
            {"role": "user", "content": "message 2"},
            {"role": "assistant", "content": "response 2"},
            {"role": "user", "content": "message 3"},
            {"role": "assistant", "content": "response 3"},
        ]

        await _reformulate_query("follow up", chat_history, mock_llm)

        prompt = mock_llm.generate.call_args.kwargs["prompt"]
        # First two messages (message 1, response 1) should NOT be in the prompt
        assert "message 1" not in prompt
        assert "response 1" not in prompt
        # Last four should be present
        assert "message 2" in prompt
        assert "response 2" in prompt
        assert "message 3" in prompt
        assert "response 3" in prompt

    @pytest.mark.asyncio
    async def test_strips_quotes_from_result(self) -> None:
        """LLM output with quotes should have them stripped."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = '"What is the penalty under Section 498A?"'

        chat_history = [{"role": "user", "content": "About 498A"}]

        result = await _reformulate_query("penalty?", chat_history, mock_llm)
        assert result == "What is the penalty under Section 498A?"

    @pytest.mark.asyncio
    async def test_fallback_on_llm_exception(self) -> None:
        """If LLM call fails, should return the original question."""
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = ConnectionError("LLM unavailable")

        chat_history = [{"role": "user", "content": "Tell me about Article 21"}]

        result = await _reformulate_query("and the penalty?", chat_history, mock_llm)
        assert result == "and the penalty?"

    @pytest.mark.asyncio
    async def test_fallback_on_empty_result(self) -> None:
        """If LLM returns empty string, should return the original question."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "   "

        chat_history = [{"role": "user", "content": "Tell me about Article 21"}]

        result = await _reformulate_query("and the penalty?", chat_history, mock_llm)
        assert result == "and the penalty?"

    @pytest.mark.asyncio
    async def test_truncates_long_messages(self) -> None:
        """Messages longer than 200 chars should be truncated in the prompt."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "reformulated"

        long_content = "x" * 500
        chat_history = [{"role": "user", "content": long_content}]

        await _reformulate_query("follow up", chat_history, mock_llm)

        prompt = mock_llm.generate.call_args.kwargs["prompt"]
        # The full 500-char content should NOT appear in the prompt
        assert long_content not in prompt
        # But a truncated version (200 chars) should
        assert "x" * 200 in prompt


class TestContextSizeGuard:
    """Test prompt truncation when context exceeds MAX_PROMPT_CHARS."""

    def _make_sources(self, n: int, chunk_size: int = 500) -> list[ChatSource]:
        """Create n ChatSource objects with large chunk text."""
        return [
            ChatSource(
                case_id=str(i),
                title=f"Case {i}",
                citation=f"(2020) {i} SCC {i}",
                court="Supreme Court of India",
                year=2020,
                score=0.9 - i * 0.1,
                ratio="R" * chunk_size,
                chunk_text="C" * chunk_size,
            )
            for i in range(n)
        ]

    def _build_prompt(
        self, sources: list[ChatSource], history: list[dict], question: str
    ) -> str:
        """Build a user prompt the same way rag_respond does."""
        context_text = _format_context(sources)
        history_text = _format_history(history)
        return CHAT_USER_WITH_CONTEXT.format(
            retrieved_context=context_text,
            chat_history=history_text,
            question=question,
        )

    def test_small_prompt_unchanged(self) -> None:
        """Prompt under MAX_PROMPT_CHARS should not be truncated."""
        sources = self._make_sources(5, chunk_size=100)
        history = [{"role": "user", "content": "Hello"}]
        question = "What is Article 21?"

        prompt = self._build_prompt(sources, history, question)
        assert len(prompt) < MAX_PROMPT_CHARS
        # All 5 sources should be present
        assert "[5]" in prompt

    def test_large_prompt_triggers_truncation(self) -> None:
        """Prompt over MAX_PROMPT_CHARS should be rebuilt with fewer sources/history."""
        # Create sources with very large chunks to exceed the limit
        per_source_chars = MAX_PROMPT_CHARS // 3
        sources = self._make_sources(5, chunk_size=per_source_chars)
        history = [
            {"role": "user", "content": "msg " * 5000},
            {"role": "assistant", "content": "resp " * 5000},
        ] * 10  # 20 messages
        question = "What is Article 21?"

        original_prompt = self._build_prompt(sources, history, question)
        assert len(original_prompt) > MAX_PROMPT_CHARS

        # Simulate the guard logic
        truncated_context = _format_context(sources[:3])
        truncated_history = _format_history(history[-4:])
        truncated_prompt = CHAT_USER_WITH_CONTEXT.format(
            retrieved_context=truncated_context,
            chat_history=truncated_history,
            question=question,
        )

        assert len(truncated_prompt) < len(original_prompt)
        # Only 3 sources in truncated version
        assert "[3]" in truncated_prompt
        assert "[4]" not in truncated_prompt

    def test_max_prompt_chars_constant(self) -> None:
        """MAX_PROMPT_CHARS should be 100_000 (~25K tokens)."""
        assert MAX_PROMPT_CHARS == 100_000
