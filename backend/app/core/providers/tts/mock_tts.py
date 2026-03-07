"""Mock TTS provider for testing and development."""

from __future__ import annotations


class MockTTS:
    """Returns minimal valid MP3 bytes for testing."""

    # Minimal valid MP3 frame header (sync word 0xFFE0+)
    _SILENT_MP3 = (
        b"\xff\xfb\x90\x00" + b"\x00" * 140
    )

    async def synthesize(self, text: str, *, language: str = "en") -> bytes:
        """Return silent MP3 bytes for testing."""
        supported = await self.get_supported_languages()
        if language not in supported:
            msg = f"Language '{language}' not supported. Supported: {supported}"
            raise ValueError(msg)
        return self._SILENT_MP3

    async def get_supported_languages(self) -> list[str]:
        """Return supported languages."""
        return ["en", "hi"]
