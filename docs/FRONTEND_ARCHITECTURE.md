# Smriti Frontend Architecture

Technical reference for rebuilding or adapting the Smriti UI. Covers every page, API endpoint, data flow pattern, and shared type. Use this to build alternative clients (WhatsApp bot, mobile app, CLI tool, etc.).

---

## 1. Frontend Tech Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Framework | Next.js (App Router) | 16.1.x | All pages are `"use client"` (CSR). No SSR/RSC used. |
| Language | TypeScript | 5.x | Strict mode. No `any` allowed. |
| Styling | Tailwind CSS | 4.x | With `tw-animate-css` for animations |
| Component Library | shadcn/ui | 3.8.x | Built on Radix UI primitives |
| Icons | lucide-react | 0.577.x | |
| Charts | recharts | 3.8.x | Used on judge profile, court stats, judge compare pages |
| Graph Visualization | react-force-graph-2d | 1.29.x | Canvas-based, loaded via `next/dynamic` (no SSR) |
| Package Manager | pnpm | | |
| Testing | Vitest + Testing Library | | 88 frontend tests |
| Fonts | Inter (sans), Lora (serif) | | Loaded via `next/font/google` |

**Design language:** Dark theme with gold accent (`var(--gold)` = `#B89B6A`). Serif font (Lora) for headings and legal text. Minimal, professional aesthetic.

---

## 2. Page Inventory

### 2.1 Home Page

| Property | Value |
|---|---|
| Route | `/` |
| File | `frontend/src/app/page.tsx` |
| Auth required | No |
| API calls | None |
| Purpose | Landing page with search bar, example queries, stats, feature overview, and CTA |

Submitting the search form navigates to `/search?q=<query>`.

### 2.2 Search Page

| Property | Value |
|---|---|
| Route | `/search?q=<query>` |
| File | `frontend/src/app/search/page.tsx` |
| Auth required | No |
| API calls | `GET /api/v1/search`, `GET /api/v1/search/facets` |
| Purpose | Hybrid search results with filters, pagination, query understanding display |

Key behavior:
- Reads `q` from URL search params on mount.
- Calls `searchFacets()` once on mount to populate filter dropdowns (court, case type, year range).
- Filters are local state; changing a filter re-executes the search.
- Clicking a result card navigates to `/case/<case_id>`.
- Pagination is client-side (re-fetches with `page` param).
- Wrapped in `<Suspense>` because `useSearchParams()` requires it in Next.js App Router.

### 2.3 Case Detail Page

| Property | Value |
|---|---|
| Route | `/case/[id]` |
| File | `frontend/src/app/case/[id]/page.tsx` |
| Auth required | No |
| API calls | `GET /api/v1/cases/:id`, `GET /api/v1/cases/:id/citations`, `GET /api/v1/cases/:id/cited-by`, `GET /api/v1/cases/:id/similar`, `GET /api/v1/graph/:id/neighborhood`, `GET /api/v1/cases/:id/audio/status` |
| Purpose | Full judgment view with sections, citations, similar cases, mini citation graph, audio digest |

Key behavior:
- All 5 API calls fire in parallel via `Promise.allSettled()` on mount.
- Judgment text is displayed in tabs, one per detected section (e.g., "facts", "arguments", "judgment").
- Sidebar shows: parties, bench (judge names link to `/judge/<name>`), ratio decidendi, keywords, acts cited, similar cases, metadata.
- Mini citation graph uses `react-force-graph-2d` with a "Full Graph" button linking to `/graph?case=<id>`.
- AudioPlayer component handles audio digest generation and playback.
- PDF tab links to `GET /api/v1/cases/:id/pdf` (opens in new tab).

### 2.4 Chat Page

| Property | Value |
|---|---|
| Route | `/chat` |
| File | `frontend/src/app/chat/page.tsx` |
| Auth required | Yes (redirects to `/login`) |
| API calls | `POST /api/v1/chat` (SSE), `POST /api/v1/chat/:session_id/message` (SSE), `GET /api/v1/chat/sessions`, `GET /api/v1/chat/:session_id/history`, `DELETE /api/v1/chat/:session_id` |
| Purpose | RAG-powered legal research chat with streaming responses and cited sources |

