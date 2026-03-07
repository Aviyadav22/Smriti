"""Unit tests for RAG pipeline helper functions."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.chat.rag import (
    ChatSource,
    RAGEvent,
    _format_context,
    _format_history,
    _generate_title,
    _reformulate_query,
)


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
        mock_llm.generate.side_effect = RuntimeError("LLM unavailable")

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
