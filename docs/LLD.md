# Smriti — Low-Level Design (LLD)

---

## 1. Database Schemas

### 1.1 PostgreSQL Tables

#### `cases` — Judgment Metadata (Primary Table)

```sql
CREATE TABLE cases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    citation        TEXT,
    case_id         TEXT,                           -- Original case number (CA 123/2024)
    cnr             TEXT,                           -- Case Number Register (AAAA + 14 digits)
    court           TEXT NOT NULL,
    year            INTEGER CHECK (year BETWEEN 1800 AND 2200),
    case_type       TEXT,                           -- Criminal Appeal, Writ Petition, PIL, SLP, etc.
    jurisdiction    TEXT,                           -- Criminal, Civil, Constitutional
    bench_type      TEXT,                           -- Constitution Bench, Division Bench, Single Judge
    judge           TEXT[],                         -- Array of judge names
    author_judge    TEXT,                           -- Judge who authored the judgment
    petitioner      TEXT,
    respondent      TEXT,
    decision_date   DATE,
    disposal_nature TEXT,                           -- Allowed, Dismissed, Withdrawn, Partly Allowed
    description     TEXT,                           -- Brief case description
    keywords        TEXT[],                         -- Legal keywords
    acts_cited      TEXT[],                         -- Statutes referenced
    cases_cited     TEXT[],                         -- Citations of cases referenced in judgment
    ratio_decidendi TEXT,                           -- Extracted core legal principle
    full_text       TEXT,                           -- Complete judgment text
    searchable_text TSVECTOR,                       -- Full-text search index
    pdf_storage_path TEXT,                          -- GCS path or local path
    s3_source_path  TEXT,                           -- Original S3 location
    source          TEXT DEFAULT 'aws_open_data',   -- aws_open_data | manual_upload | indiankanoon
    language        TEXT DEFAULT 'english',
    chunk_count     INTEGER DEFAULT 0,
    available_languages TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Primary lookups
CREATE UNIQUE INDEX idx_cases_citation ON cases(citation) WHERE citation IS NOT NULL;
CREATE INDEX idx_cases_cnr ON cases(cnr) WHERE cnr IS NOT NULL;
CREATE INDEX idx_cases_case_id ON cases(case_id) WHERE case_id IS NOT NULL;

-- Filter indexes
CREATE INDEX idx_cases_court ON cases(court);
CREATE INDEX idx_cases_year ON cases(year);
CREATE INDEX idx_cases_case_type ON cases(case_type);
CREATE INDEX idx_cases_jurisdiction ON cases(jurisdiction);
CREATE INDEX idx_cases_bench_type ON cases(bench_type);
CREATE INDEX idx_cases_source ON cases(source);

-- Composite indexes (common filter combinations)
CREATE INDEX idx_cases_court_year ON cases(court, year);
CREATE INDEX idx_cases_year_case_type ON cases(year, case_type);
CREATE INDEX idx_cases_court_case_type ON cases(court, case_type);

-- GIN indexes for arrays
CREATE INDEX idx_cases_keywords ON cases USING GIN(keywords);
CREATE INDEX idx_cases_acts_cited ON cases USING GIN(acts_cited);
CREATE INDEX idx_cases_cases_cited ON cases USING GIN(cases_cited);
CREATE INDEX idx_cases_judge ON cases USING GIN(judge);

-- Full-text search
CREATE INDEX idx_cases_searchable ON cases USING GIN(searchable_text);

-- FTS trigger: auto-update searchable_text
CREATE OR REPLACE FUNCTION update_searchable_text() RETURNS TRIGGER AS $$
BEGIN
    NEW.searchable_text :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.citation, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.court, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.judge, ' '), '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.petitioner, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.respondent, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D');
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_searchable_text
    BEFORE INSERT OR UPDATE ON cases
    FOR EACH ROW EXECUTE FUNCTION update_searchable_text();
```

#### `users` — User Accounts

