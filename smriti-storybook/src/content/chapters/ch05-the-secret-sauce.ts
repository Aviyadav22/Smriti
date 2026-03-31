import type { ChapterConfig } from "./types";

export const ch05TheSecretSauce: ChapterConfig = {
  id: "05-the-secret-sauce",
  title: "The Secret Sauce",
  subtitle: "Legal-aware chunking and seven types of memory",
  sections: [
    {
      type: "comparison",
      left: {
        label: "Generic Chunking",
        items: [
          "Fixed 2000-char splits",
          "Cuts sentences in half",
          "Mixes facts with holdings",
          "No section awareness",
        ],
        rejected: true,
      },
      right: {
        label: "Legal-Aware Chunking",
        items: [
          "2000/200 normal, 1200/300 dense",
          "Sentence-boundary aware",
          "Section-tagged (RATIO, ORDER...)",
          "Paragraph number tracking",
        ],
        accepted: true,
      },
    },
    {
      type: "stats",
      items: [
        { icon: "🧬", value: "7", label: "vector types" },
        { icon: "📈", value: "1.5x", label: "RRF boost for propositions" },
        { icon: "📐", value: "1,536", label: "dimensions per vector" },
        { icon: "📜", value: "2,932", label: "statute sections ingested" },
      ],
    },
    {
      type: "cards",
      cards: [
        {
          title: "Chunk",
          description: "Regular text chunks -- the workhorse across 35K judgments.",
          icon: "📄",
        },
        {
          title: "Proposition",
          description:
            "'Bail is a right, not a privilege' -- single legal statements extracted by AI.",
          icon: "💬",
        },
        {
          title: "Ratio",
          description:
            "The ratio decidendi -- what the case actually decided, the legal principle.",
          icon: "⚖️",
        },
        {
          title: "Headnote",
          description: "Structured case summary for quick overview and ranking.",
          icon: "🔖",
        },
        {
          title: "Statute",
          description:
            "Full text of 2,932 sections from 8 acts -- 'Section 302 IPC: Punishment for murder...'",
          icon: "📜",
        },
        {
          title: "Summary",
          description: "AI-generated case summary for high-level understanding.",
          icon: "📝",
        },
        {
          title: "Community",
          description:
            "'These 15 cases all deal with bail under NDPS Act' -- citation cluster summaries.",
          icon: "👥",
        },
      ],
      columns: 4,
    },
    {
      type: "flow",
      steps: ["Detect Sections", "Size Chunks", "Tag Metadata", "Embed (Gemini)", "Store in Pinecone"],
    },
    {
      type: "code",
      code: `# Legal section detection for chunk sizing
SECTION_PATTERNS = {
    "FACTS":        r"(?:FACTUAL BACKGROUND|FACTS OF THE CASE)",
    "ANALYSIS":     r"(?:ANALYSIS|REASONING|DISCUSSION)",
    "RATIO":        r"(?:RATIO DECIDENDI|WE HOLD THAT|IT IS HELD)",
    "ORDER":        r"(?:^ORDER$|OPERATIVE ORDER|FINAL ORDER)",
    "DISSENT":      r"(?:DISSENTING|PER .+ \\(DISSENTING\\))",
}

# Dense sections (ANALYSIS, RATIO, ORDER, DISSENT) get:
#   chunk_size=1200, overlap=300 (vs standard 2000/200)`,
      language: "python",
    },
  ],
};
