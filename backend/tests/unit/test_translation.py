"""Unit tests for the GeminiTranslator provider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def translator():
    """Create a GeminiTranslator with mocked google.genai and settings."""
    mock_client = MagicMock()
    mock_genai_module = MagicMock()
    mock_genai_module.Client.return_value = mock_client

    with patch.dict("sys.modules", {"google": MagicMock(), "google.genai": mock_genai_module}), \
         patch("app.core.providers.translation.gemini_translator.settings") as mock_settings:
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_flash_model = "gemini-2.0-flash"

        # Re-import to pick up mocked genai
        import importlib
        import app.core.providers.translation.gemini_translator as mod
        importlib.reload(mod)

        t = mod.GeminiTranslator()
        # The client is created inside __init__ via genai.Client(...)
        # We need to get the actual client instance used
        yield t, t._client


class TestGeminiTranslator:
    @pytest.mark.asyncio
    async def test_translate_returns_translated_text(self, translator):
        t, mock_client = translator
        mock_response = MagicMock()
        mock_response.text = "  translated text  "
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await t.translate("original text", source="en", target="hi")

        assert result == "translated text"
        mock_client.aio.models.generate_content.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_translate_empty_text(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock()

        result = await t.translate("", source="en", target="hi")

        assert result == ""
        mock_client.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_translate_whitespace_only(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock()

        result = await t.translate("   ", source="en", target="hi")

        assert result == "   "
        mock_client.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_translate_preserves_source_target_in_prompt(self, translator):
        t, mock_client = translator
        mock_response = MagicMock()
        mock_response.text = "अनुवादित पाठ"
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        await t.translate("original text", source="en", target="hi")

        call_args = mock_client.aio.models.generate_content.call_args
        prompt_text = str(call_args)
        assert "English" in prompt_text
        assert "Hindi" in prompt_text

    @pytest.mark.asyncio
    async def test_detect_language_hindi_text(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock()

        # Over 30% Devanagari characters — should return "hi" without LLM
        hindi_text = "भारतीय दंड संहिता की धारा के अंतर्गत हत्या का अपराध"
        result = await t.detect_language(hindi_text)

        assert result == "hi"
        mock_client.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_detect_language_english_text(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock()

        english_text = "The Indian Penal Code section 302 pertains to murder."
        result = await t.detect_language(english_text)

        assert result == "en"
        mock_client.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_detect_language_empty_text(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock()

        result = await t.detect_language("")

        assert result == "en"
        mock_client.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_detect_language_ambiguous_uses_llm(self, translator):
        t, mock_client = translator
        mock_response = MagicMock()
        mock_response.text = "hi"
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Mix with ~15% Devanagari — triggers LLM fallback
        ambiguous_text = "Section 302 IPC धारा applies to this case under the law"
        result = await t.detect_language(ambiguous_text)

        mock_client.aio.models.generate_content.assert_awaited_once()
        assert result in ("hi", "en")

    @pytest.mark.asyncio
    async def test_translate_returns_original_on_api_failure(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("API unavailable")
        )

        result = await t.translate("original text", source="en", target="hi")

        assert result == "original text"

    @pytest.mark.asyncio
    async def test_translate_handles_none_response(self, translator):
        t, mock_client = translator
        mock_response = MagicMock()
        mock_response.text = None
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await t.translate("original text", source="en", target="hi")

        assert result == "original text"

    @pytest.mark.asyncio
    async def test_detect_language_returns_en_on_api_failure(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("API unavailable")
        )

        # Ambiguous text that would normally trigger LLM call
        ambiguous_text = "Section 302 IPC धारा applies to this case under the law"
        result = await t.detect_language(ambiguous_text)

        assert result == "en"
