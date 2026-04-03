# Backend Reference

This document is a complete reference for the Smriti backend. It covers every endpoint, database table, interface, and security mechanism. Everything described here is sourced from the codebase audit performed on 2026-04-03.

---

## 1. Application Architecture

### Framework and Entry Point

- **Framework**: FastAPI (Python 3.12), fully async
- **Entry point**: `backend/app/main.py`
- **App instance**: `FastAPI(title="smriti", version="0.1.0")`
- **API docs**: Swagger UI at `/docs` and ReDoc at `/redoc` -- only enabled when `APP_DEBUG=true`
- **Config**: `pydantic-settings` (`BaseSettings`) loading from `.env` file, case-insensitive, extras ignored (`backend/app/core/config.py`)

### Startup Sequence (Lifespan)

Managed via `@asynccontextmanager async def lifespan(app)` in `backend/app/main.py`:

1. Configure structured logging (`configure_logging()`)
2. Initialize Sentry (if `SENTRY_DSN` set) with FastAPI + SQLAlchemy integrations; strips `authorization`, `cookie`, `x-csrf-token` headers before sending
3. Run Alembic migrations (`alembic upgrade head`) -- production only
4. Startup health validation (non-blocking, logs warnings): PostgreSQL, Redis, Pinecone (dimension=1536 check), Gemini API key
5. Fire-and-forget task: clean up expired user-uploaded PDFs (DPDP retention enforcement)

### Shutdown Sequence

All steps have 10-second timeout guards:

1. Dispose SQLAlchemy async engine
2. Close Redis connection
3. Close cached provider connections (graph store, reranker, IK client, web search) + clear LRU caches

### Middleware Stack

Added in reverse order (last added = outermost). Execution flows from outermost to innermost:

| Order | Middleware | Purpose |
|-------|-----------|---------|
| 1 | `TrustedHostMiddleware` | Production only. Rejects requests with non-allowed Host headers |
| 2 | `SecurityHeadersMiddleware` | Adds `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, HSTS (1 year), CSP, `Cache-Control: no-store` for `/api/` paths |
| 3 | `RequestSizeLimitMiddleware` | Rejects requests >10 MB (via Content-Length header check) |
| 4 | `CORSMiddleware` | Configurable origins (`CORS_ORIGINS` comma-separated), credentials allowed, standard methods + `X-CSRF-Token` header |
| 5 | `RequestIDMiddleware` | Assigns UUID request ID (from `X-Request-ID` header or generated), sets `contextvars`, logs `METHOD PATH STATUS DURATIONms`, returns `X-Request-ID` response header |

### Global Exception Handlers

Registered in `backend/app/main.py`:

| Exception | HTTP Status | Response Code |
|-----------|-------------|---------------|
| `AuthenticationError` | 401 | `UNAUTHORIZED` |
| `AuthorizationError` | 403 | `FORBIDDEN` |
| `RateLimitExceededError` | 429 | `RATE_LIMITED` (includes `Retry-After` header) |
| Unhandled `Exception` | 500 | `INTERNAL_ERROR` (captured to Sentry) |

### Router Registration

Each router is registered in `backend/app/main.py`:

| Router | Prefix | Tags |
|--------|--------|------|
| health | (none) | health |
| auth | `/api/v1/auth` | auth |
| cases | `/api/v1/cases` | cases |
| ingest | `/api/v1/ingest` | ingest |
| search | `/api/v1/search` | search |
| chat | `/api/v1/chat` | chat |
| graph | `/api/v1/graph` | graph |
| counsel | `/api/v1` | counsel |
| judges | `/api/v1` | judges |
| documents | `/api/v1/documents` | documents |
| audio | `/api/v1/cases` | audio |
| agents | `/api/v1/agents` | agents |
| dpdp | `/api/v1/dpdp` | dpdp |
| admin_review | `/api/v1/admin/review` | admin |
| admin_corrections | `/api/v1/admin/corrections` | admin |
| data_quality | `/api/v1/admin/data-quality` | admin |
| preferences | `/api/v1` | preferences |
| sharing | `/api/v1` | sharing |

### Dependency Injection

All external services are created via `@lru_cache` singleton factory functions in `backend/app/core/dependencies.py`:

| Factory Function | Returns (Protocol) | Concrete Implementation |
|------------------|-------------------|------------------------|
| `get_llm()` | `LLMProvider` | `GeminiLLM` |
| `get_flash_llm()` | `LLMProvider` | `GeminiLLM(model=flash)` |
| `get_embedder()` | `EmbeddingProvider` | `GeminiEmbedder` |
| `get_vector_store()` | `VectorStore` | `PineconeStore` or `PgvectorStore` |
| `get_graph_store()` | `GraphStore` | `Neo4jGraph` or `PgGraphStore` |
| `get_reranker()` | `Reranker` | `CohereReranker` |
| `get_translator()` | `TranslationProvider` | `GeminiTranslator` |
| `get_storage()` | `FileStorage` | `LocalStorage` or `GCSStorage` |
| `get_tts()` | `TTSProvider` | `SarvamTTS` or `MockTTS` |
| `get_checkpointer()` | LangGraph checkpointer | `AsyncPostgresSaver` (prod) / `MemorySaver` (dev) |
| `get_web_search()` | `WebSearchProvider` | `TavilySearchClient` |
| `get_ik_client()` | `ExternalDocProvider` | `IndianKanoonClient` |

Circuit breakers are configured for: Pinecone (5 failures, 30s cooldown), Neo4j (5 failures, 60s cooldown), Cohere (3 failures, 30s cooldown).

---

## 2. API Reference

### Auth (`backend/app/api/routes/auth.py`)

**Prefix:** `/api/v1/auth`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| POST | `/register` | None | 5/min | Register user with DPDP consent, auto-login, returns JWT pair |
| POST | `/login` | None | 15/min | Authenticate, account lockout (10 attempts / 5min lock), returns JWT pair |
| POST | `/refresh` | None | 10/min | Refresh access token (rotation: old refresh token revoked). Reads from httpOnly cookie or body |
| POST | `/logout` | JWT | 20/min | Revoke access + refresh tokens, clear httpOnly cookie |
| DELETE | `/me` | JWT | 3/hour | Delete account and all personal data (DPDP Section 12). Cascade deletes: agent_executions, chat messages/sessions, documents (storage cleanup), consents. Deactivates user, cleans Pinecone/Neo4j/Redis |

**Key schemas:**

- `RegisterRequest`: `email` (EmailStr), `password` (8-128 chars, must have uppercase/lowercase/digit), `name?`, `consent_given` (bool, required), `consent_version` (default "1.0")
- `LoginRequest`: `email`, `password`
- `TokenResponse`: `access_token`, `token_type="bearer"`, `expires_in` (seconds), `refresh_token`
- Refresh token set as httpOnly cookie `smriti_refresh` on path `/api/v1/auth`, max_age=7 days

### Search (`backend/app/api/routes/search.py`)

**Prefix:** `/api/v1/search`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/` | Optional | 30/min | Hybrid search: LLM query understanding, vector+FTS, RRF fusion, Cohere rerank. Supports Hindi translation. 15s timeout. Persists search history for authenticated users |
| GET | `/suggest` | None | 60/min | Auto-complete on case titles + citations (ILIKE). Cached 15min |
| GET | `/facets` | None | 30/min | Distinct filter values (courts, case_types, bench_types, year range). Cached 1 hour |
| GET | `/history` | JWT | 60/min | Paginated user search history (sorted by bookmarked, then recent) |
| POST | `/history/{id}/bookmark` | JWT | 30/min | Toggle bookmark on search history entry |
| DELETE | `/history/{id}` | JWT | 30/min | Delete a search history entry |

