import type { ChapterConfig } from "./types";

export const ch00TheSpark: ChapterConfig = {
  id: "00-the-spark",
  title: "The Spark",
  subtitle: "Where frustration met opportunity in an NLP classroom",
  sections: [
    {
      type: "typewriter",
      text: "What if legal search could understand meaning, not just match keywords?",
      className: "text-2xl md:text-3xl font-heading text-[#C5A880]",
      speed: 40,
    },
    {
      type: "comparison",
      left: {
        label: "Keyword Search",
        items: [
          "Exact word matching only",
          "'Homicide' misses 'murder' results",
          "No understanding of legal concepts",
          "Section numbers without context",
        ],
        rejected: true,
      },
      right: {
        label: "Semantic Search",
        items: [
          "Matches meaning, not just words",
          "'Homicide' finds 'murder' cases",
          "Understands legal reasoning",
          "Context-aware retrieval",
        ],
        accepted: true,
      },
    },
    {
      type: "prose",
      content:
        "Avi was in an NLP class at UPES when it clicked: embeddings capture meaning, but every legal tool in India was still stuck on keyword matching.",
    },
    {
      type: "timeline",
      milestones: [
        {
          date: "April 2024",
          label: "First Attempt",
          detail:
            "Basic RAG model from scratch -- it kind of worked, but 'kind of' isn't good enough for law.",
        },
        {
          date: "October 2024",
          label: "Open-Source Era",
          detail:
            "Adopted an open-source framework for a sturdier base, but no legal awareness or Indian law specificity.",
        },
        {
          date: "March 2026",
          label: "The Real Build",
          detail:
            "Started from scratch with every lesson learned -- purpose-built for Indian legal research.",
          highlight: true,
        },
      ],
    },
    {
      type: "stats",
      items: [
        { icon: "📄", value: "35,000", label: "Supreme Court judgments" },
        { icon: "🧠", value: "2.5M", label: "vector embeddings" },
        { icon: "📜", value: "62+", label: "recognized statutes" },
        { icon: "🔓", value: "CC-BY-4.0", label: "open data license" },
      ],
    },
    {
      type: "quote",
      text: "In Sanskrit, Smriti means 'memory' -- connecting the AI's ability to remember 35,000 judgments with India's oldest tradition of codified law.",
    },
  ],
};
