# Smriti — Low-Level Design (LLD)

---

## 1. Database Schemas

### 1.1 PostgreSQL Tables

#### `cases` — Judgment Metadata (Primary Table)

52 columns as of migration 014. SQLAlchemy model: `backend/app/models/case.py`

```sql
CREATE TABLE cases (
    -- Core identity (6 columns)
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    citation        VARCHAR(255),                    -- Primary citation, e.g. "(2017) 10 SCC 1"
    case_id         VARCHAR(100),                    -- Original case number (CA 123/2024)
    cnr             VARCHAR(50),                     -- Case Number Register (AAAA + 14 digits)
    case_number     VARCHAR(200),                    -- Formal case number (migration 009)

    -- Court & bench (4 columns)
    court           VARCHAR(100) NOT NULL,
    year            INTEGER,
    case_type       VARCHAR(50),                     -- Criminal Appeal, Writ Petition, PIL, SLP, etc.
    jurisdiction    VARCHAR(50),                     -- Criminal, Civil, Constitutional
    bench_type      VARCHAR(30),                     -- Constitution Bench, Division Bench, Single Judge

    -- People (4 columns)
    judge           TEXT[],                          -- Array of judge names
    author_judge    VARCHAR(255),                    -- Judge who authored the judgment
    petitioner      TEXT,
    respondent      TEXT,

    -- Decision metadata (3 columns)
    decision_date   DATE,
    disposal_nature VARCHAR(50),                     -- Allowed, Dismissed, Partly Allowed, etc. (13 values)
    is_reportable   BOOLEAN,                         -- Whether judgment is reportable (migration 009)

    -- Content (6 columns)
    description     TEXT,                            -- Brief case description
    keywords        TEXT[],                          -- Legal keywords
    ratio_decidendi TEXT,                            -- Extracted core legal principle
    headnotes       TEXT,                            -- Headnote summary (migration 009)
    outcome_summary TEXT,                            -- Brief outcome description (migration 009)
    full_text       TEXT,                            -- Complete judgment text (deferred load in ORM)

    -- Citations (3 columns)
    acts_cited      TEXT[],                          -- Statutes referenced
    cases_cited     TEXT[],                          -- Citations of cases referenced in judgment
    cited_by_count  INTEGER NOT NULL DEFAULT 0,      -- Number of cases citing this one (migration 012)

    -- Search (2 columns)
    searchable_text TSVECTOR,                        -- Weighted FTS index (auto-maintained by trigger)
    language        VARCHAR(20) NOT NULL DEFAULT 'english',
    available_languages TEXT[],

    -- Storage & ingestion (5 columns)
    pdf_storage_path VARCHAR(512),                   -- GCS path or local path
    s3_source_path  VARCHAR(512),                    -- Original S3 location
    source          VARCHAR(30) NOT NULL DEFAULT 'aws_open_data',  -- aws_open_data | manual_upload | indiankanoon
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    ingestion_status VARCHAR(20) NOT NULL DEFAULT 'complete',  -- pending | processing | complete | failed | vectors_failed | needs_review

    -- Opinion & bench composition (migration 011, 7 columns)
    coram_size      INTEGER,                         -- Number of judges on bench
    opinion_type    VARCHAR(30),                     -- unanimous | majority | plurality | per_curiam
    dissenting_judges TEXT[],                        -- Judges who dissented
    concurring_judges TEXT[],                        -- Judges who concurred separately
    split_ratio     VARCHAR(20),                     -- e.g. "3:2" for split decisions

    -- Appellate chain (migration 011, 3 columns)
    lower_court     VARCHAR(200),                    -- Court appealed from
    lower_court_case_number VARCHAR(200),             -- Lower court case number
    appeal_from     VARCHAR(200),                    -- Type of lower court/tribunal

    -- Party classification (migration 011, 3 columns)
    petitioner_type VARCHAR(50),                     -- individual | government_central | government_state | PSU | company | NGO | statutory_body | other
    respondent_type VARCHAR(50),                     -- (same values as petitioner_type)
    is_pil          BOOLEAN,                         -- Public Interest Litigation flag

    -- Related cases (migration 011, 1 column)
    companion_cases TEXT[],                          -- Related case citations

    -- Enterprise readiness (migration 013, 3 columns)
    metadata_provenance JSONB,                       -- Source/quality tracking for metadata fields
    extraction_confidence FLOAT,                     -- ML extraction confidence score (0.0-1.0)
    text_hash       VARCHAR(64),                     -- SHA-256 hash of normalized full_text for dedup

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- CHECK constraints
    CONSTRAINT ck_cases_year_range CHECK (year >= 1800 AND year <= 2200),
    CONSTRAINT ck_cases_ingestion_status CHECK (
        ingestion_status IN ('pending', 'processing', 'complete', 'failed', 'vectors_failed', 'needs_review')
    ),
    CONSTRAINT ck_cases_opinion_type CHECK (
        opinion_type IN ('unanimous', 'majority', 'plurality', 'per_curiam') OR opinion_type IS NULL
    ),
    CONSTRAINT ck_cases_coram_size CHECK (coram_size > 0 OR coram_size IS NULL),
    CONSTRAINT ck_cases_petitioner_type CHECK (
        petitioner_type IN ('individual', 'government_central', 'government_state', 'PSU', 'company', 'NGO', 'statutory_body', 'other')
        OR petitioner_type IS NULL
    ),
    CONSTRAINT ck_cases_respondent_type CHECK (
        respondent_type IN ('individual', 'government_central', 'government_state', 'PSU', 'company', 'NGO', 'statutory_body', 'other')
        OR respondent_type IS NULL
    ),
    CONSTRAINT ck_cases_disposal_nature CHECK (
        disposal_nature IN (
            'Allowed', 'Dismissed', 'Partly Allowed', 'Withdrawn', 'Remanded',
            'Disposed Of', 'Settled', 'Transferred', 'Modified', 'Other',
            'Referred to Larger Bench', 'Abated', 'Not Pressed'
        ) OR disposal_nature IS NULL
    )
);

-- Primary lookups
CREATE UNIQUE INDEX ix_cases_citation_unique ON cases(citation) WHERE citation IS NOT NULL;

-- Single-column filter indexes
CREATE INDEX ix_cases_court ON cases(court);
CREATE INDEX ix_cases_year ON cases(year);
CREATE INDEX ix_cases_case_type ON cases(case_type);
CREATE INDEX ix_cases_jurisdiction ON cases(jurisdiction);
CREATE INDEX ix_cases_bench_type ON cases(bench_type);
CREATE INDEX ix_cases_source ON cases(source);
CREATE INDEX ix_cases_ingestion_status ON cases(ingestion_status);
CREATE INDEX ix_cases_disposal_nature ON cases(disposal_nature);
CREATE INDEX ix_cases_opinion_type ON cases(opinion_type);
CREATE INDEX ix_cases_is_pil ON cases(is_pil);
CREATE INDEX ix_cases_coram_size ON cases(coram_size);

-- Composite indexes (common filter combinations)
CREATE INDEX ix_cases_court_year ON cases(court, year);
CREATE INDEX ix_cases_year_case_type ON cases(year, case_type);
CREATE INDEX ix_cases_court_case_type ON cases(court, case_type);

-- GIN indexes for array columns
CREATE INDEX ix_cases_keywords_gin ON cases USING GIN(keywords);
CREATE INDEX ix_cases_acts_cited_gin ON cases USING GIN(acts_cited);
CREATE INDEX ix_cases_cases_cited_gin ON cases USING GIN(cases_cited);
CREATE INDEX ix_cases_judge_gin ON cases USING GIN(judge);

-- Full-text search
CREATE INDEX ix_cases_searchable_text_gin ON cases USING GIN(searchable_text);

-- Trigram indexes (pg_trgm extension) for fuzzy text matching / auto-suggest
CREATE INDEX idx_cases_citation_trgm ON cases USING GIN(citation gin_trgm_ops);
CREATE INDEX idx_cases_title_trgm ON cases USING GIN(title gin_trgm_ops);

-- Authority ranking
CREATE INDEX idx_cases_cited_by_count ON cases(cited_by_count DESC);

-- Dedup
CREATE UNIQUE INDEX idx_cases_text_hash ON cases(text_hash) WHERE text_hash IS NOT NULL;

-- FTS trigger (migration 014 — single merged trigger replacing earlier dual triggers)
CREATE OR REPLACE FUNCTION cases_searchable_text_update() RETURNS TRIGGER AS $$
BEGIN
    NEW.searchable_text :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.citation, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.case_number, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.court, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.judge, ' '), '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.petitioner, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.respondent, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.headnotes, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.outcome_summary, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D') ||
        setweight(to_tsvector('english', COALESCE(LEFT(NEW.full_text, 500000), '')), 'D');
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER cases_searchable_text_trigger
    BEFORE INSERT OR UPDATE ON cases
    FOR EACH ROW EXECUTE FUNCTION cases_searchable_text_update();
```

