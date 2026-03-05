/* Shared TypeScript types matching backend API schemas. */

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export interface SearchFilters {
    court?: string | null;
    year_from?: number | null;
    year_to?: number | null;
    case_type?: string | null;
    bench_type?: string | null;
    judge?: string | null;
    act?: string | null;
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

export interface SearchSuggestion {
    case_id: string;
    title: string | null;
    citation: string | null;
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
}

export interface User {
    id: string;
    email: string;
    name: string;
    role: string;
}
