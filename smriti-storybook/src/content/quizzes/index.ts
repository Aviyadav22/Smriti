export interface QuizQuestion {
  type: "flashcard" | "drag-order" | "scenario";
  // Flashcard
  statement?: string;
  isTrue?: boolean;
  // Scenario
  question?: string;
  options?: string[];
  correctIndex?: number;
  // Drag-order
  items?: string[];
  // Shared
  explanation?: string;
}

const session1Quiz: QuizQuestion[] = [
  {
    type: "flashcard",
    statement: "Smriti started as a basic RAG model coded from scratch in April 2024.",
    isTrue: true,
    explanation: "Correct! The first version was a basic RAG model. It later moved to an open-source framework in October 2024, then was rewritten from scratch in March 2026.",
  },
  {
    type: "flashcard",
    statement: "Smriti uses MySQL as its primary database.",
    isTrue: false,
    explanation: "Smriti uses PostgreSQL 16 — chosen for its best-in-class full-text search (tsvector, ts_rank_cd) and relational integrity.",
  },
  {
    type: "flashcard",
    statement: "The project uses a single Pinecone index for all 7 vector types.",
    isTrue: true,
    explanation: "All 7 vector types (chunk, proposition, ratio, headnote, statute, summary, community) live in one Pinecone index, differentiated by a vector_type metadata field.",
  },
];

const session2Quiz: QuizQuestion[] = [
  {
    type: "flashcard",
    statement: "Smriti uses three separate databases: PostgreSQL for metadata, Pinecone for vectors, and Neo4j for citations.",
    isTrue: true,
    explanation: "Correct! Each database serves a different purpose — PostgreSQL for structured metadata & FTS, Pinecone for semantic vector search, and Neo4j for citation graph traversal.",
  },
  {
    type: "drag-order",
    question: "Put the search pipeline steps in the correct order:",
    items: [
      "Query Understanding",
      "Parallel Search (FTS + Vector)",
      "RRF Fusion (k=60)",
      "Cohere Reranking",
      "Post-Processing & Pagination",
    ],
    explanation: "The pipeline flows: understand the query → search in parallel → merge with RRF → rerank with Cohere → format results.",
  },
  {
    type: "scenario",
    question: "Why does Smriti use RRF (Reciprocal Rank Fusion) with k=60 instead of simple score averaging?",
    options: [
      "RRF is faster to compute",
      "It normalizes ranks across different scoring systems (BM25 vs cosine similarity)",
      "It reduces the number of results returned",
      "It's required by Pinecone's API",
    ],
    correctIndex: 1,
    explanation: "FTS returns BM25 scores while vector search returns cosine similarity — completely different scales. RRF fuses by rank position (not raw scores), making it robust across different scoring systems.",
  },
];

const session3Quiz: QuizQuestion[] = [
  {
    type: "scenario",
    question: "A judgment from 2022 cites Section 302 IPC. In 2024, IPC was replaced by BNS. What should Smriti's temporal validation node warn?",
    options: [
      "Nothing — IPC is still valid for pre-2024 cases",
      "This case cites IPC 302, now replaced by BNS 103",
      "This case should be ignored as outdated",
      "The citation is hallucinated",
    ],
    correctIndex: 1,
    explanation: "The temporal_validation_node flags cases citing repealed provisions and notes the equivalent new provision. IPC 302 (murder) maps to BNS 103.",
  },
  {
    type: "scenario",
    question: "The research agent found 15 supporting cases but 0 opposing cases. Which V3 stage addresses this gap?",
    options: [
      "Stage 1: Understand",
      "Stage 2: Decompose",
      "Stage 3: Investigate",
      "Stage 4: Challenge (adversarial_search_node)",
    ],
    correctIndex: 3,
    explanation: "Stage 4 (Challenge) includes the adversarial_search_node, which flips arguments to find counter-precedents. If you found cases granting bail, it searches for cases denying bail.",
  },
  {
    type: "scenario",
    question: "A case is cited by 500 other cases and was decided by a 5-judge Constitution Bench. What's its precedent strength?",
    options: [
      "PERSUASIVE — it's just one court's opinion",
      "DISTINGUISHABLE — facts may differ",
      "BINDING — highest court, largest bench, widely cited",
      "OVERRULED — too old to be relevant",
    ],
    correctIndex: 2,
    explanation: "A Constitution Bench (5+ judges) decision from the Supreme Court is BINDING on all courts. 500 citations confirms its authority as a landmark judgment.",
  },
];

const session4Quiz: QuizQuestion[] = [
  {
    type: "flashcard",
    statement: "The frontend uses Jest for testing.",
    isTrue: false,
    explanation: "Smriti's frontend uses Vitest (not Jest). Since the build uses Vite, Vitest is the natural testing choice.",
  },
  {
    type: "drag-order",
    question: "Order the Vertex AI batch ingestion phases:",
    items: [
      "Text Extraction + GCS Upload",
      "Batch Metadata (Vertex AI)",
      "Online Processing (chunks, vectors, graph)",
      "Quality Check (sample 10 cases)",
    ],
    explanation: "Phase 1 extracts text, Phase 2 uses batch LLM (50% cheaper), Phase 3 does the rest online, Phase 4 verifies quality.",
  },
  {
    type: "scenario",
    question: "Google AI Studio batch API failed for metadata extraction. The main reason was:",
    options: [
      "Rate limits were too low",
      "No responseSchema support in JSONL requests",
      "The model was too expensive",
      "It didn't support PDF files",
    ],
    correctIndex: 1,
    explanation: "AI Studio batch does NOT support responseSchema in JSONL → without structured output, Gemini returns freeform text instead of clean JSON. This was documented as ADR-020.",
  },
  {
    type: "scenario",
    question: "Which vector types get a 1.5x RRF boost in agent search (not regular search)?",
    options: [
      "chunk, summary, community",
      "proposition, ratio, headnote",
      "statute, chunk, proposition",
      "All 7 types equally",
    ],
    correctIndex: 1,
    explanation: "Proposition, ratio, and headnote vectors are boosted 1.5x in agent worker search because they contain more authoritative legal content.",
  },
  {
    type: "flashcard",
    statement: "Smriti has approximately 2,185 backend tests.",
    isTrue: true,
    explanation: "As of March 2026, Smriti has ~2,185 backend tests and ~311 frontend tests.",
  },
];

const quizzes: Record<number, QuizQuestion[]> = {
  1: session1Quiz,
  2: session2Quiz,
  3: session3Quiz,
  4: session4Quiz,
};

export function getQuizForSession(sessionId: number): QuizQuestion[] {
  return quizzes[sessionId] ?? [];
}
