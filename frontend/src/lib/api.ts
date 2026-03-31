/* Centralized API client with JWT handling. All fetch calls go through here. */

import type {
    AgentExecution,
    AgentSession,
    AgentSessionMessage,
    AgentStreamEvent,
    AudioDigestStatus,
    CaseDetail,
    ChatMessage,
    ChatSession,
    CitationItem,
    CourtStats,
    DocumentDetail,
    DocumentListResponse,
    DocumentTemplatesResponse,
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
    SearchHistoryEntry,
    SearchResponse,
    SessionDetail,
    SimilarCase,
    StreamEvent,
    TokenResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

// ---------------------------------------------------------------------------
// Token management
// ---------------------------------------------------------------------------

let accessToken: string | null = null;
let refreshToken: string | null = null;

// SECURITY TODO: migrate refresh token to httpOnly cookie to prevent XSS exfiltration.
// localStorage is accessible to any JS on the same origin. The refresh token is long-lived
// and should be stored in an httpOnly cookie instead. This requires coordinated backend
// changes (Set-Cookie headers, CSRF protection). Access token can remain in memory.
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

export function getRefreshToken(): string | null {
    return refreshToken;
}

// Session-expired event bus — lets AuthProvider react to 401s from any API call
type SessionExpiredListener = () => void;
const sessionExpiredListeners: Set<SessionExpiredListener> = new Set();

export function onSessionExpired(cb: SessionExpiredListener): () => void {
    sessionExpiredListeners.add(cb);
    return () => { sessionExpiredListeners.delete(cb); };
}

function emitSessionExpired(): void {
    for (const cb of sessionExpiredListeners) {
        try { cb(); } catch { /* listener error */ }
    }
}

/** Expose tryRefresh so AuthProvider can proactively refresh on load. */
export async function tryRefreshToken(): Promise<boolean> {
    return tryRefresh();
}

/** Check if a JWT is expired (with 60s buffer to avoid race conditions). */
function isTokenExpired(token: string): boolean {
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        // Refresh 60 seconds before actual expiry to avoid mid-request expiration
        return payload.exp * 1000 < Date.now() + 60_000;
    } catch {
        return true;
    }
}

/** Proactively refresh the access token if it's expired or about to expire. */
async function ensureFreshToken(): Promise<void> {
    if (!accessToken || !isTokenExpired(accessToken)) return;
    if (!refreshToken || isTokenExpired(refreshToken)) return;
    try {
        await tryRefresh();
    } catch {
        // Refresh failed — let the 401 handler deal with it
    }
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

/** Extract a human-readable message from any backend error response shape. */
function extractErrorMessage(err: Record<string, unknown>, fallback: string): string {
    // Format: { error: "message" } — custom handlers & rate limiter
    if (typeof err.error === "string") return err.error;
    // Format: { detail: "message" } — FastAPI HTTPException
    if (typeof err.detail === "string") return err.detail;
    // Format: { detail: [{msg: "..."}] } — Pydantic validation (422)
    if (Array.isArray(err.detail)) {
        const msgs = (err.detail as Record<string, unknown>[])
            .map((e) => (typeof e.msg === "string" ? e.msg : ""))
            .filter(Boolean);
        return msgs.length > 0 ? msgs.join("; ") : fallback;
    }
    // Fallback: { message: "..." }
    if (typeof err.message === "string") return err.message;
    return fallback;
}

function extractErrorCode(err: Record<string, unknown>): string {
    return typeof err.code === "string" ? err.code : "UNKNOWN";
}

async function apiFetch<T>(
    path: string,
    options: RequestInit = {},
): Promise<T> {
    // Proactively refresh token if expired (avoids 401 round-trip)
    await ensureFreshToken();

    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(options.headers as Record<string, string> || {}),
    };

    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    // Use caller-provided signal if available, otherwise create a timeout-only controller
    const externalSignal = options.signal;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    // If the caller already aborted, abort immediately
    if (externalSignal?.aborted) {
        controller.abort();
    } else {
        // Forward external abort to our internal controller
        externalSignal?.addEventListener("abort", () => controller.abort(), { once: true });
    }

    try {
        const res = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers,
            signal: controller.signal,
        });

        if (res.status === 401 && refreshToken) {
            let refreshed: boolean;
            try {
                refreshed = await tryRefresh();
            } catch (err) {
                // Network error during refresh — don't clear tokens, the user
                // may just be temporarily offline.
                if (err instanceof TypeError) {
                    throw new ApiError(0, "NETWORK_ERROR", "Network error during authentication");
                }
                throw err;
            }
            if (refreshed) {
                headers["Authorization"] = `Bearer ${accessToken}`;
                const retry = await fetch(`${API_BASE}${path}`, { ...options, headers });
                if (!retry.ok) {
                    const err = await retry.json().catch(() => ({}));
                    throw new ApiError(retry.status, extractErrorCode(err), extractErrorMessage(err, "Request failed"));
                }
                if (retry.status === 204) return undefined as T;
                return retry.json() as Promise<T>;
            }
            // Real auth failure (server returned non-OK) — clear tokens.
            clearTokens();
            emitSessionExpired();
            throw new ApiError(401, "UNAUTHORIZED", "Session expired — please log in again");
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new ApiError(res.status, extractErrorCode(err), extractErrorMessage(err, "Request failed"));
        }

        if (res.status === 204) return undefined as T;
        return res.json() as Promise<T>;
    } finally {
        clearTimeout(timeoutId);
    }
}