#### `case_sections` — Judgment Sections

SQLAlchemy model: `backend/app/models/case_section.py`

```sql
CREATE TABLE case_sections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    section_type        VARCHAR(50) NOT NULL,           -- facts, arguments, ratio_decidendi, order, dissent, concurrence
    content             TEXT NOT NULL,
    section_index       INTEGER NOT NULL DEFAULT 0,     -- Order within the judgment
    summary             TEXT,                           -- Optional section summary
    searchable_content  TSVECTOR                        -- FTS index on section content (migration 012)
);

CREATE INDEX ix_case_sections_case_id ON case_sections(case_id);
CREATE INDEX ix_case_sections_case_type ON case_sections(case_id, section_type);
CREATE INDEX idx_case_sections_fts ON case_sections USING GIN(searchable_content);
CREATE INDEX ix_case_sections_content_gin ON case_sections USING GIN(to_tsvector('english', content));

-- Auto-populate searchable_content (migration 012)
CREATE OR REPLACE FUNCTION case_sections_searchable_update() RETURNS TRIGGER AS $$
BEGIN
    NEW.searchable_content :=
        to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER case_sections_searchable_trigger
    BEFORE INSERT OR UPDATE ON case_sections
    FOR EACH ROW EXECUTE FUNCTION case_sections_searchable_update();
```

