# Phase 6: Security & Error Patterns
**Generated:** 2026-04-03

## Authentication Mechanism

### JWT-Based Authentication (`backend/app/security/auth.py`)
- **Algorithm:** HS256 (symmetric)
- **Access Token:** 60 min expiry (configurable via `jwt_access_token_expire_minutes`)
- **Refresh Token:** 7-day expiry (configurable via `jwt_refresh_token_expire_days`)
- **Token Claims:** `sub` (user_id), `role`, `exp`, `iat`, `jti` (unique ID), `type` (access/refresh), `iss` (smriti), `aud` (smriti-api)
- **Clock Skew Tolerance:** 30 seconds
- **Separate Secrets:** Access tokens use `jwt_secret_key`, refresh tokens use `jwt_refresh_secret_key`

### Token Revocation (Redis-backed)
- **Storage:** Redis sorted set with key `revoked:jti:{jti}`
- **Auto-expiry:** Keys expire when the token would naturally expire
- **Fail-closed:** If Redis is unavailable, tokens are treated as revoked (denied)

### Password Hashing
- **Algorithm:** bcrypt
- **Cost Factor:** Configurable via `settings.bcrypt_cost_factor`
- **Implementation:** `bcrypt.gensalt()` + `bcrypt.hashpw()`

### Account Lockout
- **Max Attempts:** 10 per 5-minute window
- **Frontend:** Shows remaining attempt warnings
- **Backend:** Tracks via rate limiting

## Authorization (RBAC) — `backend/app/security/rbac.py`

### Roles
- `admin` — Full access to all endpoints
- `user` — Standard authenticated access
- `viewer` — Read-only access
- `refresh` — Internal role for refresh tokens

### Dependencies
- `get_current_user(token)` — Extracts and validates JWT, returns `TokenPayload`
- `get_current_user_optional(token)` — Same but returns `None` if no token (for public endpoints)
- `require_role(*roles)` — Factory returning a dependency that checks user's role against allowed roles

### Usage Pattern
```python
@router.get("/admin/dashboard")
async def admin_dashboard(user: TokenPayload = Depends(require_role("admin"))):
    ...
```

## Rate Limiting — `backend/app/security/rate_limiter.py`

### Implementation
- **Primary:** Redis-backed sliding window using sorted sets
- **Fallback:** In-memory sliding window (per-instance) when Redis is down
- **Key Format:** `rate:{client_ip}:{endpoint}`
- **IP Detection:** `X-Forwarded-For` header (for Cloud Run / nginx proxy), falls back to `request.client.host`

### Configuration
- Rate limits specified as human-readable strings: `"100/minute"`, `"5/hour"`, etc.
- Applied via FastAPI dependency: `Depends(rate_limit_dependency("60/minute"))`

### In-Memory Fallback
- Max 10,000 buckets (LRU eviction when exceeded)
- Thread-safe with `threading.Lock`
- Per-instance only (not shared across Cloud Run instances)

## Input Sanitization — `backend/app/security/sanitizer.py`

### `sanitize_input(text)`
- Strips HTML tags
- Removes null bytes
- Removes control characters (preserves `\t`, `\n`, `\r`)
- Collapses excessive newlines (4+ → 3)

### `sanitize_search_query(query)`
- All of `sanitize_input` plus:
- Removes prompt injection markers (26 patterns)
- Removes role-switching patterns (`system:`, `assistant:`, etc.)
- Collapses whitespace