**Query params:** `q` (1-2000 chars), `court`, `year_from`, `year_to`, `case_type`, `bench_type`, `judge`, `act`, `section`, `page`, `page_size` (1-50), `language` (en|hi)

**Response:** `results[]` (case_id, score, title, citation, court, year, date, case_type, judge, snippet, bench_type, equivalent_citations, treatment_warning), `total_count`, `page`, `page_size`, `query_understanding` (intent, original_query, expanded_query, search_strategy, filters, entities), `facets`

### Cases (`backend/app/api/routes/cases.py`)

**Prefix:** `/api/v1/cases`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/{case_id}` | None | 60/min | Full case metadata + judgment text split into sections (FACTS, ISSUES, etc.) |
| GET | `/{case_id}/summary` | JWT | 30/min | Case summary (ratio_decidendi), optional Hindi translation |
| GET | `/{case_id}/pdf` | None | 30/min | Serve PDF from storage (inline Content-Disposition) |
| GET | `/{case_id}/citations` | None | 60/min | Outgoing CITES edges from Neo4j, enriched with PG metadata |
| GET | `/{case_id}/cited-by` | None | 60/min | Incoming CITES edges from Neo4j, enriched with PG metadata |
| GET | `/{case_id}/similar` | Optional | 20/min | Semantically similar cases via Pinecone vector search on ratio_decidendi |
| GET | `/{case_id}/timeline` | Optional | 30/min | Procedural timeline (filing, interim orders, judgment) |

### Chat (`backend/app/api/routes/chat.py`)

**Prefix:** `/api/v1/chat`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| POST | `/` | JWT | 20/min | Start new RAG chat session, stream SSE response (5min max). Prompt injection detection |
| POST | `/{session_id}/message` | JWT | 20/min | Continue conversation in existing session (IDOR check), stream SSE |
| GET | `/sessions` | JWT | 60/min | List user's chat sessions, paginated (with message counts) |
| GET | `/{session_id}/history` | JWT | 60/min | Full message history for session (decrypts content via `safe_decrypt`) |
| DELETE | `/{session_id}` | JWT | 30/min | Delete session + all messages (CASCADE). Audit logged |

**SSE event format:** `data: {"type": "...", ...}\n\n`

### Agents (`backend/app/api/routes/agents.py`)

**Prefix:** `/api/v1/agents`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| POST | `/{agent_type}/run` | JWT | 10/min | Start agent execution (research/case_prep/strategy/drafting), SSE stream. Semantic + hash cache check for research. 10min timeout. 15s keepalive heartbeats |
| GET | `/executions` | JWT | 60/min | List user's agent executions, paginated |
| GET | `/executions/{id}` | JWT | 60/min | Get execution detail (IDOR check) |
| POST | `/executions/{id}/resume` | JWT | 10/min | Resume HITL checkpoint with user input. Validates checkpoint state exists. Atomic status transition |
| DELETE | `/executions/{id}` | JWT | 30/min | Cancel running/waiting execution |
| GET | `/drafting/templates` | JWT | 60/min | List available document templates grouped by category |
| POST | `/drafting/export/{id}` | JWT | 20/min | Export completed draft as DOCX or PDF |
| POST | `/drafting/from-research` | JWT | 10/min | Start drafting from completed research (pre-populates citations) |
| POST | `/drafting/from-document` | JWT | 10/min | Upload opposing doc, auto-detect response type, generate draft |
| GET | `/drafting/versions/{id}` | JWT | 30/min | Revision history for drafting execution |
| POST | `/research/revise-section/{id}` | JWT | 10/min | Revise a single section of completed research memo, SSE stream |
| GET | `/research/export/{id}` | JWT | 20/min | Export research memo as DOCX, PDF, or Markdown |
| POST | `/{agent_type}/session` | JWT | 10/min | Create agent session + run first execution (SSE). Emits `session` event first |
| POST | `/sessions/{id}/follow-up` | JWT | 10/min | Follow-up question on completed memo within session (SSE) |

**Agent types:** `research`, `case_prep`, `strategy`, `drafting`

**SSE event types:** `status`, `progress`, `checkpoint` (HITL), `memo`, `memo_stream` (streaming chunks), `done`, `error` (categorized: rate_limit/timeout/auth_error/provider_error/no_results/llm_error), keepalive comments

### Graph (`backend/app/api/routes/graph.py`)

**Prefix:** `/api/v1/graph`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/{case_id}/neighborhood` | Optional | 30/min | Citation neighborhood (depth 1-3) as nodes + edges |
| GET | `/{case_id}/chain` | Optional | 30/min | Forward citation chain (max_depth 1-5) |
| GET | `/{case_id}/authorities` | Optional | 30/min | Most-cited cases in network (limit 1-50) |
| GET | `/stats` | Optional | 30/min | Global graph statistics (cached in Redis) |
| GET | `/{case_id}/evolution` | None | 30/min | Citation evolution timeline (forward/backward) with treatment |

