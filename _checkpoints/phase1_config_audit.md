# Phase 1: Configuration & Environment Audit

**Date**: 2026-04-03
**Auditor**: Claude (automated)
**Repo**: D:/Startup/Smriti (branch: master)

---

## CRITICAL SECURITY FINDING

**`ingestion/accounts/env_template` contains real production credentials** -- database passwords, Pinecone API keys, and Neo4j credentials are hardcoded in a tracked file. This MUST be rotated and the file cleaned before any public exposure. The file should contain only placeholders.

---

## Environment Variables

### Backend (`backend/.env.example` + `backend/app/core/config.py`)

| Variable | Purpose | Service | Secret? | Required? |
|---|---|---|---|---|
| `APP_NAME` | Application identifier | FastAPI | No | No (default: `smriti`) |
| `APP_ENV` | Environment mode (`development`/`production`/`test`) | FastAPI | No | Yes |
| `APP_DEBUG` | Enable debug mode (must be false in prod) | FastAPI | No | No (default: `false`) |
| `APP_HOST` | Server bind address | FastAPI | No | No (default: `0.0.0.0`) |
| `APP_PORT` | Server bind port | FastAPI | No | No (default: `8000`) |
| `APP_VERSION` | Semver version string | FastAPI | No | No (default: `0.1.0`) |
| `CORS_ORIGINS` | Comma-separated allowed origins (no `*` in prod) | FastAPI | No | Yes |
| `JWT_SECRET_KEY` | Access token signing key (min 32 chars in prod) | Auth | **Yes** | **Yes (prod)** |
| `JWT_REFRESH_SECRET_KEY` | Refresh token signing key (min 32 chars in prod) | Auth | **Yes** | **Yes (prod)** |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | Auth | No | No (default: `60`) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | Auth | No | No (default: `7`) |
| `BCRYPT_COST_FACTOR` | Password hashing rounds | Auth | No | No (default: `12`) |
| `ENCRYPTION_KEY` | AES-256 key for PII encryption (min 32 chars in prod) | Auth | **Yes** | **Yes (prod)** |
| `DATABASE_URL` | PostgreSQL async connection string | PostgreSQL | **Yes** | Yes |
| `DATABASE_POOL_SIZE` | Connection pool size | PostgreSQL | No | No (default: `30`) |
| `DATABASE_MAX_OVERFLOW` | Extra connections above pool | PostgreSQL | No | No (default: `20`) |
| `DATABASE_POOL_RECYCLE` | Connection recycle time (seconds) | PostgreSQL | No | No (default: `1800`) |
| `DATABASE_POOL_TIMEOUT` | Connection acquisition timeout | PostgreSQL | No | No (default: `30`) |
| `DATABASE_SSL_MODE` | SSL mode (`prefer` dev, `require` prod) | PostgreSQL | No | No |
| `REDIS_URL` | Redis connection string | Redis | **Yes** (if password) | Yes |
| `CELERY_BROKER_URL` | Celery message broker | Celery/Redis | **Yes** | No (default: `redis://localhost:6379/1`) |
| `CELERY_RESULT_BACKEND` | Celery result store | Celery/Redis | **Yes** | No (default: `redis://localhost:6379/1`) |
| `LLM_PROVIDER` | LLM provider selection | Gemini | No | No (default: `gemini`) |
| `GEMINI_API_KEY` | Google AI Studio API key | Gemini | **Yes** | **Yes (prod, unless Vertex)** |
| `GEMINI_API_KEYS` | Comma-separated keys for round-robin | Gemini | **Yes** | No |
| `GEMINI_MODEL` | Primary reasoning model | Gemini | No | No (default: `gemini-2.5-pro`) |
| `GEMINI_FLASH_MODEL` | Fast/cheap model for ingestion | Gemini | No | No (default: `gemini-2.5-flash`) |
| `GEMINI_EMBEDDING_MODEL` | Embedding model name | Gemini | No | No (default: `gemini-embedding-2-preview`) |
| `GEMINI_EMBEDDING_DIMENSION` | Embedding vector dimension | Gemini | No | No (default: `1536`) |
| `GEMINI_MAX_TOKENS` | Max output tokens | Gemini | No | No (default: `8192`) |
| `GEMINI_TEMPERATURE` | LLM temperature | Gemini | No | No (default: `0.1`) |
| `GEMINI_RATE_LIMIT_RPM` | Rate limit (requests per minute) | Gemini | No | No (default: `60`) |
| `GEMINI_CONTEXT_CACHE_ENABLED` | Enable context caching | Gemini | No | No (default: `true`) |
| `GEMINI_CONTEXT_CACHE_TTL` | Cache TTL in seconds | Gemini | No | No (default: `3600`) |
| `GEMINI_USE_VERTEXAI` | Use Vertex AI instead of AI Studio | Vertex AI | No | No (default: `false`) |
| `GEMINI_VERTEXAI_PROJECT` | GCP project ID for Vertex | Vertex AI | No | Conditional |
| `GEMINI_VERTEXAI_LOCATION` | GCP region for Vertex | Vertex AI | No | No (default: `us-central1`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON | Vertex AI | **Yes** | Conditional |
| `VECTOR_PROVIDER` | Vector DB provider (`pinecone` or `pgvector`) | Pinecone | No | No (default: `pinecone`) |
| `PINECONE_API_KEY` | Pinecone API key | Pinecone | **Yes** | **Yes (prod)** |
| `PINECONE_INDEX_NAME` | Pinecone index name | Pinecone | No | No (default: `smriti-legal`) |
| `PINECONE_ENVIRONMENT` | Pinecone cloud region | Pinecone | No | No |
| `PINECONE_DIMENSION` | Vector dimension (must match embeddings) | Pinecone | No | No (default: `1536`) |
| `PINECONE_METRIC` | Distance metric | Pinecone | No | No (default: `cosine`) |
| `PINECONE_CLOUD` | Cloud provider for Pinecone | Pinecone | No | No |
| `PINECONE_TOP_K` | Default top-K results | Pinecone | No | No (default: `20`) |
| `PINECONE_HOST` | Index-specific host URL | Pinecone | No | **Yes (prod)** |
| `GRAPH_PROVIDER` | Graph DB provider (`neo4j` or `postgresql`) | Neo4j | No | No (default: `neo4j`) |
| `NEO4J_URI` | Neo4j connection URI | Neo4j | No | Yes |
| `NEO4J_USER` | Neo4j username | Neo4j | No | Yes |
| `NEO4J_PASSWORD` | Neo4j password (no `smriti_dev` in prod) | Neo4j | **Yes** | Yes |
| `NEO4J_DATABASE` | Neo4j database name | Neo4j | No | No (default: `neo4j`) |
| `RERANKER_PROVIDER` | Reranker provider | Cohere | No | No (default: `cohere`) |
| `COHERE_API_KEY` | Cohere API key | Cohere | **Yes** | **Yes (prod)** |
| `COHERE_RERANK_MODEL` | Rerank model name | Cohere | No | No (default: `rerank-v4.0-pro`) |
| `COHERE_RERANK_TOP_N` | Reranker top-N results | Cohere | No | No (default: `10`) |
| `IK_API_TOKEN` | Indian Kanoon API token | Indian Kanoon | **Yes** | No |
| `IK_RATE_LIMIT` | IK requests per second | Indian Kanoon | No | No (default: `2`) |
| `TAVILY_API_KEY` | Tavily web search API key | Tavily | **Yes** | No |
| `WEB_SEARCH_TIMEOUT` | Web search timeout seconds | Tavily | No | No (default: `10`) |
| `TTS_PROVIDER` | TTS provider (`sarvam` or `mock`) | TTS | No | No (default: `mock`) |
| `SARVAM_API_KEY` | Sarvam AI API key | Sarvam | **Yes** | Conditional |
| `STORAGE_PROVIDER` | Storage backend (`local` or `gcs`) | Storage | No | No (default: `local`) |
| `LOCAL_STORAGE_PATH` | Local PDF storage path | Storage | No | No (default: `./data/pdfs`) |
| `GCS_BUCKET_NAME` | GCS bucket for documents | GCS | No | Conditional |
| `GCS_PROJECT_ID` | GCP project ID | GCS | No | Conditional |
| `INGESTION_TRACKER_DB` | SQLite tracker DB path | Ingestion | No | No |
| `INGESTION_BATCH_SIZE` | Ingestion batch size | Ingestion | No | No (default: `10`) |
| `INGESTION_CONCURRENCY` | Concurrent ingestion workers | Ingestion | No | No (default: `5`) |
| `SEARCH_CACHE_TTL` | Search results cache TTL (seconds) | Search | No | No (default: `300`) |
| `SEARCH_FACET_CACHE_TTL` | Facet cache TTL (seconds) | Search | No | No (default: `900`) |
| `SEARCH_RRF_K` | Reciprocal Rank Fusion k parameter | Search | No | No (default: `60`) |
| `SEARCH_RRF_K_KEYWORD_HEAVY` | RRF k for keyword-heavy queries | Search | No | No (default: `30`) |
| `SEARCH_RRF_K_VECTOR_HEAVY` | RRF k for vector-heavy queries | Search | No | No (default: `60`) |
| `SEARCH_VECTOR_TOP_K` | Vector search top-K | Search | No | No (default: `20`) |
| `SEARCH_FTS_TOP_K` | Full-text search top-K | Search | No | No (default: `20`) |
| `SEARCH_RERANK_TOP_N` | Reranker top-N | Search | No | No (default: `10`) |
| `SEARCH_DEFAULT_PAGE_SIZE` | Default pagination size | Search | No | No (default: `10`) |
| `SEARCH_MAX_PAGE_SIZE` | Maximum pagination size | Search | No | No (default: `50`) |
| `RATE_LIMIT_DEFAULT` | Default API rate limit | FastAPI | No | No (default: `100/minute`) |
| `RATE_LIMIT_SEARCH` | Search endpoint rate limit | FastAPI | No | No (default: `60/minute`) |
| `RATE_LIMIT_CHAT` | Chat endpoint rate limit | FastAPI | No | No (default: `10/minute`) |
| `RATE_LIMIT_INGEST` | Ingestion endpoint rate limit | FastAPI | No | No (default: `5/minute`) |
| `RESEARCH_MAX_REFINEMENT_ROUNDS` | Agent max refinement iterations | Agent | No | No (default: `2`) |
| `RESEARCH_MAX_CHUNKS_PER_CASE` | Max chunks per case in agent | Agent | No | No (default: `4`) |
| `RESEARCH_MAX_SNIPPET_LEN` | Max snippet character length | Agent | No | No (default: `1500`) |
| `RESEARCH_MAX_RATIO_LEN` | Max ratio decidendi length | Agent | No | No (default: `3000`) |
| `RESEARCH_CRAG_THRESHOLD_CORRECT` | CRAG correct threshold | Agent | No | No (default: `0.7`) |
| `RESEARCH_CRAG_THRESHOLD_AMBIGUOUS` | CRAG ambiguous threshold | Agent | No | No (default: `0.3`) |
| `RESEARCH_CRAG_FALLBACK_RATIO` | CRAG fallback ratio | Agent | No | No (default: `0.5`) |
| `CHAT_MAX_HISTORY` | Chat history length | Chat | No | No (default: `10`) |
| `CHAT_MAX_CONTEXT_RESULTS` | Chat context results count | Chat | No | No (default: `5`) |
| `CHAT_MAX_SNIPPET_CHARS` | Chat snippet max chars | Chat | No | No (default: `3000`) |
| `AGENT_MAX_HISTORY` | Agent follow-up history length | Agent | No | No (default: `10`) |
| `AGENT_FOLLOWUP_MAX_RESULTS` | Agent follow-up max results | Agent | No | No (default: `5`) |
| `AGENT_FOLLOWUP_MEMO_CHARS` | Agent follow-up memo size | Agent | No | No (default: `15000`) |
| `ENABLE_TREATMENT_LLM_FALLBACK` | Enable LLM citation treatment classification | Agent | No | No (default: `false`) |
| `TREATMENT_LLM_CONFIDENCE_THRESHOLD` | Threshold for LLM treatment fallback | Agent | No | No (default: `0.6`) |
| `LOG_LEVEL` | Logging level | Logging | No | No (default: `INFO`) |
| `LOG_FORMAT` | Log format (`json` for structured) | Logging | No | No |
| `LOG_PII_REDACTION` | Redact PII from logs | Logging | No | No |
| `SENTRY_DSN` | Sentry error tracking endpoint | Monitoring | No | No |
| `SENTRY_ENVIRONMENT` | Sentry environment tag | Monitoring | No | No |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry trace sampling rate | Monitoring | No | No (default: `0.1`) |
| `DATA_RETENTION_DAYS` | DPDP data retention period | Compliance | No | No (default: `365`) |
| `USER_UPLOAD_RETENTION_DAYS` | User upload retention | Compliance | No | No (default: `7`) |

### Docker Compose Production (`.env.prod.example` at repo root)

| Variable | Purpose | Secret? | Required? |
|---|---|---|---|
| `POSTGRES_PASSWORD` | PostgreSQL password for prod Docker | **Yes** | Yes |
| `REDIS_PASSWORD` | Redis password for prod Docker | **Yes** | Yes |

### Ingestion Accounts (`ingestion/accounts/env_template`)

| Variable | Purpose | Secret? | Required? |
|---|---|---|---|
| `GEMINI_USE_VERTEXAI` | Must be `true` (uses free Vertex credits) | No | Yes |
| `GEMINI_VERTEXAI_PROJECT` | GCP project ID per account | No | Yes |
| `GEMINI_VERTEXAI_LOCATION` | GCP region | No | No (default: `us-central1`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON path | **Yes** | Yes |
| `GCS_BUCKET` | GCS bucket per ingestion account | No | Yes |
| `STORAGE_PROVIDER` | Storage provider (always `local` for ingestion) | No | Yes |
| `GCS_PDF_BUCKET` | Shared GCS bucket for PDFs | No | Yes |
| `DATABASE_URL` | Shared production database URL | **Yes** | Yes |
| `PINECONE_API_KEY` | Shared Pinecone API key | **Yes** | Yes |
| `PINECONE_HOST` | Shared Pinecone host URL | No | Yes |
| `NEO4J_URI` | Shared Neo4j AuraDB URI | No | Yes |
| `NEO4J_USER` | Shared Neo4j username | No | Yes |
| `NEO4J_PASSWORD` | Shared Neo4j password | **Yes** | Yes |

### Production Validation (enforced by `config.py` model_validator)

When `APP_ENV=production`, the Settings class **raises ValueError** if:
- `jwt_secret_key` or `jwt_refresh_secret_key` is empty or < 32 chars
- `encryption_key` is empty or < 32 chars
- `cors_origins` contains `*`
- `gemini_api_key` is empty (unless `gemini_use_vertexai=true`)
- `pinecone_api_key` or `pinecone_host` is empty
- `cohere_api_key` is empty
- `neo4j_password` is `smriti_dev`
- `database_url` contains `localhost`
- `storage_provider` is `local`
- `tts_provider` is `mock`
- `app_debug` is `true`

---

## Docker Services

### Development (`docker-compose.yml`)

| Service | Image | Ports | Depends On | Purpose |
|---|---|---|---|---|
| `postgres` | `postgres:16-alpine` | `127.0.0.1:5432:5432` | -- | Primary relational DB (metadata, FTS, user accounts) |
| `redis` | `redis:7-alpine` | `127.0.0.1:6379:6379` | -- | Cache (search results, sessions), Celery broker |
| `neo4j` | `neo4j:5-community` | `127.0.0.1:7474:7474` (web), `127.0.0.1:7687:7687` (bolt) | -- | Citation graph DB with APOC plugin |

Notes:
- All ports bound to `127.0.0.1` only (not exposed externally)
- Dev passwords hardcoded: `smriti_dev` (PG, Neo4j), `dev_password` (Redis)
- Backend and frontend run outside Docker in dev (uvicorn + next dev)

### Production (`docker-compose.prod.yml`)

| Service | Image | Ports | Depends On | Purpose | Memory Limit |
|---|---|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | None (internal) | -- | PostgreSQL with pgvector extension (can replace Pinecone) | 3 GB |
| `redis` | `redis:7-alpine` | None (internal) | -- | Cache with 256 MB maxmemory, LRU eviction | 300 MB |
| `backend` | Custom build (`./backend/Dockerfile`) | None (internal) | postgres (healthy), redis (healthy) | FastAPI application server | 1 GB |
| `migrate` | Same as backend | None | postgres (healthy) | One-shot Alembic migration runner (restart: no) | -- |
| `frontend` | Custom build (`./frontend/Dockerfile`) | None (internal) | backend | Next.js SSR server | 512 MB |
| `nginx` | `nginx:alpine` | `80:80`, `443:443` | frontend, backend | Reverse proxy, SSL termination, rate limiting | 64 MB |
| `certbot` | `certbot/certbot` | None | -- | Auto-renews Let's Encrypt SSL certificates (12h loop) | -- |

Notes:
- Production uses `pgvector` image (includes vector extension) and `VECTOR_PROVIDER=pgvector`, `GRAPH_PROVIDER=postgresql` -- meaning Pinecone and Neo4j can be replaced by PostgreSQL in a self-hosted setup
- PostgreSQL is tuned for 8 GB RAM VPS (shared_buffers=2GB, effective_cache_size=4GB)
- Total memory budget: ~5 GB (fits an 8 GB VPS with OS overhead)
- Passwords injected via `${POSTGRES_PASSWORD}` and `${REDIS_PASSWORD}` from `.env` file at repo root

---

## Nginx Configuration

**File**: `nginx/nginx.conf`
**Domain**: `smriti.legal` / `www.smriti.legal`

Key features:
- HTTP-to-HTTPS redirect on port 80
- SSL with TLS 1.2/1.3 (Let's Encrypt certificates at `/etc/nginx/ssl/live/smriti.legal/`)
- Let's Encrypt ACME challenge path at `/.well-known/acme-challenge/`
- `/api/` routes proxied to backend (port 8000) with **SSE support** (proxy_buffering off, 300s read timeout)
- All other routes proxied to frontend (port 3000)
- Rate limiting: 30 req/s for API, 60 req/s for general traffic (per IP, with burst)
- Gzip enabled for text, CSS, JSON, JS, XML (min 1000 bytes)
- `client_max_body_size 50M` (for PDF uploads)

---

## Alembic Configuration

**File**: `backend/alembic.ini`
- Migrations directory: `backend/migrations/`
- `sqlalchemy.url` left empty in INI (overridden at runtime by `DATABASE_URL` env var)
- Logging: WARN for root and SQLAlchemy, INFO for Alembic

---

## Python Dependencies

**File**: `backend/pyproject.toml` (no `requirements.txt` -- uses PEP 621 `[project]` table)

### Core Dependencies

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.115.6 | Web framework -- async REST API with automatic OpenAPI docs |
| `uvicorn[standard]` | 0.34.0 | ASGI server -- runs FastAPI in dev and prod |
| `python-multipart` | 0.0.18 | Form/file upload parsing for FastAPI endpoints |
| `sqlalchemy[asyncio]` | 2.0.36 | Async ORM -- models, queries, connection pooling for PostgreSQL |
| `asyncpg` | 0.30.0 | PostgreSQL async driver (used by SQLAlchemy) |
| `alembic` | 1.14.1 | Database migration tool -- schema versioning |
| `greenlet` | 3.1.1 | Coroutine support for SQLAlchemy async |
| `redis[hiredis]` | 5.2.1 | Redis client with C-extension for caching and sessions |
| `celery[redis]` | 5.4.0 | Distributed task queue (background jobs) |
| `pyjwt` | 2.10.1 | JWT token creation and validation for authentication |
| `bcrypt` | 4.2.1 | Password hashing (configurable cost factor) |
| `cryptography` | 44.0.0 | AES-256 encryption for PII fields (DPDP compliance) |
| `google-genai` | 1.5.0 | Google Gemini SDK -- LLM reasoning, embeddings, batch API |
| `pinecone` | 5.4.2 | Pinecone vector DB client -- semantic search |
| `cohere` | 5.13.3 | Cohere reranker client -- search result reranking |
| `neo4j` | 5.27.0 | Neo4j graph DB driver -- citation graph queries |
| `langgraph` | 0.6.11 | LangGraph agent framework -- research agent state machine (pinned, pre-1.0 breaking changes) |
| `langgraph-checkpoint-postgres` | 2.0.25 | PostgreSQL checkpoint saver for LangGraph agent state |
| `psycopg[binary]` | 3.3.3 | PostgreSQL driver for LangGraph checkpointing (separate from asyncpg) |
| `psycopg-pool` | 3.3.0 | Connection pooling for psycopg |
| `pdfplumber` | 0.11.4 | PDF text extraction (primary extractor) |
| `pdfminer.six` | >=20221105 | PDF text extraction (fallback/supplementary) |
| `pytesseract` | 0.3.13 | OCR fallback for scanned PDF pages |
| `pdf2image` | 1.17.0 | PDF-to-image conversion for OCR pipeline |
| `python-docx` | >=1.1.0 | DOCX export for case prep/drafting features |
| `reportlab` | >=4.0 | PDF generation for document export |
| `networkx` | >=3.0 | In-memory graph algorithms (community detection, centrality) |
| `pyarrow` | 18.1.0 | Parquet file reading for S3 metadata ingestion |
| `pandas` | 2.2.3 | Data manipulation for ingestion pipeline |
| `pydantic[email]` | 2.10.4 | Data validation, settings, request/response schemas |
| `pydantic-settings` | 2.7.1 | Environment variable loading into typed Settings class |
| `httpx` | 0.28.1 | Async HTTP client (Indian Kanoon API, external calls) |
| `tenacity` | >=8.2,<10.0 | Retry with exponential backoff for all external service calls |
| `google-cloud-storage` | 2.19.0 | GCS client for PDF storage and batch ingestion |
| `sentry-sdk[fastapi]` | 2.20.0 | Error tracking and performance monitoring |

### Dev Dependencies

| Package | Version | Purpose |
|---|---|---|
| `pytest` | 8.3.4 | Test runner |
| `pytest-asyncio` | 0.25.0 | Async test support (auto mode) |
| `pytest-cov` | 6.0.0 | Coverage reporting |
| `pytest-mock` | 3.14.0 | Mock/patch utilities |
| `ruff` | 0.8.6 | Linter + formatter (replaces flake8/isort/black) |
| `mypy` | 1.14.1 | Static type checker (strict mode, pydantic plugin) |
| `pre-commit` | 4.0.1 | Git hook manager |
| `aiosqlite` | 0.20.0 | Async SQLite for test fixtures |
| `locust` | >=2.20 | Load testing framework |

### Ruff Configuration
- Target: Python 3.12
- Line length: 100
- Enabled rules: pycodestyle (E/W), pyflakes (F), isort (I), pep8-naming (N), pyupgrade (UP), bugbear (B), bandit security (S), no-print (T20), simplify (SIM), type-checking (TCH), ruff-specific (RUF)
- Tests: assert (`S101`) and hardcoded password detection (`S105/S106`) suppressed

### MyPy Configuration
- Strict mode enabled
- Pydantic plugin active
- Missing imports ignored for: pdfplumber, pytesseract, neo4j, pinecone, cohere, google, docx, reportlab

### Pytest Configuration
- `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`)
- Test paths: `tests/`
- Custom markers: `integration`, `security`

---

## Node/Frontend Dependencies

### Main App (`frontend/package.json`)

| Package | Version | Purpose |
|---|---|---|
| **Runtime** | | |
| `next` | 16.2.1 | React meta-framework (App Router, SSR, API routes) |
| `react` | 19.2.3 | UI library |
| `react-dom` | 19.2.3 | React DOM renderer |
| `next-intl` | ^4.8.3 | Internationalization (Hindi support) |
| `react-markdown` | ^10.1.0 | Markdown rendering in chat responses |
| `remark-gfm` | ^4.0.1 | GitHub Flavored Markdown (tables, strikethrough) |
| `rehype-sanitize` | ^6.0.0 | HTML sanitization for rendered markdown |
| `react-force-graph-2d` | ^1.29.1 | Citation graph visualization (2D force-directed) |
| `react-pdf` | ^10.4.1 | PDF viewer component for judgment display |
| `recharts` | ^3.8.0 | Charts/analytics (case statistics, dashboards) |
| `@radix-ui/react-dialog` | ^1.1.15 | Accessible modal dialogs |
| `@radix-ui/react-scroll-area` | ^1.2.10 | Custom scrollbar component |
| `@radix-ui/react-tabs` | ^1.1.13 | Tab navigation component |
| `@radix-ui/react-tooltip` | ^1.2.8 | Tooltip component |
| `radix-ui` | ^1.4.3 | Radix UI primitives (umbrella package) |
| `class-variance-authority` | ^0.7.1 | Component variant management (used by shadcn/ui) |
| `clsx` | ^2.1.1 | Conditional classname utility |
| `tailwind-merge` | ^3.5.0 | Merge Tailwind classes without conflicts |
| `lucide-react` | ^0.577.0 | Icon library |
| **Dev** | | |
| `tailwindcss` | ^4 | Utility-first CSS framework |
| `@tailwindcss/postcss` | ^4 | PostCSS plugin for Tailwind |
| `tw-animate-css` | ^1.4.0 | Animation utilities for Tailwind |
| `typescript` | ^5 | TypeScript compiler |
| `@types/node` | ^20 | Node.js type definitions |
| `@types/react` | ^19 | React type definitions |
| `@types/react-dom` | ^19 | React DOM type definitions |
| `vitest` | ^4.0.18 | Test runner (NOT jest) |
| `@testing-library/react` | ^16.3.2 | React component testing utilities |
| `@testing-library/dom` | ^10.4.1 | DOM testing utilities |
| `@testing-library/jest-dom` | ^6.9.1 | Custom DOM matchers (toBeInTheDocument, etc.) |
| `@testing-library/user-event` | ^14.6.1 | User interaction simulation |
| `@vitejs/plugin-react` | ^5.1.4 | Vite React plugin (for vitest) |
| `jsdom` | ^28.1.0 | Browser DOM simulation for tests |
| `eslint` | ^9 | JavaScript/TypeScript linter |
| `eslint-config-next` | 16.1.6 | Next.js ESLint preset |
| `shadcn` | ^3.8.5 | shadcn/ui CLI for adding components |

### Storybook/Playground (`smriti-storybook/package.json`)

This is a separate experimental UI playground, not part of the main app.

| Package | Version | Purpose |
|---|---|---|
| **Runtime** | | |
| `react` | ^19.2.4 | UI library |
| `react-dom` | ^19.2.4 | React DOM renderer |
| `react-router-dom` | ^7.13.2 | Client-side routing |
| `three` | ^0.183.2 | 3D rendering engine |
| `@react-three/fiber` | ^9.5.0 | React renderer for Three.js |
| `@react-three/drei` | ^10.7.7 | Three.js helpers and abstractions |
| `@react-three/postprocessing` | ^3.0.4 | Post-processing effects for Three.js |
| `framer-motion` | ^12.38.0 | Animation library |
| `gsap` | ^3.14.2 | GreenSock animation platform |
| `@gsap/react` | ^2.1.2 | GSAP React integration |
| `lottie-react` | ^2.4.1 | Lottie animation player |
| `howler` | ^2.2.4 | Audio playback library |
| `roughjs` | ^4.6.6 | Hand-drawn style graphics |
| `@dnd-kit/core` | ^6.3.1 | Drag-and-drop framework |
| `@dnd-kit/sortable` | ^10.0.0 | Sortable lists |
| `@dnd-kit/utilities` | ^3.2.2 | DnD utility functions |
| `zustand` | ^5.0.12 | State management |
| **Dev** | | |
| `vite` | ^8.0.1 | Build tool and dev server |
| `@vitejs/plugin-react` | ^6.0.1 | Vite React plugin |
| `typescript` | ~5.9.3 | TypeScript compiler |
| `eslint` | ^9.39.4 | Linter |
| `typescript-eslint` | ^8.57.0 | TypeScript ESLint parser |
| `tailwindcss` (via `@tailwindcss/vite`) | ^4.2.2 | Tailwind CSS |

---

## External Services

| Service | Purpose | Free Tier? | Config Location |
|---|---|---|---|
| **Google Gemini (AI Studio)** | LLM reasoning + embeddings | Yes (rate-limited) | `GEMINI_API_KEY` in backend `.env` |
| **Google Vertex AI** | LLM reasoning + embeddings (preferred for ingestion) | Yes ($300 free credits) | `GEMINI_USE_VERTEXAI`, `GEMINI_VERTEXAI_PROJECT`, service account JSON |
| **Pinecone** | Vector database for semantic search | Yes (free Starter tier, upgrade at 100K vectors) | `PINECONE_API_KEY`, `PINECONE_HOST` in backend `.env` |
| **Neo4j AuraDB** | Graph database for citation relationships | Yes (free tier) | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in backend `.env` |
| **Cohere** | Search result reranking (rerank-v4.0-pro) | Yes (rate-limited trial) | `COHERE_API_KEY` in backend `.env` |
| **Indian Kanoon API** | Legal document search and retrieval | No (paid API) | `IK_API_TOKEN` in backend `.env` |
| **Tavily** | Web search for research agent | Yes (limited free tier) | `TAVILY_API_KEY` in backend `.env` |
| **Sarvam AI** | Text-to-speech (22 Indian languages) | Unknown | `SARVAM_API_KEY` in backend `.env` |
| **Google Cloud Storage** | PDF document storage (production) | Yes ($300 free credits) | `GCS_BUCKET_NAME`, service account |
| **Sentry** | Error tracking and performance monitoring | Yes (free developer tier) | `SENTRY_DSN` in backend `.env` |
| **Let's Encrypt** | Free SSL certificates | Yes (free) | Certbot container in docker-compose.prod.yml |
| **AWS S3 (Open Data)** | Source data: 35K Supreme Court judgments | Yes (public, no auth) | No config needed (`--no-sign-request`) |

---

## Local Development Setup Steps

1. **Clone the repository**
   ```
   git clone <repo-url> && cd Smriti
   ```

2. **Start infrastructure services** (PostgreSQL, Redis, Neo4j)
   ```
   make infra
   ```
   This runs `docker compose up -d` using `docker-compose.yml`.

3. **Set up backend environment**
   ```
   cd backend
   cp .env.example .env
   ```
   Fill in at minimum:
   - `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY` (generate with `openssl rand -hex 32`)
   - `GEMINI_API_KEY` (from Google AI Studio)
   - `PINECONE_API_KEY` and `PINECONE_HOST` (from Pinecone console)
   - `COHERE_API_KEY` (from Cohere dashboard)
   - `NEO4J_PASSWORD` (default `smriti_dev` matches docker-compose)

4. **Install Python dependencies** (requires Python 3.12+)
   ```
   pip install -e ".[dev]"
   ```

5. **Run database migrations**
   ```
   make migrate
   ```
   Or: `cd backend && alembic upgrade head`

6. **Install pre-commit hooks**
   ```
   pre-commit install
   ```

7. **Start the backend**
   ```
   make backend
   ```
   Or: `cd backend && uvicorn app.main:app --reload --port 8000`

8. **Set up frontend** (in a separate terminal)
   ```
   cd frontend
   npm install
   npm run dev
   ```
   Frontend runs on `http://localhost:3000`, proxies API calls to `http://localhost:8000`.

9. **Verify setup**
   ```
   make health
   ```
   Should return JSON health check from backend.

10. **Run tests**
    ```
    make test          # Backend tests with coverage
    cd frontend && npm test  # Frontend tests
    ```

### Prerequisites
- Docker and Docker Compose
- Python 3.12+
- Node.js 22+
- npm (NOT yarn, NOT pnpm)
- Tesseract OCR (for `pytesseract` -- PDF OCR fallback)
- Poppler (for `pdf2image` -- PDF-to-image conversion)

---

## CI/CD Pipeline

**File**: `.github/workflows/ci.yml`
**Trigger**: Push to `master` or pull request targeting `master`

### Backend Job (`ubuntu-latest`)
1. Checkout code
2. Set up Python 3.12 with pip caching (keyed on `pyproject.toml`)
3. Install dependencies: `pip install -e ".[dev]"`
4. **Lint**: `ruff check app/`
5. **Security audit**: `pip-audit --strict --desc` (fails on known vulnerabilities)
6. **Test**: `pytest tests/unit/ -x --timeout=30` (unit tests only, fail-fast, 30s timeout per test)

### Frontend Job (`ubuntu-latest`)
1. Checkout code
2. Set up Node.js 22 with npm caching (keyed on `package-lock.json`)
3. Install dependencies: `npm ci`
4. **Security audit**: `npm audit --audit-level=moderate` (fails on moderate+ vulnerabilities)
5. **Test**: `npm test -- --run` (vitest in run mode)
6. **Build**: `npm run build` (verifies production build succeeds)

### Notable
- No deployment step -- CI only (lint, audit, test, build)
- No integration tests in CI (only unit tests)
- No Docker build/push step
- No environment/secrets in CI (unit tests use mocks)
- Backend and frontend jobs run in parallel

---

## Makefile Targets

| Target | Command | Purpose |
|---|---|---|
| `infra` | `docker compose up -d` | Start local infrastructure (PostgreSQL, Redis, Neo4j) |
| `backend` | `uvicorn app.main:app --reload --port 8000` | Start backend dev server with auto-reload |
| `test` | `pytest -v --cov=app` | Run all backend tests with verbose output and coverage |
| `test-unit` | `pytest tests/unit/ -v` | Run only unit tests |
| `test-integration` | `pytest tests/integration/ -v -m integration` | Run only integration tests |
| `test-security` | `pytest tests/security/ -v -m security` | Run only security tests |
| `lint` | `ruff check . && mypy app/` | Run linter and type checker |
| `format` | `ruff format .` | Auto-format Python code |
| `migrate` | `alembic upgrade head` | Apply all pending database migrations |
| `migration` | `alembic revision --autogenerate -m "$(msg)"` | Create new auto-generated migration (usage: `make migration msg="add users table"`) |
| `ingest` | `python scripts/ingest_s3.py --year $(year)` | Ingest SC judgments for a specific year (usage: `make ingest year=2023`) |
| `ingest-all` | `python scripts/ingest_s3.py --all` | Ingest all available years of SC judgments |
| `clean` | `docker compose down -v && rm -rf ...` | Destroy all Docker volumes and local data (destructive) |
| `health` | `curl localhost:8000/health` | Check backend health endpoint |

---

## Pre-commit Hooks

**File**: `.pre-commit-config.yaml`

| Hook | Source | Purpose |
|---|---|---|
| `ruff` (with `--fix`) | `astral-sh/ruff-pre-commit` v0.8.6 | Auto-fix lint issues on commit |
| `ruff-format` | `astral-sh/ruff-pre-commit` v0.8.6 | Auto-format Python code on commit |
| `mypy` | `pre-commit/mirrors-mypy` v1.14.1 | Type check `backend/app/` (with pydantic, sqlalchemy, types-redis stubs) |
| `detect-secrets` | `Yelp/detect-secrets` v1.5.0 | Prevent accidental secret commits (uses `.secrets.baseline`, excludes `.env.example`) |
| `trailing-whitespace` | `pre-commit/pre-commit-hooks` v5.0.0 | Remove trailing whitespace |
| `end-of-file-fixer` | `pre-commit/pre-commit-hooks` v5.0.0 | Ensure files end with newline |
| `check-yaml` | `pre-commit/pre-commit-hooks` v5.0.0 | Validate YAML syntax |
| `check-added-large-files` | `pre-commit/pre-commit-hooks` v5.0.0 | Block files > 1 MB |
| `check-merge-conflict` | `pre-commit/pre-commit-hooks` v5.0.0 | Prevent committing merge conflict markers |

---

## Configuration Discrepancies & Notes

1. **Model name mismatch**: `.env.example` says `gemini-3.1-pro-preview` / `gemini-3-flash-preview`, but `config.py` defaults to `gemini-2.5-pro` / `gemini-2.5-flash`. The `.env.example` is likely stale or vice versa. The MEMORY.md reference says `gemini-3.1-pro-preview` and `gemini-3-flash-preview`.

2. **JWT expiry mismatch**: `.env.example` has `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15`, but `config.py` defaults to `60`. The MEMORY.md says 60 minutes. The `.env.example` value is stale.

3. **Database pool size mismatch**: `.env.example` says `DATABASE_POOL_SIZE=10`, but `config.py` defaults to `30`.

4. **No `requirements.txt`**: The backend uses `pyproject.toml` with `[project].dependencies` (PEP 621). There is no `requirements.txt` file.

5. **`backend/.env.prod.example` references pgvector/postgresql providers**: Production docker-compose uses `pgvector/pgvector:pg16` image and sets `VECTOR_PROVIDER=pgvector`, `GRAPH_PROVIDER=postgresql`. This is a self-hosted alternative that replaces both Pinecone and Neo4j with PostgreSQL extensions.

6. **Ingestion uses multi-account Vertex AI**: The ingestion pipeline supports multiple GCP accounts (env_a, env_b, env_c, env_d) for parallel ingestion using free Vertex AI credits. This is a cost optimization strategy.

7. **Redis password inconsistency**: `docker-compose.yml` uses `dev_password` for Redis, but the default `REDIS_URL` in `.env.example` is `redis://localhost:6379/0` (no password). The backend would need `redis://:dev_password@localhost:6379/0` to connect.

8. **Storybook is standalone**: `smriti-storybook/` is a separate Vite app (not integrated into the main build or CI). It contains experimental 3D, animation, and drag-and-drop prototypes -- not part of the production app.

9. **CRITICAL: Real credentials in env_template**: `ingestion/accounts/env_template` contains actual production DATABASE_URL, PINECONE_API_KEY, and NEO4J_PASSWORD. These should be placeholders. Rotate all exposed credentials immediately.