// Mutex to prevent concurrent refresh requests
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
    // If a refresh is already in progress, wait for it instead of starting another
    if (refreshPromise) return refreshPromise;

    refreshPromise = _doRefresh();
    try {
        return await refreshPromise;
    } finally {
        refreshPromise = null;
    }
}

async function _doRefresh(): Promise<boolean> {
    // Network errors (TypeError from fetch) are intentionally NOT caught here —
    // they propagate to the caller so it can distinguish network failures from
    // real auth failures and avoid clearing tokens on a transient network blip.
    const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data: TokenResponse = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
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

export async function logout(): Promise<void> {
    // Best-effort: revoke token server-side before clearing locally
    try {
        await apiFetch("/auth/logout", { method: "POST" });
    } catch {
        // Intentionally ignored — logout should always succeed locally
    }
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
    language?: string;
    signal?: AbortSignal;
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
    if (params.language) query.set("language", params.language);
    return apiFetch<SearchResponse>(`/search?${query.toString()}`, {
        signal: params.signal,
    });
}

export async function searchFacets(): Promise<FacetsResponse> {
    return apiFetch("/search/facets");
}

// WIRED_BY_REFACTOR: Search suggest was a disconnected backend endpoint.
// Wired to frontend for typeahead autocomplete on the search page.
export interface SearchSuggestion {
    case_id: string;
    title: string;
    citation: string;
}

export async function searchSuggest(
    q: string,
    limit: number = 10,
    signal?: AbortSignal,
): Promise<{ suggestions: SearchSuggestion[] }> {
    const query = new URLSearchParams();
    query.set("q", q);
    query.set("limit", String(limit));
    return apiFetch(`/search/suggest?${query.toString()}`, { signal });
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

// WIRED_BY_REFACTOR: Case summary endpoint was disconnected from frontend.
// Wired here to support Hindi translation of ratio decidendi on case detail page.
export interface CaseSummaryResponse {
    case_id: string;
    title: string;
    citation: string;
    court: string;
    year: number;
    summary: string;
    language: string;
}

export async function getCaseSummary(
    id: string,
    language: "en" | "hi" = "en",
): Promise<CaseSummaryResponse> {
    return apiFetch(`/cases/${id}/summary?language=${language}`);
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

// ---------------------------------------------------------------------------
// Shared SSE streaming helper
// ---------------------------------------------------------------------------

/**
 * Internal helper: POST to an SSE endpoint, parse the event stream, and
 * invoke the callback for each parsed event.
 * Returns an AbortController so the caller can cancel the stream.
 */
function _streamSSE<T>(
    path: string,
    body: unknown,
    onEvent: (event: T) => void,
    onError?: (error: Error) => void,
): AbortController {
    const controller = new AbortController();

    (async () => {
        // Proactively refresh token if expired (avoids 401 round-trip)
        await ensureFreshToken();

        const headers: Record<string, string> = {
            "Content-Type": "application/json",
        };
        if (accessToken) {
            headers["Authorization"] = `Bearer ${accessToken}`;
        }
        let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
        try {
            let res = await fetch(`${API_BASE}${path}`, {
                method: "POST",
                headers,
                body: JSON.stringify(body),
                signal: controller.signal,
            });

            if (res.status === 401 && refreshToken) {
                let refreshed: boolean;
                try {
                    refreshed = await tryRefresh();
                } catch (err) {
                    if (err instanceof TypeError) {
                        throw new ApiError(0, "NETWORK_ERROR", "Network error during authentication");
                    }
                    throw err;
                }
                if (refreshed) {
                    headers["Authorization"] = `Bearer ${accessToken}`;
                    res = await fetch(`${API_BASE}${path}`, {
                        method: "POST",
                        headers,
                        body: JSON.stringify(body),
                        signal: controller.signal,
                    });
                } else {
                    clearTokens();
                    emitSessionExpired();
                    throw new ApiError(401, "UNAUTHORIZED", "Session expired — please log in again");
                }
            }

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new ApiError(res.status, extractErrorCode(err), extractErrorMessage(err, "Request failed"));
            }

            reader = res.body?.getReader();
            if (!reader) throw new Error("No response body");

            const decoder = new TextDecoder();
            let buffer = "";

            let receivedDoneEvent = false;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const event = JSON.parse(line.slice(6)) as T;
                            // Track if we got a terminal event (checkpoint also ends the stream
                            // because the backend closes the SSE connection at interrupt())
                            const eventType = (event as Record<string, unknown>)?.type;
                            if (eventType === "done" || eventType === "error" || eventType === "checkpoint") {
                                receivedDoneEvent = true;
                            }
                            onEvent(event);
                        } catch {
                            // skip malformed SSE lines
                        }
                    }
                }
            }

            // Stream ended without a done/error event — unexpected disconnect
            if (!receivedDoneEvent && !controller.signal.aborted) {
                onError?.(new Error("Connection lost — the server stopped responding. Please try again."));
            }
        } catch (err) {
            if ((err as Error).name === "AbortError") return;
            onError?.(err instanceof Error ? err : new Error(String(err)));
        } finally {
            // Always clean up the reader to prevent memory leaks.
            // cancel() closes the underlying stream; releaseLock() detaches from the body.
            if (reader) {
                try { await reader.cancel(); } catch { /* already closed */ }
                try { reader.releaseLock(); } catch { /* already released */ }
            }
        }
    })();

    return controller;
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
    return _streamSSE<StreamEvent>(path, { message }, onEvent, onError);
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
    const res = await apiFetch<{ case_id: string; authorities: GraphNode[]; total: number }>(
        `/graph/${caseId}/authorities?limit=${limit}`,
    );
    return res.authorities;
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

    // 5-minute timeout for large file uploads
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000);

    try {
        let res = await fetch(`${API_BASE}/documents/upload`, {
            method: "POST",
            headers,
            body: formData,
            signal: controller.signal,
        });

        if (res.status === 401 && refreshToken) {
            let refreshed: boolean;
            try {
                refreshed = await tryRefresh();
            } catch (err) {
                if (err instanceof TypeError) {
                    throw new ApiError(0, "NETWORK_ERROR", "Network error during authentication");
                }
                throw err;
            }
            if (refreshed) {
                headers["Authorization"] = `Bearer ${accessToken}`;
                res = await fetch(`${API_BASE}/documents/upload`, {
                    method: "POST",
                    headers,
                    body: formData,
                    signal: controller.signal,
                });
            } else {
                clearTokens();
                throw new ApiError(401, "UNAUTHORIZED", "Session expired");
            }
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new ApiError(res.status, extractErrorCode(err), extractErrorMessage(err, "Upload failed"));
        }

        return res.json();
    } finally {
        clearTimeout(timeoutId);
    }
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
    return _streamSSE<AgentStreamEvent>(path, body, onEvent, onError);
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

