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
    from app.core.config import settings
    from app.core.providers.llm.gemini import GeminiLLM
    from app.core.providers.embeddings.gemini import GeminiEmbedder
    from app.core.providers.vector.pinecone_store import PineconeStore
    from app.core.providers.rerankers.cohere_reranker import CohereReranker
    from app.core.providers.graph.neo4j_store import Neo4jGraph
    from app.core.agents.strategy import build_strategy_graph

    print("=" * 80)
    print("ARGUMENT BUILDER AGENT — QUALITY TEST")
    print("=" * 80)
    print(f"\nCase: Anti-corruption bail application")
    print(f"Relief sought: {TEST_CASE['desired_relief']}")
    print()

    # Create providers
    print("[1/2] Initializing providers...")
    llm = GeminiLLM()
    flash_llm = GeminiLLM(model=settings.gemini_flash_model)
    embedder = GeminiEmbedder()
    vector_store = PineconeStore()
    reranker = CohereReranker()
    graph_store = Neo4jGraph()

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    checkpointer = MemorySaver()

    print("[2/2] Building graph (14 nodes, with MemorySaver)...")
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

    print("\n" + "-" * 80)
    print("RUNNING AGENT (auto-approving HITL checkpoints)...")
    print("-" * 80)

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
                    print(f"  [{elapsed:6.1f}s] Completed: {node_name}")

                    if isinstance(node_output, dict) and node_output.get("error"):
                        print(f"           ERROR: {node_output['error'][:200]}")

            # Check if we're at an interrupt (HITL checkpoint)
            state = await graph.aget_state(config)
            if state.next:
                checkpoint_name = state.next[0]
                elapsed = time.time() - start
                print(f"  [{elapsed:6.1f}s] HITL checkpoint: {checkpoint_name} -> auto-approving")
                # Resume with "proceed"
                initial_input = Command(resume="proceed")
            else:
                # Graph completed
                final_state = state.values if state else {}
                break

    except Exception as e:
        print(f"\nAGENT FAILED: {e}")
        import traceback
        traceback.print_exc()
        # Try to get partial state
        try:
            state = await graph.aget_state(config)
            final_state = state.values if state else {}
            print(f"\nPartial state recovered ({len(final_state)} keys)")
        except Exception:
            return
        if not final_state:
            return

    elapsed_total = time.time() - start

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    # Node execution timeline
    print(f"\n### Execution Timeline ({elapsed_total:.1f}s total)")
    for nt in node_times:
        print(nt)

    # Fact Analysis
    fa = final_state.get("fact_analysis", {})
    print(f"\n### Fact Analysis")
    print(f"  Parties: {fa.get('parties', {}).get('petitioner', {}).get('name', 'N/A')} v. State")
    print(f"  Causes of action: {len(fa.get('causes_of_action', []))}")
    for coa in fa.get("causes_of_action", []):
        print(f"    - {coa.get('title', 'N/A')} ({coa.get('statutory_basis', 'N/A')})")
    print(f"  Jurisdictional issues: {fa.get('jurisdictional_issues', [])}")

    # Legal Elements
    elements = final_state.get("legal_elements", [])
    print(f"\n### Legal Elements ({len(elements)} elements)")
    for el in elements:
        print(f"  - [{el.get('element_id', 'N/A')}] {el.get('description', 'N/A')[:80]}")

    # Search Results
    sr = final_state.get("search_results", [])
    pm = final_state.get("precedent_map", [])
    print(f"\n### Search & Precedents")
    print(f"  Search results: {len(sr)}")
    print(f"  Precedent map: {len(pm)}")
    for p in pm[:5]:
        strength = p.get("strength", "UNKNOWN")
        print(f"  - [{strength}] {p.get('title', 'N/A')[:60]} ({p.get('citation', 'N/A')})")

    # Strength Assessment
    sa = final_state.get("strength_assessment", {})
    print(f"\n### Strength Assessment")
    print(f"  Level: {sa.get('level', 'N/A')}")
    print(f"  Score: {sa.get('score', 'N/A')}")
    print(f"  Key strengths: {sa.get('key_strengths', [])}")
    print(f"  Key weaknesses: {sa.get('key_weaknesses', [])}")

    # IRAC Arguments
    irac = final_state.get("irac_arguments", [])
    print(f"\n### IRAC Arguments ({len(irac)} arguments)")
    for i, arg in enumerate(irac):
        print(f"\n  Argument {i+1}: {arg.get('title', 'N/A')}")
        print(f"    ISSUE: {arg.get('issue', 'N/A')[:100]}")
        print(f"    RULE: {arg.get('rule', 'N/A')[:100]}")
        authorities = arg.get("rule_authorities", [])
        for auth in authorities[:3]:
            print(f"      Authority: [{auth.get('strength', '?')}] {auth.get('citation', 'N/A')}")
        print(f"    STATUTORY: {arg.get('statutory_basis', 'N/A')[:80]}")
        print(f"    APPLICATION: {arg.get('application', 'N/A')[:150]}")
        print(f"    CONCLUSION: {arg.get('conclusion', 'N/A')[:100]}")
        print(f"    Effectiveness: {arg.get('effectiveness_score', 'N/A')}/10")

    # Adversarial Results
    adv = final_state.get("adversarial_results", [])
    print(f"\n### Adversarial Search ({len(adv)} opposing cases)")
    for a in adv[:3]:
        print(f"  - {a.get('title', 'N/A')[:60]} (weakness: {a.get('target_weakness', 'N/A')[:60]})")

    # Counter Arguments
    ca = final_state.get("counter_arguments", [])
    print(f"\n### Counter-Arguments ({len(ca)} anticipated)")
    for c in ca[:3]:
        print(f"  - [{c.get('impact', '?')}] {c.get('title', 'N/A')[:80]}")

    # Argument Order
    ao = final_state.get("argument_order", [])
    print(f"\n### Argument Order: {ao}")

    # Contradictions
    contras = final_state.get("contradictions", [])
    print(f"\n### Contradictions ({len(contras)} found)")
    for c in contras:
        print(f"  - {c.get('case_a', 'N/A')} vs {c.get('case_b', 'N/A')}")
        print(f"    {c.get('description', 'N/A')[:100]}")

    # Confidence
    conf = final_state.get("confidence", 0)
    print(f"\n### Confidence: {conf:.2f}")

    # Final Memo
    memo = final_state.get("strategy_memo", "")
    print(f"\n### Strategy Memo ({len(memo)} chars)")
    print("-" * 80)
    print(memo[:3000] if memo else "(empty)")
    if len(memo) > 3000:
        print(f"\n... [truncated, {len(memo) - 3000} more chars]")
    print("-" * 80)

    # Quality Metrics
    print(f"\n### Quality Metrics")
    print(f"  Total execution time: {elapsed_total:.1f}s")
    print(f"  Nodes completed: {len(node_times)}")
    print(f"  Fact analysis fields: {len(fa)}")
    print(f"  Legal elements: {len(elements)}")
    print(f"  Search results: {len(sr)}")
    print(f"  Precedent map entries: {len(pm)}")
    print(f"  IRAC arguments: {len(irac)}")
    print(f"  Adversarial cases: {len(adv)}")
    print(f"  Counter-arguments: {len(ca)}")
    print(f"  Contradictions: {len(contras)}")
    print(f"  Confidence: {conf:.2f}")
    print(f"  Memo length: {len(memo)} chars")

    # Check for IPC/BNS dual citations in memo
    import re
    dual_citations = len(re.findall(r'(?:IPC|CrPC|IEA).*?(?:BNS|BNSS|BSA)|(?:BNS|BNSS|BSA).*?(?:IPC|CrPC|IEA)', memo))
    print(f"  Dual citations (IPC/BNS): {dual_citations}")

    # Check for IRAC structure markers in memo
    irac_markers = sum(1 for keyword in ["ISSUE:", "RULE:", "APPLICATION:", "CONCLUSION:"] if keyword in memo.upper())
    print(f"  IRAC markers in memo: {irac_markers}/4")

    # Verification warnings
    if "Verification Warnings" in memo:
        print(f"  Verification warnings: PRESENT")
    else:
        print(f"  Verification warnings: none")

    # Save full output
    output_path = Path(__file__).parent.parent / "trial_reports" / "strategy_agent_test.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
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
        }, f, indent=2, default=str)
    print(f"\n  Full output saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