```sql
CREATE TABLE users (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email             TEXT NOT NULL UNIQUE,          -- Encrypted at app layer (AES-256-GCM)
    password_hash     TEXT NOT NULL,                 -- bcrypt cost factor 12
    name              TEXT,
    role              TEXT NOT NULL DEFAULT 'researcher' CHECK (role IN ('admin', 'researcher', 'viewer')),
    is_active         BOOLEAN DEFAULT true,
    failed_login_count INTEGER DEFAULT 0,
    locked_until      TIMESTAMPTZ,
    last_login_at     TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
```

#### `chat_sessions` — Conversation Sessions

```sql
CREATE TABLE chat_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT DEFAULT 'New Research Session',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON chat_sessions(user_id);
```

#### `chat_messages` — Individual Messages

```sql
CREATE TABLE chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    sources     JSONB,                              -- [{case_id, title, citation, score}]
    tokens_used INTEGER,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_session ON chat_messages(session_id);
CREATE INDEX idx_messages_created ON chat_messages(created_at);
```

#### `documents` — User-Uploaded Documents

```sql
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    storage_path    TEXT NOT NULL,
    file_size       INTEGER,
    mime_type       TEXT DEFAULT 'application/pdf',
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message   TEXT,
    case_id         UUID REFERENCES cases(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_user ON documents(user_id);
CREATE INDEX idx_documents_status ON documents(status);
```

#### `audit_logs` — Security Audit Trail

```sql
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,                   -- search, view_case, chat, upload, login, logout, delete
    resource_type   TEXT,                            -- case, document, session, user
    resource_id     TEXT,
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB,                           -- Extra context (query text, filters, etc.)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE INDEX idx_audit_action ON audit_logs(action);
```

#### `consent_records` — DPDP Act Compliance

```sql
CREATE TABLE consent_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consent_type    TEXT NOT NULL,                   -- data_processing, analytics, marketing
    granted         BOOLEAN NOT NULL,
    version         TEXT NOT NULL DEFAULT '1.0',
    granted_at      TIMESTAMPTZ DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX idx_consent_user ON consent_records(user_id);
```

### 1.2 Neo4j Graph Schema

```cypher
// Node types
(:Judgment {
    id: UUID,            // Matches cases.id in PostgreSQL
    title: String,
    citation: String,
    court: String,
    year: Integer,
    case_type: String,
    cited_by_count: Integer
})

(:Statute {
    name: String,        // "Indian Penal Code, 1860"
    short_name: String,  // "IPC"
    year: Integer,
    replaced_by: String  // "Bharatiya Nyaya Sanhita, 2023"
})

(:Court {
    name: String,        // "Supreme Court of India"
    level: String,       // "supreme", "high", "district", "tribunal"
    state: String,       // "Maharashtra" (for High Courts)
    code: String         // "SC", "BomHC", "DelHC"
})

(:Judge {
    name: String,        // "Justice D.Y. Chandrachud"
    designation: String  // "Chief Justice", "Judge"
})

// Edge types
(:Judgment)-[:CITES {context: String, paragraph: Integer}]->(:Judgment)
(:Judgment)-[:OVERRULES {context: String}]->(:Judgment)
(:Judgment)-[:AFFIRMS {context: String}]->(:Judgment)
(:Judgment)-[:DISTINGUISHES {context: String}]->(:Judgment)
(:Judgment)-[:APPLIES {section: String, context: String}]->(:Statute)
(:Judgment)-[:DECIDED_BY {role: String}]->(:Judge)   // role: "author", "bench_member"
(:Judgment)-[:DELIVERED_AT]->(:Court)
```

### 1.3 Pinecone Vector Index

