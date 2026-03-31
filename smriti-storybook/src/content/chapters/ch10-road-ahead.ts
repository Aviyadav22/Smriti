import type { ChapterConfig } from "./types";

export const ch10RoadAhead: ChapterConfig = {
  id: "10-road-ahead",
  title: "The Road Ahead",
  subtitle: "From Supreme Court to every court, from English to every language",
  sections: [
    {
      type: "quote",
      text: "Every law student, every small-town lawyer, every public interest litigant should have access to the same quality of legal research that top-tier firms charge lakhs for.",
      attribution: "The NeetiQ vision",
    },
    {
      type: "stats",
      items: [
        { icon: "📄", value: "35,000", label: "judgments today" },
        { icon: "🧠", value: "2.5M", label: "vectors indexed" },
        { icon: "✅", value: "2,500+", label: "total tests" },
        { icon: "⚙️", value: "40+", label: "agent nodes" },
      ],
    },
    {
      type: "cards",
      cards: [
        {
          title: "More Courts",
          description:
            "25 High Courts, thousands of district courts, specialized tribunals (NCLT, SAT, ITAT).",
          icon: "🏛️",
        },
        {
          title: "Deeper Hindi NLP",
          description:
            "Native Hindi legal text understanding -- many High Court judgments are in Hindi.",
          icon: "🗣️",
        },
        {
          title: "Citation Intelligence",
          description:
            "Precedent decay analysis, automatic landmark detection, citation prediction via graph algorithms.",
          icon: "📈",
        },
        {
          title: "Multi-Agent Workflows",
          description:
            "Case Prep, Strategy, Drafting, Compliance -- specialized AI agents for every legal task.",
          icon: "🤖",
        },
        {
          title: "Real-Time Ingestion",
          description:
            "New judgments processed and indexed within hours of publication -- no more batch waits.",
          icon: "⏱️",
        },
        {
          title: "Mobile App",
          description:
            "Many Indian lawyers work from phones -- a mobile-first interface to expand reach.",
          icon: "📱",
        },
      ],
      columns: 3,
    },
    {
      type: "timeline",
      milestones: [
        {
          date: "April 2024",
          label: "The Spark",
          detail: "Basic RAG model from scratch -- proof of concept.",
        },
        {
          date: "October 2024",
          label: "Open-Source Era",
          detail: "Better foundation, but generic tools can't do domain-specific work.",
        },
        {
          date: "March 2026",
          label: "The Real Build",
          detail:
            "From-scratch rewrite: 35K judgments, 2.5M vectors, 7 vector types, 40+ agent nodes.",
          highlight: true,
        },
        {
          date: "Next",
          label: "Scale & Launch",
          detail:
            "More courts, more languages, more agents -- NeetiQ goes live at neetiq.in.",
          highlight: true,
        },
      ],
    },
    {
      type: "quote",
      text: "Neither the basic RAG model nor the open-source era was wasted -- they were training. Every limitation taught a lesson. When the time came to build it right, the decisions came fast.",
      attribution: "Avi, March 2026",
    },
  ],
};
