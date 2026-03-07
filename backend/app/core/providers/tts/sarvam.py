"""Sarvam AI TTS provider for Indian language speech synthesis."""

from __future__ import annotations

import base64

import httpx

from app.core.config import settings


class SarvamTTS:
    """Sarvam AI TTS provider supporting 22 Indian languages."""

    _BASE_URL = "https://api.sarvam.ai/text-to-speech"

    _LANGUAGE_VOICES: dict[str, str] = {
        "en": "meera",
        "hi": "meera",
    }

    def __init__(self) -> None:
        if not settings.sarvam_api_key:
            msg = "SARVAM_API_KEY is required for SarvamTTS provider"
            raise ValueError(msg)
        self._api_key = settings.sarvam_api_key

    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        """Convert text to MP3 audio via Sarvam AI API."""
        supported = await self.get_supported_languages()
        if language not in supported:
            msg = f"Language '{language}' not supported. Supported: {supported}"
            raise ValueError(msg)

        voice = self._LANGUAGE_VOICES.get(language, "meera")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self._BASE_URL,
                headers={
                    "API-Subscription-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "inputs": [text],
                    "target_language_code": language,
                    "speaker": voice,
                    "model": "bulbul:v1",
                },
            )
            response.raise_for_status()
            data = response.json()
            audio_b64 = data["audios"][0]
            return base64.b64decode(audio_b64)

    async def get_supported_languages(self) -> list[str]:
        """Return supported language codes."""
        return list(self._LANGUAGE_VOICES.keys())
