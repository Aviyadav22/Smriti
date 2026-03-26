# Security Audit -- Smriti Platform

**Last updated**: March 12, 2026
**Status**: All OWASP Top 10 (2021) categories addressed. DPDP Act 2023 compliance implemented.

---

## Executive Summary

Smriti handles legal research data for Indian lawyers. While case law itself is public data, the platform processes user accounts, chat histories, uploaded documents, and AI-generated analyses that require robust security. This audit covers all OWASP Top 10 categories with specific implementation references, plus India-specific DPDP Act compliance.

**Security module location**: `backend/app/security/`
- `auth.py` -- JWT authentication, password hashing
- `rbac.py` -- Role-based access control
- `rate_limiter.py` -- Redis-backed rate limiting with in-memory fallback
- `sanitizer.py` -- Input sanitization, prompt injection detection
- `encryption.py` -- AES-256-GCM field-level encryption
- `audit.py` -- Audit logging with PII redaction
- `consent.py` -- DPDP consent management
- `exceptions.py` -- Security-specific exception classes

**Test coverage**: 9 dedicated security test files in `backend/tests/unit/` (see TESTING_STRATEGY.md Section 9.1)

---

## OWASP Top 10 (2021) Detailed Assessment

### A01: Broken Access Control -- PASS

**Risk**: Unauthorized users accessing or modifying resources they should not.

**Controls implemented**:

| Control | Implementation | File Reference |
|---------|---------------|----------------|
| JWT authentication | All protected routes require valid Bearer token | `security/auth.py` -- `verify_access_token()` |
| RBAC enforcement | `get_current_user` + `require_role` FastAPI dependencies | `security/rbac.py` -- `require_role("admin")` |
| Row-level data isolation | Chat sessions filtered by `user_id`, documents by `uploaded_by` | Route handlers in `api/routes/chat.py`, `api/routes/cases.py` |
| Agent execution scoping | Agent executions scoped to authenticated user | `api/routes/agents.py` |
| Token revocation | Redis-backed JTI blacklist with auto-expiry | `security/auth.py` -- `revoke_token()`, `is_token_revoked()` |
| Fail-closed revocation | If Redis is down, token treated as revoked (deny by default) | `security/auth.py:70` -- `return True` on exception |
| UUID validation | All case endpoints validate UUID format before DB query | `api/routes/cases.py` |
| Admin route protection | Admin endpoints require `admin` or `super_admin` role | `api/routes/admin.py` |

**Test coverage**: `test_auth.py`, `test_auth_routes.py`, `test_rbac.py`, `test_dpdp_routes.py`

---

### A02: Cryptographic Failures -- PASS

**Risk**: Sensitive data exposed due to weak or missing encryption.

**Controls implemented**:

| Control | Details | File Reference |
|---------|---------|----------------|
| Password hashing | bcrypt with configurable cost factor (default 12) | `security/auth.py` -- `hash_password()` |
| JWT signing | HS256 with separate secrets for access and refresh tokens | `security/auth.py` -- `_ALGORITHM = "HS256"` |
| JWT secret validation | Production enforces non-empty secrets, minimum 32-char length | `core/config.py` -- `validate_critical_settings()` |
| Field-level encryption | AES-256-GCM for chat messages and sensitive fields | `security/encryption.py` -- `encrypt_field()` / `decrypt_field()` |
| Encryption key format | Supports 64-char hex or base64-encoded 32-byte keys | `security/encryption.py` -- `_get_key()` |
| Nonce generation | 96-bit random nonce per encryption (os.urandom) | `security/encryption.py:68` |
| IP address hashing | SHA-256 with salt in audit logs (no raw IPs stored) | `security/audit.py:48` |
| Migration safety | `safe_decrypt()` handles pre-existing plaintext gracefully | `security/encryption.py` -- `safe_decrypt()` |
| HSTS headers | `Strict-Transport-Security: max-age=31536000; includeSubDomains` | `main.py` -- `SecurityHeadersMiddleware` |

**What we do NOT store in plaintext**: passwords (bcrypt), chat messages (AES-256-GCM), IP addresses in audit logs (SHA-256 hashed).

**Test coverage**: `test_auth.py`, `test_encryption.py`

---

### A03: Injection -- PASS

**Risk**: Attacker-supplied data interpreted as code or commands.

**Controls implemented**:

| Attack Vector | Mitigation | File Reference |
|---------------|-----------|----------------|
| SQL injection | All queries use SQLAlchemy `text()` with parameter binding. Zero raw SQL string construction. | All route handlers and search modules |
| SQL injection (ORDER BY) | Dynamic sort columns use an allowlisted static mapping, not f-string interpolation | `api/routes/admin_review.py` |
| SQL pattern injection | ILIKE wildcard characters (`%`, `_`) escaped in user-provided filter values | `core/search/fulltext.py` -- `_escape_ilike()` |
| XSS (server-side) | HTML tags stripped from all user input | `security/sanitizer.py` -- `sanitize_input()` |
| XSS (client-side) | CSP headers via Next.js, React's built-in escaping | `frontend/next.config.ts` |
| Null byte injection | Null bytes removed from input | `security/sanitizer.py:15` |
| Control character injection | Control chars (except tab/newline/CR) stripped | `security/sanitizer.py:16-17` |
| LLM prompt injection | 28 known injection markers detected and blocked | `security/sanitizer.py` -- `_INJECTION_MARKERS` |
| Role-switching attacks | Patterns like `system:`, `assistant:` detected and stripped | `security/sanitizer.py` -- `_ROLE_SWITCH_PATTERN` |
| Encoding attacks | High special-character ratio (>15%) flagged as suspicious | `security/sanitizer.py:148-152` |

**Prompt injection defense layers**:
1. `sanitize_search_query()` strips known injection markers before LLM processing
2. `detect_prompt_injection()` returns boolean for logging/alerting
3. Agent outputs verified with citation verification (3-layer check)
4. Error sanitization in agent responses (no stack traces to client)

**Test coverage**: `test_sanitizer.py`

---

### A04: Insecure Design -- PASS

**Risk**: Architectural flaws that cannot be fixed by implementation alone.

**Controls implemented**:

| Design Principle | Implementation |
|-----------------|----------------|
| Interface/Provider pattern | All external services behind Protocol classes -- swap implementations without touching business logic | `core/interfaces/*.py` |
| Input validation everywhere | Pydantic `BaseModel` on all API request bodies and query params | All route handlers |
| Rate limiting on sensitive endpoints | Auth: 5/minute, search: 60/minute, erasure: 5/hour | `security/rate_limiter.py` |
| Account lockout | 5 failed login attempts trigger 15-minute lockout | `api/routes/auth.py` |
| Atomic data operations | DPDP erasure uses `begin_nested()` for transactional deletion | `api/routes/dpdp.py:71` |
| Separate token types | Access tokens (15min) and refresh tokens (7 days) use different secrets | `security/auth.py` |
| Token type validation | `"type"` claim checked -- refresh tokens cannot be used as access tokens | `security/auth.py` -- `_decode_token()` |
| SSE session isolation | Each SSE stream gets an independent DB session | Agent and chat SSE handlers |
| Legal disclaimers | All AI-generated output carries legal disclaimers | Agent prompt templates |

**Test coverage**: `test_config_validation.py`, `test_rate_limiter.py`, `test_auth_routes.py`

---

### A05: Security Misconfiguration -- PASS

**Risk**: Default or insecure configuration in production.

**Controls implemented**:

| Configuration | Production Setting | File Reference |
|---------------|-------------------|----------------|
| CORS origins | Explicit allowed origins list (no `*` wildcard) | `core/config.py` -- `validate_critical_settings()` |
| API docs | Swagger/ReDoc disabled (`docs_url=None`, `redoc_url=None`) | `main.py` -- FastAPI constructor |
| Security headers | X-Content-Type-Options: nosniff, X-Frame-Options: DENY, HSTS, X-XSS-Protection: 0, Content-Security-Policy | `main.py` -- `SecurityHeadersMiddleware` |
| Cache-Control | `no-store` on all `/api/` responses | `main.py:196` |
| Trusted hosts | `TrustedHostMiddleware` enabled in production | `main.py:303-308` |
| Request size limit | `RequestSizeLimitMiddleware` rejects bodies > 10 MB with HTTP 413 | `main.py` -- `RequestSizeLimitMiddleware` |
| Health endpoint error sanitization | Unauthenticated callers receive "Check failed" instead of raw exception strings | `api/routes/health.py` |
| Secret management | GCP Secret Manager in production (not env files) | Deployment configuration |
| JWT secret length | Minimum 32 characters enforced at startup | `core/config.py` -- model validator |
| Encryption key length | Minimum 32 characters enforced at startup | `core/config.py:139` |
| Debug mode | Disabled in production | `core/config.py` |
| Structured logging | JSON format for Cloud Logging, PII redacted | `core/logging_config.py` |
| Sentry integration | Error tracking with DSN configured per environment | `main.py:208` |

**Test coverage**: `test_config_validation.py`, `test_logging_config.py`

---

### A06: Vulnerable and Outdated Components -- REVIEW

**Risk**: Known vulnerabilities in third-party dependencies.

**Controls implemented**:

| Control | Details |
|---------|---------|
| Dependency pinning | All Python and npm dependencies pinned to specific versions |
| Pre-release audit | Run `pip-audit` and `npm audit` before each release |
| Minimal dependencies | Only necessary packages included |
| CI planned | Automated dependency scanning planned for CI pipeline |

**Action items**:
- [ ] Add `pip-audit` to CI pipeline
- [ ] Add `npm audit` to CI pipeline
- [ ] Set up Dependabot or Renovate for automated dependency updates

---

### A07: Identification and Authentication Failures -- PASS

**Risk**: Weak authentication allowing unauthorized access.

**Controls implemented**:

| Control | Details | File Reference |
|---------|---------|----------------|
| JWT access tokens | 15-minute expiry | `security/auth.py:107` |
| JWT refresh tokens | 7-day expiry with rotation | `security/auth.py:139` |
| Separate signing keys | Access and refresh tokens use different secrets | `security/auth.py` |
| Token claims validation | `iss` (smriti), `aud` (smriti-api) validated on decode | `security/auth.py:179` |
| Clock skew tolerance | 30-second leeway on token expiry | `security/auth.py:181` |
| Token revocation | Redis JTI blacklist with TTL matching token expiry | `security/auth.py` -- `revoke_token()` |
| Fail-closed on Redis error | Token treated as revoked if revocation check fails | `security/auth.py:70-71` |
| Unique token IDs | Every token gets a UUID v4 `jti` claim | `security/auth.py:113` |
| Password strength | Minimum 8 characters, requires uppercase + lowercase + digit | `api/routes/auth.py` |
| Password hashing | bcrypt with configurable cost factor | `security/auth.py` -- `hash_password()` |
| Account lockout | 5 failed attempts trigger 15-minute lockout | `api/routes/auth.py` |
| Consent at registration | `consent_given` and `consent_version` required | `api/routes/auth.py` |

**Test coverage**: `test_auth.py`, `test_auth_routes.py`

---

### A08: Software and Data Integrity Failures -- PASS

**Risk**: Untrusted data or code affecting system integrity.

**Controls implemented**:

| Control | Details | File Reference |
|---------|---------|----------------|
| Input validation | Pydantic models on all API endpoints -- no raw dict processing | All route handlers |
| No unsafe deserialization | No pickle, eval, or exec on user data | Codebase-wide |
| Signed JWTs | HS256 signature verified on every request | `security/auth.py` |
| Agent output verification | Citation verification with 3-layer check (DB, equivalents, fuzzy) | `core/agents/nodes/citation_verifier.py` |
| Metadata validation | LLM-extracted metadata validated by regex (reject future dates, invalid courts) | `core/ingestion/metadata.py` |
| Idempotent graph writes | Neo4j uses MERGE (not CREATE) for safe re-ingestion | `core/providers/graph/neo4j_store.py` |
| Stale vector cleanup | Re-ingestion deletes old vectors before inserting new ones | `core/ingestion/pipeline.py` |

**Test coverage**: `test_metadata.py`, `test_citation_verifier.py`, `test_ingestion_pipeline.py`

---

### A09: Security Logging and Monitoring Failures -- PASS

**Risk**: Insufficient logging to detect or investigate security incidents.

**Controls implemented**:

| Control | Details | File Reference |
|---------|---------|----------------|
| Audit logging | Every API call logged with action, user_id, resource_type, resource_id | `security/audit.py` -- `create_audit_log()` |
| PII redaction in audit | IP addresses hashed with SHA-256 + salt before storage | `security/audit.py:48-53` |
| PII redaction in logs | Application logs scrub sensitive fields | `core/logging_config.py` |
| Structured JSON logging | Cloud Logging compatible format | `core/logging_config.py` |
| Failed login tracking | Failed attempts logged with hashed IP for brute-force detection | `api/routes/auth.py` |
| DPDP audit trail | Separate `dpdp_audit_log` table for erasure and consent events | `api/routes/dpdp.py` |
| Sentry error tracking | Runtime exceptions captured with context | `main.py:208` |
| Rate limit logging | Redis fallback events logged as warnings | `security/rate_limiter.py:233` |

**Logged events include**: register, login, logout, search, document.view, document.upload, chat.message, agent.execute, admin.*, erasure_completed, consent_withdrawn.

**Test coverage**: `test_audit_logging.py`, `test_logging_config.py`

---

### A10: Server-Side Request Forgery (SSRF) -- PASS

**Risk**: Attacker causes the server to make requests to unintended destinations.

**Controls implemented**:

| Control | Details |
|---------|---------|
| No user-controlled URLs | The server never fetches URLs provided by users |
| Configured endpoints only | External calls limited to: Pinecone (host URL from env), Neo4j (URI from env), Gemini (SDK), Cohere (SDK), Sarvam AI (configured endpoint) |
| All URLs from environment | Service URLs read from `core/config.py` settings, never from request params |
| Document upload | User-uploaded PDFs are processed locally, not fetched from user-supplied URLs |

---

## DPDP Act 2023 Compliance

India's Digital Personal Data Protection Act (2023) imposes specific obligations on data fiduciaries. Smriti implements the following data subject rights:

### Implemented Endpoints (`api/routes/dpdp.py`)

| Right | DPDP Section | Endpoint | Implementation |
|-------|-------------|----------|----------------|
| Data summary | Section 11 | `GET /api/v1/dpdp/data-summary` | Returns counts of all user data categories (chat sessions, messages, documents, agent executions, audit entries, consents) |
| Data erasure | Section 12 | `POST /api/v1/dpdp/erasure` | Atomic deletion of all personal data (agent executions, chat messages, sessions, documents, consents), account deactivation, audit trail entry |
| Consent withdrawal | Section 6 | `POST /api/v1/dpdp/consent-withdraw` | Revokes all active consents, logged in DPDP audit trail |
| Consent status | -- | `GET /api/v1/dpdp/consent-status` | Returns all consent records with grant/revoke timestamps |

### Privacy-by-Design Measures

| Measure | Implementation |
|---------|---------------|
| Consent at registration | Users must provide `consent_given=true` and `consent_version` to register |
| Purpose limitation | `data_retention_days` (default: 365) and `user_upload_retention_days` (default: 7) configured in settings |
| Data minimization | Only necessary fields collected; PII encrypted at rest |
| Audit trail | All DPDP operations logged in dedicated `dpdp_audit_log` table |
| Atomic erasure | All deletions in a single transaction (`begin_nested()`) -- no partial erasure |
| Rate limiting | Erasure: 5/hour, consent-withdraw: 10/hour, data-summary: 20/minute |

### Database Schema Support

- **`consents` table**: Tracks consent grants with type, version, timestamps, and revocation
- **`dpdp_audit_log` table**: Immutable log of all privacy operations
- **Migration 007**: `007_dpdp_compliance.py` adds DPDP-specific tables and columns

**Test coverage**: `test_dpdp_routes.py`

---

## Security Headers

All responses include the following headers (via `SecurityHeadersMiddleware` in `main.py`):

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforce HTTPS |
| `X-XSS-Protection` | `0` | Disable legacy XSS filter (modern CSP preferred) |
| `Cache-Control` | `no-store` (API routes only) | Prevent caching of sensitive API responses |
| `Content-Security-Policy` | `default-src 'self'; ...` | Restrict resource loading origins |

Additional production middleware:
- **TrustedHostMiddleware**: Rejects requests with unexpected `Host` headers
- **CORSMiddleware**: Restricts to explicit origins, credentials enabled, specific allowed headers
- **RequestSizeLimitMiddleware**: Rejects request bodies larger than 10 MB (HTTP 413)

---

## Rate Limiting Architecture

**Primary**: Redis-backed sliding window using sorted sets (`security/rate_limiter.py`)
**Fallback**: In-memory sliding window when Redis is unavailable, with 10,000-key bound to prevent memory exhaustion

| Endpoint Category | Limit | Notes |
|-------------------|-------|-------|
| Auth (login/register) | 5/minute | Brute-force prevention |
| Search | 60/minute | Per-IP |
| Chat messages | 30/minute | Per-user |
| DPDP erasure | 5/hour | Prevent abuse |
| DPDP consent-withdraw | 10/hour | Prevent abuse |
| DPDP data-summary | 20/minute | Per-user |
| Admin routes | 30/minute | Per-user |

Key design: `_in_memory_check()` clears all buckets when exceeding 10K keys (prevents unbounded memory growth). On Redis error, rate limiter transparently falls back to in-memory sliding window (no 503 returned to callers); fail-closed applies only to token revocation checks.

---

## Known Limitations and Future Work

| Item | Status | Priority |
|------|--------|----------|
| Automated dependency scanning in CI | Planned | High |
| Redis-backed rate limiting for all environments | In production, in-memory fallback for dev | Medium |
| E2E security tests (Playwright) | Planned | Medium |
| Penetration testing by third party | Not yet scheduled | High (pre-launch) |
| CSP header | Implemented via `SecurityHeadersMiddleware` | Done |
| CSP header reporting (`report-uri`) | Not yet configured | Medium |
| Subresource Integrity (SRI) for CDN assets | Not applicable (self-hosted) | Low |
| Web Application Firewall (WAF) | Cloud Run built-in, no custom WAF | Low |
| API key rotation mechanism | Manual rotation via GCP Secret Manager | Medium |