### `detect_prompt_injection(text)`
- Checks for known injection markers
- Checks for role-switching patterns
- Detects excessive special characters (>15% of text is `` ` | < > { } [ ] ``)

### Injection Markers Detected
`ignore previous instructions`, `system prompt:`, `you are now`, `jailbreak`, `DAN mode`, `[INST]`, `<<SYS>>`, and 20+ more

## Encryption — `backend/app/security/encryption.py`

### AES-256-GCM Field-Level Encryption
- **Algorithm:** AES-256-GCM (authenticated encryption)
- **Nonce:** 12 bytes (96 bits), randomly generated per encryption
- **Key:** 32-byte key from `settings.encryption_key` (hex or base64 encoded)
- **Output:** Base64-encoded concatenation of `nonce + ciphertext + tag`

### Functions
- `encrypt_field(plaintext)` → Base64 encrypted string
- `decrypt_field(ciphertext)` → Plaintext string
- `safe_decrypt(value)` → Migration-safe: decrypts if encrypted, returns as-is if plaintext
- `_looks_like_ciphertext(value)` → Heuristic check

### Use Case
Used for sensitive database fields (PII, encrypted chat messages)

## CORS Configuration — `backend/app/main.py`

Configured via FastAPI's `CORSMiddleware`:
- Origins: Configurable via `settings.cors_origins`
- Credentials: Allowed
- Methods: All
- Headers: All

## Middleware Stack — `backend/app/core/middleware.py`

### RequestIDMiddleware
- Generates/propagates `X-Request-ID` header on every request
- Sets `request_id` in `contextvars` for async propagation
- Logs method, path, status code, duration (ms)
- Adds request_id to response headers

## Audit Logging — `backend/app/security/audit.py`

### `create_audit_log(db, action, user_id, resource_type, resource_id, ip_address, user_agent, metadata)`
- **Table:** `audit_logs`
- **IP Handling:** SHA-256 hashed with salt for DPDP compliance (no raw IPs stored)
- **Actions:** `login`, `search`, `document.view`, `admin.delete_user`, etc.

## DPDP Compliance — `backend/app/api/routes/dpdp.py`

- Digital Personal Data Protection Act compliance
- User consent recording during registration
- Right to data export/deletion endpoints
- IP address hashing in audit logs

## Logging — `backend/app/core/logging_config.py`

### PII Redaction
- Regex patterns automatically redact from all log output:
  - Email addresses
  - API keys / tokens
  - JWT tokens
  - Aadhaar numbers (12 digits)
  - PAN numbers (AAAAA9999A format)
  - Indian mobile numbers (+91...)

### Formatters
- **Production/Staging:** JSON format for Google Cloud Logging (includes severity, message, module, function, timestamp, request_id, exception)
- **Development:** Human-readable format (`%(asctime)s %(levelname)-8s %(name)s: %(message)s`)
- Both formatters apply PII redaction

### Log Levels
- Configured via `settings.log_level`
- Noisy third-party loggers silenced: `httpx`, `httpcore`, `urllib3`, `asyncio` → WARNING

## Custom Exceptions — `backend/app/security/exceptions.py`

| Exception | HTTP Status | Purpose |
|-----------|-------------|---------|
| `AuthenticationError` | 401 | Invalid JWT, expired token, missing credentials |
| `AuthorizationError` | 403 | Insufficient role/permissions |
| `RateLimitExceededError` | 429 | Rate limit exceeded (includes `retry_after` seconds) |

## Error Response Format
Structured JSON responses with `detail` field, consistent with FastAPI's HTTPException pattern.

## Security Architecture Summary

| Layer | Mechanism | Location |
|-------|-----------|----------|
| Authentication | JWT (HS256) + bcrypt | `security/auth.py` |
| Authorization | RBAC (role-based) | `security/rbac.py` |
| Rate Limiting | Redis sliding window + in-memory fallback | `security/rate_limiter.py` |
| Input Sanitization | HTML strip + injection detection | `security/sanitizer.py` |
| Encryption | AES-256-GCM field-level | `security/encryption.py` |
| Audit Logging | DB-backed, IP-hashed | `security/audit.py` |
| PII Protection | Log redaction + IP hashing | `core/logging_config.py`, `security/audit.py` |
| Request Tracing | X-Request-ID middleware | `core/middleware.py` |
| CORS | Configurable origins | `main.py` |
| Privacy | DPDP compliance routes | `api/routes/dpdp.py` |

## Security Concerns / Notes
- No hardcoded secrets found in source code (all via settings/env)
- Fail-closed Redis revocation is a good security practice
- Prompt injection detection covers common patterns but may need updates for new LLM-specific vectors
- In-memory rate limiter is per-instance only — under Cloud Run scaling, limits are not shared across instances
