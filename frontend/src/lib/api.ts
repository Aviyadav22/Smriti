/* Centralized API client with JWT handling. All fetch calls go through here. */

import type {
    CaseDetail,
    CitationItem,
    FacetsResponse,
    LoginRequest,
    RegisterRequest,
    SearchResponse,
    SearchSuggestion,
    SimilarCase,
    TokenResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ---------------------------------------------------------------------------
// Token management
// ---------------------------------------------------------------------------

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function setTokens(access: string, refresh: string): void {
    accessToken = access;
    refreshToken = refresh;
    if (typeof window !== "undefined") {
        localStorage.setItem("access_token", access);
        localStorage.setItem("refresh_token", refresh);
    }
}

export function clearTokens(): void {
    accessToken = null;
    refreshToken = null;
    if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
    }
}

export function loadTokens(): void {
    if (typeof window !== "undefined") {
        accessToken = localStorage.getItem("access_token");
        refreshToken = localStorage.getItem("refresh_token");
    }
}

export function getAccessToken(): string | null {
    return accessToken;
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

class ApiError extends Error {
    constructor(
        public status: number,
        public code: string,
        message: string,
    ) {
        super(message);
        this.name = "ApiError";
    }
}

async function apiFetch<T>(
    path: string,
    options: RequestInit = {},
): Promise<T> {
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(options.headers as Record<string, string> || {}),
    };

    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
    });

    if (res.status === 401 && refreshToken) {
        const refreshed = await tryRefresh();
        if (refreshed) {
            headers["Authorization"] = `Bearer ${accessToken}`;
            const retry = await fetch(`${API_BASE}${path}`, { ...options, headers });
            if (!retry.ok) {
                const err = await retry.json().catch(() => ({ error: "Request failed" }));
                throw new ApiError(retry.status, err.code || "UNKNOWN", err.error || "Request failed");
            }
            return retry.json() as Promise<T>;
        }
        clearTokens();
        throw new ApiError(401, "UNAUTHORIZED", "Session expired");
    }

    if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Request failed" }));
        throw new ApiError(res.status, err.code || "UNKNOWN", err.error || "Request failed");
    }

    return res.json() as Promise<T>;
}

async function tryRefresh(): Promise<boolean> {
    try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) return false;
        const data: TokenResponse = await res.json();
        setTokens(data.access_token, data.refresh_token);
        return true;
    } catch {
        return false;
    }
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export async function login(req: LoginRequest): Promise<TokenResponse> {
    const data = await apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(req),
    });
    setTokens(data.access_token, data.refresh_token);
    return data;
}

export async function register(req: RegisterRequest): Promise<TokenResponse> {
    const data = await apiFetch<TokenResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify(req),
    });
    setTokens(data.access_token, data.refresh_token);
    return data;
}

export function logout(): void {
    clearTokens();
}

// ---------------------------------------------------------------------------
// Search API
// ---------------------------------------------------------------------------

export async function search(params: {
    q: string;
    court?: string;
    year_from?: number;
    year_to?: number;
    case_type?: string;
    bench_type?: string;
    judge?: string;
    act?: string;
    page?: number;
    page_size?: number;
}): Promise<SearchResponse> {
    const query = new URLSearchParams();
    query.set("q", params.q);
    if (params.court) query.set("court", params.court);
    if (params.year_from) query.set("year_from", String(params.year_from));
    if (params.year_to) query.set("year_to", String(params.year_to));
    if (params.case_type) query.set("case_type", params.case_type);
    if (params.bench_type) query.set("bench_type", params.bench_type);
    if (params.judge) query.set("judge", params.judge);
    if (params.act) query.set("act", params.act);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    return apiFetch<SearchResponse>(`/search?${query.toString()}`);
}

export async function searchSuggest(q: string): Promise<{ suggestions: SearchSuggestion[] }> {
    return apiFetch(`/search/suggest?q=${encodeURIComponent(q)}`);
}

export async function searchFacets(): Promise<FacetsResponse> {
    return apiFetch("/search/facets");
}

// ---------------------------------------------------------------------------
// Cases API
// ---------------------------------------------------------------------------

export async function getCase(id: string): Promise<CaseDetail> {
    return apiFetch(`/cases/${id}`);
}

export async function getCaseCitations(id: string): Promise<{
    case_id: string;
    citations: CitationItem[];
    total: number;
}> {
    return apiFetch(`/cases/${id}/citations`);
}

export async function getCaseCitedBy(id: string): Promise<{
    case_id: string;
    cited_by: CitationItem[];
    total: number;
}> {
    return apiFetch(`/cases/${id}/cited-by`);
}

export async function getCaseSimilar(id: string, limit = 5): Promise<{
    case_id: string;
    similar: SimilarCase[];
    total: number;
}> {
    return apiFetch(`/cases/${id}/similar?limit=${limit}`);
}

export function getCasePdfUrl(id: string): string {
    return `${API_BASE}/cases/${id}/pdf`;
}

export { ApiError };
