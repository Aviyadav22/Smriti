# Smriti Production Readiness Audit

**Date:** 2026-03-25
**Auditor:** Claude Code (10 parallel deep-dive agents)
**Scope:** Full-stack audit — backend, frontend, database, infrastructure, security, performance
**Verdict:** **GO** after verification — most reported blockers were false positives (already fixed in code)

---

## Verification Notes (Post-Audit Code Review)

The 10 parallel audit agents reported ~125 findings. After manual code verification, **5 of 7 "P0 blockers" were false positives** — the code already had these fixes:
- `backend/.env` and credentials are NOT tracked in git (`.gitignore` working)
- `RequestSizeLimitMiddleware` already exists (10MB, `main.py:187-201`)
- `Content-Security-Policy` header already present (`main.py:217-227`)
- Health endpoint already returns `"error": "Check failed"` (not raw exceptions) and minimal info for unauth
- Rate limiter already has in-memory fallback (not 503) (`rate_limiter.py:233-241`)
- Admin review SQL uses allowlisted dict mapping (safe, `admin_review.py:71-79`)
- Research agent SSE already has 10-min timeout (`agents.py:354-377`)
- Search already tracks `search_degraded` flag (`hybrid.py:266`)

**Only real P0 was Next.js 16.1.6 CVEs** — now fixed (updated to 16.2.1).

---

## Executive Summary

| Dimension | Grade | Critical | High | Medium | Low |
|-----------|-------|----------|------|--------|-----|
| Security | B+ | 0 | 2 | 4 | 2 |
| Error Handling & Resilience | A- | 0 | 0 | 3 | 6 |
| Database & Data Integrity | A | 0 | 0 | 2 | 4 |
| API & Input Validation | B+ | 0 | 0 | 5 | 2 |
| Configuration & Environment | B | 0 | 0 | 2 | 0 |
| Performance | B- | 1 | 3 | 7 | 3 |
| Logging & Observability | C+ | 0 | 5 | 8 | 4 |
| Dependencies & Supply Chain | B+ | 0 | 0 | 3 | 0 |
| Frontend | A- | 0 | 0 | 1 | 4 |
| Deployment & Infrastructure | B- | 0 | 2 | 14 | 8 |
| **TOTAL** | **B+** | **1** | **12** | **49** | **33** |

**Verified findings after code review: ~95 (many duplicates/false positives removed)**

---

## P0 BLOCKERS — RESOLVED

All original P0 blockers have been verified as already fixed or now fixed:

### ~~BLOCKER 1: Secrets Committed to Git~~ — FALSE POSITIVE
- `git ls-files` confirms neither `backend/.env` nor credentials files are tracked
- `.gitignore` correctly excludes `.env` files

### ~~BLOCKER 2: SQL Injection in Admin Routes~~ — FALSE POSITIVE
- `admin_review.py:71-79` uses an allowlisted dict of static ORDER BY strings
- The f-string only interpolates from pre-built static values — no user input reaches SQL

### ~~BLOCKER 3: No Global Request Size Limit~~ — FALSE POSITIVE
- `RequestSizeLimitMiddleware` exists at `main.py:187-201` with 10MB limit

### ~~BLOCKER 4: Missing Content Security Policy Header~~ — FALSE POSITIVE
- CSP header already set at `main.py:217-227` with restrictive policy

### BLOCKER 5: Next.js 16.1.6 Has 5 Known CVEs — **FIXED**
- Updated to `next@16.2.1`

### ~~BLOCKER 6: Rate Limiter Returns 503 When Redis Down~~ — FALSE POSITIVE
- `rate_limiter.py:233-241` already falls back to in-memory rate limiting

### ~~BLOCKER 7: Health Endpoint Leaks Internal Error Details~~ — FALSE POSITIVE
- All health checks return `"error": "Check failed"` (not raw exceptions)
- Unauthenticated users only see `{"status": "healthy|degraded|unhealthy"}`

---

## P1 HIGH — Fix Before Launch (Week 1)

### Security
| # | Finding | Location | Fix |
|---|---------|----------|-----|
| S1 | Refresh token in localStorage (XSS risk) | `frontend/src/lib/api.ts:41-51` | Migrate to httpOnly cookie |
| S2 | CORS + credentials too permissive | `main.py:293-299`, `config.py:173` | Pin to single prod frontend origin |
| S3 | Token expiry logic inconsistent (0s vs 60s buffer) | `auth-context.tsx:30` vs `api.ts:99` | Centralize in shared `isTokenExpired()` |
| S4 | No admin approval workflow for corrections | `admin_corrections.py` | Add two-person rule for case edits |