#### `case_citation_equivalents` — Citation Cross-References

SQLAlchemy model: `backend/app/models/case_citation_equivalent.py`

```sql
CREATE TABLE case_citation_equivalents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    reporter        VARCHAR(50) NOT NULL,              -- SCC, AIR, SCR, MANU, JT, etc.
    citation_text   VARCHAR(200) NOT NULL,             -- e.g. "(2017) 10 SCC 1"
    year            INTEGER,                           -- Citation year

    CONSTRAINT uq_reporter_citation UNIQUE (reporter, citation_text)
);

CREATE INDEX ix_case_citation_equivalents_case_id ON case_citation_equivalents(case_id);
CREATE INDEX ix_citation_text ON case_citation_equivalents(citation_text);
```

#### `users` — User Accounts

SQLAlchemy model: `backend/app/models/user.py`

```sql
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(254) NOT NULL UNIQUE,   -- Encrypted at app layer (AES-256-GCM)
    password_hash       VARCHAR(255) NOT NULL,          -- bcrypt cost factor 12
    name                VARCHAR(255),
    role                VARCHAR(20) NOT NULL DEFAULT 'researcher',
    is_active           BOOLEAN NOT NULL DEFAULT true,
    failed_login_count  INTEGER NOT NULL DEFAULT 0,
    locked_until        TIMESTAMPTZ,
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_users_role CHECK (role IN ('admin', 'researcher', 'viewer'))
);

-- email column has implicit unique index from UNIQUE constraint
```

#### `chat_sessions` — Conversation Sessions

SQLAlchemy model: `backend/app/models/chat.py` (`ChatSession`)

```sql
CREATE TABLE chat_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL DEFAULT 'New Research Session',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_chat_sessions_user_id ON chat_sessions(user_id);
```

