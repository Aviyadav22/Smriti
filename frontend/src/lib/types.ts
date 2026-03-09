/* Shared TypeScript types matching backend API schemas. */

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export type PrecedentStrengthLevel = 'BINDING' | 'PERSUASIVE' | 'DISTINGUISHABLE' | 'OVERRULED';

export type JudgmentSection = 'FACTS' | 'ISSUES' | 'ARGUMENTS' | 'HOLDINGS' | 'REASONING' | 'ORDER';

export interface SearchFilters {
    court?: string | null;
    year_from?: number | null;
    year_to?: number | null;
    case_type?: string | null;
    bench_type?: string | null;
    judge?: string | null;
    act?: string | null;
    section?: JudgmentSection | null;
}

export interface QueryUnderstanding {
    intent: string;
    original_query: string;
    expanded_query: string;
    search_strategy: string;
    filters: SearchFilters;
    entities: {
        case_names: string[];
        statutes: string[];
        legal_concepts: string[];
        judges: string[];
        courts: string[];
    };
}

export interface SearchResultItem {
    case_id: string;
    score: number;
    title: string | null;
    citation: string | null;
    court: string | null;
    year: number | null;
    date: string | null;
    case_type: string | null;
    judge: string | null;
    snippet: string | null;
    bench_type: string | null;
    equivalent_citations: string[];
    treatment_warning?: string | null;
    precedent_strength?: PrecedentStrengthLevel;
    section_type?: JudgmentSection | null;
}

export interface SearchResponse {
    results: SearchResultItem[];
    total_count: number;
    page: number;
    page_size: number;
    query_understanding: QueryUnderstanding;
    facets: {
        courts?: Record<string, number>;
        case_types?: Record<string, number>;
        years?: Record<number, number>;
        bench_types?: Record<string, number>;
    };
}

export interface FacetsResponse {
    courts: string[];
    case_types: string[];
    bench_types: string[];
    years: { min: number | null; max: number | null };
}

// ---------------------------------------------------------------------------
// Case detail
// ---------------------------------------------------------------------------

export interface CaseDetail {
    id: string;
    title: string;
    citation: string | null;
    case_id: string | null;
    cnr: string | null;
    court: string;
    year: number | null;
    case_type: string | null;
    jurisdiction: string | null;
    bench_type: string | null;
    judge: string | null;
    author_judge: string | null;
    petitioner: string | null;
    respondent: string | null;
    decision_date: string | null;
    disposal_nature: string | null;
    description: string | null;
    keywords: string[] | null;
    acts_cited: string[] | null;
    cases_cited: string[] | null;
    ratio_decidendi: string | null;
    pdf_storage_path: string | null;
    source: string | null;
    language: string | null;
    chunk_count: number | null;
    sections: Record<string, string>;
    created_at: string | null;
    updated_at: string | null;
}

export interface CitationItem {
    case_id: string;
    relationship: string | null;
    title: string | null;
    citation: string | null;
    court: string | null;
    year: number | null;
    date: string | null;
}

