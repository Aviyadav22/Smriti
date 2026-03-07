/* Centralized API client with JWT handling. All fetch calls go through here. */

import type {
    AgentExecution,
    AgentStreamEvent,
    AudioDigestStatus,
    CaseDetail,
    ChatMessage,
    ChatSession,
    CitationItem,
    CourtStats,
    DocumentDetail,
    DocumentListResponse,
    DocumentUploadResponse,
    FacetsResponse,
    GraphData,
    GraphNode,
    GraphStats,
    JudgeCasesResponse,
    JudgeCompareResponse,
    JudgeListResponse,
    JudgeProfile,
    LoginRequest,
    RegisterRequest,
    SearchResponse,
    SearchSuggestion,
    SimilarCase,
    StreamEvent,
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
    section?: string;
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
    if (params.section) query.set("section", params.section);
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

// ---------------------------------------------------------------------------
// Chat API
// ---------------------------------------------------------------------------

/** Start a new chat session with the first message. Returns an SSE stream. */
export function createChatSession(
    message: string,
    onEvent: (event: StreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController {
    return _streamChat("/chat", message, onEvent, onError);
}

/** Send a follow-up message in an existing session. Returns an SSE stream. */
export function sendChatMessage(
    sessionId: string,
    message: string,
    onEvent: (event: StreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController {
    return _streamChat(`/chat/${sessionId}/message`, message, onEvent, onError);
}

/** List all chat sessions for the current user. */
export async function getChatSessions(): Promise<ChatSession[]> {
    return apiFetch<ChatSession[]>("/chat/sessions");
}

/** Get full message history for a session. */
export async function getChatHistory(sessionId: string): Promise<ChatMessage[]> {
    return apiFetch<ChatMessage[]>(`/chat/${sessionId}/history`);
}

/** Delete a chat session and all its messages. */
export async function deleteChatSession(sessionId: string): Promise<void> {
    await apiFetch<{ status: string }>(`/chat/${sessionId}`, { method: "DELETE" });
}

/**
 * Internal helper: POST to a chat endpoint and stream SSE events via fetch.
 * Returns an AbortController so the caller can cancel the stream.
 */
function _streamChat(
    path: string,
    message: string,
    onEvent: (event: StreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController {
    const controller = new AbortController();

    const headers: Record<string, string> = {
        "Content-Type": "application/json",
    };
    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message }),
        signal: controller.signal,
    })
        .then(async (res) => {
            if (!res.ok) {
                const err = await res.json().catch(() => ({ error: "Chat request failed" }));
                throw new ApiError(res.status, err.code || "UNKNOWN", err.error || "Chat request failed");
            }

            const reader = res.body?.getReader();
            if (!reader) throw new Error("No response body");

            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const event = JSON.parse(line.slice(6)) as StreamEvent;
                            onEvent(event);
                        } catch {
                            // skip malformed SSE lines
                        }
                    }
                }
            }
        })
        .catch((err) => {
            if (err.name === "AbortError") return;
            onError?.(err instanceof Error ? err : new Error(String(err)));
        });

    return controller;
}

// ---------------------------------------------------------------------------
// Graph API
// ---------------------------------------------------------------------------

/** Get the citation neighborhood for a case. */
export async function getGraphNeighborhood(
    caseId: string,
    depth = 1,
): Promise<GraphData> {
    return apiFetch<GraphData>(`/graph/${caseId}/neighborhood?depth=${depth}`);
}

/** Get the forward citation chain for a case. */
export async function getGraphChain(
    caseId: string,
    maxDepth = 3,
): Promise<GraphData> {
    return apiFetch<GraphData>(`/graph/${caseId}/chain?max_depth=${maxDepth}`);
}

/** Get the most-cited authorities in a case's network. */
export async function getGraphAuthorities(
    caseId: string,
    limit = 20,
): Promise<GraphNode[]> {
    return apiFetch<GraphNode[]>(`/graph/${caseId}/authorities?limit=${limit}`);
}

/** Get global graph statistics. */
export async function getGraphStats(): Promise<GraphStats> {
    return apiFetch<GraphStats>("/graph/stats");
}

// ---------------------------------------------------------------------------
// Judge Analytics API
// ---------------------------------------------------------------------------

export async function getJudges(params?: {
    search?: string;
    page?: number;
    page_size?: number;
}): Promise<JudgeListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.set("search", params.search);
    if (params?.page) searchParams.set("page", String(params.page));
    if (params?.page_size) searchParams.set("page_size", String(params.page_size));
    const qs = searchParams.toString();
    return apiFetch<JudgeListResponse>(`/judges${qs ? `?${qs}` : ""}`);
}

export async function getJudgeProfile(name: string): Promise<JudgeProfile> {
    return apiFetch<JudgeProfile>(`/judges/${encodeURIComponent(name)}`);
}