### Error Handling & Resilience
| # | Finding | Location | Fix |
|---|---------|----------|-----|
| E1 | Circuit breakers only for LLM, not Pinecone/Neo4j/Cohere | `circuit_breaker.py` exists but not wired | Create + wire circuit breakers for all external services |
| E2 | Both search methods fail → empty results, no degradation signal | `hybrid.py:244-260` | Return degraded flag in response; frontend shows "search unavailable" |
| E3 | Research agent SSE streams have no timeout | `agents.py` SSE handlers | Wrap in `asyncio.timeout(600)` |

### Performance
| # | Finding | Location | Fix |
|---|---------|----------|-----|
| P1 | Unbounded result fetching in judge analytics | `judge_analytics.py:136-282` | Add LIMIT clauses; use SQL GROUP BY for aggregation |
| P2 | No embedding cache — same query = new API call every time | `hybrid.py:434`, `embeddings/gemini.py` | Cache embeddings in Redis keyed by normalized query |
| P3 | No LLM response cache for query understanding | `query.py:226-244` | Cache structured outputs by hash(prompt+schema) |

### Observability
| # | Finding | Location | Fix |
|---|---------|----------|-----|
| O1 | No frontend error tracking (Sentry) | `error-boundary.tsx` logs to console only | Add `@sentry/nextjs` SDK |
| O2 | No Prometheus metrics (latency, error rates) | Backend-wide | Add `prometheus-client` instrumentation |
| O3 | Registration not audit-logged | `auth.py:74-133` | Add `create_audit_log(action="user.registered")` |
| O4 | No distributed tracing (OpenTelemetry) | Backend-wide | Add OTLP auto-instrumentation |

### Dependencies
| # | Finding | Location | Fix |
|---|---------|----------|-----|
| D1 | No Python lock file | `backend/` missing | Generate with `pip-compile` or `poetry lock` |
| D2 | No `pip audit` in CI | `.github/workflows/ci.yml` | Add security scanning step |
| D3 | LangGraph version range too broad (pre-1.0) | `pyproject.toml:40` | Pin to exact version |

### Deployment
| # | Finding | Location | Fix |
|---|---------|----------|-----|
| I1 | No database backup/recovery runbook | (none exists) | Document Supabase backup + restore procedure |
| I2 | No automated deployment in CI | `.github/workflows/ci.yml` | Add deploy job on push to master |
| I3 | VECTOR_PROVIDER conflict (pgvector vs Pinecone) | `docker-compose.prod.yml` vs `deploy.sh` | Clarify and align |

---

## P2 MEDIUM — Fix Before Scale-Up (Month 1)

### Security & Auth
- Add DPDP data residency verification
- Tighten refresh token rate limit (10/min → 3/min)
- Add token revocation fallback to PostgreSQL when Redis is down

### Error Handling
- LLM unavailable during ingestion → implement regex-only fallback metadata extraction
- Neo4j down during ingestion → add `ingestion_status='graph_failed'` and retry queue
- Startup health checks should block if critical services are misconfigured

### Performance
- Sync PDF parsing (pdfplumber) blocks async event loop → wrap in `asyncio.to_thread()`
- Memory risk in batch ingestion (100 concurrent * 50MB PDFs) → stream chunks incrementally
- Facet computation in Python instead of SQL → use `GROUP BY` aggregation
- Pagination is offset-based; results may shift between pages

### API
- Cap search query max_length from 2000 → 500
- Cap comma-separated filter lists (courts, judges) to max 10
- Agent query max_length from 5000 → 2000
- Stream file uploads instead of buffering 50MB into memory

### Observability
- Add audit logging for document uploads, chat sessions, admin reviews
- Increase Sentry `traces_sample_rate` from 0.1 → 0.3-1.0
- Add structured fields to request logging (method, path, status_code, duration_ms)
- Frontend SSE: count consecutive JSON parse errors, abort after 3

### Config
- Add `APP_DEBUG=false` enforcement for production
- Remove Neo4j hardcoded default password `smriti_dev`
- Document PostgreSQL SSL requirement for production

### Database
- Add NOT NULL constraints to `year`, `case_type`, `decision_date` with migration defaults
- Verify `text_hash` unique index enforcement
- Ensure `ingestion_status` always set on re-ingest