### Documents (`backend/app/api/routes/documents.py`)

**Prefix:** `/api/v1/documents`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| POST | `/upload` | JWT | 10/min | Upload PDF (50MB max, magic byte validation). Queues Celery analysis task |
| GET | `/` | JWT | 60/min | List user's documents, paginated |
| GET | `/{id}` | JWT | 60/min | Document detail + analysis results (if completed) |
| DELETE | `/{id}` | JWT | 20/min | Delete document from storage + DB. Audit logged |
| GET | `/{id}/memo` | JWT | 30/min | Get research memo for analyzed document |

### Audio (`backend/app/api/routes/audio.py`)

**Prefix:** `/api/v1/cases`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| POST | `/{case_id}/audio/generate` | JWT | 5/min | Queue audio digest generation (Celery). Returns status if already exists |
| GET | `/{case_id}/audio/status` | None | 60/min | Check available audio digests for a case |
| GET | `/{case_id}/audio` | None | 10/min | Stream audio MP3 file |

### Judges (`backend/app/api/routes/judges.py`)

**Prefix:** `/api/v1/judges`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/judges` | None | 30/min | List judges with participation + authorship counts, searchable |
| GET | `/judges/compare` | None | 30/min | Compare 2-3 judges side-by-side |
| GET | `/judges/predict` | None | 30/min | Predict outcome based on historical judge patterns |
| GET | `/judges/{name}` | None | 30/min | Judge profile with analytics (cached 1hr) |
| GET | `/judges/{name}/cases` | None | 30/min | Judge's cases, paginated with filters |
| GET | `/courts/{name}/stats` | None | 30/min | Court-level statistics (cached 1hr) |

### Counsel (`backend/app/api/routes/counsel.py`)

**Prefix:** `/api/v1/counsel`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/counsel` | None | 30/min | Search counsels by name |
| GET | `/counsel/{name}` | None | 30/min | Counsel profile with analytics (cached 1hr) |
| GET | `/counsel/{name}/cases` | None | 30/min | Counsel's cases, paginated with filters |
| GET | `/counsel/{name}/matchups` | None | 30/min | Head-to-head records against opposing counsels |

### Health (`backend/app/api/routes/health.py`)

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/health` | Optional | 60/min | Health check. Minimal `{"status": "healthy|degraded|unhealthy"}` for unauthenticated. Full dependency details for authenticated. Returns 503 if PostgreSQL (critical) is down |

Dependencies checked (concurrent, 5s timeout each): PostgreSQL, Redis, Pinecone, Neo4j, Gemini.

### Ingest -- Admin (`backend/app/api/routes/ingest.py`)

**Prefix:** `/api/v1/ingest`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| POST | `/upload` | Admin | 30/min | Upload PDF for ingestion (admin-only variant) |
| GET | `/status/{id}` | JWT | 60/min | Check ingestion status |
| GET | `/dashboard/completeness` | Admin | 60/min | Data completeness dashboard: field coverage %, status distribution, confidence buckets, year coverage |
| GET | `/review-queue` | Admin | 60/min | DEPRECATED: List cases needing review |
| PATCH | `/cases/{id}/metadata` | Admin | 30/min | Update allowed metadata fields (27 field whitelist) |
| POST | `/cases/{id}/approve` | Admin | 30/min | DEPRECATED: Mark case as approved |
| POST | `/cases/{id}/retry` | Admin | 30/min | DEPRECATED: Reset failed case to pending |

### DPDP -- Data Protection (`backend/app/api/routes/dpdp.py`)

**Prefix:** `/api/v1/dpdp`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/data-summary` | JWT | 20/min | Summary of all personal data held (DPDP Section 11) |
| POST | `/erasure` | JWT | 5/hour | Delete all personal data, deactivate account (DPDP Section 12) |
| POST | `/consent-withdraw` | JWT | 10/hour | Withdraw data processing consent (DPDP Section 6) |
| GET | `/consent-status` | JWT | 30/min | Current consent records |

### Admin Review (`backend/app/api/routes/admin_review.py`)

**Prefix:** `/api/v1/admin/review`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/` | Admin | 60/min | Review queue: filterable by status (needs_review/failed/processing), sortable by created_at/confidence/year |
| GET | `/{case_id}` | Admin | 60/min | Full review detail including provenance |
| POST | `/{case_id}/approve` | Admin | 30/min | Set ingestion_status = 'complete' |
| POST | `/{case_id}/reject` | Admin | 30/min | Set ingestion_status = 'rejected' |

### Admin Corrections (`backend/app/api/routes/admin_corrections.py`)

**Prefix:** `/api/v1/admin/corrections`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| POST | `/{case_id}/correct` | Admin | 30/min | Correct single metadata field with reason. Full audit trail (old value, new value, reason, corrected_by). Updates metadata_provenance to 'admin_corrected' |
| GET | `/{case_id}/history` | Admin | 60/min | Correction audit history for a case |

### Data Quality (`backend/app/api/routes/data_quality.py`)

**Prefix:** `/api/v1/admin/data-quality`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/` | Admin | 30/min | Field population rates, citation resolution, average metadata fields per case |

### Preferences (`backend/app/api/routes/preferences.py`)

