# Phase 4: Frontend Architecture Deep Dive

Generated: 2026-04-03

---

## 1. Frontend Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Framework | Next.js (App Router) | 16.2.1 | `output: "standalone"` for Cloud Run |
| Language | TypeScript | ^5 | Strict mode enabled |
| React | React + ReactDOM | 19.2.3 | Latest concurrent features |
| Styling | Tailwind CSS v4 | ^4 | CSS-first config (no tailwind.config.ts), tw-animate-css for animations |
| Component Library | shadcn/ui + Radix UI | ^3.8.5 (shadcn) | 13 UI primitives |
| Icons | Lucide React | ^0.577.0 | Tree-shakeable SVG icons |
| Markdown | react-markdown + remark-gfm + rehype-sanitize | ^10.1.0 | Chat and memo rendering |
| Charts | Recharts | ^3.8.0 | Judge/court analytics visualizations |
| Graph Viz | react-force-graph-2d | ^1.29.1 | Citation network graphs (canvas, dynamic import) |
| PDF | react-pdf | ^10.4.1 | Self-hosted worker, transpiled via webpack |
| i18n | next-intl | ^4.8.3 | English + Hindi, cookie-based locale |
| Testing | Vitest + Testing Library + jsdom | ^4.0.18 | ~311 tests, NOT jest |
| Linting | ESLint + eslint-config-next | ^9 | |
| Package Manager | npm | | |
| State Management | React Context (AuthProvider) + local component state | | No Redux/Zustand |
| Build Tool | Next.js built-in (Turbopack dev, webpack prod) | | |

### Fonts
Three Google fonts loaded with `next/font`:
- **Inter** (sans-serif): body text, `--font-inter`
- **Lora** (serif): headings and case titles, `--font-lora`
- **Noto Sans Devanagari**: Hindi text, `--font-devanagari`

### Color Theme
Custom CSS variables in `globals.css`:
- Light mode: Warm parchment aesthetic (cream backgrounds `#F5F0E8`, off-black text `#1A1A1A`)
- Gold accent: `--gold` variable used throughout for brand identity
- Chart colors: `--chart-1` through `--chart-5` for Recharts

---

## 2. Routes

Every route in the application:

| Path | Component File | Auth Required? | Purpose |
|---|---|---|---|
| `/` | `src/app/page.tsx` | No | Landing page: hero, search box, stats, features, pricing, CTA |
| `/login` | `src/app/login/page.tsx` | No (redirects if auth'd) | Email/password login form |
| `/register` | `src/app/register/page.tsx` | No | Registration with DPDP consent checkbox |
| `/search` | `src/app/search/page.tsx` | No | Full-text + semantic search with filters, facets, suggestions, pagination |
| `/case/[id]` | `src/app/case/[id]/page.tsx` | No | Case detail: sections, citations, graph, timeline, PDF, audio, similar cases |
| `/chat` | `src/app/chat/page.tsx` | Yes | Multi-session RAG chat with SSE streaming, source citations |
| `/agents` | `src/app/agents/page.tsx` | Yes | Agent hub: cards for Research, Case Prep, Strategy, Drafting |
| `/agents/research` | `src/app/agents/research/page.tsx` | Yes | Research agent workspace: SSE streaming, step timeline, memo viewer, footnotes panel, sessions sidebar, follow-up thread |
| `/agents/case-prep` | `src/app/agents/case-prep/page.tsx` | Yes | Case prep agent: select uploaded document, run analysis |
| `/agents/strategy` | `src/app/agents/strategy/page.tsx` | Yes | Strategy agent: input case facts + desired relief + optional judge/bench |
| `/agents/drafting` | `src/app/agents/drafting/page.tsx` | Yes | Drafting agent: template selection, case facts, export (docx/pdf). Can receive `research_execution_id` via query param |
| `/agents/history` | `src/app/agents/history/page.tsx` | Yes | Agent execution history: status badges, cancel, export, session conversations |
| `/graph` | `src/app/graph/page.tsx` | No | Full-page citation graph explorer: search, depth control, neighborhood/chain/authorities views |
| `/judges` | `src/app/judges/page.tsx` | No | Judge directory: search, paginated list, link to profiles |
| `/judge/[name]` | `src/app/judge/[name]/page.tsx` | No | Judge profile: cases by year (bar chart), disposal patterns (pie), bench combos, top cited judgments, prediction card |
| `/judges/compare` | `src/app/judges/compare/page.tsx` | No | Side-by-side judge comparison: select 2-3 judges, grouped bar charts |
| `/counsel` | `src/app/counsel/page.tsx` | No | Counsel (lawyer) directory: search, paginated list |
| `/counsel/[name]` | `src/app/counsel/[name]/page.tsx` | No | Counsel profile: win rate, case types, matchups against opponents |
| `/courts` | `src/app/courts/page.tsx` | No | Court analytics: select court, cases by year, case types, disposal patterns, top judges |
| `/documents` | `src/app/documents/page.tsx` | Yes | User's uploaded documents: list with status badges |
| `/documents/[id]` | `src/app/documents/[id]/page.tsx` | Yes | Document detail: processing status, issues, counter-arguments, research memo |
| `/upload` | `src/app/upload/page.tsx` | Yes | PDF upload (drag-and-drop, max 50MB) |
| `/shared/[token]` | `src/app/shared/[token]/page.tsx` | No | Public shared research memo viewer (no auth needed) |
| `/about` | `src/app/about/page.tsx` | No | Static about page (server component with metadata export) |
| `/privacy` | `src/app/privacy/page.tsx` | No | Privacy policy (DPDP Act 2023 compliant) |
| `/terms` | `src/app/terms/page.tsx` | No | Terms of service |

### SEO Files
| File | Purpose |
|---|---|
| `src/app/robots.ts` | Allows `/`, disallows `/api/`, `/chat/`, `/agents/`, `/documents/`, `/upload/` |
| `src/app/sitemap.ts` | Static sitemap: home, search, login, register. Base URL: `https://smriti.legal` |

### Error & Loading Pages
| File | Handles |
|---|---|
| `src/app/search/error.tsx` | "Search failed" with retry button |
| `src/app/search/loading.tsx` | Centered spinner |
| `src/app/case/[id]/error.tsx` | "Failed to load case" with retry |
| `src/app/case/[id]/loading.tsx` | Centered spinner |
| `src/app/agents/research/error.tsx` | "Research agent error" with retry |
| `src/app/judge/[name]/error.tsx` | "Failed to load judge profile" with retry |
| `src/app/judge/[name]/loading.tsx` | Centered spinner |

---

## 3. Layout & Navigation

### Root Layout (`src/app/layout.tsx`)
- Server component (async) that fetches locale and messages via `next-intl/server`
- Wraps everything in: `<NextIntlClientProvider>` -> `<Providers>` -> `<ErrorBoundary>` -> `{children}` + `<CookieConsent />`
- Sets `<html lang={locale}>` dynamically
- Applies all three font CSS variables to `<body>`

### Providers (`src/app/providers.tsx`)
- Client component (`"use client"`)
- Single provider: `<AuthProvider>` wrapping children
- No theme provider, no query client, no Redux store

### Header (`src/components/header.tsx`)
- Sticky top bar (`sticky top-0 z-50`) with blur backdrop
- Contains:
  - Logo: Scale icon + "Smriti" in Lora font, links to `/`
  - Desktop search bar (hidden on mobile)
  - Navigation links: Search, Chat, Graph, Agents, Judges, Courts, Upload, Documents
  - Language toggle (EN/HI): sets cookie, reloads page
  - Auth buttons: Login/Register (unauthenticated) or Logout (authenticated)
- Mobile: hamburger menu opens a dropdown with all nav items + search

### Footer (`src/components/footer.tsx`)
- Branding: Scale icon + "Smriti" + tagline
- Links: CC-BY-4.0 license, Privacy, Terms, About
- Legal disclaimer text (i18n-aware)

### Page Structure Pattern
Every page follows the same layout pattern:
```
<div className="min-h-screen flex flex-col">
  <Header />
  <main className="flex-1">
    {/* page content */}
  </main>
  <Footer />
</div>
```

Exceptions:
- Chat page: no footer, sidebar + main chat area with flex layout
- Research agent page: sidebar + main workspace, sheet for mobile sidebar

### Cookie Consent (`src/components/cookie-consent.tsx`)
- Fixed bottom banner, shown if `smriti_cookie_consent` not in localStorage
- Two options: "Essential Only" or "Accept All"
- i18n-aware text

---

## 4. Key Components

### Layout Components

#### `Header` (`src/components/header.tsx`)
- **Props**: none
- **Purpose**: Global sticky navigation bar with search, nav links, language toggle, auth controls
- **API calls**: none (uses `useAuth()` context)
- **Used by**: Every page

#### `Footer` (`src/components/footer.tsx`)
- **Props**: none
- **Purpose**: Page footer with links and disclaimer
- **API calls**: none

#### `ErrorBoundary` (`src/components/error-boundary.tsx`)
- **Props**: `{ children: ReactNode }`
- **Purpose**: React class component error boundary wrapping the entire app. Shows "Something went wrong" with retry button.
- **API calls**: none

#### `CookieConsent` (`src/components/cookie-consent.tsx`)
- **Props**: none
- **Purpose**: GDPR/DPDP cookie consent banner
- **API calls**: none

### Search Components

#### `PrecedentBadge` (`src/components/precedent-badge.tsx`)
- **Props**: `{ strength: PrecedentStrengthLevel; className?: string }`
- **Purpose**: Color-coded badge showing BINDING (green), PERSUASIVE (yellow), DISTINGUISHABLE (orange), OVERRULED (red/strikethrough). Tooltip explains meaning.
- **API calls**: none
- **Used by**: Search results page

#### `BenchStrength` (`src/components/bench-strength.tsx`)
- **Props**: `{ benchType: string | null; judgeCount?: number; className?: string }`
- **Purpose**: Shows bench type (Single Judge, Division Bench, Full Bench, Constitution Bench). Constitution bench gets a special blue badge.
- **API calls**: none
- **Used by**: Search results page

#### `EquivalentCitations` (`src/components/equivalent-citations.tsx`)
- **Props**: `{ citations: string[]; primaryCitation?: string | null; className?: string }`
- **Purpose**: Shows clickable citation strings (SCC, AIR, etc.) with copy-to-clipboard (Clipboard API + execCommand fallback)
- **API calls**: none
- **Used by**: Search results page

#### `ConfidenceMeter` (`src/components/confidence-meter.tsx`)
- **Props**: `{ score: number; className?: string }`
- **Purpose**: Horizontal progress bar showing relevance score (green >= 60%, yellow >= 40%, orange >= 20%, red < 20%)
- **API calls**: none
- **Used by**: Search results page

#### `LegalDisclaimer` (`src/components/legal-disclaimer.tsx`)
- **Props**: `{ className?: string }`
- **Purpose**: Amber banner: "AI-assisted legal research -- not legal advice. Verify all citations and reasoning independently."
- **API calls**: none
- **Used by**: Search page, chat page, all agent pages

#### `SearchResultSkeleton` / `CaseDetailSkeleton` (`src/components/skeleton.tsx`)
- **Props**: none (or `{ className }` for base `Skeleton`)
- **Purpose**: Loading placeholders with pulse animation
- **API calls**: none
- **Used by**: Search page, case detail page

#### `SearchHistoryDropdown` (`src/components/search/SearchHistoryDropdown.tsx`)
- **Props**: `{ onSelectQuery: (query, filters?) => void; isOpen: boolean; onClose: () => void }`
- **Purpose**: Dropdown showing recent searches with bookmark toggle and delete. Shows when search input is focused and query < 3 chars.
- **API calls**: `getSearchHistory()`, `toggleSearchBookmark()`, `deleteSearchHistoryEntry()`
- **Used by**: Search page

#### `SectionFilter` (`src/components/section-filter.tsx`)
- **DEPRECATED** -- superseded by inline pill tabs in search page

### Case Detail Components

#### `CaseTimeline` (`src/components/case-timeline.tsx`)
- **Props**: `{ caseId: string }`
- **Purpose**: Shows procedural history timeline + citation evolution (forward/backward) for a case
- **API calls**: `getCaseTimeline(caseId)`, `getCitationEvolution(caseId, direction)`
- **Used by**: Case detail page (Timeline tab)

#### `AudioPlayer` (`src/components/audio-player.tsx`)
- **Props**: `{ caseId: string }`
- **Purpose**: Audio digest player with language selector (22 Indian languages). Shows generate button if digest not available.
- **API calls**: `getAudioStatus(caseId)`, `generateAudioDigest(caseId, language)`, `getAudioUrl(caseId, language)`
- **Used by**: Case detail page

#### `PdfViewer` (`src/components/pdf-viewer.tsx`)
- **Props**: `{ file: string; onError: () => void }`
- **Purpose**: Renders PDF using react-pdf with self-hosted worker (`/pdf.worker.min.mjs`)
- **API calls**: none (receives URL)
- **Used by**: Footnote preview panel

### Agent Components

#### `AgentHubCard` (`src/components/agent-hub-card.tsx`)
- **Props**: `{ title: string; description: string; icon: ReactNode; href: string; badge?: string }`
- **Purpose**: Card linking to an agent workspace from the `/agents` hub page
- **API calls**: none
- **Used by**: Agents hub page

#### `AgentStepTimeline` (`src/components/agent-step-timeline.tsx`)
- **Props**: `{ steps: AgentStep[] }`
- **Purpose**: Vertical timeline showing agent pipeline progress. Maps internal node names to human-readable labels (e.g., `classify` -> "Understanding your question"). Status icons: pending (circle), active (spinner), completed (check), error (alert).
- **API calls**: none
- **Used by**: Research, case-prep, strategy, drafting agent pages

#### `AgentCheckpointPrompt` (`src/components/agent-checkpoint-prompt.tsx`)
- **Props**: `{ question: string; context?: Record<string, unknown>; onSubmit: (input: string) => void; disabled?: boolean; error?: string | null; onClearError?: () => void; suggestions?: string[] }`
- **Purpose**: HITL (human-in-the-loop) checkpoint prompt. Shows the agent's question, auto-infers contextual suggestion chips (e.g., "Looks good, proceed"), allows free-text response.
- **API calls**: none
- **Used by**: All agent pages at checkpoint steps

#### `AgentMemoViewer` (`src/components/agent-memo-viewer.tsx`)
- **Props**: `{ content: string; confidence?: number; maxFootnote?: number; footnotes?: ResearchFootnote[]; executionId?: string; onFootnoteClick?: (num: number) => void; onExportClick?: (format) => void }`
- **Purpose**: Rich markdown renderer for research memos. Features: inline footnote references with hover cards showing verification status (verified_pg/ik/neo4j, unverified, removed, flagged), confidence breakdown badges, copy/share/export buttons, memo sharing (create/revoke share link), editable title.
- **API calls**: `createMemoShare()`, `getMemoShareStatus()`, `revokeMemoShare()`, `exportResearchMemo()`
- **Used by**: Research agent, case-prep agent, history page, shared memo page

#### `PlanReview` (`src/components/plan-review.tsx`)
- **Props**: Plan data with research steps, sub-queries, classification details
- **Purpose**: Allows user to review and modify the research plan at a checkpoint -- toggle steps on/off, delete steps, add feedback
- **API calls**: none
- **Used by**: Research agent page (checkpoint_plan step)

#### `ResearchProcessPanel` (`src/components/research-process-panel.tsx`)
- **Props**: `{ events: ProcessEvent[]; isRunning: boolean }`
- **Purpose**: Collapsible log showing real-time process events (searching, found, evaluating, reflection, gap analysis, drafting, verification). Each event type has a distinct icon and color.
- **API calls**: none
- **Used by**: Research agent page

#### `ResearchProgressBar` (`src/components/research-progress-bar.tsx`)
- **Props**: `{ events: ProcessEvent[]; isRunning: boolean }`
- **Purpose**: 5-stage horizontal progress bar (Understand -> Decompose -> Investigate -> Challenge -> Synthesize) with weighted completion percentages
- **API calls**: none
- **Used by**: Research agent page

#### `FootnotesPanel` (`src/components/footnotes-panel.tsx`)
- **Props**: `{ footnotes: ResearchFootnote[]; selectedFootnoteNumber: number | null; onFootnoteSelect: (num | null) => void; isOpen: boolean; onToggle: () => void }`
- **Purpose**: Slide-out panel listing all footnotes with tabs (All/Cited/Unused), search, and detail preview
- **API calls**: none
- **Used by**: Research agent page

#### `FootnoteListItem` (`src/components/footnote-list-item.tsx`)
- **Props**: `{ footnote: ResearchFootnote; isSelected: boolean; onClick: () => void }`
- **Purpose**: Single row in the footnotes panel with source type icon (Case/Web/Statute/Constitution), verification badge
- **API calls**: none

#### `FootnotePreview` (`src/components/footnote-preview.tsx`)
- **Props**: `{ footnote: ResearchFootnote }`
- **Purpose**: Expanded footnote detail: excerpt, verification status, case metadata, PDF link, embedded PDF viewer
- **API calls**: `getCasePdfUrl()`

#### `VerificationBanner` (`src/components/verification-banner.tsx`)
- **Props**: `{ banner: string; citationsVerified: number; citationsRemoved: number }`
- **Purpose**: Green (all clean) or amber (some removed) banner showing citation verification results
- **API calls**: none

#### `ResearchAuditTrail` (`src/components/research-audit-trail.tsx`)
- **Props**: `{ audit: ResearchAudit }`
- **Purpose**: Collapsible stats panel: sources searched, cited, unused, searches executed, refinement rounds, deep reads, strategy pivots
- **API calls**: none

#### `DraftSectionViewer` (`src/components/draft-section-viewer.tsx`)
- **Props**: `{ sections: Record<string, string>; onRevise?: (sectionName, feedback) => void; onExport?: (format) => void; disabled?: boolean }`
- **Purpose**: Expandable section-by-section draft viewer with inline revision feedback and export buttons
- **API calls**: none (callbacks for export)
- **Used by**: Drafting agent page

#### `AgentSessionSidebar` (`src/components/agents/AgentSessionSidebar.tsx`)
- **Props**: `{ sessions: AgentSession[]; activeSessionId: string | null; onSelectSession: (id) => void; onNewSession: () => void; onDeleteSession: (id) => void; loading: boolean }`
- **Purpose**: Sidebar listing agent conversation sessions with relative timestamps, delete buttons, "New Session" action
- **API calls**: none (callbacks)
- **Used by**: Research agent page

#### `AgentFollowUpThread` (`src/components/agents/AgentFollowUpThread.tsx`)
- **Props**: `{ messages: AgentSessionMessage[]; isStreaming: boolean; streamingContent: string }`
- **Purpose**: Threaded conversation view showing user queries and assistant responses (markdown rendered) within an agent session
- **API calls**: none

#### `AgentFollowUpInput` (`src/components/agents/AgentFollowUpInput.tsx`)
- **Props**: `{ onSend: (message) => void; disabled: boolean; placeholder?: string }`
- **Purpose**: Auto-resizing textarea with send button for follow-up messages. Min 5 chars, max height 120px.
- **API calls**: none

### Analytics Components

#### `JudgePredictionCard` (`src/components/judge-prediction-card.tsx`)
- **Props**: Judge name (uses internal state to fetch prediction)
- **Purpose**: Outcome prediction: select case type and acts, shows predicted outcome with probabilities, confidence, sample size, contributing factors, caveats
- **API calls**: `getJudgePrediction()`
- **Used by**: Judge profile page

### Utility Components

#### `ProcessingStatus` (`src/components/processing-status.tsx`)
- **Props**: `{ status: string; step: string | null; error?: string | null }`
- **Purpose**: Step-by-step processing indicator for document uploads (extracting -> analyzing -> searching -> generating -> completed)
- **API calls**: none
- **Used by**: Document detail page

#### `FileUpload` (`src/components/file-upload.tsx`)
- **Props**: `{ onFileSelected: (file: File) => void; disabled?: boolean }`
- **Purpose**: Drag-and-drop PDF upload zone. Validates: PDF only, max 50MB.
- **API calls**: none (callback)
- **Used by**: Upload page

---

## 5. API Client

### Architecture (`src/lib/api.ts`)
All API communication flows through a centralized client module. Key design decisions:

**Base URL**: `NEXT_PUBLIC_API_URL` env var, defaults to `/api/v1` (proxied to backend via Next.js rewrites in dev).

**Core `apiFetch<T>()` function**:
- Generic typed wrapper around `fetch()`
- Adds `Authorization: Bearer {token}` header if token exists
- 30-second timeout via `AbortController`
- Proactively refreshes token before each request if expired (`ensureFreshToken()`)
- On 401: attempts token refresh, retries original request, or emits `sessionExpired` event
- Parses JSON response, handles 204 (no content)
- Returns typed response or throws `ApiError(status, code, message)`

**Error extraction**: Handles 3 backend error formats:
1. `{ error: "message" }` -- custom handlers
2. `{ detail: "message" }` -- FastAPI HTTPException
3. `{ detail: [{msg: "..."}] }` -- Pydantic validation (422)

### API Endpoints Called

| Function | Method | Endpoint | Used By |
|---|---|---|---|
| `login()` | POST | `/auth/login` | Login page |
| `register()` | POST | `/auth/register` | Register page |
| `logout()` | POST | `/auth/logout` | Header |
| `tryRefreshToken()` | POST | `/auth/refresh` | Internal (auto-refresh) |
| `search()` | GET | `/search?q=...&court=...&...` | Search page |
| `searchFacets()` | GET | `/search/facets` | Search page |
| `searchSuggest()` | GET | `/search/suggest?q=...&limit=...` | Search page typeahead |
| `getCase()` | GET | `/cases/{id}` | Case detail page |
| `getCaseCitations()` | GET | `/cases/{id}/citations` | Case detail page |
| `getCaseCitedBy()` | GET | `/cases/{id}/cited-by` | Case detail page |
| `getCaseSimilar()` | GET | `/cases/{id}/similar?limit=5` | Case detail page |
| `getCasePdfUrl()` | -- | `/cases/{id}/pdf` (URL builder) | Case detail, footnote preview |
| `getCaseSummary()` | GET | `/cases/{id}/summary?language=hi` | Case detail (Hindi toggle) |
| `getCaseTimeline()` | GET | `/cases/{id}/timeline` | CaseTimeline component |
| `getCitationEvolution()` | GET | `/graph/{id}/evolution?direction=forward` | CaseTimeline component |
| `createChatSession()` | POST (SSE) | `/chat` | Chat page |
| `sendChatMessage()` | POST (SSE) | `/chat/{sessionId}/message` | Chat page |
| `getChatSessions()` | GET | `/chat/sessions` | Chat page sidebar |
| `getChatHistory()` | GET | `/chat/{sessionId}/history` | Chat page |
| `deleteChatSession()` | DELETE | `/chat/{sessionId}` | Chat page |
| `getGraphNeighborhood()` | GET | `/graph/{id}/neighborhood?depth=1` | Case detail, graph page |
| `getGraphChain()` | GET | `/graph/{id}/chain?max_depth=3` | Graph page |
| `getGraphAuthorities()` | GET | `/graph/{id}/authorities?limit=20` | Graph page |
| `getGraphStats()` | GET | `/graph/stats` | Graph page |
| `getJudges()` | GET | `/judges?search=...&page=...` | Judges page |
| `getJudgeProfile()` | GET | `/judges/{name}` | Judge profile page |
| `getJudgeCases()` | GET | `/judges/{name}/cases?...` | Judge profile page |
| `compareJudges()` | GET | `/judges/compare?names=...` | Judge compare page |
| `getJudgePrediction()` | GET | `/judges/predict?judges=...&case_type=...` | JudgePredictionCard |
| `getCourtStats()` | GET | `/courts/{court}/stats` | Courts page |
| `searchCounsel()` | GET | `/counsel?search=...&page=...` | Counsel page |
| `getCounselProfile()` | GET | `/counsel/{name}` | Counsel profile page |
| `getCounselCases()` | GET | `/counsel/{name}/cases?page=...` | Counsel profile page |
| `getCounselMatchups()` | GET | `/counsel/{name}/matchups?limit=10` | Counsel profile page |
| `uploadDocument()` | POST | `/documents/upload` (FormData) | Upload page |
| `getDocuments()` | GET | `/documents?page=...` | Documents page |
| `getDocument()` | GET | `/documents/{id}` | Document detail page |
| `deleteDocument()` | DELETE | `/documents/{id}` | Document detail page |
| `generateAudioDigest()` | POST | `/cases/{id}/audio/generate?language=en` | AudioPlayer |
| `getAudioStatus()` | GET | `/cases/{id}/audio/status` | AudioPlayer |
| `getAudioUrl()` | -- | `/cases/{id}/audio?language=en` (URL builder) | AudioPlayer |
| `runResearchAgent()` | POST (SSE) | `/agents/research/run` | Research agent page |
| `runCasePrepAgent()` | POST (SSE) | `/agents/case_prep/run` | Case-prep agent page |
| `runStrategyAgent()` | POST (SSE) | `/agents/strategy/run` | Strategy agent page |
| `runDraftingAgent()` | POST (SSE) | `/agents/drafting/run` | Drafting agent page |
| `runDraftingFromResearch()` | POST (SSE) | `/agents/drafting/from-research` | Drafting agent page |
| `resumeAgentExecution()` | POST (SSE) | `/agents/executions/{id}/resume` | All agent pages (HITL) |
| `getAgentExecutions()` | GET | `/agents/executions?page=...` | History page |
| `getAgentExecution()` | GET | `/agents/executions/{id}` | History page |
| `cancelExecution()` | DELETE | `/agents/executions/{id}` | History page |
| `exportResearchMemo()` | GET | `/agents/research/export/{id}?format=docx` | History page, memo viewer |
| `getDraftingTemplates()` | GET | `/agents/drafting/templates` | Drafting agent page |
| `exportDraft()` | POST | `/agents/drafting/export/{id}?format=docx` | Drafting agent page |
| `createAgentSession()` | POST (SSE) | `/agents/{type}/session` | Research agent page |
| `sendAgentFollowUp()` | POST (SSE) | `/agents/sessions/{id}/follow-up` | Research agent page |
| `getAgentSessions()` | GET | `/agents/sessions?agent_type=...` | Research agent sidebar, history page |
| `getAgentSessionMessages()` | GET | `/agents/sessions/{id}/messages` | Research agent page |
| `getAgentSessionDetail()` | GET | `/agents/sessions/{id}` | Research agent page |
| `deleteAgentSession()` | DELETE | `/agents/sessions/{id}` | Research agent sidebar, history page |
| `getSearchHistory()` | GET | `/search/history?page=...` | SearchHistoryDropdown |
| `toggleSearchBookmark()` | POST | `/search/history/{id}/bookmark` | SearchHistoryDropdown |
| `deleteSearchHistoryEntry()` | DELETE | `/search/history/{id}` | SearchHistoryDropdown |
| `createMemoShare()` | POST | `/agents/research/{id}/share` | AgentMemoViewer |
| `getMemoShareStatus()` | GET | `/agents/research/{id}/share` | AgentMemoViewer |
| `revokeMemoShare()` | DELETE | `/agents/research/{id}/share` | AgentMemoViewer |
| `getSharedMemo()` | GET | `/shared/{token}` | Shared memo page (no auth) |
| `getUserPreferences()` | GET | `/users/me/preferences` | Search page (filter defaults) |
| `updateUserPreferences()` | PUT | `/users/me/preferences` | (not wired to UI yet) |
| `refreshUserPreferences()` | POST | `/users/me/preferences/refresh` | (not wired to UI yet) |

---

## 6. Authentication Flow

### Token Strategy
- **Access token**: Held in module-scoped variable (`let accessToken: string | null`). NEVER stored in localStorage. Lost on page reload -- restored via refresh.
- **Refresh token**: Stored in httpOnly cookie (set by backend). JS cannot read it. A `smriti_refresh_fallback` localStorage key exists as fallback for dev proxy issues.

### Login Flow
1. User submits email + password on `/login`
2. `login()` POSTs to `/auth/login` with `credentials: "include"` (so browser stores httpOnly cookie)
3. Backend returns `{ access_token, expires_in, refresh_token? }`
4. `setTokens(access_token)` stores in memory
5. If `refresh_token` present, stored in `smriti_refresh_fallback` localStorage
6. `AuthProvider` sets `isAuthenticated = true`
7. Router pushes to `/search`

### Registration Flow
Same as login but POSTs to `/auth/register` with additional `name` and `consent_given` fields.

### Token Refresh
- **Proactive**: Before every `apiFetch()` call, `ensureFreshToken()` checks if token expires within 60 seconds. If so, calls `tryRefresh()`.
- **Reactive**: On 401 response, attempts `tryRefresh()`. If successful, retries the original request with new token. If failed, clears tokens and emits `sessionExpired`.
- **Mutex**: `refreshPromise` prevents concurrent refresh requests (all callers wait on the same promise).
- **Network error handling**: `TypeError` from fetch during refresh does NOT clear tokens (transient network issue), only server rejection does.

### Page Load Restoration
1. `AuthProvider.init()` runs on mount
2. Calls `loadTokens()` (migrates legacy localStorage tokens)
3. Checks if access token exists and is not expired
4. If expired/missing, calls `tryRefreshToken()` (uses httpOnly cookie)
5. Sets `isAuthenticated` accordingly

### Session Expiration
- `onSessionExpired()` event bus lets any component react to auth failures
- `AuthProvider` subscribes and sets `isAuthenticated = false` + shows error
- Protected pages check `if (!authLoading && !isAuthenticated) router.push("/login")`

### Logout
1. Best-effort POST to `/auth/logout` (server revokes refresh token)
2. `clearTokens()` clears memory variable and legacy localStorage
3. `AuthProvider` sets `isAuthenticated = false`

---

## 7. State Management

### No global state library
The app uses React Context for auth and local component state (useState/useRef) for everything else. No Redux, Zustand, or React Query.

### AuthProvider (Context)
- Single context: `AuthContext` via `src/lib/auth-context.tsx`
- Provides: `isAuthenticated`, `isLoading`, `authError`, `login()`, `register()`, `logout()`, `clearAuthError()`
- Wraps entire app via `<Providers>` in layout

### Local State Patterns
Each page manages its own state. Common patterns:

**Search page state**: query, results, facets, filters (court, yearFrom, yearTo, caseType, sectionFilter), suggestions, pagination, loading, error -- all via `useState()`

**Chat page state**: sessions list, active session ID, messages array, input text, streaming flag, abort controller ref -- all local

**Agent page state**: Complex local state including query, running status, execution ID, steps array, checkpoint data, memo content, streaming memo, confidence, footnotes, research audit, process events, session management -- all via `useState()` and `useRef()`

**Data fetching**: Manual `useEffect()` + async functions. No SWR, no React Query. Abort controllers managed via `useRef()`.

---

## 8. Real-time Features

### SSE (Server-Sent Events) Streaming

All real-time communication uses SSE via the `_streamSSE<T>()` helper in `api.ts`:

**Mechanism**:
1. POST request to SSE endpoint (e.g., `/agents/research/run`)
2. Reads response body as `ReadableStream` via `getReader()`
3. Decodes chunks with `TextDecoder`, splits on newlines
4. Parses `data: {JSON}\n\n` SSE format
5. Calls `onEvent(event)` callback for each parsed event
6. Returns `AbortController` so caller can cancel

**Event Types**:

*Chat events* (`StreamEvent`):
- `session` -- new session created (includes `session_id`, `title`)
- `chunk` -- streaming text content
- `source` -- cited case reference
- `disclaimer` -- legal disclaimer text
- `done` -- stream complete

*Agent events* (`AgentStreamEvent`):
- `status` -- pipeline step change
- `progress` -- progress update with label
- `checkpoint` -- HITL prompt (pauses stream)
- `memo` / `memo_stream` -- research memo content (final / streaming chunks)
- `done` -- execution complete (includes `data` with confidence, footnotes, audit)
- `error` -- execution failed (includes `recoverable` flag)
- `plan` / `searching` / `found` / `evaluating` / `reflection` / `gap` / `drafting` / `verification` / `quality` -- process events for research panel
- `session` -- session created (includes `session_id`)

**Stream Safety**:
- `receivedDoneEvent` flag tracks if stream terminated properly
- If stream ends without done/error/checkpoint event AND not user-aborted, calls `onError("Connection lost")`
- Reader cleanup: `reader.cancel()` + `reader.releaseLock()` in finally block
- Auth: proactive token refresh before streaming, 401 retry with new token

**Chat Streaming Optimization**:
- Content accumulated in `streamingContentRef` (not state)
- Flushed to React state via `setInterval(100ms)` -- reduces re-renders from per-chunk to ~10/sec
- Final flush on `done` event

**Agent Memo Typewriter Effect**:
- Research agent uses `requestAnimationFrame` tick loop
- Chunks queued in `streamQueueRef`, rendered 30 chars per frame
- Creates smooth typewriter animation for memo text

---

## 9. i18n (Internationalization)

### Setup
- **Library**: next-intl v4.8.3
- **Supported locales**: English (`en`), Hindi (`hi`)
- **Locale detection**: Cookie-based (`locale` cookie), defaults to `en`
- **Config**: `src/i18n/request.ts` reads cookie at request time, loads matching JSON

### Message Files
- `src/messages/en.json` -- English translations
- `src/messages/hi.json` -- Hindi translations

### Namespace Structure
- `common`: shared labels (search, login, logout, loading, etc.)
- `header`: navigation labels and search placeholder
- `footer`: disclaimer, data source, tagline
- `agents`: hub page titles and descriptions for each agent
- `cookieConsent`: consent banner text

### Usage Pattern
- Server components: `getLocale()` + `getMessages()` in root layout
- Client components: `useTranslations("namespace")` hook, e.g. `const t = useTranslations("header"); t("chat")`
- Language toggle: `LanguageToggle` component in Header sets cookie + reloads page

### Hindi Translation of Content
- Case detail page: toggles ratio decidendi between English and Hindi via `getCaseSummary(id, "hi")` API call
- Search: `language` parameter passed to search API

---

## 10. Build & Deploy

### Dev Server
```bash
npm run dev     # next dev (Turbopack)
```
- API proxy: Next.js rewrites `/api/v1/*` to `BACKEND_URL` (default `http://127.0.0.1:8000/api/v1`)
- Dev CSP: `unsafe-eval` + `unsafe-inline` for script-src, WebSocket allowed for HMR

### Build
```bash
npm run build   # next build
```
- Output: `standalone` mode (self-contained Node.js server, no `node_modules` needed)
- Webpack config: stubs `canvas` for react-pdf SSR, transpiles `react-pdf` package

### Test
```bash
npm run test        # vitest run
npm run test:watch  # vitest (watch mode)
```
- Test framework: Vitest (NOT Jest)
- DOM: jsdom
- Testing utilities: @testing-library/react, @testing-library/user-event, @testing-library/jest-dom

### Deployment (Google Cloud Run)
- Standalone output deployed as Docker container
- Backend URL configured via `BACKEND_URL` env var
- Security headers set in `next.config.ts` (X-Frame-Options, HSTS, etc.)
- CSP set per-request in middleware with nonce support

### Middleware (`src/middleware.ts`)
- Runs on every request (except static files and prefetches)
- Generates per-request nonce for CSP
- Production CSP: `script-src 'self' 'nonce-{nonce}' 'strict-dynamic'`
- Dev CSP: `unsafe-eval` + `unsafe-inline` (required for Next.js HMR)
- `img-src`: allows `data:`, `blob:`, `https://storage.googleapis.com` (GCS)
- `worker-src`: allows `blob:` (react-pdf worker)
- `connect-src`: `'self'` + backend URL
- `frame-ancestors: 'none'` (prevents embedding)

---

## 11. UI Component Library (shadcn/ui)

All components in `src/components/ui/` are shadcn/ui primitives built on Radix UI:

| Component | File | Radix Primitive | Purpose |
|---|---|---|---|
| `Button` | `ui/button.tsx` | -- | Primary interactive element, variants: default, outline, ghost, destructive |
| `Input` | `ui/input.tsx` | -- | Text input field |
| `Textarea` | `ui/textarea.tsx` | -- | Multi-line text input |
| `Card` | `ui/card.tsx` | -- | Container with CardHeader, CardTitle, CardDescription, CardContent |
| `Badge` | `ui/badge.tsx` | -- | Status/label badge, variants: default, secondary, destructive, outline |
| `Tabs` | `ui/tabs.tsx` | `@radix-ui/react-tabs` | Tab navigation (TabsList, TabsTrigger, TabsContent) |
| `Select` | `ui/select.tsx` | radix-ui | Dropdown select (SelectTrigger, SelectContent, SelectItem, SelectValue) |
| `Separator` | `ui/separator.tsx` | `@radix-ui/react-scroll-area` | Horizontal/vertical divider |
| `ScrollArea` | `ui/scroll-area.tsx` | `@radix-ui/react-scroll-area` | Scrollable container with custom scrollbar |
| `Sheet` | `ui/sheet.tsx` | `@radix-ui/react-dialog` | Slide-out panel (used for mobile sidebars) |
| `Tooltip` | `ui/tooltip.tsx` | `@radix-ui/react-tooltip` | Hover tooltip |
| `HoverCard` | `ui/hover-card.tsx` | -- | Rich hover preview card (footnotes) |
| `DropdownMenu` | `ui/dropdown-menu.tsx` | -- | Dropdown menu (export options, etc.) |

### Styling Approach
- `class-variance-authority` (CVA) for component variants
- `clsx` + `tailwind-merge` via `cn()` utility for conditional class merging
- All components use Tailwind CSS v4 with CSS custom properties from `globals.css`

---

## 12. Error Handling

### Layers of Error Handling

**1. Global Error Boundary** (`src/components/error-boundary.tsx`)
- React class component wrapping entire app (in root layout)
- Catches unhandled rendering errors
- Shows: "Something went wrong" with "Try again" button
- Logs error + errorInfo to console

**2. Next.js Route Error Pages**
Four route-level `error.tsx` files catch errors during page rendering/data fetching:
- `/search/error.tsx`: "Search failed"
- `/case/[id]/error.tsx`: "Failed to load case"
- `/agents/research/error.tsx`: "Research agent error"
- `/judge/[name]/error.tsx`: "Failed to load judge profile"

All follow the same pattern: show error message + "Try again" button that calls `reset()`.

**3. Next.js Route Loading Pages**
Three `loading.tsx` files show spinners during route transitions:
- `/search/loading.tsx`
- `/case/[id]/loading.tsx`
- `/judge/[name]/loading.tsx`

**4. API-Level Error Handling** (`src/lib/api.ts`)
- `ApiError` class with `status`, `code`, and `message` properties
- `extractErrorMessage()` handles FastAPI, Pydantic, and custom error response formats
- Network errors during auth refresh are distinguished from server rejections
- Session expiration triggers `emitSessionExpired()` event bus

**5. Component-Level Error Handling**
Every page that makes API calls has local error state:
- `const [error, setError] = useState<string | null>(null)`
- Errors displayed as red text with retry buttons
- Chat page: dedicated `networkError` state for connection issues with dismiss button
- Agent pages: distinguish between recoverable errors (show retry) and fatal errors
- Search page: `facetsError` tracked separately from search errors
- All catch blocks surface errors to UI (hardened in Silent Failure Audit)

**6. Streaming Error Handling**
- `_streamSSE()` detects unexpected stream termination (`receivedDoneEvent` flag)
- If stream ends without done/error/checkpoint event, calls `onError("Connection lost")`
- Chat streaming: errors update the last assistant message with error text
- Agent streaming: errors set `error` state and stop running state
- AbortError from user cancellation is silently ignored

**7. Offline Detection**
- Research agent page monitors `navigator.onLine` + `online`/`offline` events
- Sets `isOffline` state to show appropriate UI warnings

**8. Input Validation**
- Login/Register: client-side email regex + password length validation with field-level errors
- File upload: PDF-only + 50MB max size validation
- Search: 500 char max length
- Chat: 5000 char max length
- Agent follow-up: 5 char minimum