Key behavior:
- Left sidebar lists past sessions; main area shows messages.
- New chat: calls `POST /api/v1/chat` with `{ message }`, receives SSE stream.
- Follow-up: calls `POST /api/v1/chat/:session_id/message`.
- SSE events are parsed and update the UI incrementally (see Section 8).
- Sources appear as clickable badges below assistant messages, linking to `/case/<case_id>`.
- Sidebar is responsive (overlay on mobile, persistent on desktop).
- Enter sends, Shift+Enter for newline. Textarea auto-resizes.

### 2.5 Graph Explorer Page

| Property | Value |
|---|---|
| Route | `/graph` |
| File | `frontend/src/app/graph/page.tsx` |
| Auth required | No |
| API calls | `GET /api/v1/graph/stats`, `GET /api/v1/graph/:id/neighborhood`, `GET /api/v1/graph/:id/chain`, `GET /api/v1/graph/:id/authorities`, `GET /api/v1/search` (for case search) |
| Purpose | Interactive citation graph visualization with force-directed layout |

Key behavior:
- Search bar with debounced autocomplete (uses search API with `page_size=5`).
- Two modes: "Network" (neighborhood) and "Chain" (forward citations).
- Depth control: 1, 2, or 3 levels.
- Clicking a node selects it (shows detail panel on right). Right-click navigates to case detail.
- Edge colors: gray=cites, red=overrules, green=affirms, orange=distinguishes.
- Authorities panel shows most-cited cases in the network.
- Global stats (total judgments, total citations) shown in empty state.

### 2.6 Judge Directory Page

| Property | Value |
|---|---|
| Route | `/judges` |
| File | `frontend/src/app/judges/page.tsx` |
| Auth required | No |
| API calls | `GET /api/v1/judges` |
| Purpose | Searchable, paginated list of judges with case counts |

Key behavior:
- Debounced search input (300ms).
- Table columns: Judge name, Total cases, Cases authored.
- Clicking a row navigates to `/judge/<name>`.
- Pagination with Previous/Next buttons.

### 2.7 Judge Profile Page

| Property | Value |
|---|---|
| Route | `/judge/[name]` |
| File | `frontend/src/app/judge/[name]/page.tsx` |
| Auth required | No |
| API calls | `GET /api/v1/judges/:name`, `GET /api/v1/judges/:name/cases` |
| Purpose | Comprehensive judge analytics with charts |

Key behavior:
- Both API calls fire in parallel via `Promise.allSettled()`.
- Stats cards: total cases, cases authored, bench combinations count, case types count.
- Charts (recharts): Cases by Year (bar), Disposal Patterns (pie), Case Types (horizontal bar), Acts & Statutes (progress bars).
- Bench combinations link to other judge profiles.
- Top cited judgments link to case detail pages.
- Recent cases list with "Author" badge.

### 2.8 Judge Compare Page

| Property | Value |
|---|---|
| Route | `/judges/compare` |
| File | `frontend/src/app/judges/compare/page.tsx` |
| Auth required | No |
| API calls | `GET /api/v1/judges` (for search), `GET /api/v1/judges/compare` |
| Purpose | Side-by-side comparison of 2-3 judges |

Key behavior:
- Search-and-select UI: type to search judges, click to add (max 3).
- Selected judges shown as removable pills.
- "Compare" button calls the compare endpoint.
- Results: summary cards per judge + grouped bar chart of disposal patterns.

### 2.9 Court Statistics Page

| Property | Value |
|---|---|
| Route | `/courts` |
| File | `frontend/src/app/courts/page.tsx` |
| Auth required | No |
| API calls | `GET /api/v1/courts/:court_name/stats` |
| Purpose | Court-level analytics (currently hardcoded to "Supreme Court of India") |

Key behavior:
- Stats cards: court name, total cases, total judges.
- Charts: Cases by Year (bar), Disposal Patterns (pie).
- Top Judges section with links to judge profiles.

### 2.10 Login Page

| Property | Value |
|---|---|
| Route | `/login` |
| File | `frontend/src/app/login/page.tsx` |
| Auth required | No |
| API calls | `POST /api/v1/auth/login` |
| Purpose | Email/password login form |

On success, stores tokens and redirects to `/search`.

### 2.11 Register Page

