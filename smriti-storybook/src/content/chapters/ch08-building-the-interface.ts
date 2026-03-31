import type { ChapterConfig } from "./types";

export const ch08BuildingTheInterface: ChapterConfig = {
  id: "08-building-the-interface",
  title: "Building the Interface",
  subtitle: "Making 35,000 judgments and an AI research agent accessible to everyone",
  sections: [
    {
      type: "stats",
      items: [
        { icon: "📱", value: "32+", label: "pages & routes" },
        { icon: "🔌", value: "68", label: "API endpoints" },
        { icon: "✅", value: "311", label: "frontend tests" },
        { icon: "🌐", value: "22", label: "TTS languages" },
      ],
    },
    {
      type: "cards",
      cards: [
        {
          title: "Hybrid Search",
          description:
            "Type a question, get results ranked by meaning with filters for court, year, judge, act.",
          icon: "🔍",
        },
        {
          title: "Research Workspace",
          description:
            "5-stage progress bar, streaming memo viewer, footnote hover previews, confidence meter.",
          icon: "🧠",
        },
        {
          title: "AI Chat",
          description:
            "Conversational legal Q&A grounded in real cases with citation sources.",
          icon: "💬",
        },
        {
          title: "Judge Analytics",
          description:
            "Case history, bench compositions, disposition patterns, citation networks per judge.",
          icon: "📊",
        },
        {
          title: "Document Upload",
          description:
            "Upload PDFs -- 6-step analysis pipeline with audio digests in 22 Indian languages.",
          icon: "📤",
        },
        {
          title: "Case Detail",
          description:
            "Structured metadata, ratio decidendi, acts cited, equivalent citations, similar cases.",
          icon: "📋",
        },
      ],
      columns: 3,
    },
    {
      type: "comparison",
      left: {
        label: "Server Components",
        items: [
          "SEO-critical pages (home, search)",
          "Static metadata rendering",
          "Zero client-side JS bundle",
          "Fast initial page load",
        ],
      },
      right: {
        label: "Client Components",
        items: [
          "Interactive features (research, chat)",
          "SSE streaming connections",
          "Real-time progress updates",
          "Rich user interactions",
        ],
      },
    },
    {
      type: "highlight-box",
      icon: "📡",
      title: "Real-Time Streaming",
      description:
        "The research agent streams progress via Server-Sent Events -- the memo appears word by word, like watching a lawyer draft. Keepalive heartbeats every 15 seconds prevent timeouts.",
      accent: "#C5A880",
    },
  ],
};
