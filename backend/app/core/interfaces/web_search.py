"""Web search provider interface for external web search APIs."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class WebSearchProvider(Protocol):
    """Contract for web search providers (e.g. Tavily)."""

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_domains: list[str] | None = None,
        time_range: str | None = None,
        country: str | None = None,
        include_raw_content: bool = False,
    ) -> list[dict]: ...
