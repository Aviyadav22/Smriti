"""Text-to-speech interface for audio generation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TTSProvider(Protocol):
    """Contract for text-to-speech providers."""

    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        """Convert text to audio bytes (MP3 format)."""
        ...

    async def get_supported_languages(self) -> list[str]:
        """Return list of supported language codes."""
        ...
