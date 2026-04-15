"""Translation provider interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TranslationProvider(Protocol):
    """Contract for language translation providers."""

    async def translate(
        self,
        text: str,
        *,
        source: str,
        target: str,
    ) -> str:
        """Translate text from source language to target language.

        Args:
            text: Text to translate.
            source: Source language code (e.g., "hi", "en").
            target: Target language code (e.g., "en", "hi").

        Returns:
            Translated text.
        """
        ...

    async def detect_language(self, text: str) -> str:
        """Detect the language of the given text.

        Returns:
            ISO 639-1 language code (e.g., "en", "hi").
        """
        ...