#### `chat_messages` — Individual Messages

SQLAlchemy model: `backend/app/models/chat.py` (`ChatMessage`)

```sql
CREATE TABLE chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL,
    content     TEXT NOT NULL,
    sources     JSONB,                              -- [{case_id, title, citation, score}]
    tokens_used INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_chat_messages_role CHECK (role IN ('user', 'assistant'))
);

CREATE INDEX ix_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX ix_chat_messages_session_created ON chat_messages(session_id, created_at DESC);
```

#### `documents` — User-Uploaded Documents

SQLAlchemy model: `backend/app/models/document.py`

```sql
CREATE TABLE documents (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename                VARCHAR(255) NOT NULL,
    storage_path            VARCHAR(512) NOT NULL,
    file_size               INTEGER,
    mime_type               VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message           TEXT,
    processing_step         VARCHAR(50),                  -- Current pipeline step (e.g. extracting_text, finding_arguments)
    processing_started_at   TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    case_id                 UUID REFERENCES cases(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_documents_status CHECK (
        status IN ('pending', 'extracting', 'analyzing', 'searching', 'generating', 'completed', 'failed')
    )
);

CREATE INDEX ix_documents_user_id ON documents(user_id);
CREATE INDEX ix_documents_case_id ON documents(case_id);
```

#### `document_analyses` — Document Analysis Results

SQLAlchemy model: `backend/app/models/document_analysis.py`

```sql
CREATE TABLE document_analyses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE UNIQUE,
    extracted_text  TEXT,                               -- Raw text extracted from PDF
    issues          JSONB,                              -- [{title, description}]
    parties         JSONB,                              -- {petitioner, respondent}
    key_facts       TEXT,                               -- Key facts (plain text, not array)
    relief_sought   TEXT,                               -- Relief sought by petitioner
    counter_arguments JSONB,                            -- [{issue_title, arguments: [{argument, response}]}]
    research_memo   TEXT,                               -- Generated research memo (Markdown)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### `audio_digests` — Audio Digests (TTS)

SQLAlchemy model: `backend/app/models/audio_digest.py`

```sql
CREATE TABLE audio_digests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    language            TEXT NOT NULL,                   -- 'en', 'hi', etc.
    summary_text        TEXT,                            -- Generated summary used for TTS
    audio_storage_path  TEXT,                            -- GCS/local path to MP3 file
    duration_seconds    INTEGER,
    status              TEXT NOT NULL DEFAULT 'generating',
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_audio_digests_case_language UNIQUE (case_id, language),
    CONSTRAINT ck_audio_digests_status CHECK (status IN ('generating', 'completed', 'failed'))
);
```

#### `audit_logs` — Security Audit Trail

SQLAlchemy model: `backend/app/models/audit.py`

Note: This model does NOT use `UUIDPrimaryKeyMixin` or `TimestampMixin`. It uses `BIGSERIAL` for the PK and manages `created_at` directly.

```sql
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,                   -- search, view_case, chat, upload, login, logout, delete
    resource_type   TEXT,                            -- case, document, session, user
    resource_id     TEXT,
    ip_address      TEXT,                            -- Stored as text (not INET) in ORM
    user_agent      TEXT,
    metadata        JSONB,                           -- Extra context (query text, filters, etc.)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX ix_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX ix_audit_logs_action ON audit_logs(action);
```

#### `consents` — DPDP Act Compliance

SQLAlchemy model: `backend/app/models/consent.py`

```sql
CREATE TABLE consents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consent_type    TEXT NOT NULL,                   -- data_processing, analytics, marketing
    granted         BOOLEAN NOT NULL,
    version         TEXT NOT NULL DEFAULT '1.0',
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_consents_user_id ON consents(user_id);
```

#### `dpdp_audit_log` — DPDP-Specific Audit Trail (Migration 007)

Compliance-mandated record of data operations under the Digital Personal Data Protection Act. Separate from the general `audit_logs` table for regulatory isolation.

```sql
CREATE TABLE dpdp_audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action      VARCHAR(50) NOT NULL,               -- data_access, data_deletion, consent_change, etc.
    user_id     UUID,                                -- No FK constraint (user may be deleted)
    details     JSON DEFAULT '{}',                   -- Context about the operation
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