**Prefix:** `/api/v1/users/me/preferences`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| GET | `/users/me/preferences` | JWT | 60/min | Get user preferences (from JSONB) |
| PUT | `/users/me/preferences` | JWT | 20/min | Merge partial update into preferences JSONB |
| POST | `/users/me/preferences/refresh` | JWT | 5/min | Auto-populate preferences from last 30 days of search history |

### Sharing (`backend/app/api/routes/sharing.py`)

**Prefix:** `/api/v1`

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|------------|---------|
| POST | `/agents/research/{id}/share` | JWT | 20/min | Create or return existing shareable link (token_urlsafe, optional expiry) |
| GET | `/agents/research/{id}/share` | JWT | 60/min | Check share status |
| DELETE | `/agents/research/{id}/share` | JWT | 20/min | Revoke share |
| GET | `/shared/{token}` | None | 60/min | Public endpoint: retrieve shared memo by token (no auth, increments view_count) |

---

## 3. Database Models

All models are SQLAlchemy ORM classes. Models are defined in `backend/app/models/`. Migrations live in `backend/migrations/versions/`.

### `users`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| email | VARCHAR(254) | No | -- | Unique, user email |
| password_hash | VARCHAR(255) | No | -- | bcrypt hash |
| name | VARCHAR(255) | Yes | -- | Display name |
| role | VARCHAR(20) | No | 'researcher' | CHECK: admin, researcher, viewer |
| is_active | BOOLEAN | No | true | Account active flag |
| failed_login_count | INTEGER | No | 0 | Lockout counter |
| locked_until | TIMESTAMPTZ | Yes | -- | Account lock expiry |
| last_login_at | TIMESTAMPTZ | Yes | -- | Last successful login |
| preferences | JSONB | No | '{}' | User preferences |
| created_at | TIMESTAMPTZ | No | now() | |
| updated_at | TIMESTAMPTZ | No | now() | |

### `cases`

The largest table with 70+ columns. Organized by migration phase below.

**Core columns:**

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| title | VARCHAR | No | -- | Case title |
| citation | VARCHAR(255) | Yes | -- | Primary citation (unique partial index) |
| case_id | VARCHAR(100) | Yes | -- | External case identifier |
| cnr | VARCHAR(50) | Yes | -- | Case Number Record |
| court | VARCHAR(100) | No | -- | Court name |
| year | INTEGER | Yes | -- | CHECK: 1800-2200 |
| case_type | VARCHAR(50) | Yes | -- | |
| jurisdiction | VARCHAR(50) | Yes | -- | CHECK: civil, criminal, constitutional, tax, labor, etc. (14 values) |
| bench_type | VARCHAR(30) | Yes | -- | |
| judge | TEXT[] | Yes | -- | Array of judge names (GIN indexed) |
| author_judge | VARCHAR(255) | Yes | -- | Author of opinion |
| petitioner | VARCHAR | Yes | -- | |
| respondent | VARCHAR | Yes | -- | |
| decision_date | DATE | Yes | -- | |
| disposal_nature | VARCHAR(50) | Yes | -- | CHECK: Allowed, Dismissed, Partly Allowed, etc. (13 values) |
| description | TEXT | Yes | -- | |
| keywords | TEXT[] | Yes | -- | GIN indexed |
| acts_cited | TEXT[] | Yes | -- | GIN indexed |
| cases_cited | TEXT[] | Yes | -- | GIN indexed |
| ratio_decidendi | TEXT | Yes | -- | Core legal holding |
| full_text | TEXT | Yes | -- | Deferred loading (not loaded by default) |
| searchable_text | TSVECTOR | Yes | -- | Full-text search column (GIN indexed) |
| pdf_storage_path | VARCHAR(512) | Yes | -- | |
| s3_source_path | VARCHAR(512) | Yes | -- | |
| source | VARCHAR(30) | No | 'aws_open_data' | |
| language | VARCHAR(20) | No | 'english' | |
| chunk_count | INTEGER | No | 0 | |
| available_languages | TEXT[] | Yes | -- | |

**Migration 009 columns (ingestion):**

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| case_number | VARCHAR(200) | Yes | -- | |
| is_reportable | BOOLEAN | Yes | -- | |
| headnotes | TEXT | Yes | -- | |
| outcome_summary | TEXT | Yes | -- | |
| ingestion_status | VARCHAR(20) | No | 'pending' | CHECK: pending, processing, complete, failed, vectors_failed, needs_review, rejected |

**Migration 010-015 columns (enrichment):**

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| cited_by_count | INTEGER | No | 0 | |
| coram_size | INTEGER | Yes | -- | CHECK: > 0 |
| lower_court | VARCHAR(200) | Yes | -- | |
| lower_court_case_number | VARCHAR(200) | Yes | -- | |
| appeal_from | VARCHAR(200) | Yes | -- | |
| opinion_type | VARCHAR(30) | Yes | -- | CHECK: unanimous, majority, plurality, per_curiam |
| dissenting_judges | TEXT[] | Yes | -- | |
| concurring_judges | TEXT[] | Yes | -- | |
| split_ratio | VARCHAR(20) | Yes | -- | |
| petitioner_type | VARCHAR(50) | Yes | -- | CHECK: individual, government_central, etc. (8 values) |
| respondent_type | VARCHAR(50) | Yes | -- | |
| is_pil | BOOLEAN | Yes | -- | Public Interest Litigation |
| companion_cases | TEXT[] | Yes | -- | |
| metadata_provenance | JSONB | Yes | -- | Source tracking per field |
| extraction_confidence | FLOAT | Yes | -- | LLM confidence 0.0-1.0 |
| text_hash | VARCHAR(64) | Yes | -- | SHA-256 dedup (unique partial index) |
| hindi_searchable_text | TSVECTOR | Yes | -- | |
| is_anonymized | BOOLEAN | No | false | |
| anonymization_flags | TEXT[] | Yes | -- | |

**Migration 023 columns (Ingestion V2):**

