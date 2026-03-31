import type { ChapterConfig } from "./types";

export const ch03ThreeWaysToRemember: ChapterConfig = {
  id: "03-three-ways-to-remember",
  title: "Three Ways to Remember",
  subtitle: "How AI, regex, and three databases work together to understand judgments",
  sections: [
    {
      type: "stats",
      items: [
        { icon: "🗄️", value: "3", label: "databases in sync" },
        { icon: "📊", value: "16", label: "metadata fields extracted" },
        { icon: "📜", value: "62+", label: "act patterns recognized" },
        { icon: "🔗", value: "16", label: "citation format patterns" },
      ],
    },
    {
      type: "comparison",
      left: {
        label: "LLM Only",
        items: [
          "Creative extraction from messy text",
          "Understands context and meaning",
          "Can extract ratio decidendi",
          "Sometimes hallucinates citations",
        ],
        rejected: true,
      },
      right: {
        label: "LLM + Regex Hybrid",
        items: [
          "AI extracts, regex validates",
          "62+ act patterns recognized",
          "16 citation format patterns",
          "Zero hallucinated citations",
        ],
        accepted: true,
      },
    },
    {
      type: "cards",
      cards: [
        {
          title: "PostgreSQL",
          description:
            "Structured data: title, court, year, judges. Full-text search via tsvector understands stems and phrases.",
          icon: "🗄️",
        },
        {
          title: "Pinecone",
          description:
            "2.5M embeddings in 1,536 dimensions -- 'homicide' matches 'murder' because they're semantically close.",
          icon: "🧠",
        },
        {
          title: "Neo4j",
          description:
            "CITES, OVERRULES, DISTINGUISHES edges reveal the hidden web connecting 35K cases.",
          icon: "🕸️",
        },
      ],
      columns: 3,
    },
    {
      type: "code",
      code: `-- PostgreSQL tsvector: smarter than keyword search
SELECT title, ts_rank_cd(searchable_text, query) AS rank
FROM cases,
     websearch_to_tsquery('bail under NDPS Act') AS query
WHERE searchable_text @@ query
ORDER BY rank DESC;

-- Stems words: "conditions" -> "condit"
-- Handles phrases: "rarest of rare"
-- Boolean: "murder AND bail"`,
      language: "sql",
    },
    {
      type: "highlight-box",
      icon: "🤝",
      title: "The Hybrid Approach",
      description:
        "AI is creative but hallucinates. Regex is rigid but precise. Together they extract 16 metadata fields with zero hallucinated citations.",
      accent: "#C5A880",
    },
  ],
};
