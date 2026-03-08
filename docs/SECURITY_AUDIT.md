# Security Audit Checklist

## OWASP Top 10 (2021) Status

### A01: Broken Access Control — PASS
- RBAC enforced via `get_current_user` + `require_role` dependencies
- Row-level security: documents filtered by `uploaded_by`, chat sessions by `user_id`
- Agent executions scoped to user
- JWT token revocation via Redis blacklist

### A02: Cryptographic Failures — PASS
- Passwords: bcrypt with cost factor 12
- Chat messages: AES-256-GCM field-level encryption
- JWT: HS256 with 256-bit secrets (validated in production)
- PII in audit logs: IP addresses hashed with SHA-256

### A03: Injection — PASS
- SQL: All queries use SQLAlchemy `text()` with parameter binding
- XSS: Input sanitization in `security/sanitizer.py`, CSP headers in Next.js
- Prompt injection: Detection in `security/sanitizer.py`
- No raw SQL string construction anywhere

### A04: Insecure Design — PASS
- Protocol-based architecture (interfaces/providers pattern)
- Pydantic validation on all inputs
- Rate limiting on auth endpoints (5/minute)
- Account lockout after 5 failed attempts

### A05: Security Misconfiguration — PASS
- Production config validator enforces non-empty secrets, minimum lengths
- CORS restricted to explicit origins (no wildcard in production)
- Debug endpoints disabled in production (docs_url=None, redoc_url=None)
- Secrets via GCP Secret Manager (not env files)

### A06: Vulnerable and Outdated Components — REVIEW
- Run `pip-audit` and `npm audit` before each release
- All dependencies pinned to specific versions

### A07: Identification and Authentication Failures — PASS
- JWT access tokens: 15-minute expiry
- JWT refresh tokens: 7-day expiry with rotation
- Token revocation via Redis blacklist
- Password strength: uppercase, lowercase, digit, min 8 chars
- Account lockout: 5 failures → 15-minute lock
- iss/aud claims validated

### A08: Software and Data Integrity Failures — PASS
- Input validation via Pydantic on all API endpoints
- No deserialization of untrusted data
- Agent outputs verified (citation verification, 3-layer check)

### A09: Security Logging and Monitoring Failures — PASS
- Audit logging on every API call (security/audit.py)
- Structured JSON logging for Cloud Logging
- Sentry error tracking
- Failed login attempts tracked with IP hash

### A10: Server-Side Request Forgery (SSRF) — PASS
- No user-controlled URLs fetched server-side
- External service calls only to configured endpoints (Pinecone, Neo4j, Gemini)
- All service URLs from environment config, not user input
