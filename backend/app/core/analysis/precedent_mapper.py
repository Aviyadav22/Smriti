"""Precedent mapper — finds supporting and opposing precedents per issue."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.interfaces import EmbeddingProvider, LLMProvider, Reranker, VectorStore
from app.core.search.hybrid import SearchResultItem, hybrid_search

logger = logging.getLogger(__name__)


@dataclass
class PrecedentResult:
    """Precedents found for a single legal issue."""

    issue_title: str
    supporting: list[SearchResultItem] = field(default_factory=list)
    opposing: list[SearchResultItem] = field(default_factory=list)
    statutes: list[str] = field(default_factory=list)


class PrecedentMapperService:
    """Maps legal issues to relevant precedents using hybrid search."""

    def __init__(
        self,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        reranker: Reranker,
        db: AsyncSession,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._vector_store = vector_store
        self._reranker = reranker
        self._db = db

    async def map_precedents(
        self,
        issues: list[dict[str, str]],
        acts_referenced: list[str] | None = None,
        max_per_issue: int = 5,
    ) -> list[PrecedentResult]:
        """Find precedents for each issue in parallel."""
        tasks = [
            self._search_for_issue(issue, acts_referenced, max_per_issue)
            for issue in issues
        ]
        return await asyncio.gather(*tasks)

    async def _search_for_issue(
        self,
        issue: dict[str, str],
        acts_referenced: list[str] | None,
        max_per_issue: int,
    ) -> PrecedentResult:
        """Search for precedents relevant to a single issue."""
        title = issue.get("title", "")
        description = issue.get("description", "")

        query = f"{title}: {description}"
        if acts_referenced:
            query += " " + " ".join(acts_referenced[:3])

        try:
            search_result = await hybrid_search(
                query,
                page=1,
                page_size=max_per_issue,
                llm=self._llm,
                embedder=self._embedder,
                vector_store=self._vector_store,
                reranker=self._reranker,
                db=self._db,
            )

            supporting = search_result.results[:max_per_issue]
            statutes = acts_referenced[:5] if acts_referenced else []

            return PrecedentResult(
                issue_title=title,
                supporting=supporting,
                statutes=statutes,
            )
        except Exception:
            logger.exception("Precedent search failed for issue: %s", title)
            return PrecedentResult(issue_title=title)
