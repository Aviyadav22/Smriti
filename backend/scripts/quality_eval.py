"""Full V3 pipeline quality evaluation with a real legal query.

Usage:
    cd backend
    python -m scripts.quality_eval
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run() -> None:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    from app.core.agents.research import build_research_graph
    from app.core.dependencies import (
        get_embedder,
        get_flash_llm,
        get_graph_store,
        get_ik_client,
        get_llm,
        get_reranker,
        get_vector_store,
        get_web_search,
    )

    llm = get_llm()
    flash_llm = get_flash_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()
    graph_store = get_graph_store()
    ik_client = get_ik_client()
    web_search = get_web_search()

    graph = build_research_graph(
        llm=llm,
        flash_llm=flash_llm,
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        graph_store=graph_store,
        web_search=web_search,
        ik_client=ik_client,
        checkpointer=MemorySaver(),
    )

    config = {"configurable": {"thread_id": "quality-eval-1"}}

    # Real lawyer question - multi-issue, requires statute + case law + temporal
    query = (
        "My client is accused of murder under Section 302 IPC. "
        "The incident occurred in 2024 after BNS came into force. "
        "There was sudden provocation by the deceased. "
        "What are the legal defences available, and which code applies - IPC or BNS? "
        "Cite relevant Supreme Court judgments."
    )

    # ===== STAGE 1: Run until first interrupt (checkpoint_plan) =====
    start = time.monotonic()

    async for _event in graph.astream(
        {"query": query, "messages": []}, config=config, stream_mode="values"
    ):
        pass

    time.monotonic() - start

    # Get full state after interrupt
    full_state = await graph.aget_state(config)
    state = full_state.values

    # Classification
    state.get("complexity", "?")
    state.get("procedural_context", "?")
    state.get("client_position", "?")

    # Rewritten query
    state.get("rewritten_query", "?")

    # Statute context
    statutes = state.get("statute_context", [])
    for s in statutes:
        " [REPEALED]" if s.get("is_repealed") else ""
        len(s.get("section_text", ""))
        s.get("section_title", "?")[:50]

    # Legal elements
    elements = state.get("legal_elements", [])
    for e in elements:
        " [CONTESTED]" if e.get("is_contested") else ""
        if e.get("search_query"):
            pass

    # Research plan
    plan = state.get("research_plan", [])
    task_types: dict[str, int] = {}
    for t in plan:
        tt = t.get("task_type", "?")
        task_types[tt] = task_types.get(tt, 0) + 1

    # ===== STAGE 2: Resume through all HITL interrupts until completion =====
    start2 = time.monotonic()

    # Resume through up to 5 interrupts (plan, findings, memo, etc.)
    for _resume_round in range(5):
        try:
            async for _event in graph.astream(
                Command(resume="proceed"), config=config, stream_mode="values"
            ):
                pass
        except Exception as e:
            pass

        full_state_now = await graph.aget_state(config)
        state_now = full_state_now.values
        memo = state_now.get("final_memo", "") or state_now.get("draft_memo", "")

        if full_state_now.next:
            pass
        else:
            break

    time.monotonic() - start2

    # Get final state
    full_state2 = await graph.aget_state(config)
    state2 = full_state2.values

    # Worker results
    worker_results = state2.get("worker_results", [])
    total_results = 0
    for wr in worker_results:
        if isinstance(wr, dict):
            results = wr.get("results", [])
            wr.get("task_type", "?")
            error = wr.get("error", "")
        else:
            results = wr.results if hasattr(wr, "results") else []
            wr.task_type if hasattr(wr, "task_type") else "?"
            error = wr.error if hasattr(wr, "error") else ""
        count = len(results)
        total_results += count
        "OK" if not error else f"ERR: {error[:50]}"

    # Extracted passages (CRAG)
    state2.get("extracted_passages", [])

    # Temporal warnings
    temporal = state2.get("temporal_warnings", [])
    for tw in temporal[:5]:
        tw.get("severity", "?") if isinstance(tw, dict) else "?"
        tw.get("warning", "?") if isinstance(tw, dict) else str(tw)[:80]

    # ===== FINAL OUTPUT =====
    if memo:
        if len(memo) > 10000:
            pass
    else:
        draft = state2.get("draft_memo", "")
        if draft:
            pass


if __name__ == "__main__":
    asyncio.run(run())