| Column Group | Columns |
|-------------|---------|
| Judge Behavior | arguments_raised (JSONB), relief_granted (TEXT), relief_sought (TEXT), sentence_details (JSONB), damages_awarded (JSONB), judicial_tone (VARCHAR 30), key_observations (TEXT[]), hearing_count (INTEGER) |
| Citation Intelligence | citation_treatments (JSONB), distinguished_cases (TEXT[]), overruled_cases (TEXT[]), legal_principles_applied (TEXT[]) |
| Procedural | procedural_history (JSONB), interim_orders (TEXT[]), filing_date (DATE), urgency_indicators (TEXT[]) |
| Party and Case | party_counsel (JSONB, GIN jsonb_path_ops), issue_classification (TEXT[]), fact_pattern_tags (TEXT[]) |
| Output Quality | operative_order (TEXT), conditions_imposed (TEXT[]), costs_awarded (JSONB) |
| Other | page_map (JSONB), enrichment_status (VARCHAR 20), source_dataset (VARCHAR 50), legal_propositions (JSONB), statute_sections_interpreted (JSONB), fact_pattern_summary (TEXT) |

**Indexes (30+ total):**

- Single-column: court, year, case_type, jurisdiction, bench_type, source, opinion_type, is_pil, coram_size, decision_date, text_hash, judicial_tone, filing_date, enrichment_status, ingestion_status, disposal_nature
- Composite: (court, year), (year, case_type), (court, case_type), (court, decision_date DESC)
- Partial unique: citation (WHERE NOT NULL), text_hash (WHERE NOT NULL), author_judge (WHERE NOT NULL)
- GIN: keywords, acts_cited, cases_cited, judge, fact_pattern_tags, issue_classification, legal_principles_applied, distinguished_cases, overruled_cases, party_counsel (jsonb_path_ops), searchable_text

### `documents`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| user_id | UUID FK(users) | No | -- | CASCADE delete |
| filename | VARCHAR(255) | No | -- | |
| storage_path | VARCHAR(512) | No | -- | |
| file_size | INTEGER | Yes | -- | |
| mime_type | VARCHAR(100) | No | 'application/pdf' | |
| status | VARCHAR(20) | No | 'pending' | CHECK: pending, extracting, analyzing, searching, generating, completed, failed |
| error_message | TEXT | Yes | -- | |
| processing_step | VARCHAR(50) | Yes | -- | |
| processing_started_at | TIMESTAMPTZ | Yes | -- | |
| processing_completed_at | TIMESTAMPTZ | Yes | -- | |
| case_id | UUID FK(cases) | Yes | -- | SET NULL on delete, indexed |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

### `chat_sessions`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| user_id | UUID FK(users) | No | -- | CASCADE, indexed |
| title | VARCHAR(255) | No | 'New Research Session' | |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

Relationship: `messages` -> ChatMessage (cascade all, delete-orphan)

### `chat_messages`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| session_id | UUID FK(chat_sessions) | No | -- | CASCADE, indexed |
| role | VARCHAR(20) | No | -- | CHECK: user, assistant |
| content | TEXT | No | -- | Encrypted with AES-256-GCM |
| sources | JSONB | Yes | -- | Citation sources |
| tokens_used | INTEGER | Yes | -- | |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

Index: (session_id, created_at DESC)

### `agent_sessions`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| user_id | UUID FK(users) | No | -- | CASCADE, indexed |
| agent_type | VARCHAR(20) | No | -- | CHECK: research, case_prep, strategy, drafting |
| title | VARCHAR(255) | No | 'New Research Session' | |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

Index: (user_id, agent_type). Relationships: messages -> AgentMessage, executions -> AgentExecution

### `agent_messages`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| session_id | UUID FK(agent_sessions) | No | -- | CASCADE, indexed |
| execution_id | UUID FK(agent_executions) | Yes | -- | SET NULL |
| role | VARCHAR(20) | No | -- | CHECK: user, assistant |
| content | TEXT | No | -- | Encrypted |
| sources | JSONB | Yes | -- | |
| message_type | VARCHAR(20) | No | 'query' | CHECK: query, memo, follow_up, follow_up_response |
| tokens_used | INTEGER | Yes | -- | |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

### `agent_executions`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| user_id | UUID FK(users) | No | -- | CASCADE |
| agent_type | VARCHAR(20) | No | -- | CHECK: research, case_prep, strategy, drafting |
| status | VARCHAR(20) | No | 'running' | CHECK: running, waiting_input, completed, failed, cancelled |
| input_data | JSONB | Yes | -- | |
| result_data | JSONB | Yes | -- | Contains memo, confidence, footnotes, etc. |
| thread_id | UUID | No | uuid4 | LangGraph thread ID |
| current_step | VARCHAR(100) | Yes | -- | |
| steps_completed | INTEGER | No | 0 | |
| total_steps | INTEGER | Yes | -- | |
| completed_at | TIMESTAMPTZ | Yes | -- | |
| session_id | UUID FK(agent_sessions) | Yes | -- | SET NULL |
| error_message | TEXT | Yes | -- | |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

### `statutes`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| act_name | VARCHAR(200) | No | -- | Full act name |
| act_short_name | VARCHAR(50) | No | -- | Short code (e.g., IPC) |
| act_number | VARCHAR(50) | Yes | -- | |
| act_year | INTEGER | No | -- | |
| part | VARCHAR(100) | Yes | -- | |
| chapter | VARCHAR(100) | Yes | -- | |
| section_number | VARCHAR(20) | No | -- | |
| section_title | VARCHAR(500) | Yes | -- | |
| section_text | TEXT | No | -- | |
| explanation | TEXT | Yes | -- | |
| effective_date | DATE | Yes | -- | |
| effective_from / effective_until | DATE | Yes | -- | |
| amendment_history | JSONB | Yes | -- | |
| is_repealed | BOOLEAN | No | false | |
| replaced_by / replaces | VARCHAR(200) | Yes | -- | |
| document_type | VARCHAR(20) | No | -- | |
| searchable_text | TSVECTOR | Yes | -- | GIN indexed |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

Unique constraint: (act_short_name, section_number)

