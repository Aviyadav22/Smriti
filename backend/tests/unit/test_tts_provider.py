"""Tests for TTS providers."""

import pytest

from app.core.interfaces.tts import TTSProvider
from app.core.providers.tts.mock_tts import MockTTS


class TestMockTTS:
    @pytest.fixture()
    def tts(self) -> MockTTS:
        return MockTTS()

    async def test_implements_protocol(self, tts: MockTTS) -> None:
        assert isinstance(tts, TTSProvider)

    async def test_synthesize_returns_bytes(self, tts: MockTTS) -> None:
        audio = await tts.synthesize("Hello world", language="en")
        assert isinstance(audio, bytes)
        assert len(audio) > 0

    async def test_synthesize_hindi(self, tts: MockTTS) -> None:
        audio = await tts.synthesize("नमस्ते", language="hi")
        assert isinstance(audio, bytes)
        assert len(audio) > 0

    async def test_unsupported_language_raises(self, tts: MockTTS) -> None:
        with pytest.raises(ValueError, match="not supported"):
            await tts.synthesize("Hello", language="fr")

    async def test_get_supported_languages(self, tts: MockTTS) -> None:
        langs = await tts.get_supported_languages()
        assert "en" in langs
        assert "hi" in langs

    async def test_synthesize_starts_with_mp3_sync_bytes(self, tts: MockTTS) -> None:
        audio = await tts.synthesize("Test", language="en")
        assert audio[:2] == b"\xff\xfb"
