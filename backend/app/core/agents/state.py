"""Agent state schemas for LangGraph."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


# ---------------------------------------------------------------------------
# Research Agent V2 — TypedDicts for typed sub-structures
# ---------------------------------------------------------------------------


class ResearchTask(TypedDict):
    """A single typed research task produced by plan_research_node."""
    task_id: str          # UUID
    task_type: str        # "case_law"|"named_case"|"statute"|"constitution"|"ik_search"|"web"|"graph"|"llm_direct"
    nl_query: str         # Natural language query (for vector/semantic search)
    boolean_query: str    # Structured boolean query (for FTS/keyword search)
    named_cases: list[dict]  # [{name, citation, relevance}] — LLM-known landmark cases
    rationale: str        # Why this task exists (shown in HITL review)
    filters: dict         # year, court, act, etc.
    priority: int         # 1=high, 3=low


class WorkerResult(TypedDict):
    """Result from a single worker execution."""
    task_id: str
    task_type: str
    query: str
    results: list[dict]   # Standard search result dicts
    source_urls: list[str]  # Indian Kanoon URLs, web URLs for linking
    metadata: dict        # source-specific: ik_doc_id, web_domain, etc.
    error: str | None
    reasoning: str        # [MA-RAG] Worker-level CoT (populated by batch_worker_cot_node)


class EvidenceGap(TypedDict):
    """A gap identified by gap_analysis_node."""
    description: str
    suggested_query: str
    suggested_source: str  # Which worker should handle it
    priority: int
    conditioned_on: list[str]  # [MC-RAG] Case IDs/citations from prior round
    conditioning_context: str  # [MC-RAG] Why this gap exists


class ExtractedPassage(TypedDict):
    """A verbatim passage extracted from a source document."""
    case_id: str
    citation: str
    passage: str          # Verbatim text from source
    source_field: str     # "chunk_text" | "ratio" | "ik_fragment" | "full_text"
    relevance: str        # Why this passage matters
    is_verbatim: bool     # True if exact copy, False if paraphrased


class RelevanceScore(TypedDict):
    """[CRAG] Per-document relevance evaluation from the retrieval evaluator."""
    case_id: str
    score: float          # 0.0-1.0 relevance to research question
    verdict: str          # "correct" | "ambiguous" | "incorrect"
    reason: str           # Why this document is/isn't relevant
    action: str           # "keep" | "filter" | "needs_web_fallback"


class CommunitySummary(TypedDict):
    """[GraphRAG] Pre-computed summary of a citation community cluster."""
    community_id: str
    title: str            # "Section 498A IPC misuse cluster"
    summary: str          # 2-3 paragraph summary
    key_cases: list[str]  # Top 5 case_ids in this community
    legal_principles: list[str]
    size: int             # Number of cases in community


class SynthesisDraft(TypedDict):
    """[Speculative RAG] One of N parallel synthesis drafts."""
    draft_id: str
    strategy: str         # "relevance" | "authority" | "recency"
    memo_text: str
    confidence: float
    sources_used: list[str]


class Footnote(TypedDict):
    """A structured footnote linking to a source document."""
    number: int
    citation: str         # Full case citation or statute reference
    source_type: str      # "case_law"|"statute"|"constitution"|"web"|"llm_knowledge"
    source_url: str       # Link to case viewer, IK page, or web URL
    case_id: str | None   # Our internal case_id if available
    excerpt: str          # Relevant passage
    is_used: bool         # True if cited in memo, False if searched but not cited
    verification_status: str  # [T4] "verified_pg"|"verified_ik"|"verified_neo4j"|"unverified"|"removed"
    verified_against: str     # [T4] Which source confirmed
    # Enriched fields for preview panel
    title: str                # Case title or web page title
    court: str                # Court name (e.g., "Supreme Court of India")
    year: int | None          # Decision year
    author: str               # Author judge
    bench: str                # Bench composition
    ik_doc_id: str            # Indian Kanoon doc ID (for IK link)
    pdf_available: bool       # True if pdf_storage_path exists
    source_label: str         # Display label: "Case" | "Statute" | "Web" | "Constitution"


class LegalQualityResult(TypedDict):
    """[Q4 LeMAJ] Legal reasoning quality assessment of final memo."""
    overall_score: float
    data_points: list[dict]  # [{claim, supported, evidence_id, issue}]
    omissions: list[dict]    # [{missed_authority, relevance}]
    logical_issues: list[str]
    pass_threshold: bool     # True if score >= 0.7


class StrategyAdjustment(TypedDict):
    """[Q5 Deep Research Reflection] Mid-research strategy pivot."""
    should_pivot: bool
    pivot_reason: str
    new_tasks: list[dict]     # Additional ResearchTask-shaped dicts
    reframe_query: str | None


class StatuteContext(TypedDict):
    """[V3] Statute text retrieved before planning."""
    act_short_name: str         # "IPC"
    section_number: str         # "302"
    section_title: str          # "Punishment for murder"
    section_text: str           # Full section text
    is_repealed: bool
    replaced_by: str            # "BNS, Section 103"
    new_code_text: str          # Auto-fetched new-code equivalent text


class LegalElement(TypedDict):
    """[V3] Constituent legal element decomposed from the research question."""
    element_id: str             # "mens_rea"
    description: str            # What needs to be established
    statute_basis: str          # "IPC Section 300, Exception 1"
    search_query: str           # Targeted case law search query
    is_contested: bool          # Whether likely disputed


class TemporalWarning(TypedDict):
    """[V3] Warning about old-code case validity under new codes."""
    case_id: str
    case_citation: str
    old_section: str            # "IPC 302"
    new_section: str            # "BNS 103"
    similarity: float           # 0.0-1.0 text similarity
    warning: str                # Human-readable warning


# ---------------------------------------------------------------------------
# Research Agent State (V2 — backward-compatible with V1 fields)
# ---------------------------------------------------------------------------


class ResearchState(TypedDict):
    """State for the Research Agent graph."""
    # --- V1 fields (kept for backward compatibility) ---
    query: str
    target_court: str
    target_bench: str
    language: str
    sub_queries: list[str]
    search_results: list[dict]
    cross_references: list[dict]
    contradictions: list[dict]
    draft_memo: str
    confidence: float
    messages: Annotated[list[dict], operator.add]
    iteration: int
    error: str
    # --- V2 fields ---
    rewritten_query: str
    complexity: str  # [S9] "simple"|"complex"|"multi_issue" from classify
    research_plan: list[ResearchTask]
    worker_results: Annotated[list[WorkerResult], operator.add]  # REDUCER for Send()
    worker_reasonings: list[str]  # [S4] Batched CoT reasoning
    relevance_scores: list[RelevanceScore]  # [CRAG] Per-document evaluations
    community_summaries: list[CommunitySummary]  # [GraphRAG]
    extracted_passages: list[ExtractedPassage]
    evidence_gaps: list[EvidenceGap]
    refinement_round: int  # 0, 1, or 2 max
    synthesis_drafts: list[SynthesisDraft]  # [Speculative RAG]
    footnotes: list[Footnote]
    source_attribution: dict  # {citation: {source_type, worker, url, case_id}}
    research_audit: dict  # {total_sources_searched, sources_cited, sources_unused, ...}
    precomputed_embeddings: dict  # [S6] {query_str: vector} pre-warmed during HITL
    strategy_adjustment: StrategyAdjustment | None  # [Q5] Reflection output
    legal_quality_result: LegalQualityResult | None  # [Q4] LeMAJ check
    citation_verification_results: list[dict]  # [T4] Per-citation verification
    process_events: Annotated[list[dict], operator.add]  # [T1] Accumulated SSE events
    # --- V3 fields (sequential-reactive pipeline) ---
    statute_context: list[StatuteContext]     # [V3] Statute text found before planning
    legal_elements: list[LegalElement]        # [V3] Element-wise breakdown
    procedural_context: str                   # [V3] "trial"|"appeal"|"slp"|"advisory"|""
    client_position: str                      # [V3] "petitioner"|"respondent"|"accused"|""
    include_adversarial: bool                 # [V3] User toggle from HITL
    temporal_warnings: list[TemporalWarning]  # [V3] Old-code vs new-code warnings


class CasePrepState(TypedDict):
    """State for the Case Prep Agent graph."""
    document_id: str
    language: str
    analysis: dict
    prioritized_issues: list[dict]
    argument_order: list[dict]
    enhanced_memo: str
    messages: Annotated[list[dict], operator.add]
    iteration: int
    error: str


class StrategyState(TypedDict):
    """State for the Strategy Agent graph."""
    case_facts: str
    target_judge: str          # optional, empty string if not provided
    target_bench: str          # optional, empty string if not provided
    target_court: str          # inferred or explicit
    desired_relief: str
    language: str              # "en" or "hi"
    # Produced by nodes:
    fact_analysis: dict        # parsed facts, parties, causes of action
    judge_profile: dict        # from Judge Analytics (if target_judge set)
    search_results: list[dict]  # hybrid search hits
    precedent_map: list[dict]  # per-argument precedents with strength
    strength_assessment: dict  # {level: "strong"|"moderate"|"weak", reasoning: str, score: float}
    legal_arguments: list[dict]  # ordered arguments with citations
    counter_arguments: list[dict]  # anticipated counters + rebuttals
    judge_considerations: list[dict]  # judge-specific strategic notes
    procedural_suggestions: list[str]
    strategy_memo: str         # final synthesized output
    confidence: float
    messages: Annotated[list[dict], operator.add]
    iteration: int
    error: str


class DraftingState(TypedDict):
    """State for the Drafting Agent graph."""
    doc_type: str            # key into TEMPLATES
    case_facts: str
    language: str            # "en" or "hi"
    relevant_precedents: list[dict]  # user-provided or from prior agent
    additional_context: dict  # type-specific fields (e.g., fir_details for bail)
    target_court: str
    # Produced by nodes:
    template: dict           # resolved DocumentTemplate as dict
    statutory_provisions: list[dict]  # relevant statute sections
    verified_precedents: list[dict]   # citation-verified precedents
    section_drafts: dict     # {section_name: draft_text}
    full_draft: str          # assembled document
    revision_feedback: str   # user feedback for section revision
    messages: Annotated[list[dict], operator.add]
    iteration: int
    error: str
