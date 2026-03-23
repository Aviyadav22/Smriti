"""Sarvam AI TTS provider for Indian language speech synthesis."""

from __future__ import annotations

import base64
import logging

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


class _RateLimitError(Exception):
    """Raised when a 429 response is received so tenacity can retry."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited (Retry-After: {retry_after}s)")


def _wait_for_rate_limit(retry_state) -> float:
    """Custom wait strategy that respects Retry-After header when available."""
    exc = retry_state.outcome.exception()
    if isinstance(exc, _RateLimitError) and exc.retry_after is not None:
        return min(exc.retry_after, 60.0)  # Cap at 60s
    # Fall back to exponential backoff
    return wait_exponential(multiplier=1, min=1, max=10)(retry_state)


_sarvam_retry = retry(
    stop=stop_after_attempt(3),
    wait=_wait_for_rate_limit,
    retry=retry_if_exception_type((
        httpx.TimeoutException, httpx.ConnectError,
        ConnectionError, OSError, _RateLimitError,
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


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

    @_sarvam_retry
    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        """Convert text to MP3 audio via Sarvam AI API."""
        supported = await self.get_supported_languages()
        if language not in supported:
            msg = f"Language '{language}' not supported. Supported: {supported}"
            raise ValueError(msg)

        voice = self._LANGUAGE_VOICES.get(language, "meera")

        try:
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
                # Handle 429 rate limiting with Retry-After support
                if response.status_code == 429:
                    retry_after_raw = response.headers.get("Retry-After")
                    retry_after: float | None = None
                    if retry_after_raw:
                        try:
                            retry_after = float(retry_after_raw)
                        except (ValueError, TypeError):
                            retry_after = None
                    logger.warning(
                        "Sarvam TTS rate limited (429), Retry-After: %s",
                        retry_after,
                    )
                    raise _RateLimitError(retry_after=retry_after)
                response.raise_for_status()
        except _RateLimitError:
            raise  # Let tenacity handle the retry
        except httpx.TimeoutException as exc:
            logger.error("Sarvam TTS request timed out for language '%s': %s", language, exc)
            raise RuntimeError(f"Sarvam TTS request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Sarvam TTS HTTP error (status %d) for language '%s': %s",
                exc.response.status_code,
                language,
                exc,
            )
            raise RuntimeError(f"Sarvam TTS HTTP error {exc.response.status_code}: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.error("Sarvam TTS HTTP request failed for language '%s': %s", language, exc)
            raise RuntimeError(f"Sarvam TTS request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Sarvam TTS returned invalid JSON: %s", exc)
            raise RuntimeError(f"Sarvam TTS returned invalid JSON response: {exc}") from exc

        if "audios" not in data:
            logger.error("Sarvam TTS response missing 'audios' key. Keys present: %s", list(data.keys()))
            raise RuntimeError("Sarvam TTS response missing 'audios' key")

        if not data["audios"]:
            logger.error("Sarvam TTS returned empty 'audios' array")
            raise RuntimeError("Sarvam TTS returned empty audios array")

        try:
            audio_b64 = data["audios"][0]
            return base64.b64decode(audio_b64)
        except (IndexError, base64.binascii.Error) as exc:
            logger.error("Failed to decode Sarvam TTS audio: %s", exc)
            raise RuntimeError(f"Failed to decode Sarvam TTS audio: {exc}") from exc

    async def get_supported_languages(self) -> list[str]:
        """Return supported language codes."""
        return list(self._LANGUAGE_VOICES.keys())
