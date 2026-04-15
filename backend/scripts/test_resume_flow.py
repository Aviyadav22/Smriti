"""Test script to diagnose the checkpoint_plan loop bug.

Simulates EXACTLY what the UI does:
1. Builds graph with MemorySaver checkpointer
2. Runs until interrupt (checkpoint_plan)
3. Resumes with the exact JSON the frontend sends
4. Checks if it proceeds or loops back

Usage:
    cd backend
    python -m scripts.test_resume_flow
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Enable WARNING logging so we see the debug lines
logging.basicConfig(level=logging.WARNING, format="%(name)s %(message)s")

# Suppress noisy loggers
for name in ("httpx", "httpcore", "urllib3", "neo4j", "google", "grpc"):
    logging.getLogger(name).setLevel(logging.ERROR)


async def test_resume_flow() -> None:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    from app.core.agents.research import build_research_graph
    from app.core.dependencies import (
        cleanup_providers,
        get_embedder,
        get_flash_llm,
        get_graph_store,
        get_ik_client,
        get_llm,
        get_reranker,
        get_vector_store,
        get_web_search,
    )


    checkpointer = MemorySaver()

    try:
        ik_client = get_ik_client()
    except Exception:
        ik_client = None
    try:
        web_search = get_web_search()
    except Exception:
        web_search = None

    graph = build_research_graph(
        llm=get_llm(),
        flash_llm=get_flash_llm(),
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        reranker=get_reranker(),
        graph_store=get_graph_store(),
        web_search=web_search,
        ik_client=ik_client,
        checkpointer=checkpointer,
    )

    config = {"configurable": {"thread_id": "test-resume-1"}}
    # Use a complex multi-issue query that will definitely go through plan_research
    query = (
        "Compare the legal positions on anticipatory bail under Section 438 CrPC "
        "and its equivalent under BNSS, analyzing how the Supreme Court's approach "
        "has evolved from Gurbaksh Singh Sibbia to Sushila Aggarwal, and identify "
        "the current test for granting anticipatory bail in economic offences"
    )

    # ---- STEP 1: Run until first interrupt ----
    nodes_visited = []
    async for event in graph.astream(
        {"query": query, "messages": []}, config=config, stream_mode="updates"
    ):
        for node_name in event:
            nodes_visited.append(node_name)

    state = await graph.aget_state(config)

    if state.tasks:
        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                iv = task.interrupts[0].value
                if isinstance(iv, dict):
                    iv.get("research_plan", [])

    len(state.values.get("research_plan", []))
    len(state.values.get("messages", []))

    if "checkpoint_plan" not in (state.next or []):
        await cleanup_providers()
        return

    # ---- STEP 2: Resume with EXACT frontend approve payload ----
    # This is exactly what plan-review.tsx handleApprove() sends:
    approve_payload = json.dumps({
        "action": "approve",
        "include_adversarial": True,
        "removed_tasks": 0,
    })

    # This is exactly what the backend does:
    resume_input = Command(resume=approve_payload)

    nodes_after_resume = []
    try:
        async for event in graph.astream(
            resume_input, config=config, stream_mode="updates"
        ):
            for node_name in event:
                nodes_after_resume.append(node_name)
                # Stop after a few nodes to avoid running the whole pipeline
                if len(nodes_after_resume) > 5:
                    break
            if len(nodes_after_resume) > 5:
                break
    except Exception:
        pass

    state2 = await graph.aget_state(config)
    len(state2.values.get("research_plan", []))
    len(state2.values.get("messages", []))


    # Check the critical feedback message
    messages = state2.values.get("messages", [])
    plan_feedbacks = [
        m for m in messages
        if isinstance(m, dict) and m.get("type") == "user_feedback" and m.get("step") == "plan"
    ]
    for pf in plan_feedbacks:
        pf.get("content")

    # Did it loop back to plan_research or proceed?
    if "plan_research" in nodes_after_resume or ("checkpoint_plan" in nodes_after_resume and len(nodes_after_resume) == 1) or any(n in nodes_after_resume for n in ["pre_warm_embeddings", "dispatch_workers"]):
        pass
    else:
        pass

    await cleanup_providers()


if __name__ == "__main__":
    asyncio.run(test_resume_flow())