| Property | Value |
|---|---|
| Route | `/register` |
| File | `frontend/src/app/register/page.tsx` |
| Auth required | No |
| API calls | `POST /api/v1/auth/register` |
| Purpose | Registration form with DPDP consent checkbox |

Validates password >= 8 chars client-side. On success, stores tokens and redirects to `/search`.

### 2.12 Document Upload Page

| Property | Value |
|---|---|
| Route | `/upload` |
| File | `frontend/src/app/upload/page.tsx` |
| Auth required | Yes (implicit -- upload API requires auth) |
| API calls | `POST /api/v1/documents/upload` (multipart/form-data) |
| Purpose | Drag-and-drop PDF upload for AI analysis |

On success, redirects to `/documents/<document_id>`.

### 2.13 Documents List Page

| Property | Value |
|---|---|
| Route | `/documents` |
| File | `frontend/src/app/documents/page.tsx` |
| Auth required | Yes |
| API calls | `GET /api/v1/documents` |
| Purpose | List user's uploaded documents with status badges |

Clicking a document navigates to `/documents/<id>`.

### 2.14 Document Detail Page

| Property | Value |
|---|---|
| Route | `/documents/[id]` |
| File | `frontend/src/app/documents/[id]/page.tsx` |
| Auth required | Yes |
| API calls | `GET /api/v1/documents/:id`, `DELETE /api/v1/documents/:id` |
| Purpose | Document analysis results: issues, precedents, counter-arguments, research memo |

Key behavior:
- Polls every 3 seconds while document is in processing state.
- Stops polling when status is "completed" or "failed".
- Shows processing pipeline steps with `ProcessingStatus` component.
- Completed analysis shows: Case Overview (parties, key facts, relief sought), Legal Issues (expandable cards with supporting precedents), Counter-Arguments, Research Memo (with copy button).

---

## 3. API Surface Map

All endpoints are prefixed with `/api/v1`. The base URL is configured via `NEXT_PUBLIC_API_URL` env var (default: `http://localhost:8000/api/v1`).

### 3.1 Auth Endpoints

| Method | Endpoint | Auth | Request Body | Response | Used By |
|---|---|---|---|---|---|
| `POST` | `/auth/register` | No | `{ email, password, name }` | `{ access_token, refresh_token, expires_in }` | Register page |
| `POST` | `/auth/login` | No | `{ email, password }` | `{ access_token, refresh_token, expires_in }` | Login page |
| `POST` | `/auth/refresh` | No | `{ refresh_token }` | `{ access_token, refresh_token, expires_in }` | Auto (apiFetch 401 handler) |

### 3.2 Search Endpoints

| Method | Endpoint | Auth | Parameters | Response | Used By |
|---|---|---|---|---|---|
| `GET` | `/search` | No | `q`, `court?`, `year_from?`, `year_to?`, `case_type?`, `bench_type?`, `judge?`, `act?`, `page?`, `page_size?` | `SearchResponse` | Search page, Graph page (for case lookup) |
| `GET` | `/search/suggest` | No | `q` (min 3 chars) | `{ suggestions: SearchSuggestion[] }` | (Available, not currently wired to UI) |
| `GET` | `/search/facets` | No | None | `FacetsResponse` | Search page (filter dropdowns) |

### 3.3 Case Endpoints

| Method | Endpoint | Auth | Parameters | Response | Used By |
|---|---|---|---|---|---|
| `GET` | `/cases/:id` | No | | `CaseDetail` (with `sections` dict) | Case detail page |
| `GET` | `/cases/:id/pdf` | No | | PDF binary (inline) | Case detail page (PDF tab) |
| `GET` | `/cases/:id/citations` | No | | `{ case_id, citations: CitationItem[], total }` | Case detail page |
| `GET` | `/cases/:id/cited-by` | No | | `{ case_id, cited_by: CitationItem[], total }` | Case detail page |
| `GET` | `/cases/:id/similar` | No | `limit?` (default 5) | `{ case_id, similar: SimilarCase[], total }` | Case detail page |

### 3.4 Chat Endpoints

