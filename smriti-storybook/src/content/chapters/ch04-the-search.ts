import type { ChapterConfig } from "./types";

export const ch04TheSearch: ChapterConfig = {
  id: "04-the-search",
  title: "The Search",
  subtitle: "Where keyword search meets semantic search and a reranker plays referee",
  sections: [
    {
      type: "flow",
      steps: ["Query Analysis", "FTS + Vector + Citation", "RRF Fusion (k=60)", "Cohere Rerank", "Top Results"],
    },
    {
      type: "stats",
      items: [
        { icon: "🔀", value: "k=60", label: "RRF fusion constant" },
        { icon: "📐", value: "1,536", label: "embedding dimensions" },
        { icon: "🎯", value: "7", label: "vector types searched" },
        { icon: "🏆", value: "Top 100", label: "reranked per query" },
      ],
    },
    {
      type: "cards",
      cards: [
        {
          title: "1. Query Understanding",
          description:
            "Gemini analyzes topic, entities, jurisdiction, and complexity -- infers filters before search starts.",
          icon: "🔍",
        },
        {
          title: "2. Parallel Search",
          description:
            "Three engines fire simultaneously: Pinecone vectors, PostgreSQL FTS, and exact citation lookup.",
          icon: "⚡",
        },
        {
          title: "3. RRF Fusion",
          description:
            "Three ranked lists become one -- score-agnostic, only cares about rank, not raw scores.",
          icon: "🔀",
        },
        {
          title: "4. Cohere Reranking",
          description:
            "Cohere rerank-v4.0-pro gives the top 100 results a second opinion to catch false positives.",
          icon: "🏆",
        },
      ],
      columns: 2,
    },
    {
      type: "comparison",
      left: {
        label: "Basic Search",
        items: [
          "Single search method",
          "Keywords OR meaning, not both",
          "No query understanding",
          "Raw results, no reranking",
        ],
        rejected: true,
      },
      right: {
        label: "Smriti Hybrid Search",
        items: [
          "Three engines in parallel",
          "Keywords AND meaning combined",
          "AI-powered query analysis",
          "Cohere reranker as final judge",
        ],
        accepted: true,
      },
    },
    {
      type: "highlight-box",
      icon: "💡",
      title: "Why RRF?",
      description:
        "A Pinecone cosine similarity of 0.85 and a PostgreSQL ts_rank of 3.2 mean completely different things -- RRF only cares about rank position, making it perfect for fusing heterogeneous engines.",
      accent: "#C5A880",
    },
  ],
};