```
Index: smriti-legal
Dimensions: 1536 (Gemini gemini-embedding-001)
Metric: cosine
Pod type: Starter (free tier)

Vector metadata per record:
{
    "doc_id": "uuid-of-case",         // FK to cases.id
    "case_id": "CA-123-2024",
    "citation": "(2024) 3 SCC 45",
    "court": "Supreme Court of India",
    "year": 2024,
    "case_type": "Criminal Appeal",
    "section_type": "ratio_decidendi",  // facts, arguments, ratio, order, full
    "chunk_index": 3,
    "language": "english"
}

Filterable fields: court, year, case_type, section_type, language
```

---

## 2. API Endpoint Specifications

### 2.1 Search API

#### `POST /api/v1/search`

Hybrid search across all case law.

**Request:**
```json
{
    "query": "right to privacy Supreme Court",
    "filters": {
        "court": ["Supreme Court of India"],
        "year_from": 2017,
        "year_to": 2024,
        "case_type": "Writ Petition",
        "bench_type": null,
        "judge": null,
        "jurisdiction": null
    },
    "page_size": 20,
    "cursor": null
}
```

**Response (200):**
```json
{
    "results": [
        {
            "id": "uuid",
            "title": "Justice K.S. Puttaswamy (Retd.) v. Union of India",
            "citation": "(2017) 10 SCC 1",
            "court": "Supreme Court of India",
            "year": 2017,
            "case_type": "Writ Petition",
            "bench_type": "Constitution Bench",
            "judges": ["Justice D.Y. Chandrachud", "Justice S.K. Kaul"],
            "snippet": "...the right to privacy is protected as an intrinsic part of the right to life and personal liberty under Article 21...",
            "section_type": "ratio_decidendi",
            "relevance_score": 0.94,
            "cited_by_count": 1247
        }
    ],
    "total": 156,
    "next_cursor": "eyJvZmZzZXQiOjIwfQ==",
    "facets": {
        "courts": [{"name": "Supreme Court of India", "count": 89}],
        "years": [{"year": 2023, "count": 12}],
        "case_types": [{"name": "Writ Petition", "count": 45}]
    },
    "query_understanding": {
        "intent": "topic_search",
        "entities": {"topic": "right to privacy", "court": "Supreme Court"},
        "reformulated": "constitutional right to privacy fundamental rights Article 21"
    }
}
```

**Auth**: Optional (unauthenticated gets limited results)
**Rate limit**: 100/min authenticated, 20/min unauthenticated

#### `GET /api/v1/search/facets`

Get available filter values for the search sidebar.

**Response (200):**
```json
{
    "courts": ["Supreme Court of India", "High Court of Delhi", ...],
    "case_types": ["Criminal Appeal", "Civil Appeal", "Writ Petition", ...],
    "bench_types": ["Constitution Bench", "Division Bench", "Single Judge"],
    "year_range": {"min": 1950, "max": 2025},
    "jurisdictions": ["Criminal", "Civil", "Constitutional"]
}
```

### 2.2 Cases API

#### `GET /api/v1/cases/{case_id}`

**Response (200):**
```json
{
    "id": "uuid",
    "title": "Kesavananda Bharati v. State of Kerala",
    "citation": "(1973) 4 SCC 225",
    "court": "Supreme Court of India",
    "year": 1973,
    "case_type": "Writ Petition",
    "bench_type": "Constitution Bench",
    "judges": ["Justice S.M. Sikri", "Justice J.M. Shelat", ...],
    "author_judge": "Justice S.M. Sikri",
    "petitioner": "Kesavananda Bharati",
    "respondent": "State of Kerala",
    "decision_date": "1973-04-24",
    "disposal_nature": "Partly Allowed",
    "ratio_decidendi": "Parliament's power to amend the Constitution under Article 368 does not include the power to destroy its basic structure.",
    "acts_cited": ["Constitution of India - Article 368", "Constitution of India - Article 13"],
    "cases_cited": ["Golaknath v. State of Punjab (1967)", "Shankari Prasad v. Union of India (1951)"],
    "cited_by_count": 2341,
    "keywords": ["basic structure", "constitutional amendment", "fundamental rights"],
    "pdf_url": "/api/v1/cases/uuid/pdf",
    "language": "english",
    "available_languages": ["english", "hindi"]
}
```

