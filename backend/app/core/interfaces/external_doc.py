"""External document provider interface for legal document APIs."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ExternalDocProvider(Protocol):
    """Contract for external legal document providers (e.g. Indian Kanoon)."""

    async def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        court_filter: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]: ...

    async def get_document(self, doc_id: str) -> dict: ...

    async def get_fragment(self, doc_id: str, query: str) -> dict: ...

    async def get_metadata(self, doc_id: str) -> dict: ...