| Method | Endpoint | Auth | Request Body | Response | Used By |
|---|---|---|---|---|---|
| `POST` | `/chat` | Yes | `{ message }` | SSE stream (`StreamEvent`) | Chat page (new session) |
| `POST` | `/chat/:session_id/message` | Yes | `{ message }` | SSE stream (`StreamEvent`) | Chat page (follow-up) |
| `GET` | `/chat/sessions` | Yes | | `ChatSession[]` | Chat page (sidebar) |
| `GET` | `/chat/:session_id/history` | Yes | | `ChatMessage[]` | Chat page (load session) |
| `DELETE` | `/chat/:session_id` | Yes | | `{ status: "deleted" }` | Chat page (delete button) |

### 3.5 Graph Endpoints

| Method | Endpoint | Auth | Parameters | Response | Used By |
|---|---|---|---|---|---|
| `GET` | `/graph/:id/neighborhood` | No | `depth?` (1-3, default 1) | `GraphData` (`{ nodes, edges }`) | Graph page, Case detail page |
| `GET` | `/graph/:id/chain` | No | `max_depth?` (1-5, default 3) | `GraphData` | Graph page |
| `GET` | `/graph/:id/authorities` | No | `limit?` (1-50, default 20) | `GraphNode[]` | Graph page |
| `GET` | `/graph/stats` | No | | `GraphStats` | Graph page (empty state) |

### 3.6 Judge Analytics Endpoints

| Method | Endpoint | Auth | Parameters | Response | Used By |
|---|---|---|---|---|---|
| `GET` | `/judges` | No | `search?`, `page?`, `page_size?` | `JudgeListResponse` | Judges page, Judge compare page |
| `GET` | `/judges/compare` | No | `names` (comma-separated) | `JudgeCompareResponse` | Judge compare page |
| `GET` | `/judges/:name` | No | | `JudgeProfile` | Judge profile page |
| `GET` | `/judges/:name/cases` | No | `page?`, `page_size?`, `year?`, `case_type?` | `JudgeCasesResponse` | Judge profile page |
| `GET` | `/courts/:name/stats` | No | | `CourtStats` | Courts page |

### 3.7 Document Endpoints

| Method | Endpoint | Auth | Request Body | Response | Used By |
|---|---|---|---|---|---|
| `POST` | `/documents/upload` | Yes | `multipart/form-data` (file field) | `DocumentUploadResponse` | Upload page |
| `GET` | `/documents` | Yes | `page?`, `page_size?` | `DocumentListResponse` | Documents page |
| `GET` | `/documents/:id` | Yes | | `DocumentDetail` (with optional `analysis`) | Document detail page |
| `DELETE` | `/documents/:id` | Yes | | 204 No Content | Document detail page |
| `GET` | `/documents/:id/memo` | Yes | | `{ memo: string }` | (Available, not directly used -- memo is embedded in DocumentDetail.analysis) |

### 3.8 Audio Endpoints

| Method | Endpoint | Auth | Parameters | Response | Used By |
|---|---|---|---|---|---|
| `POST` | `/cases/:id/audio/generate` | Yes | `language?` (default "en") | `{ status, case_id, language }` | AudioPlayer component |
| `GET` | `/cases/:id/audio/status` | No | | `AudioDigestStatus` | AudioPlayer component |
| `GET` | `/cases/:id/audio` | No | `language?` | audio/mpeg stream | AudioPlayer component |

### 3.9 Other Endpoints

| Method | Endpoint | Auth | Response | Notes |
|---|---|---|---|---|
| `GET` | `/health` | No | `{ status, postgres, redis, version }` | Not mounted under `/api/v1` -- at root `/health` |

---

## 4. Authentication Flow

### 4.1 Token Management

File: `frontend/src/lib/api.ts`

Tokens are stored in two places simultaneously:
1. **Module-level variables** (`accessToken`, `refreshToken`) for in-memory access during the session.
2. **`localStorage`** (`access_token`, `refresh_token`) for persistence across page reloads.

```
setTokens(access, refresh)  --> sets both module vars + localStorage
clearTokens()               --> clears both module vars + localStorage
loadTokens()                --> reads localStorage into module vars (called on app init)
```

### 4.2 Auth Context

File: `frontend/src/lib/auth-context.tsx`

The `AuthProvider` wraps the entire app (via `frontend/src/app/providers.tsx` -> `frontend/src/app/layout.tsx`).