#### `agent_executions` — Agent Run Tracking (Migration 005)

SQLAlchemy model: `backend/app/models/agent_execution.py`

Tracks LangGraph agent execution lifecycle. Each row represents one agent run (research, case prep, strategy, or drafting).

```sql
CREATE TABLE agent_executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_type      VARCHAR(20) NOT NULL,              -- research | case_prep | strategy | drafting
    status          VARCHAR(20) NOT NULL DEFAULT 'running',  -- running | waiting_input | completed | failed | cancelled
    input_data      JSONB,                             -- Agent input parameters (query, case_id, etc.)
    result_data     JSONB,                             -- Agent output (memo, analysis, draft, etc.)
    thread_id       UUID NOT NULL,                     -- LangGraph thread ID for checkpoint recovery
    current_step    VARCHAR(100),                      -- Current node in the agent graph
    steps_completed INTEGER NOT NULL DEFAULT 0,        -- Progress counter
    total_steps     INTEGER,                           -- Expected total steps (null if unknown)
    completed_at    TIMESTAMPTZ,                       -- When agent finished (success or failure)
    error_message   TEXT,                              -- Error details on failure
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_agent_executions_agent_type CHECK (
        agent_type IN ('research', 'case_prep', 'strategy', 'drafting')
    ),
    CONSTRAINT ck_agent_executions_status CHECK (
        status IN ('running', 'waiting_input', 'completed', 'failed', 'cancelled')
    )
);

CREATE INDEX ix_agent_executions_user_id ON agent_executions(user_id);
CREATE INDEX ix_agent_executions_status ON agent_executions(status);
```

#### `legal_synonyms` — Legal Abbreviation Synonyms (Migration 012)

Application-level synonym dictionary for expanding legal abbreviation queries during FTS. Used by the query expansion layer (not a PostgreSQL text search dictionary).

```sql
CREATE TABLE legal_synonyms (
    id          SERIAL PRIMARY KEY,
    term        TEXT NOT NULL UNIQUE,               -- Abbreviation or short form (e.g. 'IPC', 'CrPC')
    synonyms    TEXT[] NOT NULL                     -- Array of equivalent terms
);
```

Seeded with 28 common Indian legal abbreviations including:
- Statute mappings: IPC/BNS, CrPC/BNSS, CPC, IEA/BSA
- Court abbreviations: SC, HC
- Reporter abbreviations: AIR, SCC, MANU
- Tribunal abbreviations: NCLAT, NCLT, DRT, SAT, ITAT, CESTAT, CAT, NGT
- Legal term abbreviations: PIL, FIR, SLP, RTI, RERA, POCSO, PMLA, NDPS, NIA

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
**Rate limit**: 30/min (search), 60/min (suggest), 30/min (facets)

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

Deletes: user record, chat history, uploaded documents, audit logs (anonymized), consents.

### 2.7 Document Upload API (Phase 5)

#### `POST /api/v1/documents/upload` — Upload PDF for analysis

Upload a PDF document (multipart/form-data, max 50 MB) to trigger the analysis pipeline.

**Response (202):**
```json
{
    "id": "uuid",
    "filename": "arbitration_clause_dispute.pdf",
    "status": "pending"
}
```

#### `GET /api/v1/documents` — List user's documents (paginated)

**Query parameters:** `page` (default 1), `page_size` (default 20)

**Response (200):**
```json
{
    "items": [
        {
            "id": "uuid",
            "filename": "arbitration_clause_dispute.pdf",
            "status": "completed",
            "created_at": "2026-03-07T10:30:00Z"
        }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20
}
```

#### `GET /api/v1/documents/{id}` — Document detail + analysis

