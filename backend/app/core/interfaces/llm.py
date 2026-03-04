"""LLM provider interface for text generation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Contract for large language model providers."""

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> str: ...

    async def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict: ...

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]: ...
