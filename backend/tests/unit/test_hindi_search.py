"""Unit tests for Hindi search integration via GeminiTranslator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def translator():
    """Create a GeminiTranslator with mocked google.genai and settings."""
    mock_client = MagicMock()
    mock_genai_module = MagicMock()
    mock_genai_module.Client.return_value = mock_client

    with (
        patch.dict("sys.modules", {"google": MagicMock(), "google.genai": mock_genai_module}),
        patch("app.core.config.settings") as mock_settings,
    ):
        mock_settings.gemini_api_key = "test-key"
        mock_settings.gemini_flash_model = "gemini-3-flash-preview"

        import importlib

        import app.core.providers.translation.gemini_translator as mod

        importlib.reload(mod)

        t = mod.GeminiTranslator()
        yield t, t._client


class TestHindiSearchIntegration:
    @pytest.mark.asyncio
    async def test_hindi_query_detected(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock()

        result = await t.detect_language("भारतीय दंड संहिता")

        assert result == "hi"
        mock_client.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_english_query_detected(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock()

        result = await t.detect_language("Supreme Court judgment on property rights")

        assert result == "en"
        mock_client.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mixed_script_detection(self, translator):
        t, mock_client = translator
        mock_response = MagicMock()
        mock_response.text = "hi"
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        mixed_text = "IPC धारा 302 murder conviction appeal"
        result = await t.detect_language(mixed_text)

        assert result in ("hi", "en")

    @pytest.mark.asyncio
    async def test_translate_hindi_to_english(self, translator):
        t, mock_client = translator
        mock_response = MagicMock()
        mock_response.text = "Indian Penal Code section 302"
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await t.translate(
            "भारतीय दंड संहिता धारा 302",
            source="hi",
            target="en",
        )

        assert result == "Indian Penal Code section 302"
        call_args = mock_client.aio.models.generate_content.call_args
        prompt_text = str(call_args)
        assert "Hindi" in prompt_text
        assert "English" in prompt_text

    @pytest.mark.asyncio
    async def test_translate_english_to_hindi(self, translator):
        t, mock_client = translator
        mock_response = MagicMock()
        mock_response.text = "भारतीय दंड संहिता धारा 302"
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await t.translate(
            "Indian Penal Code section 302",
            source="en",
            target="hi",
        )

        assert result == "भारतीय दंड संहिता धारा 302"
        call_args = mock_client.aio.models.generate_content.call_args
        prompt_text = str(call_args)
        assert "English" in prompt_text
        assert "Hindi" in prompt_text

    @pytest.mark.asyncio
    async def test_empty_query_defaults_to_english(self, translator):
        t, mock_client = translator
        mock_client.aio.models.generate_content = AsyncMock()

        result = await t.detect_language("")

        assert result == "en"
        mock_client.aio.models.generate_content.assert_not_awaited()