// WIRED_BY_REFACTOR: The following 4 agent management functions were disconnected
// backend endpoints. Wired here for history page cancel/export/detail actions.

export async function getAgentExecution(executionId: string): Promise<AgentExecution> {
    return apiFetch(`/agents/executions/${executionId}`);
}

export async function cancelExecution(
    executionId: string,
): Promise<{ status: string; execution_id: string }> {
    return apiFetch(`/agents/executions/${executionId}`, { method: "DELETE" });
}

export async function exportResearchMemo(
    executionId: string,
    format: "docx" | "pdf" | "md" = "docx",
): Promise<Blob> {
    const headers: Record<string, string> = {};
    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    let res = await fetch(
        `${API_BASE}/agents/research/export/${executionId}?format=${format}`,
        { headers },
    );

    if (res.status === 401 && refreshToken) {
        let refreshed: boolean;
        try {
            refreshed = await tryRefresh();
        } catch (err) {
            if (err instanceof TypeError) {
                throw new ApiError(0, "NETWORK_ERROR", "Network error during authentication");
            }
            throw err;
        }
        if (refreshed) {
            headers["Authorization"] = `Bearer ${accessToken}`;
            res = await fetch(
                `${API_BASE}/agents/research/export/${executionId}?format=${format}`,
                { headers },
            );
        } else {
            clearTokens();
            throw new ApiError(401, "UNAUTHORIZED", "Session expired");
        }
    }

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new ApiError(
            res.status,
            extractErrorCode(err),
            extractErrorMessage(err, "Export failed"),
        );
    }

    return res.blob();
}

