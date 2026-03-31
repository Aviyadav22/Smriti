import type { ChapterConfig } from "./types";

export const ch02TeachingSmritiToRead: ChapterConfig = {
  id: "02-teaching-smriti-to-read",
  title: "Teaching Smriti to Read",
  subtitle: "Cracking open PDFs, defeating invisible characters, and OCR rescue missions",
  sections: [
    {
      type: "flow",
      steps: ["PDF Upload", "Text Extraction", "NFKC Cleanup", "Header Dedup", "Page Joining", "OCR Rescue", "Quality Score"],
    },
    {
      type: "cards",
      cards: [
        {
          title: "Text Extraction",
          description:
            "PyMuPDF cracks open the PDF; NFKC normalization strips invisible zero-width characters that break NLP.",
          icon: "📄",
        },
        {
          title: "Header Dedup",
          description:
            "'SUPREME COURT OF INDIA' on every page? If a line repeats on 50%+ pages, strip it.",
          icon: "🔍",
        },
        {
          title: "Smart Page Joining",
          description:
            "No period at end of page? The sentence continues on the next page -- merge automatically.",
          icon: "🔗",
        },
        {
          title: "Per-Page OCR",
          description:
            "Pages 1-50 clean text, pages 51-53 scanned appendix? Only OCR the flagged pages (max 20).",
          icon: "👁️",
        },
      ],
      columns: 2,
    },
    {
      type: "stats",
      items: [
        { icon: "📄", value: "35,000", label: "judgments processed" },
        { icon: "🧠", value: "2.5M", label: "vectors generated" },
        { icon: "👁️", value: "3", label: "extraction versions" },
        { icon: "⭐", value: "HIGH", label: "quality tier target" },
      ],
    },
    {
      type: "code",
      code: `Quality Tiers:
  HIGH   -- Clean extraction, many legal keywords, no OCR needed
  MEDIUM -- Some OCR pages, reasonable keyword count
  LOW    -- Heavy OCR, few keywords, possible garbled text

Scoring: character count + legal keyword density + OCR ratio
The quality score travels with the document forever.`,
      language: "text",
    },
    {
      type: "highlight-box",
      icon: "🔄",
      title: "Three Versions, Three Lessons",
      description:
        "V1: basic PyMuPDF. V2: OCR fallback + quality scoring. V3: per-page OCR, NFKC normalization, smart joining. Each version was born from real failures on real judgments.",
      accent: "#C5A880",
    },
  ],
};
