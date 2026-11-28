"""OpenRouter-backed translation, reusing the Gemini translator's prompts."""

from __future__ import annotations

from app.core.config import settings
from app.core.providers.llm.openrouter import OpenRouterLLM
from app.core.providers.translation.gemini_translator import GeminiTranslator


class OpenRouterTranslator(GeminiTranslator):
    """Translation provider using the OpenRouter fast model."""

    def __init__(self, model: str | None = None) -> None:
        # No Gemini client: everything goes through _complete().
        self._llm = OpenRouterLLM(model=model or settings.openrouter_flash_model)

    async def _complete(self, prompt: str) -> str | None:
        return await self._llm.generate(prompt, max_tokens=2048)