### Frontend
- Add `error.tsx` files for `/case/[id]/`, `/judge/[name]/`, `/agents/research/`
- Add `loading.tsx` skeleton boundaries for async routes
- Show clipboard copy errors in toast, not just console
- Show "Filters unavailable" when search facets fail to load

### Deployment
- Create staging environment in Cloud Run
- Add security scanning to CI (pip-audit, npm audit, Trivy container scan)
- Align Python version: CI uses 3.13, Dockerfile uses 3.12
- Align Node version: CI uses 22, Dockerfile uses 20
- Add HEALTHCHECK directive to Dockerfiles

---

## P3 LOW — Post-Launch Polish

- Standardize Pinecone retry config (3 → 5 attempts to match other services)
- Wrap Cohere client in async context manager for proper cleanup
- Add certificate pinning for third-party API connections
- Log query hashes instead of raw query text
- Lazy load graph component with `next/dynamic`
- Virtual scrolling for large judge/case lists
- Frontend chat: increase streaming flush interval to 200-500ms
- Add `X-API-Version: 1` response header
- Document citation table `target_case_id` SET NULL on delete design decision
- Move `search_rrf_k` to env var for tuning without redeployment

---

## What's Working Well

These areas are **production-grade already**:

- **Database security**: All SQL parameterized, Neo4j labels allowlisted, MERGE for idempotency
- **Auth fundamentals**: bcrypt cost 12, JWT access/refresh split, account lockout (10 attempts/5 min)
- **Input validation**: Pydantic models, field validators, file magic byte checks, prompt injection detection
- **Health checks**: Comprehensive 5-dependency check (PG, Redis, Pinecone, Neo4j, Gemini) with degraded/unhealthy states
- **PII redaction**: Regex-based log scrubbing (email, API keys, JWT, Aadhaar, PAN, phone)
- **Graceful shutdown**: SQLAlchemy, Redis, provider connections closed with 10s timeouts
- **Search resilience**: Vector/FTS run in parallel with `return_exceptions=True`; reranker timeout falls back to RRF order
- **Retry logic**: Tenacity exponential backoff on all 5 external services (2-60s, 3-5 attempts)
- **Frontend security**: No `dangerouslySetInnerHTML`, markdown sanitized via `rehypeSanitize`, strong CSP in Next.js
- **RBAC**: `require_role("admin")` on all admin endpoints, session ownership checks on user data
- **Encryption**: AES-256-GCM for PII fields
- **Audit logging**: Login, logout, token refresh, account deletion, agent executions tracked
- **35 database migrations**: All have upgrade + downgrade, concurrent index creation, proper constraints

---

## Recommended Fix Order

```
Week 0 (TODAY):
  1. Rotate all leaked secrets
  2. Remove secrets from git history
  3. Update Next.js to 16.2.1+

Week 1 (Before first users):
  4. Fix SQL injection in admin_review.py
  5. Add request size limit middleware
  6. Add CSP header
  7. Fix rate limiter Redis fallback
  8. Sanitize health endpoint errors
  9. Add circuit breakers for Pinecone/Neo4j/Cohere
  10. Add frontend Sentry

Week 2 (Before public launch):
  11. Migrate refresh token to httpOnly cookie
  12. Add embedding/LLM caching (Redis)
  13. Generate Python lock file
  14. Add pip audit + npm audit to CI
  15. Create backup/recovery runbook
  16. Add deployment automation

Month 1 (Scale-up prep):
  17-35. P2 items from above
```

---

## Methodology

10 specialized audit agents ran in parallel, each examining 30-60 files across the full codebase:

1. **Security** — Auth, injection, secrets, OWASP top 10 (54 tool calls, 6 min)
2. **Error Handling** — Silent failures, retries, circuit breakers (47 calls, 2.5 min)
3. **Database** — Migrations, indexes, pooling, transactions (49 calls, 2.7 min)
4. **API** — Routes, CORS, rate limiting, validation (48 calls, 2.5 min)
5. **Configuration** — Env vars, defaults, secrets management (45 calls, 3.3 min)
6. **Performance** — N+1 queries, caching, async patterns (32 calls, 2.1 min)
7. **Observability** — Logging, metrics, health checks, tracing (48 calls, 2.7 min)
8. **Dependencies** — Versions, vulnerabilities, licenses (33 calls, 2 min)
9. **Frontend** — Error boundaries, loading states, accessibility (66 calls, 2.7 min)
10. **Deployment** — Docker, CI/CD, health checks, scaling (54 calls, 3.7 min)

Total: **476 tool calls**, **~28 minutes** of parallel analysis