**Response (200):**
```json
{
    "id": "uuid",
    "filename": "arbitration_clause_dispute.pdf",
    "status": "completed",
    "analysis": {
        "issues": [
            {"title": "Validity of arbitration clause", "description": "Whether the arbitration clause in the agreement is enforceable..."}
        ],
        "parties": {"petitioner": "ABC Corp", "respondent": "XYZ Ltd"},
        "key_facts": ["Agreement executed on 2024-01-15", "Clause 12 contains arbitration provision"],
        "counter_arguments": [
            {
                "issue_title": "Validity of arbitration clause",
                "arguments": [
                    {"argument": "Clause is unconscionable", "response": "Supreme Court in Centrotrade held..."}
                ]
            }
        ]
    }
}
```

#### `DELETE /api/v1/documents/{id}` — Delete document + analysis

**Response:** `204 No Content`

#### `GET /api/v1/documents/{id}/memo` — Get research memo

**Response (200):**
```json
{
    "memo": "# Research Memo\n\n## Issues Identified\n\n..."
}
```

### 2.8 Audio Digest API (Phase 5)

#### `POST /api/v1/cases/{id}/audio/generate` — Trigger audio generation

**Request:**
```json
{
    "language": "en"
}
```

**Response (202):**
```json
{
    "status": "generating",
    "case_id": "uuid",
    "language": "en"
}
```

Supported languages: `"en"` (English), `"hi"` (Hindi). Additional Indian languages available via Sarvam AI TTS.

#### `GET /api/v1/cases/{id}/audio/status` — Check audio availability

**Response (200):**
```json
{
    "available": true,
    "languages": [
        {"language": "en", "status": "completed", "duration_seconds": 187},
        {"language": "hi", "status": "generating", "duration_seconds": null}
    ]
}
```

#### `GET /api/v1/cases/{id}/audio` — Stream audio MP3

**Query parameters:** `language` (default `"en"`)

**Response:** `audio/mpeg` stream (binary MP3 data)

Returns `404` if audio not yet generated for the requested language.

### 2.9 Agents API

Routes: `backend/app/api/routes/agents.py`

#### `POST /api/v1/agents/{agent_type}/run` — Start agent execution (SSE stream)

Starts a LangGraph agent and streams progress events via SSE. Supports HITL (human-in-the-loop) checkpoints where the agent pauses for user input.

**Path parameter:** `agent_type` — one of `research`, `case_prep`, `strategy`, `drafting`

**Request:**
```json
{
    "query": "What are the grounds for challenging an arbitration award under Section 34?",
    "case_id": "uuid"
}
```

**Response (SSE stream):**
```
data: {"type": "status", "execution_id": "uuid", "step": "searching"}
data: {"type": "progress", "step": "analyzing_results", "steps_completed": 2, "total_steps": 5}
data: {"type": "checkpoint", "execution_id": "uuid", "prompt": "I found 12 cases. Should I focus on...", "options": [...]}
data: {"type": "memo", "content": "# Research Memo\n\n..."}
data: {"type": "done", "execution_id": "uuid"}
```

**Auth:** Required (JWT)

#### `POST /api/v1/agents/{execution_id}/resume` — Resume agent after checkpoint

Provides user input to a paused agent execution.

**Request:**
```json
{
    "input": "Focus on Section 34(2)(b) grounds"
}
```

**Response:** SSE stream (same format as `/run`)

#### `GET /api/v1/agents/executions` — List user's agent executions

**Query parameters:** `agent_type` (optional filter), `page` (default 1), `page_size` (default 20)

**Response (200):**
```json
{
    "items": [
        {
            "id": "uuid",
            "agent_type": "research",
            "status": "completed",
            "current_step": null,
            "steps_completed": 5,
            "total_steps": 5,
            "created_at": "2026-03-10T14:30:00Z",
            "completed_at": "2026-03-10T14:32:00Z"
        }
    ],
    "total": 12
}
```

#### `GET /api/v1/agents/{execution_id}` — Get execution detail + result

#### `GET /api/v1/agents/drafting/templates` — List available drafting templates

#### `POST /api/v1/agents/drafting/{execution_id}/export` — Export draft to DOCX/PDF

**Query parameters:** `format` — `docx` or `pdf`

**Response:** Binary file download

### 2.10 Error Format (All Endpoints)

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