On mount:
1. Calls `loadTokens()` to restore tokens from `localStorage`.
2. Sets `isAuthenticated = !!getAccessToken()`.
3. Sets `isLoading = false`.

Exposed state:
- `isAuthenticated: boolean` -- whether a token exists (no JWT decode/validation on client).
- `isLoading: boolean` -- true during initial token load.
- `login(req)` -- calls API, stores tokens, sets `isAuthenticated = true`.
- `register(req)` -- calls API, stores tokens, sets `isAuthenticated = true`.
- `logout()` -- clears tokens, sets `isAuthenticated = false`.

### 4.3 Token Refresh

Handled automatically inside `apiFetch()`:
1. If a request returns 401 and a refresh token exists, call `POST /auth/refresh`.
2. If refresh succeeds, retry the original request with the new access token.
3. If refresh fails, clear all tokens and throw `ApiError(401, "UNAUTHORIZED", "Session expired")`.

Token lifetimes (set by backend):
- Access token: 15 minutes (`expires_in: 900`).
- Refresh token: rotation on each use (old token invalidated).

### 4.4 Auth Guards

There is no middleware-level auth guard. Individual pages check auth:
- **Chat page**: `useEffect` checks `isAuthenticated` and redirects to `/login` if false.
- **Document pages**: implicitly guarded (API returns 401 without token).
- **All other pages**: public (search, case detail, graph, judges, courts).

### 4.5 Rebuilding Auth for Another Client

To implement auth in a non-browser client:
1. `POST /auth/login` with `{ email, password }` --> get `{ access_token, refresh_token }`.
2. Include `Authorization: Bearer <access_token>` in all subsequent requests.
3. On 401, `POST /auth/refresh` with `{ refresh_token }` --> get new token pair.
4. Store tokens securely (keychain on mobile, encrypted storage on server).

---

## 5. Data Flow Patterns

### 5.1 Standard Fetch Pattern

Most pages follow this pattern:

```
Page mounts
  --> useEffect fires
  --> call api.ts function (which calls apiFetch)
  --> apiFetch adds Authorization header if token exists
  --> fetch() to API_BASE + path
  --> on 401: try refresh, retry, or throw
  --> on success: parse JSON, return typed result
  --> component sets state with result
  --> React re-renders
```

### 5.2 Parallel Loading

Case detail and judge profile pages fire multiple API calls in parallel using `Promise.allSettled()`:

```typescript
const [c, cit, cb, sim, graph] = await Promise.allSettled([
    getCase(caseId),
    getCaseCitations(caseId),
    getCaseCitedBy(caseId),
    getCaseSimilar(caseId),
    getGraphNeighborhood(caseId, 1),
]);
```

Each result is handled independently -- a failure in one call does not block others.

### 5.3 Debounced Search

Judge directory, graph explorer, and judge compare pages use debounced search:

```
User types in input
  --> handleSearchChange(value) sets input state
  --> clears previous timer
  --> sets new setTimeout (300-400ms)
  --> on timer fire: call API with search query
  --> update results state
```

### 5.4 Polling

Document detail page polls for processing status:

```
Page mounts
  --> fetch document
  --> if status != "completed" and status != "failed":
      --> start setInterval(fetchDoc, 3000)
  --> when status becomes terminal:
      --> clearInterval
```

AudioPlayer similarly polls every 5 seconds while audio is generating.

### 5.5 File Upload

The upload flow uses `FormData` instead of JSON:

```typescript
const formData = new FormData();
formData.append("file", file);
// Note: Content-Type header is NOT set -- browser sets it with boundary
fetch(url, { method: "POST", headers: { Authorization: ... }, body: formData });
```

---

## 6. Component Hierarchy

### 6.1 Layout Components

| Component | File | Used By |
|---|---|---|
| `Header` | `frontend/src/components/header.tsx` | Every page |
| `Footer` | `frontend/src/components/footer.tsx` | Every page (except chat, documents) |

**Header** contains:
- Logo (links to `/`)
- Global search bar (desktop only)
- Navigation links: Search, Chat, Graph, Judges, Upload
- Auth buttons: Login/Register (unauthenticated) or Logout (authenticated)
- Mobile hamburger menu with the same links