### `audit_logs`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | BIGINT | No | autoincrement | Primary key |
| user_id | UUID FK(users) | Yes | -- | SET NULL |
| action | VARCHAR | No | -- | e.g., login.success, agent.run, metadata.correction |
| resource_type | VARCHAR | Yes | -- | |
| resource_id | VARCHAR | Yes | -- | |
| ip_address | VARCHAR | Yes | -- | SHA-256 hashed (DPDP compliance) |
| user_agent | VARCHAR | Yes | -- | |
| metadata | JSONB | Yes | -- | |
| created_at | TIMESTAMPTZ | No | now() | |

### `consents`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| user_id | UUID FK(users) | No | -- | CASCADE |
| consent_type | VARCHAR | No | -- | e.g., data_processing |
| granted | BOOLEAN | No | -- | |
| version | VARCHAR | No | '1.0' | |
| granted_at | TIMESTAMPTZ | No | now() | |
| revoked_at | TIMESTAMPTZ | Yes | -- | |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

### `search_history`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| user_id | UUID FK(users) | No | -- | CASCADE |
| query | VARCHAR(2000) | No | -- | |
| filters | JSONB | Yes | -- | |
| result_count | INTEGER | Yes | -- | |
| is_bookmarked | BOOLEAN | No | false | |
| created_at | TIMESTAMPTZ | No | now() | |

### `shared_memos`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | gen_random_uuid() | Primary key |
| execution_id | UUID FK(agent_executions) | No | -- | CASCADE |
| user_id | UUID FK(users) | No | -- | CASCADE |
| share_token | VARCHAR(32) | No | -- | Unique |
| expires_at | TIMESTAMPTZ | Yes | -- | Optional expiry |
| is_active | BOOLEAN | No | true | Soft revocation |
| view_count | INTEGER | No | 0 | |
| created_at | TIMESTAMPTZ | No | now() | |

### `audio_digests`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| case_id | UUID FK(cases) | No | -- | CASCADE |
| language | VARCHAR | No | -- | |
| summary_text | TEXT | Yes | -- | LLM-generated summary |
| audio_storage_path | VARCHAR | Yes | -- | |
| duration_seconds | INTEGER | Yes | -- | |
| status | VARCHAR | No | 'generating' | CHECK: generating, completed, failed |
| error_message | TEXT | Yes | -- | |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

Unique constraint: (case_id, language)

### `document_analyses`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| document_id | UUID FK(documents) | No | -- | CASCADE, unique |
| extracted_text | TEXT | Yes | -- | |
| issues | JSONB | Yes | -- | |
| parties | JSONB | Yes | -- | |
| key_facts | TEXT | Yes | -- | |
| relief_sought | TEXT | Yes | -- | |
| counter_arguments | JSONB | Yes | -- | |
| research_memo | TEXT | Yes | -- | |
| created_at, updated_at | TIMESTAMPTZ | No | now() | |

### `case_citation_equivalents`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| case_id | UUID FK(cases) | No | -- | CASCADE, indexed |
| reporter | VARCHAR(50) | No | -- | e.g., SCC, AIR, SCR |
| citation_text | VARCHAR(200) | No | -- | Full citation text |
| year | INTEGER | Yes | -- | |

Unique constraint: (reporter, citation_text). Index on citation_text.

### `case_sections`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| case_id | UUID FK(cases) | No | -- | CASCADE |
| section_type | VARCHAR(50) | No | -- | e.g., FACTS, ISSUES, ARGUMENTS |
| content | TEXT | No | -- | |
| section_index | INTEGER | No | 0 | |
| summary | TEXT | Yes | -- | |

Indexes: (case_id, section_type), (case_id)

### `case_statute_interpretations`

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| id | UUID | No | uuid4 | Primary key |
| case_id | FK(cases) | No | -- | CASCADE, indexed |
| section_text | VARCHAR(200) | No | -- | Original citation text |
| normalized_section | VARCHAR(200) | No | -- | Normalized form, indexed |
| act_name | VARCHAR(200) | No | -- | Indexed |
| interpretation_summary | TEXT | Yes | -- | |
| is_primary_holding | BOOLEAN | No | false | |

Unique constraint: (case_id, normalized_section)

---

## 4. Interfaces and Providers

All interfaces are `@runtime_checkable` Protocol classes in `backend/app/core/interfaces/`. Concrete implementations live in `backend/app/core/providers/`. All are instantiated via `@lru_cache` singletons in `backend/app/core/dependencies.py`.

### LLMProvider

**Interface:** `backend/app/core/interfaces/llm.py`
**Implementation:** `backend/app/core/providers/llm/gemini.py` (`GeminiLLM`)

```python
async def generate(prompt, *, system=None, temperature=0.1, max_tokens=8192) -> str
async def generate_structured(prompt, *, system=None, output_schema, temperature=0.1) -> dict
async def generate_structured_from_pdf(pdf_path, *, prompt, system=None, output_schema, temperature=0.1) -> dict
async def stream(prompt, *, system=None, temperature=0.1, max_tokens=None) -> AsyncIterator[str]
```

### EmbeddingProvider

**Interface:** `backend/app/core/interfaces/embeddings.py`
**Implementation:** `backend/app/core/providers/embeddings/gemini.py` (`GeminiEmbedder`)

```python
async def embed_text(text, *, task_type="RETRIEVAL_QUERY") -> list[float]
async def embed_batch(texts, *, task_type="RETRIEVAL_DOCUMENT") -> list[list[float]]
@property dimension -> int
```

### VectorStore

**Interface:** `backend/app/core/interfaces/vector_store.py`
**Implementation:** `backend/app/core/providers/vector_store/pinecone.py` (`PineconeStore`) or `pgvector.py` (`PgvectorStore`)

```python
async def upsert(vectors: list[dict]) -> None  # Each dict: id, values, metadata
async def search(query_vector, *, top_k=20, filters=None, user_scope=None) -> list[SearchResult]
async def delete_by_metadata(filter, *, exclude_ids=None) -> None
```

