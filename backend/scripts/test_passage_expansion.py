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
        get_llm, get_embedder, get_vector_store, get_reranker,
    )
    from app.db.postgres import async_session_factory

    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()

    # Run a single hybrid search to get raw results
    from app.core.search.hybrid import hybrid_search

    query = "right to privacy fundamental right"
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}\n")

    async with async_session_factory() as db:
        response = await hybrid_search(
            query,
            llm=llm,
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            db=db,
        )

        print(f"Search returned {len(response.results)} results\n")

        # Check char_start/char_end propagation
        has_positions = 0
        for i, r in enumerate(response.results[:10]):
            snippet_len = len(r.snippet or "")
            chunk_len = len(r.chunk_text or "")
            print(
                f"  [{i}] {r.citation or r.title or r.case_id[:20]}"
                f"  score={r.score:.3f}"
                f"  snippet={snippet_len}chars"
                f"  chunk={chunk_len}chars"
                f"  char_start={r.char_start}"
                f"  char_end={r.char_end}"
            )
            if r.char_start and r.char_end:
                has_positions += 1

        print(f"\nResults with char_start/char_end: {has_positions}/{min(10, len(response.results))}")

        # Now test passage expansion directly
        from dataclasses import asdict
        from app.core.agents.nodes.common import expand_passages_from_full_text

        result_dicts = [asdict(r) for r in response.results[:8]]  # Simulate post-CRAG top 8

        print(f"\n{'='*60}")
        print(f"Running expand_passages_from_full_text on top {len(result_dicts)} results...")
        print(f"{'='*60}\n")

        expanded = await expand_passages_from_full_text(result_dicts, db)

        # Report
        expansion_count = 0
        for i, r in enumerate(expanded):
            exp_text = r.get("expanded_text")
            snippet = r.get("snippet") or r.get("chunk_text") or ""
            if exp_text:
                expansion_count += 1
                print(
                    f"  [{i}] EXPANDED: {len(snippet)} -> {len(exp_text)} chars "
                    f"({len(exp_text)/max(len(snippet),1):.1f}x) "
                    f"  case={r['case_id'][:20]}"
                )
                print(f"       snippet[:80]:  {snippet[:80]!r}")
                print(f"       expanded[:80]: {exp_text[:80]!r}")
            else:
                print(
                    f"  [{i}] NOT EXPANDED: snippet={len(snippet)}chars "
                    f"  case={r['case_id'][:20]}"
                )

        print(f"\n{'='*60}")
        print(f"RESULT: {expansion_count}/{len(expanded)} results had passages expanded")
        if expansion_count == 0:
            print("WARNING: No passages were expanded! Check logs above for failure reasons.")
        elif expansion_count < len(expanded) // 2:
            print("PARTIAL: Less than half expanded. Check logs for non-expanded results.")
        else:
            print("SUCCESS: Passage expansion is working.")
        print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
