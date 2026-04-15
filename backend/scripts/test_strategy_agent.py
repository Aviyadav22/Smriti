"""Standalone test of the Strategy/Argument Builder agent.

Runs the agent graph with auto_approve=True (skips HITL checkpoints)
to produce a full argument memo for quality evaluation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
# Show our agent logs at INFO level
logging.getLogger("app.core.agents").setLevel(logging.INFO)

TEST_CASE = {
    "case_facts": """\
My client, Rajesh Kumar, is a 35-year-old government employee working as a clerk \
in the Delhi Municipal Corporation. On 15 March 2025, he was arrested by the \
Delhi Police Anti-Corruption Branch for allegedly accepting a bribe of Rs. 50,000 \
from a contractor seeking approval for a building permit. The trap was laid based \
on a complaint by the contractor, Suresh Gupta. During the trap operation, the \
marked currency notes were recovered from Rajesh's desk drawer. However, Rajesh \
claims the money was planted and that Suresh had a personal grudge against him \
because Rajesh had previously rejected his building permit application on legitimate \
grounds (structural safety violations). Rajesh has been in judicial custody for \
45 days. He has no prior criminal record, has a family with two minor children, \
and his wife is unemployed. The case is registered under Section 7 of the Prevention \
of Corruption Act, 1988 (as amended in 2018). The Special Judge, CBI Court, Delhi \
has denied bail twice citing the seriousness of the offence and the recovery of \
marked currency. We want to move the High Court for bail.\
""",
    "desired_relief": "Regular bail under Section 439 CrPC / Section 483 BNSS from the High Court of Delhi",
    "target_judge": "",
    "target_bench": "single",
    "language": "en",
}


async def main() -> None:
    from app.core.agents.strategy import build_strategy_graph
    from app.core.config import settings
    from app.core.providers.embeddings.gemini import GeminiEmbedder
    from app.core.providers.graph.neo4j_store import Neo4jGraph
    from app.core.providers.llm.gemini import GeminiLLM
    from app.core.providers.rerankers.cohere_reranker import CohereReranker
    from app.core.providers.vector.pinecone_store import PineconeStore

    # Create providers
    llm = GeminiLLM()
    flash_llm = GeminiLLM(model=settings.gemini_flash_model)
    embedder = GeminiEmbedder()
    vector_store = PineconeStore()
    reranker = CohereReranker()
    graph_store = Neo4jGraph()

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    checkpointer = MemorySaver()

    graph = build_strategy_graph(
        llm=llm,
        flash_llm=flash_llm,
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        graph_store=graph_store,
        checkpointer=checkpointer,
    )

    initial_input = {**TEST_CASE}
    config = {"configurable": {"thread_id": "test-strategy-001"}}

    start = time.time()
    node_times: list[str] = []

    try:
        final_state = None

        # Run until completion, auto-approving each HITL checkpoint
        while True:
            async for event in graph.astream(initial_input, config=config, stream_mode="updates"):
                for node_name, node_output in event.items():
                    elapsed = time.time() - start
                    node_times.append(f"  [{elapsed:6.1f}s] {node_name}")

                    if isinstance(node_output, dict) and node_output.get("error"):
                        pass

            # Check if we're at an interrupt (HITL checkpoint)
            state = await graph.aget_state(config)
            if state.next:
                state.next[0]
                elapsed = time.time() - start
                # Resume with "proceed"
                initial_input = Command(resume="proceed")
            else:
                # Graph completed
                final_state = state.values if state else {}
                break

    except Exception:
        import traceback

        traceback.print_exc()
        # Try to get partial state
        try:
            state = await graph.aget_state(config)
            final_state = state.values if state else {}
        except Exception:
            return
        if not final_state:
            return

    elapsed_total = time.time() - start

    # Node execution timeline
    for _nt in node_times:
        pass

    # Fact Analysis
    fa = final_state.get("fact_analysis", {})
    for _coa in fa.get("causes_of_action", []):
        pass

    # Legal Elements
    elements = final_state.get("legal_elements", [])
    for _el in elements:
        pass

    # Search Results
    sr = final_state.get("search_results", [])
    pm = final_state.get("precedent_map", [])
    for p in pm[:5]:
        p.get("strength", "UNKNOWN")

    # Strength Assessment
    sa = final_state.get("strength_assessment", {})

    # IRAC Arguments
    irac = final_state.get("irac_arguments", [])
    for _i, arg in enumerate(irac):
        authorities = arg.get("rule_authorities", [])
        for _auth in authorities[:3]:
            pass

    # Adversarial Results
    adv = final_state.get("adversarial_results", [])
    for _a in adv[:3]:
        pass

    # Counter Arguments
    ca = final_state.get("counter_arguments", [])
    for _c in ca[:3]:
        pass

    # Argument Order
    ao = final_state.get("argument_order", [])

    # Contradictions
    contras = final_state.get("contradictions", [])
    for _c in contras:
        pass

    # Confidence
    conf = final_state.get("confidence", 0)

    # Final Memo
    memo = final_state.get("strategy_memo", "")
    if len(memo) > 3000:
        pass

    # Quality Metrics

    # Check for IPC/BNS dual citations in memo
    import re

    len(
        re.findall(r"(?:IPC|CrPC|IEA).*?(?:BNS|BNSS|BSA)|(?:BNS|BNSS|BSA).*?(?:IPC|CrPC|IEA)", memo)
    )

    # Check for IRAC structure markers in memo
    sum(
        1
        for keyword in ["ISSUE:", "RULE:", "APPLICATION:", "CONCLUSION:"]
        if keyword in memo.upper()
    )

    # Verification warnings
    if "Verification Warnings" in memo:
        pass
    else:
        pass

    # Save full output
    output_path = Path(__file__).parent.parent / "trial_reports" / "strategy_agent_test.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "test_input": TEST_CASE,
                "fact_analysis": fa,
                "legal_elements": elements,
                "strength_assessment": sa,
                "irac_arguments": irac,
                "adversarial_results": adv,
                "counter_arguments": ca,
                "argument_order": ao,
                "contradictions": contras,
                "confidence": conf,
                "memo": memo,
                "precedent_count": len(pm),
                "search_result_count": len(sr),
                "execution_time_seconds": elapsed_total,
            },
            f,
            indent=2,
            default=str,
        )


if __name__ == "__main__":
    asyncio.run(main())
