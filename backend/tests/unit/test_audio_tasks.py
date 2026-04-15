"""Tests for audio generation Celery task."""

from unittest.mock import patch

from app.core.providers.tts.mock_tts import MockTTS
from app.tasks.audio_tasks import _get_tts_provider


class TestGetTTSProvider:
    @patch("app.core.config.settings")
    def test_returns_mock_when_no_api_key(self, mock_settings) -> None:
        mock_settings.tts_provider = "mock"
        mock_settings.sarvam_api_key = ""
        provider = _get_tts_provider()
        assert isinstance(provider, MockTTS)

    @patch("app.core.config.settings")
    def test_returns_mock_when_sarvam_no_key(self, mock_settings) -> None:
        mock_settings.tts_provider = "sarvam"
        mock_settings.sarvam_api_key = ""
        provider = _get_tts_provider()
        assert isinstance(provider, MockTTS)