#### `GET /api/v1/cases/{case_id}/sections`

**Response (200):**
```json
{
    "sections": [
        {"type": "facts", "title": "Facts of the Case", "content": "...", "start_page": 1},
        {"type": "arguments_petitioner", "title": "Arguments (Petitioner)", "content": "...", "start_page": 5},
        {"type": "arguments_respondent", "title": "Arguments (Respondent)", "content": "...", "start_page": 12},
        {"type": "analysis", "title": "Analysis", "content": "...", "start_page": 18},
        {"type": "ratio_decidendi", "title": "Ratio Decidendi", "content": "...", "start_page": 45},
        {"type": "order", "title": "Order", "content": "...", "start_page": 50}
    ]
}
```

#### `GET /api/v1/cases/{case_id}/cited-by?page_size=20&cursor=`

#### `GET /api/v1/cases/{case_id}/cites`

#### `GET /api/v1/cases/{case_id}/pdf` — returns PDF file stream

### 2.3 Chat API

#### `POST /api/v1/chat` — New session + first message (SSE stream)

**Request:**
```json
{
    "message": "What are the key Supreme Court judgments on the right to be forgotten under Article 21?"
}
```

**Response (SSE stream):**
```
data: {"type": "session", "session_id": "uuid", "title": "Right to be forgotten"}

data: {"type": "chunk", "content": "The right to be forgotten has been "}
data: {"type": "chunk", "content": "recognized by Indian courts in several "}
data: {"type": "chunk", "content": "key judgments:\n\n"}
data: {"type": "chunk", "content": "1. **Justice K.S. Puttaswamy v. Union of India** "}
data: {"type": "source", "case_id": "uuid", "citation": "(2017) 10 SCC 1", "title": "K.S. Puttaswamy v. Union of India"}
data: {"type": "chunk", "content": "established privacy as a fundamental right..."}
data: {"type": "done", "tokens_used": 1250, "sources": [...]}
```

#### `POST /api/v1/chat/{session_id}` — Continue conversation (SSE stream)

#### `GET /api/v1/chat/sessions` — List user's sessions

#### `DELETE /api/v1/chat/{session_id}` — Delete session + messages

### 2.4 Graph API

#### `GET /api/v1/graph/{case_id}?depth=2`

**Response (200):**
```json
{
    "nodes": [
        {"id": "uuid", "title": "Case A", "citation": "...", "court": "...", "year": 2020, "cited_by_count": 50},
        {"id": "uuid2", "title": "Case B", "citation": "...", "court": "...", "year": 2015, "cited_by_count": 200}
    ],
    "edges": [
        {"from": "uuid", "to": "uuid2", "type": "cites", "context": "Relied upon the ratio in..."},
        {"from": "uuid3", "to": "uuid", "type": "overrules", "context": "The reasoning in Case A is no longer good law..."}
    ]
}
```

### 2.5 Ingest API

#### `POST /api/v1/ingest/upload` — multipart/form-data

#### `GET /api/v1/ingest/status/{doc_id}`

### 2.6 Auth API

#### `POST /api/v1/auth/register`
```json
{"email": "user@firm.com", "password": "...", "name": "Advocate Name"}
```

#### `POST /api/v1/auth/login`
```json
{"email": "user@firm.com", "password": "..."}
→ {"access_token": "jwt...", "refresh_token": "jwt...", "expires_in": 900}
```

#### `POST /api/v1/auth/refresh`
```json
{"refresh_token": "jwt..."}
→ {"access_token": "jwt...", "refresh_token": "new-jwt...", "expires_in": 900}
```

#### `DELETE /api/v1/auth/account` — Right to erasure (DPDP Act)

Deletes: user record, chat history, uploaded documents, audit logs (anonymized), consent records.

### 2.7 Error Format (All Endpoints)

```json
{
    "error": "Human-readable message",
    "code": "CASE_NOT_FOUND",
    "details": {"case_id": "uuid"}
}
```