`SearchResult` dataclass: `id: str, score: float, metadata: dict`

### GraphStore

**Interface:** `backend/app/core/interfaces/graph_store.py`
**Implementation:** `backend/app/core/providers/graph_store/neo4j.py` (`Neo4jGraph`) or `pg_graph.py` (`PgGraphStore`)

```python
async def create_node(label, properties) -> str
async def get_node(node_id) -> dict | None
async def query(cypher, *, params=None) -> list[dict]
async def get_neighbors(node_id, *, relationship=None, direction="both", depth=1) -> dict
async def ensure_constraints() -> None
async def batch_create_nodes(nodes, *, batch_size=500) -> int
async def batch_create_citation_edges(edges, *, batch_size=500) -> int
async def delete_node(node_id) -> bool
```

### Reranker

**Interface:** `backend/app/core/interfaces/reranker.py`
**Implementation:** `backend/app/core/providers/reranker/cohere.py` (`CohereReranker`)

```python
async def rerank(query, documents, *, top_n=10) -> list[RerankResult]
```

`RerankResult` dataclass: `index: int, score: float, text: str`

### FileStorage

**Interface:** `backend/app/core/interfaces/storage.py`
**Implementation:** `backend/app/core/providers/storage/local.py` (`LocalStorage`) or `gcs.py` (`GCSStorage`)

```python
async def store(file_path, destination) -> str  # Returns storage path
async def retrieve(storage_path) -> bytes
def retrieve_chunked(storage_path, chunk_size=8192) -> AsyncIterator[bytes]
async def delete(storage_path) -> None
async def exists(storage_path) -> bool
```

### TranslationProvider

**Interface:** `backend/app/core/interfaces/translation.py`
**Implementation:** `backend/app/core/providers/translation/gemini.py` (`GeminiTranslator`)

```python
async def translate(text, *, source, target) -> str
async def detect_language(text) -> str  # Returns ISO 639-1 code
```

### TTSProvider

**Interface:** `backend/app/core/interfaces/tts.py`
**Implementation:** `backend/app/core/providers/tts/sarvam.py` (`SarvamTTS`) or `mock.py` (`MockTTS`)

```python
async def synthesize(text, *, language="en") -> bytes  # MP3 format
async def get_supported_languages() -> list[str]
```

### WebSearchProvider

**Interface:** `backend/app/core/interfaces/web_search.py`
**Implementation:** `backend/app/core/providers/web_search/tavily.py` (`TavilySearchClient`)

```python
async def search(query, *, max_results=5, search_depth="advanced",
                 include_domains=None, time_range=None, country=None,
                 include_raw_content=False) -> list[dict]
```

### DocumentParser

**Interface:** `backend/app/core/interfaces/document_parser.py`

```python
async def extract_text(file_path) -> str
async def extract_text_with_ocr(file_path) -> str
```

### ExternalDocProvider (Indian Kanoon)

**Interface:** `backend/app/core/interfaces/external_doc.py`
**Implementation:** `backend/app/core/providers/external_doc/indian_kanoon.py` (`IndianKanoonClient`)

```python
async def search(query, *, max_results=10, boolean_query=None,
                 court_filter=None, from_date=None, to_date=None,
                 sort_by=None, max_pages=1, title_filter=None,
                 cite_filter=None, author_filter=None,
                 bench_filter=None, max_cites=None) -> list[dict]
async def get_document(doc_id) -> dict
async def get_fragment(doc_id, query) -> dict
async def get_metadata(doc_id) -> dict
async def get_court_copy(doc_id) -> dict
```

---

## 5. Security

### Authentication

**File:** `backend/app/security/auth.py`

| Property | Value |
|----------|-------|
| Mechanism | JWT (HS256) via `PyJWT` library |
| Access token expiry | 60 minutes |
| Access token claims | `sub` (user_id), `role`, `exp`, `iat`, `jti` (unique token ID), `type: "access"`, `iss: "smriti"`, `aud: "smriti-api"` |
| Refresh token expiry | 7 days |
| Refresh token claims | Same as access but `type: "refresh"`, `role: "refresh"`, signed with separate `jwt_refresh_secret_key` |
| Refresh cookie | httpOnly, SameSite=Lax, Secure (prod only), path `/api/v1/auth`, max-age 7 days |
| Token rotation | On refresh, old token is revoked, new pair issued |
| Clock skew tolerance | 30-second leeway on verification |
| Password hashing | bcrypt with configurable cost factor (default 12) |
| Account lockout | 10 failed attempts -> 5-minute lock (stored in `locked_until` column) |

### Token Revocation

- **Mechanism**: Redis-backed blacklist with auto-expiry
- **Key pattern**: `revoked:jti:<jti>`
- **TTL**: Matches token's remaining TTL (or 7 days default)
- **Fail-closed**: If Redis is unavailable, treats token as revoked (denies access)

### RBAC (Role-Based Access Control)

Three roles with hierarchy:

| Role | Access Level |
|------|-------------|
| `admin` | Full access: manage ingestion, review cases, correct metadata |
| `researcher` | Standard authenticated access: search, chat, agents, documents |
| `viewer` | Read-only access |

**Implementation (dependency functions):**

| Function | Purpose |
|----------|---------|
| `get_current_user()` | Extracts + validates JWT from Bearer header |
| `get_current_user_optional()` | Returns None if no token (graceful degradation for optional auth) |
| `require_role(*roles)` | Dependency factory that checks `current_user.role in roles` |

### Rate Limiting

**File:** `backend/app/security/rate_limiter.py`

- **Mechanism**: Redis sorted-set sliding window algorithm
- **Key pattern**: `rate:<client_ip>:<endpoint_path>` (reads `X-Forwarded-For` for proxy support)
- **Fallback**: In-memory sliding window (OrderedDict, 10K buckets max, LRU eviction) when Redis unavailable
- **Configuration**: Human-readable strings parsed at startup (e.g., `"30/minute"`, `"5/hour"`)

Representative limits:

