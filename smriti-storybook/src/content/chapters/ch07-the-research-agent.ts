import type { ChapterConfig } from "./types";

export const ch07TheResearchAgent: ChapterConfig = {
  id: "07-the-research-agent",
  title: "The Research Agent",
  subtitle: "An AI that researches like a lawyer -- reading statutes, breaking down questions, finding counter-arguments",
  sections: [
    {
      type: "flow",
      steps: ["Understand", "Decompose", "Investigate", "Challenge", "Synthesize"],
    },
    {
      type: "stats",
      items: [
        { icon: "🔄", value: "5", label: "sequential stages" },
        { icon: "⚙️", value: "30", label: "max parallel workers" },
        { icon: "🔍", value: "7", label: "worker types" },
        { icon: "✋", value: "HITL", label: "human-in-the-loop" },
      ],
    },
    {
      type: "cards",
      cards: [
        {
          title: "statute_lookup_node",
          description:
            "Reads statute text in Stage 1 -- auto-expands old/new code mappings (IPC 302 → BNS 103).",
          icon: "📖",
        },
        {
          title: "element_decomposition_node",
          description:
            "Breaks 'Is the accused liable under S.302?' into actus reus, mens rea, exceptions, standard of proof.",
          icon: "🧩",
        },
        {
          title: "adversarial_search_node",
          description:
            "Found cases granting bail? Now search for cases denying bail -- anticipate the other side.",
          icon: "🛡️",
        },
        {
          title: "temporal_validation_node",
          description:
            "Deterministic (no LLM) -- checks if cited cases reference repealed provisions and flags them.",
          icon: "⏰",
        },
      ],
      columns: 2,
    },
    {
      type: "highlight-box",
      icon: "✋",
      title: "Human-in-the-Loop",
      description:
        "At key moments the agent pauses via LangGraph's interrupt() mechanism, sends the plan to the browser, and waits for lawyer approval. Lawyers guide the research, not just watch.",
      accent: "#C5A880",
    },
    {
      type: "code",
      code: `# Agent state grows as it progresses through the graph
class ResearchState(TypedDict):
    query: str
    classification: Classification
    statute_context: list[StatuteSection]  # NEW in V3
    elements: list[LegalElement]           # NEW in V3
    plan: ResearchPlan
    worker_results: list[WorkerResult]
    adversarial_findings: list[Finding]    # NEW in V3
    temporal_warnings: list[Warning]       # NEW in V3
    memo: str
    confidence: ConfidenceScore`,
      language: "python",
    },
  ],
};