| HTTP Status | Code | Meaning |
|------------|------|---------|
| 400 | VALIDATION_ERROR | Invalid request body |
| 401 | UNAUTHORIZED | Missing or invalid token |
| 403 | FORBIDDEN | Insufficient role |
| 404 | NOT_FOUND | Resource doesn't exist |
| 429 | RATE_LIMITED | Too many requests |
| 500 | INTERNAL_ERROR | Server error |

---

## 3. Frontend Component Tree

```
app/
├── layout.tsx (RootLayout)
│   ├── Providers (QueryClientProvider, ThemeProvider)
│   ├── Navbar
│   │   ├── Logo (link to /)
│   │   ├── SearchBar (compact, always visible)
│   │   ├── NavLinks (Search, Chat, Graph)
│   │   └── UserMenu (login/logout, profile)
│   └── {children}
│
├── page.tsx (HomePage)
│   ├── HeroSection
│   │   ├── HeroSearch (large search bar + example queries)
│   │   └── StatsBar (35K+ cases, 25 courts, etc.)
│   └── RecentCasesGrid (latest ingested cases)
│
├── search/page.tsx (SearchPage)
│   ├── SearchBar (full-width, with query + submit)
│   ├── ActiveFilters (pills showing applied filters)
│   ├── Layout: [FilterSidebar | SearchResults]
│   │   ├── FilterSidebar
│   │   │   ├── CourtFilter (checkbox list + count)
│   │   │   ├── YearRangeSlider
│   │   │   ├── CaseTypeFilter (checkbox list)
│   │   │   ├── BenchTypeFilter
│   │   │   └── JudgeFilter (searchable dropdown)
│   │   └── SearchResults
│   │       ├── ResultsHeader (count, sort toggle)
│   │       ├── CaseCard[] (per result)
│   │       │   ├── CaseTitle (clickable link)
│   │       │   ├── CitationBadge
│   │       │   ├── CourtYearBadge
│   │       │   ├── SnippetText (highlighted matches)
│   │       │   ├── RelevanceScore (bar)
│   │       │   └── CitedByCount
│   │       └── Pagination (cursor-based load more)
│   └── QueryUnderstanding (shows parsed intent/entities)
│
├── case/[id]/page.tsx (CaseDetailPage)
│   ├── CaseHeader
│   │   ├── Title
│   │   ├── CitationBadge
│   │   ├── CourtBadge
│   │   └── DateBadge
│   ├── MetadataPanel (collapsible sidebar or top strip)
│   │   ├── Judges (with author highlighted)
│   │   ├── Parties (petitioner v. respondent)
│   │   ├── CaseType + BenchType + Jurisdiction
│   │   ├── DisposalNature
│   │   └── Keywords (tag pills)
│   ├── TabView
│   │   ├── SectionsTab
│   │   │   └── JudgmentSection[] (color-coded by type)
│   │   │       ├── SectionHeader (Facts/Arguments/Ratio/Order)
│   │   │       └── SectionContent (text with paragraph numbers)
│   │   ├── PDFTab
│   │   │   └── PDFViewer (react-pdf or iframe)
│   │   ├── CitationsTab
│   │   │   ├── ActsCitedList (statute + section)
│   │   │   ├── CasesCitedList (clickable links)
│   │   │   └── CitedByList (clickable links + count)
│   │   └── GraphTab
│   │       └── MiniCitationGraph (depth=1, expandable)
│   └── RelatedCases (based on similarity)
│
├── chat/page.tsx (ChatPage)
│   ├── Layout: [SessionSidebar | ChatArea]
│   │   ├── SessionSidebar
│   │   │   ├── NewSessionButton
│   │   │   └── SessionList[]
│   │   │       └── SessionItem (title, date, delete)
│   │   └── ChatArea
│   │       ├── MessageList
│   │       │   ├── UserMessage (text + timestamp)
│   │       │   └── AssistantMessage
│   │       │       ├── StreamingText
│   │       │       └── SourceCitations[]
│   │       │           └── CitationBadge (clickable → case page)
│   │       └── ChatInput
│   │           ├── TextArea (auto-resize)
│   │           ├── SendButton
│   │           └── ExampleQueries (shown when empty)
│
├── graph/page.tsx (GraphExplorerPage)
│   ├── GraphSearchBar (find case to center on)
│   ├── Layout: [GraphCanvas | NodeDetail]
│   │   ├── GraphCanvas (d3 force-directed)
│   │   │   ├── JudgmentNode[] (circles, sized by authority)
│   │   │   └── CitationEdge[] (colored by type)
│   │   ├── GraphControls
│   │   │   ├── DepthSlider (1-3)
│   │   │   ├── EdgeTypeFilter (checkboxes)
│   │   │   └── CourtFilter
│   │   └── NodeDetail (sidebar on node click)
│   │       ├── CaseTitle
│   │       ├── QuickMetadata
│   │       └── ViewCaseButton
│
├── upload/page.tsx (UploadPage)
│   ├── DropZone (drag & drop or file picker)
│   ├── UploadQueue
│   │   └── UploadItem[] (filename, progress, status)
│   └── ProcessedDocuments (list of user's uploads)
│
├── auth/
│   ├── login/page.tsx (LoginForm)
│   └── register/page.tsx (RegisterForm)
│
└── components/ui/  (shadcn/ui primitives: Button, Input, Card, Badge, etc.)
```