| Category | Limit |
|----------|-------|
| Auth endpoints | 5-20/min depending on endpoint |
| Search | 30/min |
| Chat | 20/min |
| Agent execution | 10/min |
| Audio generation | 5/min |
| Data erasure | 5/hour |

### Input Sanitization

**File:** `backend/app/security/sanitizer.py`

| Function | Purpose |
|----------|---------|
| `sanitize_input(text)` | Strips HTML tags, null bytes, control characters (preserves whitespace), collapses excessive newlines |
| `sanitize_search_query(query)` | sanitize_input + removes prompt injection markers + role-switching patterns + collapses whitespace |
| `detect_prompt_injection(text)` | Detects 25+ injection markers (e.g., "ignore previous instructions", "DAN mode", chat-ML tokens), role-switching patterns (`system:`, `assistant:`, etc.), suspicious special character density (>15%) |

### Encryption

**File:** `backend/app/security/encryption.py`

| Property | Value |
|----------|-------|
| Algorithm | AES-256-GCM field-level encryption |
| Key source | `ENCRYPTION_KEY` setting (64-char hex string or base64-encoded 32-byte key) |
| Nonce | 12 bytes (96 bits), randomly generated per encrypt |
| Output format | base64(nonce + ciphertext + tag) |
| Migration helper | `safe_decrypt(value)` -- decrypts if ciphertext, returns as-is if plaintext |
| Used for | chat message content, agent message content |

### Audit Logging

**File:** `backend/app/security/audit.py`

Records to `audit_logs` table. IP addresses are SHA-256 hashed with salt before storage (DPDP compliance).

**Logged actions:** user.registered, login.success, login.failure, token.refresh, account.deleted, session.delete, document.delete, agent.run, agent.resume, agent.cancel, agent.export, agent_session.create, metadata.correction, metadata.corrected

---

## 6. Background Tasks

### Worker Configuration

**File:** `backend/app/worker.py`

Celery with Redis broker:

| Setting | Value |
|---------|-------|
| broker | redis://localhost:6379/1 |
| backend | redis://localhost:6379/1 |
| serializer | json |
| timezone | UTC |
| task_acks_late | True |
| worker_prefetch_multiplier | 1 |
| autodiscover | app.tasks |

### Audio Digest Generation

**File:** `backend/app/tasks/audio_tasks.py`

- **Task**: `generate_audio(case_id, language)`
- **Max retries**: 2, retry delay 60s
- **Pipeline**: (1) Check if exists -> (2) Load case from PG -> (3) Generate summary via GeminiLLM (AUDIO_SUMMARY prompt, temp 0.3, max 2048 tokens) -> (4) TTS synthesis -> (5) Store MP3 -> (6) Update DB record
- **Duration estimate**: word_count / 150 * 60 seconds

### Document Analysis

**File:** `backend/app/tasks/document_tasks.py`

- **Task**: `analyze_document(document_id)`
- **Max retries**: 2, retry delay 60s
- **Pipeline**: (1) Extract PDF text (with OCR fallback) -> (2) Extract legal issues via LLM -> (3) Map precedents via vector search + rerank -> (4) Generate counter-arguments -> (5) Generate research memo -> (6) Chunk, embed, index to Pinecone -> (7) Store analysis results to `document_analyses`
- **Status tracking**: Updates document status through: extracting -> analyzing -> searching -> generating -> indexing -> completed/failed

### Startup Task

- **Expired upload cleanup**: Runs as fire-and-forget asyncio task on startup. Deletes storage files and nullifies `storage_path` for documents older than `USER_UPLOAD_RETENTION_DAYS` (default 7). DPDP compliance.

---

## 7. Error Handling

### Custom Exceptions

**File:** `backend/app/security/exceptions.py`

| Exception | Purpose | HTTP Status |
|-----------|---------|-------------|
| `AuthenticationError(detail)` | Invalid/expired/revoked JWT | 401 |
| `AuthorizationError(detail)` | Insufficient role permissions | 403 |
| `RateLimitExceededError(detail, retry_after)` | Rate limit exceeded | 429 |

### Error Response Format

All error responses follow a consistent JSON structure:

```json
{
  "error": "Human-readable message",
  "code": "ERROR_CODE"
}
```

Codes: `UNAUTHORIZED`, `FORBIDDEN`, `RATE_LIMITED`, `INTERNAL_ERROR`

Rate limit responses include `Retry-After` header (seconds).

### Agent Error Categorization

SSE error events are categorized for frontend handling:

| Category | Recoverable | Trigger |
|----------|-------------|---------|
| `rate_limit` | Yes | "rate limit", "429", "quota" in message |
| `timeout` | Yes | "timeout", "timed out" |
| `auth_error` | No | "401", "403", "permission" (non-Google) |
| `provider_error` | No | Google/Gemini auth errors |
| `no_results` | Yes | "no results", "not found" |
| `llm_error` | No | Default / infrastructure errors |

### Unhandled Exceptions

Caught by global handler in `backend/app/main.py`, logged with full traceback, captured to Sentry, returns generic 500 with `INTERNAL_ERROR` code. Stack traces are never exposed to the client.

### Logging

**File:** `backend/app/core/logging_config.py`

| Aspect | Detail |
|--------|--------|
| Production/Staging format | JSON structured logging (`JSONFormatter`) with fields: severity, message, module, function, timestamp, request_id, exception |
| Development format | Human-readable: `%(asctime)s %(levelname)-8s %(name)s: %(message)s` |
| PII redaction | Both formatters redact email addresses, API keys/tokens/passwords, JWT tokens, Aadhaar numbers, PAN numbers, Indian mobile numbers |
| Request tracing | `RequestIDMiddleware` sets a `contextvars.ContextVar` per request; a `logging.Filter` on the root logger injects `request_id` into every log record |
| Silenced loggers | httpx, httpcore, urllib3, asyncio set to WARNING level |
| Audit IP hashing | IP addresses in audit logs are SHA-256 hashed with salt `smriti_audit_ip_v1` before storage (DPDP compliance) |