**Footer** contains:
- Brand mark
- CC-BY-4.0 attribution link
- Legal disclaimer

### 6.2 Feature Components

| Component | File | Used By |
|---|---|---|
| `AudioPlayer` | `frontend/src/components/audio-player.tsx` | Case detail page |
| `FileUpload` | `frontend/src/components/file-upload.tsx` | Upload page |
| `ProcessingStatus` | `frontend/src/components/processing-status.tsx` | Document detail page |

**AudioPlayer**: Self-contained component that manages audio digest lifecycle:
- Checks audio status on mount
- Shows "Generate Audio" button if not available (with language selector for 10 Indian languages)
- Shows "Generating..." with polling while in progress
- Shows full audio player (play/pause, seek bar, playback speed, download) when ready

**FileUpload**: Drag-and-drop zone for PDF files. Validates file type (PDF only) and size (max 50MB). Calls `onFileSelected(file)` callback.

**ProcessingStatus**: Step-by-step progress indicator for document processing pipeline. Steps: extracting -> analyzing -> searching -> generating -> completed.

### 6.3 UI Primitives (shadcn/ui)

All in `frontend/src/components/ui/`:

| Component | File | Notes |
|---|---|---|
| `Badge` | `badge.tsx` | Variants: default, secondary, destructive, outline |
| `Button` | `button.tsx` | Variants: default, destructive, outline, secondary, ghost, link. Sizes: default, sm, lg, icon |
| `Card` | `card.tsx` | Card, CardContent, CardDescription, CardHeader, CardTitle |
| `Input` | `input.tsx` | Standard text input |
| `Select` | `select.tsx` | Select, SelectContent, SelectItem, SelectTrigger, SelectValue |
| `Separator` | `separator.tsx` | Horizontal/vertical divider |
| `Sheet` | `sheet.tsx` | Slide-out panel (available but not currently used in pages) |
| `Tabs` | `tabs.tsx` | Tabs, TabsContent, TabsList, TabsTrigger |

### 6.4 Providers

| Component | File | Purpose |
|---|---|---|
| `Providers` | `frontend/src/app/providers.tsx` | Wraps children in `AuthProvider` |
| `AuthProvider` | `frontend/src/lib/auth-context.tsx` | Provides auth state to all components |

The provider chain: `RootLayout` -> `Providers` -> `AuthProvider` -> page content.

---

## 7. State Management

There is no global state library (no Redux, Zustand, Jotai, etc.). State is managed through:

### 7.1 React Context

Only one context: `AuthContext` via `useAuth()` hook. Provides `isAuthenticated`, `isLoading`, `login()`, `register()`, `logout()`.

### 7.2 Local Component State (`useState`)

Every page manages its own data state. Examples:
- Search page: `results`, `facets`, `loading`, `error`, `page`, filter values
- Chat page: `sessions`, `activeSessionId`, `messages`, `input`, `isStreaming`
- Case detail: `caseData`, `citations`, `citedBy`, `similar`, `graphData`

### 7.3 URL State

- Search query: `/search?q=<query>` (read via `useSearchParams()`)
- Case ID: `/case/[id]` (read via `useParams()`)
- Judge name: `/judge/[name]` (read via `useParams()`)
- Document ID: `/documents/[id]` (read via `useParams()`)
- Graph initial case: `/graph?case=<id>` (not currently read -- available for linking)

### 7.4 Module-Level State

- `accessToken` and `refreshToken` in `api.ts` are module-level variables (singleton per browser tab).

### 7.5 localStorage

- `access_token` and `refresh_token` persisted for session survival across page reloads.

---

## 8. SSE Streaming Pattern

The chat feature uses Server-Sent Events (SSE) for real-time response streaming. This pattern is reusable for future agent features.

### 8.1 Backend Side

File: `backend/app/api/routes/chat.py`

The backend returns a `StreamingResponse` with `media_type="text/event-stream"`:

```python
async def event_stream():
    async for event in rag_respond(...):
        yield f"data: {json.dumps(event.data | {'type': event.type})}\n\n"

return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # Important for nginx/Cloud Run
})
```

### 8.2 Frontend Side

File: `frontend/src/lib/api.ts`, function `_streamChat()`

The frontend uses the Fetch API (not EventSource) for SSE because it needs to send a POST body:

```typescript
function _streamChat(path, message, onEvent, onError): AbortController {
    const controller = new AbortController();

    fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: ... },
        body: JSON.stringify({ message }),
        signal: controller.signal,
    })
    .then(async (res) => {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";  // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const event = JSON.parse(line.slice(6));
                    onEvent(event);
                }
            }
        }
    });

    return controller;  // Caller can abort the stream
}
```

### 8.3 Event Types

```typescript
interface StreamEvent {
    type: "session" | "chunk" | "source" | "done";
    session_id?: string;    // Only in "session" event
    title?: string;         // Session title (in "session"), source title (in "source")
    content?: string;       // Text chunk (in "chunk")
    index?: number;
    case_id?: string;       // Source case ID (in "source")
    citation?: string;      // Source citation (in "source")
    court?: string;
    year?: number;
    score?: number;
    source_count?: number;  // Total sources (in "done")
}
```

Event sequence for a chat response:
1. `{ type: "session", session_id: "...", title: "..." }` -- emitted once for new sessions
2. `{ type: "chunk", content: "..." }` -- emitted many times as text streams in
3. `{ type: "source", case_id: "...", title: "...", citation: "...", ... }` -- emitted per source
4. `{ type: "done", source_count: N }` -- signals end of response

### 8.4 Chat Page State Machine

```
IDLE (no active stream)
  --> User submits message
  --> Add user message to messages array
  --> Add empty assistant message (isStreaming: true)
  --> Call createChatSession() or sendChatMessage()
  --> STREAMING

STREAMING
  --> "session" event: set activeSessionId, add to sessions list
  --> "chunk" event: append content to last assistant message
  --> "source" event: collect in local sources array
  --> "done" event: set sources on assistant message, isStreaming=false
  --> IDLE

ABORT (user navigates away or starts new chat)
  --> controller.abort()
  --> AbortError caught and ignored
```

### 8.5 Reusing for Agents

To add a new streaming agent feature:
1. Create a new backend endpoint that returns `StreamingResponse` with `text/event-stream`.
2. Define your event types (can reuse the `session/chunk/source/done` pattern or define new ones).
3. On the frontend, use the same `_streamChat` pattern (or generalize it) -- POST with fetch, read stream, parse SSE lines.
4. The `AbortController` pattern lets users cancel long-running agent tasks.

---

## 9. Key Types

All types are defined in `frontend/src/lib/types.ts`. They mirror the backend API response schemas.

### 9.1 Search Types

```typescript
SearchFilters { court?, year_from?, year_to?, case_type?, bench_type?, judge?, act? }
QueryUnderstanding { intent, original_query, expanded_query, search_strategy, filters, entities }
SearchResultItem { case_id, score, title, citation, court, year, date, case_type, judge, snippet }
SearchResponse { results: SearchResultItem[], total_count, page, page_size, query_understanding, facets }
SearchSuggestion { case_id, title, citation }
FacetsResponse { courts: string[], case_types: string[], bench_types: string[], years: { min, max } }
```

### 9.2 Case Types

```typescript
CaseDetail { id, title, citation, case_id, cnr, court, year, case_type, jurisdiction, bench_type,
             judge, author_judge, petitioner, respondent, decision_date, disposal_nature,
             description, keywords, acts_cited, cases_cited, ratio_decidendi, pdf_storage_path,
             source, language, chunk_count, sections: Record<string, string>, created_at, updated_at }
CitationItem { case_id, relationship, title, citation, court, year, date }
SimilarCase { case_id, similarity_score, title, citation, court, year, date, ratio_decidendi }
```

### 9.3 Auth Types

```typescript
TokenResponse { access_token, refresh_token, expires_in }
LoginRequest { email, password }
RegisterRequest { email, password, name }
User { id, email, name, role }
```

### 9.4 Chat Types

```typescript
ChatSession { id, title, created_at, updated_at, message_count }
ChatSource { case_id, title, citation, court, year, score }
ChatMessage { id, role: "user"|"assistant", content, sources: ChatSource[], created_at }
StreamEvent { type: "session"|"chunk"|"source"|"done", session_id?, title?, content?,
              index?, case_id?, citation?, court?, year?, score?, source_count? }
```