### State Management

- **TanStack Query** for all server state
- Query keys:
  - `['search', query, filters]` — search results
  - `['case', id]` — case detail
  - `['case', id, 'sections']` — case sections
  - `['case', id, 'cited-by']` — citing cases
  - `['chat', 'sessions']` — session list
  - `['chat', sessionId, 'messages']` — messages
  - `['graph', caseId, depth]` — graph data
  - `['facets']` — filter facet values
- **Optimistic updates** for chat messages (show user message immediately)
- No global state library needed for MVP
- Use `useState` for local UI state (filter toggles, tab selection)

---

## 4. File Upload Pipeline

```
User drops PDF
  → Frontend: validate type (PDF only) + size (< 50MB)
  → POST /api/v1/ingest/upload (multipart/form-data)
  → Backend:
    1. Validate MIME type (application/pdf)
    2. Generate UUID, store to GCS/local
    3. Create `documents` row (status: pending)
    4. Return doc_id immediately (202 Accepted)
    5. Background task:
       a. Extract text (pdfplumber + Tesseract OCR fallback)
       b. Detect sections (Facts, Ratio, Order)
       c. Extract metadata (Gemini structured output)
       d. Create `cases` row with extracted metadata
       e. Chunk text (legal-aware, 2000 chars, 200 overlap)
       f. Generate embeddings (Gemini gemini-embedding-001)
       g. Upsert to Pinecone
       h. Extract citations → create Neo4j edges
       i. Update `documents` row (status: completed, case_id: linked)
  → Frontend polls GET /api/v1/ingest/status/{doc_id} every 5s
  → On complete: show metadata for user review
```

---

## 5. Prompt Templates Location

All prompts live in `backend/app/core/legal/prompts.py` as string constants. See `PROMPT_LIBRARY.md` for the full catalog. Structure:

```python
# prompts.py

QUERY_UNDERSTANDING_SYSTEM = """..."""
QUERY_UNDERSTANDING_USER = """..."""

METADATA_EXTRACTION_SYSTEM = """..."""
METADATA_EXTRACTION_USER = """..."""

CHAT_SYSTEM = """..."""
CHAT_USER_WITH_CONTEXT = """..."""

SECTION_DETECTION_SYSTEM = """..."""
```

Each prompt has:
1. System message (role, constraints, output format)
2. User message template with `{variable}` placeholders
3. Few-shot examples where needed (embedded in system message)
