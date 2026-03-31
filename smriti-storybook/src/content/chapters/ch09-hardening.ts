import type { ChapterConfig } from "./types";

export const ch09Hardening: ChapterConfig = {
  id: "09-hardening",
  title: "Hardening for Production",
  subtitle: "From 100 test cases to 35,000 judgments -- scaling, security, and resilience",
  sections: [
    {
      type: "stats",
      items: [
        { icon: "✅", value: "2,185", label: "backend tests" },
        { icon: "🗃️", value: "36", label: "DB migrations" },
        { icon: "🔐", value: "10", label: "security fixes" },
        { icon: "💰", value: "50%", label: "cost savings (Vertex batch)" },
      ],
    },
    {
      type: "cards",
      cards: [
        {
          title: "JWT Auth",
          description:
            "60-min access tokens, 7-day refresh, proactive refresh before every API call.",
          icon: "🔐",
        },
        {
          title: "Account Lockout",
          description:
            "10 failed attempts trigger 5-minute lock with 'N attempts remaining' warnings.",
          icon: "🔒",
        },
        {
          title: "Circuit Breakers",
          description:
            "10 consecutive failures stop external calls automatically -- Gemini, Indian Kanoon, all protected.",
          icon: "⚡",
        },
        {
          title: "Silent Failure Audit",
          description:
            "Every catch block now surfaces errors to the UI -- no more blank screens on API failures.",
          icon: "⚠️",
        },
      ],
      columns: 2,
    },
    {
      type: "timeline",
      milestones: [
        {
          date: "March 22",
          label: "10x Audit Fix",
          detail:
            "10 major steps: data flow, search ranking, CRAG evaluation, prompt upgrades, citation verification.",
        },
        {
          date: "March 23",
          label: "Silent Failure Audit",
          detail:
            "Found and fixed all places where errors were silently swallowed. Stream disconnect detection added.",
        },
        {
          date: "March 27",
          label: "Security Hardening",
          detail:
            "Removed hardcoded credentials, added rate limiting, CORS protection, injection prevention.",
        },
        {
          date: "March 28",
          label: "Vertex AI Batch",
          detail:
            "Switched to Vertex AI batch processing: 50% cost savings, ~$34 per 1,000 cases.",
          highlight: true,
        },
      ],
    },
    {
      type: "highlight-box",
      icon: "🛡️",
      title: "Production-Grade Resilience",
      description:
        "Tenacity retry with exponential backoff (2-60s, 5 attempts) on every external provider. Queue-based workers with circuit breaker (10 failures), graceful shutdown, and ETA logging.",
      accent: "#C5A880",
    },
  ],
};
