"""Gemini-based translation provider using Flash model for cost-effective translation."""

from __future__ import annotations

import logging
import unicodedata
from typing import TYPE_CHECKING

from app.core.config import settings
from app.security.sanitizer import sanitize_search_query

logger = logging.getLogger(__name__)


class GeminiTranslator:
    """Translation provider using Gemini Flash model."""

    def __init__(self, model: str | None = None) -> None:
        from google import genai

        if not settings.gemini_api_key or not settings.gemini_api_key.strip():
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY environment variable.")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = model or settings.gemini_flash_model

    async def translate(
        self,
        text: str,
        *,
        source: str,
        target: str,
    ) -> str:
        """Translate text using Gemini Flash."""
        if not text.strip():
            return text

        # Unicode normalization (NFC) for consistent Devanagari handling
        text = unicodedata.normalize("NFC", text)

        # Sanitize to prevent prompt injection
        sanitized_text = sanitize_search_query(text)

        lang_names = {"en": "English", "hi": "Hindi"}
        source_name = lang_names.get(source, source)
        target_name = lang_names.get(target, target)

        prompt = (
            f"Translate the following text from {source_name} to {target_name}. "
            f"Return ONLY the translated text, nothing else. "
            f"Preserve legal terminology accurately. "
            f"If the text contains case citations, statute names, or section numbers, "
            f"keep them in their original form (do not translate proper nouns, "
            f"case names, or citation formats).\n\n"
            f"Text to translate:\n{sanitized_text}"
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            if response.text is None:
                logger.warning(
                    "Gemini returned None response in translate(), returning original text"
                )
                return text
            return response.text.strip()
        except Exception:
            logger.warning("Gemini translation failed, returning original text", exc_info=True)
            return text

    async def detect_language(self, text: str) -> str:
        """Detect language using Gemini Flash."""
        if not text.strip():
            return "en"

        # Unicode normalization (NFC) for consistent Devanagari handling
        text = unicodedata.normalize("NFC", text)

        # Quick heuristic: check for Devanagari characters
        devanagari_count = sum(1 for c in text if "\u0900" <= c <= "\u097f")
        total_alpha = sum(1 for c in text if c.isalpha())

        if total_alpha > 0 and devanagari_count / total_alpha > 0.3:
            return "hi"

        if devanagari_count == 0:
            return "en"

        # Ambiguous case -- use LLM
        # Sanitize to prevent prompt injection
        sanitized_text = sanitize_search_query(text[:500])

        prompt = (
            "What language is this text written in? "
            "Return ONLY the ISO 639-1 language code (e.g., 'en' for English, 'hi' for Hindi). "
            "Return nothing else.\n\n"
            f"Text: {sanitized_text}"
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            if response.text is None:
                logger.warning(
                    "Gemini returned None response in detect_language(), defaulting to 'en'"
                )
                return "en"
            code = response.text.strip().lower()[:2]
            return code if code in ("en", "hi") else "en"
        except Exception:
            logger.warning("Gemini language detection failed, defaulting to 'en'", exc_info=True)
            return "en"


# Verify protocol compliance at type-check time
if TYPE_CHECKING:
    from app.core.interfaces.translator import TranslationProvider

    _: type[TranslationProvider] = GeminiTranslator