### 9.5 Graph Types

```typescript
GraphNode { id, title, citation, court, year, cited_by_count }
GraphEdge { from, to, type, context? }
GraphData { nodes: GraphNode[], edges: GraphEdge[] }
GraphStats { total_judgments, total_edges, most_cited: { id, title, citation, cited_by_count }[] }
```

### 9.6 Judge Analytics Types

```typescript
JudgeListItem { name, total_cases, cases_authored }
JudgeListResponse { judges: JudgeListItem[], total, page, page_size, total_pages }
JudgeProfile { name, total_cases, cases_authored, cases_by_year, disposal_patterns,
               bench_combinations, top_cited_judgments, acts_frequency, case_types }
JudgeCaseItem { id, title, citation, year, case_type, court, decision_date, is_author }
JudgeCasesResponse { items: JudgeCaseItem[], total, page, page_size, total_pages }
JudgeCompareResponse { judges: (JudgeProfile | null)[] }
CourtStats { court, total_cases, cases_by_year, case_types, disposal_patterns, top_judges }
```

### 9.7 Document Types

```typescript
DocumentUploadResponse { document_id, filename, status, message }
DocumentListItem { id, filename, status, processing_step, file_size, created_at, updated_at, error_message }
DocumentListResponse { documents: DocumentListItem[], total, page, page_size, total_pages }
DocumentIssue { title, description, supporting_precedents, statutes }
DocumentCounterArgument { issue_title, argument, response }
DocumentAnalysis { issues, parties, key_facts, relief_sought, counter_arguments, research_memo }
DocumentDetail extends DocumentListItem { processing_started_at, processing_completed_at, analysis? }
```

### 9.8 Audio Types

```typescript
AudioDigestInfo { language, status, duration_seconds }
AudioDigestStatus { case_id, available: string[], generating: string[], digests: AudioDigestInfo[] }
```

---

## 10. File Reference

```
frontend/
  src/
    app/
      layout.tsx              # Root layout (fonts, metadata, Providers wrapper)
      providers.tsx            # AuthProvider wrapper
      page.tsx                 # Home/landing page
      search/page.tsx          # Search results page
      case/[id]/page.tsx       # Case detail page
      chat/page.tsx            # RAG chat page
      graph/page.tsx           # Citation graph explorer
      judges/page.tsx          # Judge directory
      judges/compare/page.tsx  # Judge comparison
      judge/[name]/page.tsx    # Judge profile
      courts/page.tsx          # Court statistics
      login/page.tsx           # Login form
      register/page.tsx        # Registration form
      upload/page.tsx          # Document upload
      documents/page.tsx       # Document list
      documents/[id]/page.tsx  # Document detail/analysis
    components/
      header.tsx               # Global header with nav
      footer.tsx               # Global footer
      audio-player.tsx         # Audio digest player
      file-upload.tsx          # Drag-and-drop file upload
      processing-status.tsx    # Document processing steps
      ui/                      # shadcn/ui primitives
        badge.tsx, button.tsx, card.tsx, input.tsx,
        select.tsx, separator.tsx, sheet.tsx, tabs.tsx
    lib/
      api.ts                   # All API client functions + token management
      types.ts                 # All TypeScript type definitions
      auth-context.tsx         # Auth React context + provider

backend/
  app/
    main.py                    # FastAPI app, CORS, route registration
    api/routes/
      health.py                # GET /health
      auth.py                  # POST /auth/login, /auth/register, /auth/refresh
      cases.py                 # GET /cases/:id, /cases/:id/pdf, /citations, /cited-by, /similar
      search.py                # GET /search, /search/suggest, /search/facets
      chat.py                  # POST /chat, /chat/:id/message; GET /chat/sessions, /chat/:id/history; DELETE /chat/:id
      graph.py                 # GET /graph/:id/neighborhood, /chain, /authorities, /graph/stats
      judges.py                # GET /judges, /judges/compare, /judges/:name, /judges/:name/cases, /courts/:name/stats
      documents.py             # POST /documents/upload; GET /documents, /documents/:id, /documents/:id/memo; DELETE /documents/:id
      audio.py                 # POST /cases/:id/audio/generate; GET /cases/:id/audio/status, /cases/:id/audio
```