export async function getJudgeCases(
    name: string,
    params?: { page?: number; page_size?: number; year?: number; case_type?: string },
): Promise<JudgeCasesResponse> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", String(params.page));
    if (params?.page_size) searchParams.set("page_size", String(params.page_size));
    if (params?.year) searchParams.set("year", String(params.year));
    if (params?.case_type) searchParams.set("case_type", params.case_type);
    const qs = searchParams.toString();
    return apiFetch<JudgeCasesResponse>(
        `/judges/${encodeURIComponent(name)}/cases${qs ? `?${qs}` : ""}`,
    );
}

export async function compareJudges(names: string[]): Promise<JudgeCompareResponse> {
    const namesParam = names.map((n) => encodeURIComponent(n)).join(",");
    return apiFetch<JudgeCompareResponse>(`/judges/compare?names=${namesParam}`);
}

export async function getCourtStats(court: string): Promise<CourtStats> {
    return apiFetch<CourtStats>(`/courts/${encodeURIComponent(court)}/stats`);
}

// ---------------------------------------------------------------------------
// Phase 5: Document Upload + Audio Digests
// ---------------------------------------------------------------------------

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const headers: Record<string, string> = {};
    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    const res = await fetch(`${API_BASE}/documents/upload`, {
        method: "POST",
        headers,
        body: formData,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Upload failed" }));
        throw new ApiError(res.status, "UPLOAD_ERROR", err.detail || err.error || "Upload failed");
    }

    return res.json();
}

export async function getDocuments(
    page: number = 1,
    pageSize: number = 20,
): Promise<DocumentListResponse> {
    return apiFetch<DocumentListResponse>(
        `/documents?page=${page}&page_size=${pageSize}`,
    );
}

export async function getDocument(id: string): Promise<DocumentDetail> {
    return apiFetch<DocumentDetail>(`/documents/${id}`);
}

export async function deleteDocument(id: string): Promise<void> {
    await apiFetch<void>(`/documents/${id}`, { method: "DELETE" });
}

export async function getResearchMemo(id: string): Promise<{ memo: string }> {
    return apiFetch<{ memo: string }>(`/documents/${id}/memo`);
}

export async function generateAudioDigest(
    caseId: string,
    language: string = "en",
): Promise<{ status: string; case_id: string; language: string }> {
    return apiFetch(`/cases/${caseId}/audio/generate?language=${language}`, {
        method: "POST",
    });
}

export async function getAudioStatus(caseId: string): Promise<AudioDigestStatus> {
    return apiFetch<AudioDigestStatus>(`/cases/${caseId}/audio/status`);
}

export function getAudioUrl(caseId: string, language: string = "en"): string {
    return `${API_BASE}/cases/${caseId}/audio?language=${language}`;
}

// ---------------------------------------------------------------------------
// Agent API
// ---------------------------------------------------------------------------

/**
 * Internal helper: POST to an agent endpoint and stream SSE events via fetch.
 * Returns an AbortController so the caller can cancel the stream.
 */
function _streamAgent(
    path: string,
    body: Record<string, unknown>,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController {
    const controller = new AbortController();

    (async () => {
        try {
            const res = await fetch(`${API_BASE}${path}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
                },
                body: JSON.stringify(body),
                signal: controller.signal,
            });

            if (!res.ok) {
                throw new Error(`Agent request failed: ${res.status}`);
            }

            const reader = res.body?.getReader();
            if (!reader) throw new Error("No response body");

            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const event = JSON.parse(line.slice(6)) as AgentStreamEvent;
                            onEvent(event);
                        } catch {
                            // skip malformed
                        }
                    }
                }
            }
        } catch (err) {
            if ((err as Error).name === "AbortError") return;
            onError?.(err instanceof Error ? err : new Error(String(err)));
        }
    })();

    return controller;
}

export function runResearchAgent(
    query: string,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController {
    return _streamAgent("/agents/research/run", { query }, onEvent, onError);
}

export function runCasePrepAgent(
    documentId: string,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController {
    return _streamAgent("/agents/case_prep/run", { document_id: documentId }, onEvent, onError);
}

export function resumeAgentExecution(
    executionId: string,
    input: string,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController {
    return _streamAgent(`/agents/executions/${executionId}/resume`, { input }, onEvent, onError);
}

export async function getAgentExecutions(
    page: number = 1,
    pageSize: number = 20,
): Promise<{ executions: AgentExecution[]; total: number; page: number; page_size: number }> {
    return apiFetch(`/agents/executions?page=${page}&page_size=${pageSize}`);
}

export async function getAgentExecution(id: string): Promise<AgentExecution> {
    return apiFetch(`/agents/executions/${id}`);
}

export async function cancelAgentExecution(id: string): Promise<void> {
    await apiFetch(`/agents/executions/${id}`, { method: "DELETE" });
}

export { ApiError };