export function runStrategyAgent(
    caseFacts: string,
    desiredRelief: string,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
    targetJudge?: string,
    targetBench?: string,
): AbortController {
    return _streamAgent(
        "/agents/strategy/run",
        {
            case_facts: caseFacts,
            desired_relief: desiredRelief,
            target_judge: targetJudge || "",
            target_bench: targetBench || "",
        },
        onEvent,
        onError,
    );
}

export function runDraftingAgent(
    docType: string,
    caseFacts: string,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
    targetCourt?: string,
    relevantPrecedents?: Record<string, unknown>[],
    additionalContext?: Record<string, unknown>,
): AbortController {
    return _streamAgent(
        "/agents/drafting/run",
        {
            doc_type: docType,
            case_facts: caseFacts,
            target_court: targetCourt || "",
            relevant_precedents: relevantPrecedents || [],
            additional_context: additionalContext || {},
        },
        onEvent,
        onError,
    );
}

export async function getDraftingTemplates(): Promise<DocumentTemplatesResponse> {
    return apiFetch<DocumentTemplatesResponse>("/agents/drafting/templates");
}

export async function exportDraft(
    executionId: string,
    format: "docx" | "pdf" = "docx",
): Promise<Blob> {
    const headers: Record<string, string> = {};
    if (accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`;
    }

    let res = await fetch(
        `${API_BASE}/agents/drafting/export/${executionId}?format=${format}`,
        { method: "POST", headers },
    );

    if (res.status === 401 && refreshToken) {
        let refreshed: boolean;
        try {
            refreshed = await tryRefresh();
        } catch (err) {
            if (err instanceof TypeError) {
                throw new ApiError(0, "NETWORK_ERROR", "Network error during authentication");
            }
            throw err;
        }
        if (refreshed) {
            headers["Authorization"] = `Bearer ${accessToken}`;
            res = await fetch(
                `${API_BASE}/agents/drafting/export/${executionId}?format=${format}`,
                { method: "POST", headers },
            );
        } else {
            clearTokens();
            throw new ApiError(401, "UNAUTHORIZED", "Session expired");
        }
    }

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new ApiError(
            res.status,
            extractErrorCode(err),
            extractErrorMessage(err, "Export failed"),
        );
    }

    return res.blob();
}

// ---------------------------------------------------------------------------
// Agent Sessions (Conversation History)
// ---------------------------------------------------------------------------

export function createAgentSession(
    agentType: string,
    body: Record<string, unknown>,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController {
    return _streamSSE<AgentStreamEvent>(`/agents/${agentType}/session`, body, onEvent, onError);
}

export function sendAgentFollowUp(
    sessionId: string,
    message: string,
    onEvent: (event: AgentStreamEvent) => void,
    onError?: (error: Error) => void,
): AbortController {
    return _streamSSE<AgentStreamEvent>(
        `/agents/sessions/${sessionId}/follow-up`,
        { message },
        onEvent,
        onError,
    );
}

export async function getAgentSessions(
    agentType?: string,
    page = 1,
    pageSize = 20,
): Promise<{ sessions: AgentSession[]; total: number }> {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (agentType) params.set("agent_type", agentType);
    const data = await apiFetch<{ sessions: AgentSession[]; total: number }>(
        `/agents/sessions?${params.toString()}`,
    );
    return data;
}

export async function getAgentSessionMessages(
    sessionId: string,
): Promise<AgentSessionMessage[]> {
    const data = await apiFetch<{ messages: AgentSessionMessage[] }>(
        `/agents/sessions/${sessionId}/messages`,
    );
    return data.messages;
}

export async function getAgentSessionDetail(
    sessionId: string,
): Promise<SessionDetail> {
    return apiFetch<SessionDetail>(`/agents/sessions/${sessionId}`);
}

export async function deleteAgentSession(sessionId: string): Promise<void> {
    await apiFetch<unknown>(`/agents/sessions/${sessionId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Search History
// ---------------------------------------------------------------------------

export async function getSearchHistory(
    page = 1,
    pageSize = 20,
): Promise<{ history: SearchHistoryEntry[]; total: number }> {
    return apiFetch<{ history: SearchHistoryEntry[]; total: number }>(
        `/search/history?page=${page}&page_size=${pageSize}`,
    );
}

export async function toggleSearchBookmark(
    historyId: string,
): Promise<{ id: string; is_bookmarked: boolean }> {
    return apiFetch<{ id: string; is_bookmarked: boolean }>(
        `/search/history/${historyId}/bookmark`,
        { method: "POST" },
    );
}

export async function deleteSearchHistoryEntry(historyId: string): Promise<void> {
    await apiFetch<unknown>(`/search/history/${historyId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Memo Sharing
// ---------------------------------------------------------------------------

export async function createMemoShare(executionId: string): Promise<{ share_token: string; share_url: string; share_id: string }> {
    return apiFetch(`/agents/research/${executionId}/share`, { method: "POST" });
}

export async function getMemoShareStatus(executionId: string): Promise<{ shared: boolean; share_url?: string; share_token?: string; view_count?: number }> {
    return apiFetch(`/agents/research/${executionId}/share`);
}

export async function revokeMemoShare(executionId: string): Promise<{ revoked: boolean }> {
    return apiFetch(`/agents/research/${executionId}/share`, { method: "DELETE" });
}

export async function getSharedMemo(token: string): Promise<{ title: string; memo: string; footnotes: unknown[]; confidence: number | null; agent_type: string }> {
    const baseUrl = typeof window !== "undefined" ? window.location.origin : "";
    const res = await fetch(`${baseUrl}/api/shared/${token}`);
    if (!res.ok) throw new Error("Memo not found or expired");
    return res.json();
}

// ---------------------------------------------------------------------------
// Case Timeline & Citation Evolution
// ---------------------------------------------------------------------------

export async function getCaseTimeline(caseId: string): Promise<{ case_title: string; events: { date: string; type: string; court: string; detail: string }[] }> {
    return apiFetch(`/cases/${caseId}/timeline`);
}

export async function getCitationEvolution(caseId: string, direction: "forward" | "backward" = "forward"): Promise<{ root_case: { id: string; title: string; year: number; citation: string }; evolution: { case_id: string; title: string; year: number; citation: string; court: string; treatment: string; ratio_snippet: string }[]; direction: string }> {
    return apiFetch(`/graph/${caseId}/evolution?direction=${direction}`);
}

// ---------------------------------------------------------------------------
// Counsel Analytics API
// ---------------------------------------------------------------------------

export async function searchCounsel(
    query: string,
    page = 1,
    size = 20,
): Promise<{ counsels: { name: string; total_cases: number; designation: string }[]; total: number }> {
    return apiFetch(`/counsel?search=${encodeURIComponent(query)}&page=${page}&size=${size}`);
}

export async function getCounselProfile(name: string): Promise<Record<string, unknown>> {
    return apiFetch(`/counsel/${encodeURIComponent(name)}`);
}

export async function getCounselCases(
    name: string,
    page = 1,
    size = 20,
): Promise<{ cases: unknown[]; total: number }> {
    return apiFetch(`/counsel/${encodeURIComponent(name)}/cases?page=${page}&size=${size}`);
}

export async function getCounselMatchups(
    name: string,
    limit = 10,
): Promise<{ matchups: { opponent: string; total: number; wins: number; losses: number; win_rate: number }[] }> {
    return apiFetch(`/counsel/${encodeURIComponent(name)}/matchups?limit=${limit}`);
}

export { ApiError };