export interface SimilarCase {
    case_id: string;
    similarity_score: number;
    title: string | null;
    citation: string | null;
    court: string | null;
    year: number | null;
    date: string | null;
    ratio_decidendi: string | null;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenResponse {
    access_token: string;
    refresh_token: string;
    expires_in: number;
}

export interface LoginRequest {
    email: string;
    password: string;
}

export interface RegisterRequest {
    email: string;
    password: string;
    name: string;
    consent_given: boolean;
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export interface ChatSession {
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
}

export interface ChatSource {
    case_id: string;
    title: string | null;
    citation: string | null;
    court: string | null;
    year: number | null;
    score: number;
}

export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources: ChatSource[];
    created_at: string;
}

export interface StreamEvent {
    type: "session" | "chunk" | "source" | "done" | "disclaimer";
    session_id?: string;
    title?: string;
    content?: string;
    index?: number;
    case_id?: string;
    citation?: string;
    court?: string;
    year?: number;
    score?: number;
    source_count?: number;
    message?: string;
}

// ---------------------------------------------------------------------------
// Graph
// ---------------------------------------------------------------------------

export interface GraphNode {
    id: string;
    title: string | null;
    citation: string | null;
    court: string | null;
    year: number | null;
    cited_by_count: number;
}

export interface GraphEdge {
    from: string;
    to: string;
    type: string;
    context?: string | null;
}

export interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

export interface GraphStats {
    total_judgments: number;
    total_edges: number;
    most_cited: {
        id: string;
        title: string | null;
        citation: string | null;
        cited_by_count: number;
    }[];
}

// ---------------------------------------------------------------------------
// Judge Analytics
// ---------------------------------------------------------------------------

export interface JudgeListItem {
    name: string;
    total_cases: number;
    cases_authored: number;
}

export interface JudgeListResponse {
    judges: JudgeListItem[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface BenchCombination {
    judge: string;
    cases_together: number;
}

export interface JudgmentSummary {
    id: string;
    title: string;
    citation: string | null;
    year: number | null;
    citation_count?: number;
}

export interface JudgeProfile {
    name: string;
    total_cases: number;
    cases_authored: number;
    cases_by_year: Record<string, number>;
    disposal_patterns: Record<string, number>;
    bench_combinations: BenchCombination[];
    top_cited_judgments: JudgmentSummary[];
    acts_frequency: Record<string, number>;
    case_types: Record<string, number>;
}

export interface JudgeCaseItem {
    id: string;
    title: string;
    citation: string | null;
    year: number | null;
    case_type: string | null;
    court: string;
    decision_date: string | null;
    is_author: boolean;
}

export interface JudgeCasesResponse {
    cases: JudgeCaseItem[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface JudgeCompareResponse {
    judges: (JudgeProfile | null)[];
}

export interface CourtJudge {
    judge: string;
    cases: number;
}

export interface CourtStats {
    court: string;
    total_cases: number;
    cases_by_year: Record<string, number>;
    case_types: Record<string, number>;
    disposal_patterns: Record<string, number>;
    top_judges: CourtJudge[];
}

// ---------------------------------------------------------------------------
// Phase 5: Document Upload + Audio Digests
// ---------------------------------------------------------------------------

export interface DocumentUploadResponse {
    document_id: string;
    filename: string;
    status: string;
    message: string;
}

export interface DocumentListItem {
    id: string;
    filename: string;
    status: string;
    processing_step: string | null;
    file_size: number | null;
    created_at: string;
    updated_at: string;
    error_message: string | null;
}

export interface DocumentListResponse {
    documents: DocumentListItem[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

export interface DocumentIssue {
    title: string;
    description: string;
    supporting_precedents: {
        case_id: string;
        title: string | null;
        citation: string | null;
        score: number;
    }[];
    statutes: string[];
}

export interface DocumentCounterArgument {
    issue_title: string;
    argument: string;
    response: string;
}

export interface DocumentAnalysis {
    issues: DocumentIssue[];
    parties: Record<string, string | null>;
    key_facts: string;
    relief_sought: string | null;
    counter_arguments: DocumentCounterArgument[];
    research_memo: string;
}

export interface DocumentDetail extends DocumentListItem {
    processing_started_at: string | null;
    processing_completed_at: string | null;
    analysis?: DocumentAnalysis;
}

export interface AudioDigestInfo {
    language: string;
    status: string;
    duration_seconds: number | null;
}

export interface AudioDigestStatus {
    case_id: string;
    available: string[];
    generating: string[];
    digests: AudioDigestInfo[];
}

// ---------------------------------------------------------------------------
// Agent Types
// ---------------------------------------------------------------------------

export type AgentType = "research" | "case_prep" | "strategy" | "drafting";

export type AgentStatus = "running" | "waiting_input" | "completed" | "failed" | "cancelled";

export interface AgentExecution {
    id: string;
    agent_type: AgentType;
    status: AgentStatus;
    input_data: Record<string, unknown>;
    result_data: Record<string, unknown> | null;
    current_step: string | null;
    steps_completed: number;
    total_steps: number | null;
    created_at: string;
    updated_at: string;
    completed_at: string | null;
    error_message: string | null;
}

export interface AgentStreamEvent {
    type: "status" | "checkpoint" | "memo" | "done" | "error";
    step?: string;
    message?: string;
    question?: string;
    context?: Record<string, unknown>;
    content?: string;
    execution_id?: string;
    status?: string;
    recoverable?: boolean;
    data?: Record<string, unknown>;
}

export interface AgentStep {
    name: string;
    status: "pending" | "active" | "completed" | "error";
    message?: string;
}

// ---------------------------------------------------------------------------
// Drafting Agent Templates
// ---------------------------------------------------------------------------

export interface DocumentTemplate {
    doc_type: string;
    display_name: string;
    sections: string[];
    required_fields: string[];
    statutory_basis: string;
}

export interface DocumentTemplatesResponse {
    templates: DocumentTemplate[];
}
