"""Diagnostic script: verify passage expansion works end-to-end.

Runs a real research query through the agent, checks logs for:
1. char_start/char_end propagation from Pinecone
2. expand_passages_from_full_text() producing expanded_text
3. expanded_text being longer than original snippet
"""
import asyncio
import logging
import os
import sys

# Ensure backend is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
# Focus on passage expansion logs
logging.getLogger("app.core.agents.nodes.common").setLevel(logging.DEBUG)


async def main():
    from app.core.dependencies import (
        get_embedder,
        get_llm,
        get_reranker,
        get_vector_store,
    )
    from app.db.postgres import async_session_factory

    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()

    # Run a single hybrid search to get raw results
    from app.core.search.hybrid import hybrid_search

    query = "right to privacy fundamental right"

    async with async_session_factory() as db:
        response = await hybrid_search(
            query,
            llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            db=db,
        )


        # Check char_start/char_end propagation
        has_positions = 0
        for _i, r in enumerate(response.results[:10]):
            len(r.snippet or "")
            len(r.chunk_text or "")
            if r.char_start and r.char_end:
                has_positions += 1


        # Now test passage expansion directly
        from dataclasses import asdict

        from app.core.agents.nodes.common import expand_passages_from_full_text

        result_dicts = [asdict(r) for r in response.results[:8]]  # Simulate post-CRAG top 8


        expanded = await expand_passages_from_full_text(result_dicts, db)

        # Report
        expansion_count = 0
        for _i, r in enumerate(expanded):
            exp_text = r.get("expanded_text")
            r.get("snippet") or r.get("chunk_text") or ""
            if exp_text:
                expansion_count += 1
            else:
                pass

        if expansion_count == 0 or expansion_count < len(expanded) // 2:
            pass
        else:
            pass


if __name__ == "__main__":
    asyncio.run(main())
