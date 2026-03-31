import type { ChapterConfig } from "./types";

export const ch01LayingTheFoundation: ChapterConfig = {
  id: "01-laying-the-foundation",
  title: "Laying the Foundation",
  subtitle: "Choosing the right weapons for Indian legal AI",
  sections: [
    {
      type: "stats",
      items: [
        { icon: "⚡", value: "6", label: "core technologies" },
        { icon: "🔌", value: "8", label: "external integrations" },
        { icon: "🧩", value: "1", label: "modular monolith" },
        { icon: "🔄", value: "0", label: "vendor lock-in" },
      ],
    },
    {
      type: "cards",
      cards: [
        {
          title: "FastAPI",
          description:
            "Python backend with native async -- critical when making dozens of LLM calls per request.",
          icon: "⚡",
        },
        {
          title: "Next.js 16",
          description:
            "React framework with SSR, App Router, and TypeScript for a modern legal interface.",
          icon: "🖥️",
        },
        {
          title: "PostgreSQL",
          description:
            "Metadata, full-text search via tsvector, relational integrity across 35K cases.",
          icon: "🗄️",
        },
        {
          title: "Pinecone",
          description:
            "2.5M embeddings in 1,536 dimensions -- finds judgments by meaning, not keywords.",
          icon: "🧠",
        },
        {
          title: "Neo4j",
          description:
            "Graph database mapping citations between 35K cases -- no other Indian legal AI has this.",
          icon: "🕸️",
        },
        {
          title: "Google Gemini",
          description:
            "Pro for reasoning, Flash for bulk tasks, 1M token context window reads entire judgments.",
          icon: "✨",
        },
      ],
      columns: 3,
    },
    {
      type: "code",
      code: `# The Protocol (contract)
class LLMProvider(Protocol):
    async def generate(self, prompt: str) -> str: ...
    async def generate_json(self, prompt: str, schema: dict) -> dict: ...

# The Implementation (swappable)
class GeminiLLM(LLMProvider):
    async def generate(self, prompt: str) -> str:
        return await self.client.generate_content(prompt)

# Could be Gemini today, Claude tomorrow, a mock for testing`,
      language: "python",
    },
    {
      type: "highlight-box",
      icon: "🔌",
      title: "The Interface Pattern",
      description:
        "Every external service hides behind a Protocol class. The code never talks to Gemini directly -- it talks to an LLMProvider. Swap the provider without touching business logic.",
      accent: "#C5A880",
    },
  ],
};
