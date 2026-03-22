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
    from app.core.dependencies import (
        get_llm, get_flash_llm, get_embedder, get_vector_store,
        get_reranker, get_graph_store, get_ik_client, get_web_search,
    )
    from app.core.agents.research import build_research_graph
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    llm = get_llm()
    flash_llm = get_flash_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()
    graph_store = get_graph_store()
    ik_client = get_ik_client()
    web_search = get_web_search()

    graph = build_research_graph(
        llm=llm, flash_llm=flash_llm, embedder=embedder,
        vector_store=vector_store, reranker=reranker,
        graph_store=graph_store, web_search=web_search,
        ik_client=ik_client, checkpointer=MemorySaver(),
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

    print("=" * 70)
    print("QUALITY EVALUATION - Research Agent V3")
    print("=" * 70)
    print(f"Query: {query}")
    print("=" * 70)

    # ===== STAGE 1: Run until first interrupt (checkpoint_plan) =====
    print()
    print(">>> STAGE 1: Understand + Decompose (until HITL interrupt)")
    print("-" * 70)
    start = time.monotonic()

    async for event in graph.astream(
        {"query": query, "messages": []}, config=config, stream_mode="values"
    ):
        pass

    elapsed1 = time.monotonic() - start

    # Get full state after interrupt
    full_state = await graph.aget_state(config)
    state = full_state.values

    print(f"  Time: {elapsed1:.1f}s")
    print()

    # Classification
    complexity = state.get("complexity", "?")
    proc_ctx = state.get("procedural_context", "?")
    client_pos = state.get("client_position", "?")
    print("  CLASSIFY:")
    print(f"    Complexity: {complexity}")
    print(f"    Procedural context: {proc_ctx}")
    print(f"    Client position: {client_pos}")

    # Rewritten query
    rq = state.get("rewritten_query", "?")
    print(f"  REWRITE: {rq[:150]}")

    # Statute context
    statutes = state.get("statute_context", [])
    print(f"  STATUTE LOOKUP: {len(statutes)} statutes found")
    for s in statutes:
        repealed = " [REPEALED]" if s.get("is_repealed") else ""
        text_len = len(s.get("section_text", ""))
        title = s.get("section_title", "?")[:50]
        print(f"    - {s['act_short_name']} s.{s['section_number']} ({title}) [{text_len} chars]{repealed}")

    # Legal elements
    elements = state.get("legal_elements", [])
    print(f"  ELEMENT DECOMPOSITION: {len(elements)} elements")
    for e in elements:
        contested = " [CONTESTED]" if e.get("is_contested") else ""
        print(f"    - {e['element_id']}: {e['description'][:80]}{contested}")
        if e.get("search_query"):
            print(f"      Search: {e['search_query'][:80]}")

    # Research plan
    plan = state.get("research_plan", [])
    print(f"  RESEARCH PLAN: {len(plan)} tasks")
    task_types: dict[str, int] = {}
    for t in plan:
        tt = t.get("task_type", "?")
        task_types[tt] = task_types.get(tt, 0) + 1
        print(f"    [{tt:15s}] {t.get('nl_query', '')[:75]}")
    print(f"  Task type distribution: {dict(sorted(task_types.items()))}")

    # ===== STAGE 2: Resume through all HITL interrupts until completion =====
    print()
    print(">>> STAGE 2: Investigate + Challenge + Synthesize")
    print("-" * 70)
    start2 = time.monotonic()

    # Resume through up to 5 interrupts (plan, findings, memo, etc.)
    for resume_round in range(5):
        try:
            async for event in graph.astream(
                Command(resume="proceed"), config=config, stream_mode="values"
            ):
                pass
        except Exception as e:
            print(f"  Pipeline error (round {resume_round}): {type(e).__name__}: {str(e)[:200]}")

        full_state_now = await graph.aget_state(config)
        state_now = full_state_now.values
        memo = state_now.get("final_memo", "") or state_now.get("draft_memo", "")

        if full_state_now.next:
            next_node = full_state_now.next
            print(f"  [Resume {resume_round + 1}] Hit interrupt at {next_node}, resuming...")
        else:
            print(f"  [Resume {resume_round + 1}] Pipeline complete.")
            break

    elapsed2 = time.monotonic() - start2

    # Get final state
    full_state2 = await graph.aget_state(config)
    state2 = full_state2.values

    print(f"  Time: {elapsed2:.1f}s")

    # Worker results
    worker_results = state2.get("worker_results", [])
    print(f"  WORKERS: {len(worker_results)} worker runs")
    total_results = 0
    for wr in worker_results:
        if isinstance(wr, dict):
            results = wr.get("results", [])
            task_type = wr.get("task_type", "?")
            error = wr.get("error", "")
        else:
            results = wr.results if hasattr(wr, "results") else []
            task_type = wr.task_type if hasattr(wr, "task_type") else "?"
            error = wr.error if hasattr(wr, "error") else ""
        count = len(results)
        total_results += count
        status = "OK" if not error else f"ERR: {error[:50]}"
        print(f"    [{task_type:15s}] {count:2d} results  {status}")
    print(f"  Total evidence collected: {total_results}")

    # Extracted passages (CRAG)
    passages = state2.get("extracted_passages", [])
    print(f"  CRAG EXTRACTION: {len(passages)} passages kept")

    # Temporal warnings
    temporal = state2.get("temporal_warnings", [])
    print(f"  TEMPORAL WARNINGS: {len(temporal)}")
    for tw in temporal[:5]:
        sev = tw.get("severity", "?") if isinstance(tw, dict) else "?"
        warn = tw.get("warning", "?") if isinstance(tw, dict) else str(tw)[:80]
        print(f"    - [{sev}] {warn[:80]}")

    # ===== FINAL OUTPUT =====
    print()
    print("=" * 70)
    print("FINAL RESEARCH MEMO")
    print("=" * 70)
    if memo:
        print(memo[:10000])
        if len(memo) > 10000:
            print(f"\n... [truncated, total {len(memo)} chars]")
    else:
        print("  [No memo generated]")
        draft = state2.get("draft_memo", "")
        if draft:
            print(f"  Draft memo ({len(draft)} chars):")
            print(draft[:5000])

    print()
    print("=" * 70)
    print(f"TOTAL TIME: {elapsed1 + elapsed2:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run())
