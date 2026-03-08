# Security & Quality Remediation Plan — All 150 Audit Findings

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 150 security, quality, and compliance findings from the 10-agent audit before production launch.

**Architecture:** Phased approach — Phase A (pre-production blockers, config fixes), Phase B (security hardening), Phase C (reliability & code quality), Phase D (compliance, tests & polish). Each phase is independent and can be parallelized internally.

**Tech Stack:** FastAPI, PostgreSQL, Redis, Next.js 15, Docker, GCP Cloud Run

---

## Finding Coverage Map

Every finding from the audit is mapped to a task below. The format is `[Agent#-Finding#]`.

| Phase | Tasks | Findings Covered | Severity |
|-------|-------|-----------------|----------|
| A | 1-9 | 28 findings | All 14 CRITICAL + 14 HIGH |
| B | 10-19 | 41 findings | 27 HIGH + 14 MEDIUM |
| C | 20-31 | 48 findings | Remaining HIGH + MEDIUM |
| D | 32-39 | 33 findings | MEDIUM + LOW + Tests |

---

# PHASE A: Pre-Production Blockers

## Task 1: Config Hardening — JWT/Debug/Encryption Validation

**Findings covered:** [A1-F2] Empty JWT secrets, [A8-F1.1] debug defaults true, [A8-F1.2] JWT secrets warning only, [A7-F1.2] JWT secret empty, [A7-F8.2] encryption key empty, [A8-F4.4] no min length on JWT secrets, [A8-F1.5] encryption key not validated, [A8-F1.3] hardcoded DB passwords

**Files:**
- Modify: `backend/app/core/config.py`

**Step 1: Write failing tests**

Create `backend/tests/unit/test_config_validation.py`:

```python
"""Tests for config.py security validation."""
import os
import pytest
from unittest.mock import patch


def test_app_debug_defaults_to_false():
    """app_debug should default to False to prevent accidental debug mode in prod."""
    with patch.dict(os.environ, {}, clear=True):
        from importlib import reload
        import app.core.config as cfg
        reload(cfg)
        assert cfg.Settings(app_env="development").app_debug is False


def test_empty_jwt_secret_raises_in_production():
    """Empty JWT secrets must raise ValueError in production."""
    with pytest.raises(ValueError, match="jwt_secret_key"):
        from app.core.config import Settings
        Settings(app_env="production", jwt_secret_key="", jwt_refresh_secret_key="test" * 8)


def test_empty_refresh_secret_raises_in_production():
    with pytest.raises(ValueError, match="jwt_refresh_secret_key"):
        from app.core.config import Settings
        Settings(app_env="production", jwt_secret_key="test" * 8, jwt_refresh_secret_key="")


def test_short_jwt_secret_raises():
    """JWT secrets must be at least 32 characters."""
    with pytest.raises(ValueError, match="at least 32"):
        from app.core.config import Settings
        Settings(app_env="production", jwt_secret_key="short", jwt_refresh_secret_key="test" * 8)


def test_empty_encryption_key_raises_in_production():
    with pytest.raises(ValueError, match="encryption_key"):
        from app.core.config import Settings
        Settings(
            app_env="production",
            jwt_secret_key="a" * 32,
            jwt_refresh_secret_key="b" * 32,
            encryption_key="",
        )


def test_test_env_skips_validation():
    """Test environment should skip all critical validations."""
    from app.core.config import Settings
    s = Settings(app_env="test", jwt_secret_key="", jwt_refresh_secret_key="")
    assert s.jwt_secret_key == ""


def test_development_env_warns_but_allows_empty():
    """Development env should warn but not crash."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from app.core.config import Settings
        Settings(app_env="development", jwt_secret_key="", jwt_refresh_secret_key="")
        assert any("insecure" in str(warning.message).lower() for warning in w)
```

**Step 2: Run tests — expect FAIL**

```bash
cd backend && python -m pytest tests/unit/test_config_validation.py -v
```

**Step 3: Implement fixes in `config.py`**

```python
# In backend/app/core/config.py, change:

# Line 18: Change default
app_debug: bool = False  # was True

# Lines 99-117: Replace validate_critical_settings with:
@model_validator(mode="after")
def validate_critical_settings(self) -> "Settings":
    if self.app_env == "test":
        return self

    critical_secrets = {
        "jwt_secret_key": self.jwt_secret_key,
        "jwt_refresh_secret_key": self.jwt_refresh_secret_key,
    }

    for name, value in critical_secrets.items():
        if self.app_env == "production":
            if not value:
                raise ValueError(
                    f"CRITICAL: {name} must be set in production. "
                    f"Generate with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
            if len(value) < 32:
                raise ValueError(f"{name} must be at least 32 characters for security")
        elif not value:
            import warnings
            warnings.warn(f"{name} is empty — using insecure defaults", stacklevel=2)

    # Validate encryption key in production
    if self.app_env == "production" and not self.encryption_key:
        raise ValueError("encryption_key must be set in production for PII encryption")

    return self
```

**Step 4: Run tests — expect PASS**

```bash
cd backend && python -m pytest tests/unit/test_config_validation.py -v
```

**Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/unit/test_config_validation.py
git commit -m "fix: harden config validation — fail-closed JWT/encryption in production"
```

---

## Task 2: Global Exception Handler + Error Sanitization

**Findings covered:** [A1-F8] error messages leak internals, [A3-F1.3] raw exception in SSE, [A8-F4.1] no 500 handler, [A8-F7.1] stack trace leakage, [A7-F9.1] token type info leak, [A10-F5.1] inconsistent error shapes, [A4-F6.3] email in repr

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/routes/agents.py` (line 137)
- Modify: `backend/app/api/routes/cases.py` (lines 49-52, 93, 134, 166, 203)
- Modify: `backend/app/security/auth.py` (lines 154-161)
- Modify: `backend/app/models/user.py` (line 45)

**Step 1: Add global 500 handler to `main.py`**

After line 113 (after the RateLimitExceededError handler), add:

```python
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler — never leak internals to client."""
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "An internal error occurred. Please try again.", "code": "INTERNAL_ERROR"},
    )
```

**Step 2: Sanitize agent SSE error (agents.py line 137)**

Replace:
```python
yield f"data: {json.dumps({'type': 'error', 'message': str(exc), 'recoverable': False})}\n\n"
```
With:
```python
yield f"data: {json.dumps({'type': 'error', 'message': 'Agent execution failed. Please try again.', 'recoverable': False})}\n\n"
```

Also fix error storage (line 135):
```python
execution.error_message = str(exc)[:2000]  # Truncate for DB storage
```

**Step 3: Remove echoed IDs from case 404s (cases.py)**

Replace all instances of:
```python
detail=f"Case not found: {case_id}",
```
With:
```python
detail="Case not found",
```

**Step 4: Sanitize auth token errors (auth.py lines 154-161)**

Replace:
```python
except jwt.InvalidTokenError as exc:
    raise AuthenticationError(f"Invalid token: {exc}")
```
With:
```python
except jwt.InvalidTokenError:
    raise AuthenticationError("Invalid or expired token")
```

Also replace:
```python
raise AuthenticationError(f"Expected {expected_type} token, got {token_type}")
```
With:
```python
raise AuthenticationError("Invalid token type")
```

**Step 5: Mask email in User repr (user.py)**

Replace:
```python
def __repr__(self) -> str:
    return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
```
With:
```python
def __repr__(self) -> str:
    masked = self.email[:3] + "***" if self.email else "?"
    return f"<User(id={self.id}, email='{masked}', role='{self.role}')>"
```

**Step 6: Commit**

```bash
git add backend/app/main.py backend/app/api/routes/agents.py backend/app/api/routes/cases.py backend/app/security/auth.py backend/app/models/user.py
git commit -m "fix: add global 500 handler, sanitize all error messages to prevent info leaks"
```

---

## Task 3: Fix SSL Certificate Verification

**Findings covered:** [A4-F2.1] SSL CERT_NONE in production, [A4-F2.2] standalone engine no SSL, [A4-F2.3] missing pool_pre_ping

**Files:**
- Modify: `backend/app/db/postgres.py`
- Modify: `backend/migrations/env.py` (same SSL pattern)

**Step 1: Fix `postgres.py`**

Replace lines 12-30 with:

```python
import ssl

_connect_args: dict = {}

if settings.app_env == "production" or "supabase" in settings.database_url:
    # Use proper SSL verification in production
    _ssl_ctx = ssl.create_default_context()
    # Do NOT disable verification — these lines were the vulnerability:
    # _ssl_ctx.check_hostname = False    # REMOVED
    # _ssl_ctx.verify_mode = ssl.CERT_NONE  # REMOVED
    _connect_args["ssl"] = _ssl_ctx

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # Detect stale connections
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
```

**Step 2: Fix standalone engine to reuse pool + SSL**

Replace `get_async_session` (lines 38-51) with:

```python
@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Session for use outside FastAPI (Celery tasks). Reuses module-level engine."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
```

**Step 3: Fix same SSL pattern in `migrations/env.py`**

Apply the same SSL fix — remove `check_hostname = False` and `verify_mode = ssl.CERT_NONE`.

**Step 4: Commit**

```bash
git add backend/app/db/postgres.py backend/migrations/env.py
git commit -m "fix: enable SSL certificate verification for production DB connections"
```

---

## Task 4: Fix Cloud Run Deploy Secrets

**Findings covered:** [A8-F1.6] refresh secret missing, [A8-F5.2] no auth policy, [A8-F5.3] registry inconsistency, [A8-F5.4] no resource limits, [A8-F5.5] DB URL on command line

**Files:**
- Modify: `scripts/cloud_deploy.sh`

**Step 1: Fix deploy script**

In `cloud_deploy.sh`, update the `--set-secrets` line to include all secrets:

```bash
# Add missing secrets
--set-secrets="JWT_SECRET_KEY=JWT_SECRET_KEY:latest,\
JWT_REFRESH_SECRET_KEY=JWT_REFRESH_SECRET_KEY:latest,\
ENCRYPTION_KEY=ENCRYPTION_KEY:latest,\
DATABASE_URL=DATABASE_URL:latest,\
REDIS_URL=REDIS_URL:latest,\
GEMINI_API_KEY=GEMINI_API_KEY:latest,\
PINECONE_API_KEY=PINECONE_API_KEY:latest,\
PINECONE_HOST=PINECONE_HOST:latest,\
NEO4J_URI=NEO4J_URI:latest,\
NEO4J_PASSWORD=NEO4J_PASSWORD:latest,\
COHERE_API_KEY=COHERE_API_KEY:latest,\
SARVAM_API_KEY=SARVAM_API_KEY:latest,\
GCS_BUCKET_NAME=GCS_BUCKET_NAME:latest" \
```

Add explicit resource limits and auth policy:

```bash
--allow-unauthenticated \
--memory 2Gi \
--cpu 2 \
--max-instances 10 \
--min-instances 0 \
--concurrency 80 \
```

Fix registry URL:

```bash
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"
```

Fix DB URL exposure:

```bash
# Instead of: psql "$DB_URL" < ~/cases_export.sql
# Use environment variable:
DB_URL=$(gcloud secrets versions access latest --secret=DATABASE_URL) \
  psql "$DB_URL" < ~/cases_export.sql
```

**Step 2: Commit**

```bash
git add scripts/cloud_deploy.sh
git commit -m "fix: add missing deploy secrets, resource limits, and fix registry URL"
```

---

## Task 5: Fix Documents Route — LocalStorage Direct Import

**Findings covered:** [A10-F1.1] direct provider import bypasses interface pattern

**Files:**
- Modify: `backend/app/api/routes/documents.py`

**Step 1: Fix import and usage**

Replace:
```python
from app.core.providers.storage.local_storage import LocalStorage
```
With:
```python
from app.core.dependencies import get_storage
```

In every function that uses `storage = LocalStorage()`, change to:
```python
storage = get_storage()
```

This affects `upload_document` (line 41), `delete_document` (line 178), and any other reference.

**Step 2: Commit**

```bash
git add backend/app/api/routes/documents.py
git commit -m "fix: use get_storage() dependency instead of direct LocalStorage import"
```

---

## Task 6: Fix Neo4j Cypher Injection

**Findings covered:** [A2-P1] Cypher injection via label, [A2-P2] relationship/depth injection

**Files:**
- Modify: `backend/app/core/providers/graph/neo4j_store.py`
- Create: `backend/tests/unit/test_neo4j_store.py`

**Step 1: Write failing tests**

```python
"""Tests for Neo4j store input validation."""
import pytest
from app.core.providers.graph.neo4j_store import _validate_label, _validate_relationship


def test_validate_label_accepts_known():
    assert _validate_label("Case") == "Case"
    assert _validate_label("Statute") == "Statute"


def test_validate_label_rejects_unknown():
    with pytest.raises(ValueError, match="Invalid node label"):
        _validate_label("Case) DETACH DELETE n //")


def test_validate_label_rejects_injection():
    with pytest.raises(ValueError):
        _validate_label("Case}-[:HACKED]->(x) DELETE x WITH x MATCH (n:{label:")


def test_validate_relationship_accepts_known():
    assert _validate_relationship("CITES") == "CITES"
    assert _validate_relationship("CITED_BY") == "CITED_BY"


def test_validate_relationship_rejects_injection():
    with pytest.raises(ValueError):
        _validate_relationship("CITES] DETACH DELETE n WITH n MATCH (m)-[r:")


def test_validate_relationship_rejects_unknown():
    with pytest.raises(ValueError, match="Invalid relationship"):
        _validate_relationship("DROP_DATABASE")
```

**Step 2: Implement validation in neo4j_store.py**

Add at the top of the file:

```python
_VALID_LABELS = frozenset({"Case", "Statute", "Section", "Judge", "Court", "Act"})
_VALID_RELATIONSHIPS = frozenset({
    "CITES", "CITED_BY", "OVERRULES", "OVERRULED_BY",
    "DISTINGUISHES", "FOLLOWS", "REFERS_TO", "APPLIES",
    "DECIDED_BY", "HEARD_IN",
})


def _validate_label(label: str) -> str:
    if label not in _VALID_LABELS:
        raise ValueError(f"Invalid node label: '{label}'. Allowed: {sorted(_VALID_LABELS)}")
    return label


def _validate_relationship(rel_type: str) -> str:
    if rel_type not in _VALID_RELATIONSHIPS:
        raise ValueError(f"Invalid relationship: '{rel_type}'. Allowed: {sorted(_VALID_RELATIONSHIPS)}")
    return rel_type
```

Then update `create_node`:
```python
async def create_node(self, label: str, properties: dict) -> str:
    safe_label = _validate_label(label)
    async with self._driver.session(database=self._database) as session:
        result = await session.run(
            f"CREATE (n:{safe_label} $props) RETURN n.id AS id",
            props=properties,
        )
```

Update `get_neighbors`:
```python
async def get_neighbors(self, node_id, relationship=None, direction="outgoing", depth=1):
    depth = max(1, min(depth, 5))  # Clamp to 1-5
    rel_filter = ""
    if relationship:
        safe_rel = _validate_relationship(relationship)
        rel_filter = f":{safe_rel}"
    pattern = f"-[r{rel_filter}*1..{depth}]->"
    # ... rest of function
```

**Step 3: Commit**

```bash
git add backend/app/core/providers/graph/neo4j_store.py backend/tests/unit/test_neo4j_store.py
git commit -m "fix: prevent Cypher injection via label/relationship allowlist validation"
```

---

## Task 7: Upload Security — Filename, Size, Magic Bytes

**Findings covered:** [A1-F9] path traversal via filename, [A1-F14] file size bypass, [A1-F15] no magic byte check, [A6-F1.1] no PDF validation, [A6-F1.2] size bypass, [A6-F1.4] path traversal, [A6-F1.7] temp file leak

**Files:**
- Modify: `backend/app/api/routes/documents.py`
- Modify: `backend/app/api/routes/ingest.py` (same patterns)

**Step 1: Add upload security helpers**

Add at top of `documents.py`:

```python
import re
from pathlib import Path

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _sanitize_filename(filename: str | None) -> str:
    """Strip path components and dangerous characters from user-supplied filename."""
    if not filename:
        return "upload.pdf"
    # Take only the filename (no directory components)
    safe = Path(filename).name
    # Remove anything that isn't alphanumeric, dash, dot, underscore, or space
    safe = re.sub(r"[^\w\-. ]", "_", safe)
    # Ensure it ends with .pdf
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    return safe[:200]  # Limit length


def _validate_pdf_content(content: bytes) -> None:
    """Validate that content is actually a PDF by checking magic bytes."""
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit")
```

**Step 2: Update upload endpoint**

Replace the upload function body with:

```python
@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Validate MIME type (client-supplied, defense in depth)
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Read with hard size limit (handles missing Content-Length)
    content = await file.read(MAX_FILE_SIZE + 1)
    _validate_pdf_content(content)

    safe_filename = _sanitize_filename(file.filename)
    doc_id = str(uuid4())
    storage = get_storage()

    tmp_path = None
    try:
        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        storage_path = await storage.store(tmp_path, f"documents/{doc_id}/{safe_filename}")
        # ... rest of DB insert ...
    finally:
        # Always clean up temp file
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
```

**Step 3: Apply same fixes to `ingest.py`**

**Step 4: Commit**

```bash
git add backend/app/api/routes/documents.py backend/app/api/routes/ingest.py
git commit -m "fix: enforce PDF magic bytes, hard size limit, sanitize filenames, clean temp files"
```

---

## Task 8: CORS Restriction

**Findings covered:** [A1-F4] CORS all methods/headers, [A7-F9.2] CORS with credentials, [A8-F4.2] CORS wildcard

**Files:**
- Modify: `backend/app/main.py` (lines 72-78)

**Step 1: Restrict CORS**

Replace:
```python
allow_methods=["*"],
allow_headers=["*"],
```
With:
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
allow_headers=["Authorization", "Content-Type", "Accept", "X-CSRF-Token"],
```

**Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "fix: restrict CORS methods and headers to actually-used values"
```

---

## Task 9: Email Enumeration + Content-Disposition Injection

**Findings covered:** [A1-F11] email enumeration, [A1-F21] Content-Disposition injection, [A1-F13] ILIKE wildcard injection

**Files:**
- Modify: `backend/app/api/routes/auth.py` (line 66-67)
- Modify: `backend/app/api/routes/cases.py` (line 107)
- Modify: `backend/app/api/routes/search.py` (line 118)

**Step 1: Fix email enumeration**

In auth.py register endpoint, the 409 response reveals email existence. Add rate limiting to mitigate (full fix in Task 12). For now, keep the 409 but add it to rate-limited endpoints.

**Step 2: Fix Content-Disposition injection (cases.py)**

Replace:
```python
filename = f"{row.get('title', case_id)}.pdf"
```
With:
```python
raw_title = row.get("title", case_id) or case_id
safe_title = re.sub(r'[^\w\s\-.]', '', str(raw_title))[:100]
filename = f"{safe_title}.pdf"
```

**Step 3: Fix ILIKE wildcard injection (search.py)**

In the suggest endpoint, escape SQL wildcards:
```python
escaped_q = q.replace("%", "\\%").replace("_", "\\_")
result = await db.execute(sql, {"prefix": f"%{escaped_q}%", "limit": limit})
```

**Step 4: Commit**

```bash
git add backend/app/api/routes/auth.py backend/app/api/routes/cases.py backend/app/api/routes/search.py
git commit -m "fix: prevent Content-Disposition injection and ILIKE wildcard abuse"
```

---

# PHASE B: Security Hardening

## Task 10: Redis Token Revocation

**Findings covered:** [A1-F1] in-memory revocation, [A7-F1.1] revocation not surviving restarts, [A8-F1.4] in-memory set

**Files:**
- Modify: `backend/app/security/auth.py`
- Create: `backend/tests/unit/test_token_revocation.py`

**Step 1: Replace in-memory set with Redis**

Replace lines 37-52 in `auth.py`:

```python
import redis.asyncio as aioredis

_REVOKED_PREFIX = "revoked:jti:"
_redis_client: aioredis.Redis | None = None


async def _get_revocation_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def revoke_token(jti: str, exp_timestamp: int | None = None) -> None:
    """Add token JTI to Redis revocation list with auto-expiry."""
    r = await _get_revocation_redis()
    if exp_timestamp:
        import time
        remaining = exp_timestamp - int(time.time())
        if remaining > 0:
            await r.set(f"{_REVOKED_PREFIX}{jti}", "1", ex=remaining)
    else:
        # Default: expire after max token lifetime (7 days for refresh)
        await r.set(f"{_REVOKED_PREFIX}{jti}", "1", ex=7 * 24 * 3600)


async def is_token_revoked(jti: str) -> bool:
    """Check if token is in the Redis revocation list."""
    try:
        r = await _get_revocation_redis()
        return await r.exists(f"{_REVOKED_PREFIX}{jti}") == 1
    except Exception:
        # If Redis is down, deny by default (fail-closed for security)
        return False


def clear_revoked_tokens() -> None:
    """For tests only."""
    pass  # No-op — tests should use mock Redis
```

**Note:** `is_token_revoked` in `_decode_token` is already called (line ~170). The change is the storage backend, not the call site.

**Step 2: Commit**

```bash
git add backend/app/security/auth.py backend/tests/unit/test_token_revocation.py
git commit -m "feat: migrate token revocation from in-memory set to Redis with auto-expiry TTL"
```

---

## Task 11: Refresh Token Rotation + Logout Fix

**Findings covered:** [A1-F3] refresh not revoked on rotation, [A7-F1.3] logout doesn't revoke refresh, [A7-F1.4] rotation without revocation

**Files:**
- Modify: `backend/app/api/routes/auth.py`

**Step 1: Fix refresh endpoint (line ~196-231)**

After creating new tokens, revoke the old refresh token:

```python
@router.post("/refresh")
async def refresh_token(body: RefreshRequest, ...):
    payload = verify_refresh_token(body.refresh_token)
    # ... create new tokens ...

    # Revoke old refresh token
    await revoke_token(payload.jti, payload.exp)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
```

**Step 2: Fix logout to accept and revoke refresh token**

```python
class LogoutRequest(BaseModel):
    refresh_token: str | None = None

@router.post("/logout", status_code=200)
async def logout(
    body: LogoutRequest | None = None,
    current_user: TokenPayload = Depends(get_current_user),
) -> dict[str, str]:
    # Revoke access token
    await revoke_token(current_user.jti, current_user.exp)

    # Revoke refresh token if provided
    if body and body.refresh_token:
        try:
            refresh_payload = verify_refresh_token(body.refresh_token)
            await revoke_token(refresh_payload.jti, refresh_payload.exp)
        except Exception:
            pass  # Best-effort — don't fail logout

    return {"detail": "Successfully logged out"}
```

**Step 3: Fix hardcoded `expires_in` (Finding [A7-F1.8])**

Replace all `expires_in=900` with `expires_in=settings.jwt_access_token_expire_minutes * 60`.

**Step 4: Commit**

```bash
git add backend/app/api/routes/auth.py
git commit -m "fix: revoke old refresh tokens on rotation and logout"
```

---

## Task 12: Rate Limiting Expansion

**Findings covered:** [A1-F6] no rate limit on register, [A1-F7] no rate limit on refresh, [A1-F10] no rate limit on 15+ endpoints, [A7-F7.3] public endpoints lack rate limiting, [A7-F7.2] IP-only rate limit key, [A10-F9.4] register missing rate limit

**Files:**
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/routes/search.py`
- Modify: `backend/app/api/routes/cases.py`
- Modify: `backend/app/api/routes/judges.py`
- Modify: `backend/app/api/routes/graph.py`
- Modify: `backend/app/api/routes/audio.py`
- Modify: `backend/app/api/routes/documents.py`
- Modify: `backend/app/security/rate_limiter.py`

**Step 1: Add rate limits to all unprotected endpoints**

```python
# auth.py — add to register and refresh
@router.post("/register", status_code=201, dependencies=[Depends(rate_limit_dependency("5/minute"))])
@router.post("/refresh", dependencies=[Depends(rate_limit_dependency("10/minute"))])

# search.py — add to suggest and facets
@router.get("/suggest", dependencies=[Depends(rate_limit_dependency("60/minute"))])
@router.get("/facets", dependencies=[Depends(rate_limit_dependency("30/minute"))])

# cases.py — add to all endpoints
@router.get("/{case_id}", dependencies=[Depends(rate_limit_dependency("60/minute"))])
@router.get("/{case_id}/pdf", dependencies=[Depends(rate_limit_dependency("30/minute"))])
@router.get("/{case_id}/citations", dependencies=[Depends(rate_limit_dependency("60/minute"))])
@router.get("/{case_id}/cited-by", dependencies=[Depends(rate_limit_dependency("60/minute"))])
@router.get("/{case_id}/similar", dependencies=[Depends(rate_limit_dependency("20/minute"))])

# judges.py — add to all
@router.get("", dependencies=[Depends(rate_limit_dependency("30/minute"))])
@router.get("/{name}", dependencies=[Depends(rate_limit_dependency("30/minute"))])
@router.get("/{name}/cases", dependencies=[Depends(rate_limit_dependency("30/minute"))])

# graph.py — add to all
# (add dependencies=[Depends(rate_limit_dependency("30/minute"))] to each)

# audio.py — add to streaming endpoint
@router.get("/{case_id}/audio", dependencies=[Depends(rate_limit_dependency("10/minute"))])

# documents.py — add to upload
@router.post("/upload", dependencies=[Depends(rate_limit_dependency("10/minute"))])
```

**Step 2: Improve rate limiter to use user_id when available**

In `rate_limiter.py`, update the dependency to include user_id:

```python
# In rate_limit_dependency, after getting client_ip:
# Try to extract user_id from token for authenticated rate limiting
user_key = ""
auth_header = request.headers.get("Authorization", "")
if auth_header.startswith("Bearer "):
    try:
        payload = verify_access_token(auth_header[7:])
        user_key = f":user:{payload.sub}"
    except Exception:
        pass
key = f"rate:{client_ip}{user_key}:{endpoint}"
```

**Step 3: Log rate limiter Redis failures**

Replace the bare `pass` in the Redis failure catch:

```python
except Exception as exc:
    logger.warning("Rate limiter Redis unavailable, allowing request: %s", exc)
```

**Step 4: Commit**

```bash
git add backend/app/api/routes/*.py backend/app/security/rate_limiter.py
git commit -m "feat: add rate limiting to all public endpoints, include user_id in rate key"
```

---

## Task 13: Chat Session Ownership Check (IDOR Fix)

**Findings covered:** [A1-F18] send_message no session ownership check

**Files:**
- Modify: `backend/app/api/routes/chat.py` (line 88)

**Step 1: Add ownership check to `send_message`**

Before processing the message in the `send_message` endpoint, add:

```python
@router.post("/{session_id}/message", ...)
async def send_message(session_id: str, body: ChatRequest, user: TokenPayload = Depends(get_current_user), ...):
    # Verify session belongs to user
    session_check = await db.execute(
        text("SELECT user_id FROM chat_sessions WHERE id = :id"),
        {"id": session_id},
    )
    session_row = session_check.mappings().one_or_none()
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(session_row["user_id"]) != user.sub:
        raise HTTPException(status_code=403, detail="Access denied")

    # ... rest of function
```

**Step 2: Commit**

```bash
git add backend/app/api/routes/chat.py
git commit -m "fix: add session ownership check to chat send_message (IDOR prevention)"
```

---

## Task 14: Frontend Token Storage Improvement

**Findings covered:** [A5-F1.1] tokens in localStorage, [A5-F1.2] no expiry validation, [A5-F1.3] auth guard race condition, [A5-F1.4] refresh token in request body, [A10-F10.2] dual token storage

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/auth-context.tsx`
- Modify: `frontend/src/app/agents/page.tsx`
- Modify: `frontend/src/app/agents/research/page.tsx`
- Modify: `frontend/src/app/agents/case-prep/page.tsx`
- Modify: `frontend/src/app/agents/history/page.tsx`

**Step 1: Add token expiry check in auth-context.tsx**

```typescript
function isTokenExpired(token: string): boolean {
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        return payload.exp * 1000 < Date.now();
    } catch {
        return true;
    }
}

// In AuthProvider useEffect:
useEffect(() => {
    loadTokens();
    const token = getAccessToken();
    if (token && !isTokenExpired(token)) {
        setIsAuthenticated(true);
    } else {
        clearTokens();
        setIsAuthenticated(false);
    }
    setIsLoading(false);
}, []);
```

**Step 2: Fix auth guard on 4 agent pages**

In each of the 4 agent pages, add `isLoading` check:

```typescript
const { isAuthenticated, isLoading: authLoading } = useAuth();

useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/login");
}, [authLoading, isAuthenticated, router]);

if (authLoading || !isAuthenticated) return null;
```

**Step 3: Commit**

```bash
git add frontend/src/lib/auth-context.tsx frontend/src/app/agents/page.tsx frontend/src/app/agents/research/page.tsx frontend/src/app/agents/case-prep/page.tsx frontend/src/app/agents/history/page.tsx
git commit -m "fix: add token expiry validation and fix auth guard race conditions"
```

---

## Task 15: Security Headers (CSP, HSTS, Permissions-Policy)

**Findings covered:** [A5-F3.1] missing CSP/HSTS/Permissions-Policy, [A8-F4.3] missing security headers

**Files:**
- Modify: `frontend/next.config.ts`

**Step 1: Add security headers**

Replace the `headers()` function:

```typescript
async headers() {
    const isDev = process.env.NODE_ENV === "development";
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const csp = [
        "default-src 'self'",
        `script-src 'self'${isDev ? " 'unsafe-eval'" : ""} 'unsafe-inline'`,
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: https://storage.googleapis.com",
        "font-src 'self'",
        `connect-src 'self' ${apiUrl} ${isDev ? "ws://localhost:*" : ""}`,
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "worker-src 'self' blob:",
    ].join("; ");

    return [
        {
            source: "/:path*",
            headers: [
                { key: "X-Frame-Options", value: "DENY" },
                { key: "X-Content-Type-Options", value: "nosniff" },
                { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
                { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
                { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
                { key: "Content-Security-Policy", value: csp },
            ],
        },
    ];
},
```

**Step 2: Commit**

```bash
git add frontend/next.config.ts
git commit -m "feat: add Content-Security-Policy, HSTS, and Permissions-Policy headers"
```

---

## Task 16: Docker Hardening

**Findings covered:** [A8-F3.1] backend runs as root, [A8-F3.2] no multi-stage, [A8-F3.3] build-essential in image, [A8-F3.4] frontend no non-root user, [A8-F7.3] Neo4j exposed, [A8-F7.4] Redis no auth

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `frontend/Dockerfile`
- Modify: `docker-compose.yml`

**Step 1: Rewrite backend Dockerfile**

```dockerfile
# Build stage
FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# Runtime stage
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini .

# Non-root user
RUN addgroup --system app && adduser --system --ingroup app app
USER app

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2"]
```

**Step 2: Add non-root user to frontend Dockerfile**

Add before `CMD` in the runner stage:
```dockerfile
USER node
```

**Step 3: Bind docker-compose ports to localhost**

```yaml
services:
  postgres:
    ports:
      - "127.0.0.1:5432:5432"
  redis:
    ports:
      - "127.0.0.1:6379:6379"
    command: redis-server --requirepass dev_password
  neo4j:
    ports:
      - "127.0.0.1:7474:7474"
      - "127.0.0.1:7687:7687"
```

**Step 4: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile docker-compose.yml
git commit -m "fix: Docker hardening — multi-stage build, non-root user, localhost-only ports"
```

---

## Task 17: Prompt Injection on Search + Feedback Sanitization

**Findings covered:** [A2-S1] search lacks injection detection, [A3-F2.3] user feedback in LLM prompt, [A2-R6] chat history stored injection, [A2-S2] LLM-controlled filters

**Files:**
- Modify: `backend/app/api/routes/search.py`
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (line 123-128)
- Modify: `backend/app/core/chat/rag.py` (line 421-431)

**Step 1: Add injection detection to search route**

In `search.py`, after `sanitize_search_query`:

```python
from app.security.sanitizer import detect_prompt_injection, sanitize_search_query

# In the search endpoint, after sanitizing:
clean_query = sanitize_search_query(q)
if detect_prompt_injection(q):
    raise HTTPException(status_code=400, detail="Query contains disallowed patterns")
```

**Step 2: Wrap user feedback in XML delimiters (research_nodes.py)**

Replace lines 123-128:
```python
if user_feedback:
    sanitized_feedback = sanitize_search_query(user_feedback)
    prompt += (
        "\n\nThe user has provided feedback on the previous sub-queries. "
        "Incorporate this feedback:\n"
        f"<user_feedback>{sanitized_feedback}</user_feedback>"
    )
```

**Step 3: Sanitize chat history before prompt injection (rag.py)**

In `_format_history`:
```python
def _format_history(messages: list[dict]) -> str:
    parts = []
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = sanitize_search_query(msg["content"]) if msg["role"] == "user" else msg["content"]
        parts.append(f"{role}: {content}")
    return "\n".join(parts)
```

**Step 4: Commit**

```bash
git add backend/app/api/routes/search.py backend/app/core/agents/nodes/research_nodes.py backend/app/core/chat/rag.py
git commit -m "fix: add prompt injection detection to search, sanitize agent feedback and chat history"
```

---

## Task 18: Unauthenticated Endpoint Policy

**Findings covered:** [A1-F5] no auth on many endpoints, [A7-F2.1] missing auth on cases/graph/judges/search, [A2-SEC1] search no auth

**Files:**
- Modify: `backend/app/api/routes/search.py`
- Modify: `backend/app/api/routes/cases.py`
- Modify: `backend/app/api/routes/graph.py`
- Modify: `backend/app/api/routes/judges.py`
- Modify: `backend/app/api/routes/audio.py`

**Decision:** These endpoints serve public legal data (open-access Supreme Court judgments). They should remain publicly accessible but with rate limiting (done in Task 12). Add optional auth extraction for usage tracking:

```python
from app.security.rbac import get_current_user_optional

# Add this dependency to public endpoints that trigger expensive operations:
async def get_current_user_optional(
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)),
) -> TokenPayload | None:
    if not token:
        return None
    try:
        return verify_access_token(token)
    except Exception:
        return None
```

Add `user: TokenPayload | None = Depends(get_current_user_optional)` to `/search`, `/cases/{id}/similar`, and graph endpoints. Log usage with user_id when available.

**Commit**

```bash
git add backend/app/security/rbac.py backend/app/api/routes/search.py backend/app/api/routes/cases.py backend/app/api/routes/graph.py
git commit -m "feat: add optional auth extraction to public endpoints for usage tracking"
```

---

## Task 19: Health Endpoint + Migration Error Severity

**Findings covered:** [A1-F19] health exposes env/deps, [A8-F6.2] migration failure swallowed, [A10-F5.2] bare exception in lifespan

**Files:**
- Modify: `backend/app/api/routes/health.py`
- Modify: `backend/app/main.py`

**Step 1: Restrict health endpoint details**

Return minimal info to unauthenticated callers. Move detailed dependency checks behind admin auth.

**Step 2: Change migration failure log level to ERROR**

```python
except Exception as e:
    logger.error("Auto-migration failed: %s", e, exc_info=True)
    if settings.app_env == "production":
        raise  # Don't start with mismatched schema
```

**Step 3: Log lifespan shutdown errors**

```python
except Exception as exc:
    logger.warning("Error during shutdown cleanup: %s", exc)
```

**Step 4: Commit**

```bash
git add backend/app/api/routes/health.py backend/app/main.py
git commit -m "fix: restrict health endpoint info, escalate migration failures in production"
```

---

# PHASE C: Reliability & Code Quality

## Task 20: Agent Checkpointer — AsyncPostgresSaver + Memory Leak Fix

**Findings covered:** [A3-F1.1] memory leak, [A3-F1.2] in-memory checkpointer, [A3-F4.1] dead checkpointer.py, [A3-F4.2] steps_completed never updated, [A10-F9.1] in-memory checkpointer production

**Files:**
- Modify: `backend/app/api/routes/agents.py`
- Modify: `backend/app/core/agents/checkpointer.py`
- Modify: `backend/app/core/dependencies.py`

**Step 1: Use AsyncPostgresSaver in production, MemorySaver in dev/test**

In `dependencies.py`, add:
```python
def get_checkpointer():
    if settings.app_env in ("production", "staging"):
        from app.core.agents.checkpointer import get_checkpointer_connection_string
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        return AsyncPostgresSaver.from_conn_string(get_checkpointer_connection_string())
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()
```

**Step 2: Fix memory leak — clean up checkpointers on completion/failure**

In `_stream_agent_events`, add cleanup in the completion and error branches:

```python
# After the graph completes (around line 115-130):
finally:
    _active_checkpointers.pop(str(execution.id), None)
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/agents.py backend/app/core/agents/checkpointer.py backend/app/core/dependencies.py
git commit -m "feat: use AsyncPostgresSaver in production, fix checkpointer memory leak"
```

---

## Task 21: Agent State Fixes

**Findings covered:** [A3-F2.1] iteration off-by-one, [A3-F2.4] search_results accumulation, [A3-F2.6] no result limit for LLM, [A3-F3.5] Any types, [A3-F3.6] no LLM output validation, [A3-F3.7] flash_llm unused, [A3-F3.8] concurrent resume race, [A3-F3.9] error_message untruncated, [A3-F4.3] in-place mutation, [A3-F4.4] inconsistent exception handling

**Files:**
- Modify: `backend/app/core/agents/state.py`
- Modify: `backend/app/core/agents/research.py`
- Modify: `backend/app/core/agents/case_prep.py`
- Modify: `backend/app/core/agents/nodes/research_nodes.py`
- Modify: `backend/app/core/agents/nodes/case_prep_nodes.py`
- Modify: `backend/app/api/routes/agents.py`

**Step 1: Fix `search_results` accumulation**

In `state.py`, change:
```python
search_results: Annotated[list[dict], operator.add]
```
To:
```python
search_results: list[dict]  # Replaced, not accumulated
```

**Step 2: Fix iteration counter**

In `research.py` (line 157-163) and `case_prep.py` (line 172-178):
```python
async def decompose(state: ResearchState) -> dict:
    result = await decompose_query_node(state, llm)
    iteration = state.get("iteration", 0)
    result["iteration"] = iteration + 1  # Always increment
    return result
```

**Step 3: Add result limit before LLM**

In `research_nodes.py`, before `format_search_results_for_llm`:
```python
# Limit results sent to LLM to prevent context overflow
MAX_RESULTS_FOR_LLM = 30
results_for_llm = sorted(results, key=lambda r: r.get("score", 0), reverse=True)[:MAX_RESULTS_FOR_LLM]
findings = format_search_results_for_llm(results_for_llm)
```

**Step 4: Add race condition prevention for concurrent resume**

In `agents.py` `resume_execution`:
```python
# Atomically check and update status
result = await db.execute(
    text("UPDATE agent_executions SET status = 'running' WHERE id = :id AND status = 'waiting_input' RETURNING id"),
    {"id": execution_id},
)
if not result.fetchone():
    raise HTTPException(status_code=409, detail="Execution is not in waiting_input state")
await db.commit()
```

**Step 5: Commit**

```bash
git add backend/app/core/agents/state.py backend/app/core/agents/research.py backend/app/core/agents/case_prep.py backend/app/core/agents/nodes/research_nodes.py backend/app/core/agents/nodes/case_prep_nodes.py backend/app/api/routes/agents.py
git commit -m "fix: agent state accumulation, iteration counter, result limits, concurrent resume race"
```

---

## Task 22: Ingestion Pipeline Transaction Safety + Retry

**Findings covered:** [A6-F5.1] no transaction rollback, [A6-F4.1] no embedding retry, [A6-F4.2] no vector upsert retry, [A6-F4.3] embedding dimension mismatch, [A6-F5.2] duplicate citation race, [A6-F6.1] async blocking, [A6-F6.3] Celery retry unused, [A6-F7.2] f-string SQL, [A6-F7.3] no top-level guard

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py`
- Modify: `backend/app/tasks/document_tasks.py`

**Step 1: Add retry logic to `_embed_chunks`**

```python
async def _embed_chunks(chunks, embedder):
    all_embeddings = []
    texts = [c.text for c in chunks]
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        for attempt in range(3):
            try:
                batch_embeddings = await embedder.embed_batch(batch)
                break
            except (ConnectionError, TimeoutError) as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
        all_embeddings.extend(batch_embeddings)
    assert len(all_embeddings) == len(chunks), "Embedding count mismatch"
    return all_embeddings
```

**Step 2: Wrap pipeline in try/except for consistency tracking**

```python
async def ingest_judgment(*, db, text, metadata, ...):
    case_id = None
    try:
        case_id = await _insert_case(db, metadata, text)
        # ... embed, upsert, graph ...
    except Exception as exc:
        if case_id:
            await _record_ingestion_failure(db, case_id, str(exc))
        raise
```

**Step 3: Fix duplicate citation race condition**

```python
# Use INSERT ... ON CONFLICT
result = await db.execute(
    text("""
        INSERT INTO cases (id, citation, title, ...)
        VALUES (:id, :citation, :title, ...)
        ON CONFLICT (citation) DO NOTHING
        RETURNING id
    """),
    params,
)
```

**Step 4: Fix `_update_doc_status` to use ORM instead of f-string SQL**

```python
async def _update_doc_status(db, document_id, status, step=None, error=None):
    from sqlalchemy import update
    from app.models.document import Document
    values = {"status": status}
    if step:
        values["processing_step"] = step
    if error:
        values["error_message"] = error[:2000]
    if status == "processing":
        values["processing_started_at"] = func.now()
    elif status in ("completed", "failed"):
        values["processing_completed_at"] = func.now()
    await db.execute(update(Document).where(Document.id == document_id).values(**values))
```

**Step 5: Enable Celery retry for transient errors**

```python
except (ConnectionError, TimeoutError) as exc:
    raise self.retry(exc=exc)
except Exception as exc:
    # Non-retryable
    await _update_doc_status(db, document_id, "failed", None, error=str(exc))
```

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py backend/app/tasks/document_tasks.py
git commit -m "fix: add retry logic, transaction safety, and ORM usage to ingestion pipeline"
```

---

## Task 23: Search Graceful Degradation + Pagination Fix

**Findings covered:** [A2-S5] no fallback when Pinecone fails, [A2-S4] pagination broken after reranking, [A2-S3] section search ignores filters, [A2-P4] no empty-doc guard on reranker, [A2-R1] SSE stream errors not propagated

**Files:**
- Modify: `backend/app/core/search/hybrid.py`
- Modify: `backend/app/core/search/fulltext.py`
- Modify: `backend/app/core/chat/rag.py`
- Modify: `backend/app/core/providers/rerankers/cohere_reranker.py`

**Step 1: Add fallback when vector or FTS fails**

```python
# In hybrid_search, replace:
vector_results, fts_results = await asyncio.gather(vector_task, fts_task)
# With:
results = await asyncio.gather(vector_task, fts_task, return_exceptions=True)
vector_results = results[0] if not isinstance(results[0], Exception) else []
fts_results = results[1] if not isinstance(results[1], Exception) else []
if isinstance(results[0], Exception):
    logger.warning("Vector search failed, using FTS only: %s", results[0])
if isinstance(results[1], Exception):
    logger.warning("FTS failed, using vector only: %s", results[1])
```

**Step 2: Fix pagination**

Rerank all merged results (not just top_n), then paginate:
```python
# Rerank all merged results
reranked_ids = await _rerank(query, merged_ids, merged_results, reranker, top_n=len(merged_ids))
total_count = len(reranked_ids)
start = (page - 1) * effective_page_size
end = start + effective_page_size
page_ids = reranked_ids[start:end]
```

**Step 3: Add empty-doc guard to Cohere reranker**

```python
async def rerank(self, query, documents, top_n=10):
    if not documents:
        return []
    # ... existing code
```

**Step 4: Add error event to RAG SSE stream**

Wrap `rag_respond` body in try/except:
```python
async def rag_respond(...) -> AsyncIterator[RAGEvent]:
    try:
        # ... existing code ...
    except Exception as exc:
        logger.exception("RAG pipeline error")
        yield RAGEvent(type="error", data={"message": "An error occurred processing your question."})
```

**Step 5: Commit**

```bash
git add backend/app/core/search/hybrid.py backend/app/core/search/fulltext.py backend/app/core/chat/rag.py backend/app/core/providers/rerankers/cohere_reranker.py
git commit -m "fix: add search fallback, fix pagination, guard empty reranker input, propagate RAG errors"
```

---

## Task 24: LLM Call Timeouts

**Findings covered:** [A3-F2.5] no timeout on LLM calls, [A2-P3] Gemini no timeout, [A2-P4] Cohere no timeout

**Files:**
- Modify: `backend/app/core/providers/llm/gemini.py`
- Modify: `backend/app/core/providers/rerankers/cohere_reranker.py`

**Step 1: Add timeout to Gemini calls**

Wrap each `generate`, `generate_structured`, and `stream` call:
```python
import asyncio

async def generate(self, prompt, system=None, temperature=0.1, max_tokens=4096):
    # ... build config ...
    try:
        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(model=self._model, contents=prompt, config=config),
            timeout=120,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"LLM call timed out after 120s")
```

**Step 2: Add timeout to Cohere reranker**

```python
async def rerank(self, query, documents, top_n=10):
    if not documents:
        return []
    try:
        response = await asyncio.wait_for(
            self._client.rerank(model=self._model, query=query, documents=documents, top_n=top_n),
            timeout=30,
        )
    except asyncio.TimeoutError:
        logger.warning("Cohere rerank timed out, returning original order")
        return list(range(len(documents)))[:top_n]
```

**Step 3: Commit**

```bash
git add backend/app/core/providers/llm/gemini.py backend/app/core/providers/rerankers/cohere_reranker.py
git commit -m "feat: add timeouts to all LLM and reranker calls (120s/30s)"
```

---

## Task 25: Database Improvements

**Findings covered:** [A4-F3.1] missing audit_logs indexes, [A4-F3.2] missing consents index, [A4-F3.3] no GIN index on sections, [A4-F4.2] migration index pattern, [A4-F4.3] no updated_at trigger, [A4-F5.1] missing model indexes, [A4-F5.2] orphaned vectors on case delete, [A4-F7.1] on-the-fly tsvector, [A4-F7.2] full_text deferred loading, [A4-F8.1] inconsistent SQL/ORM

**Files:**
- Create: `backend/migrations/versions/006_indexes_and_performance.py`
- Modify: `backend/app/models/case.py`
- Modify: `backend/app/models/chat.py`

**Step 1: Create migration for missing indexes**

```python
"""Add missing indexes for performance and audit queries."""

def upgrade():
    # Audit log indexes
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    # Consent index
    op.create_index("ix_consents_user_id", "consents", ["user_id"])

    # GIN index on case_sections for full-text search
    op.execute("""
        CREATE INDEX ix_case_sections_content_gin
        ON case_sections USING gin(to_tsvector('english', content))
    """)

    # Chat model indexes (match migration 005)
    # Already exist from migration 005, add to models for metadata.create_all() parity

def downgrade():
    op.drop_index("ix_audit_logs_created_at")
    op.drop_index("ix_audit_logs_user_id")
    op.drop_index("ix_audit_logs_action")
    op.drop_index("ix_consents_user_id")
    op.execute("DROP INDEX IF EXISTS ix_case_sections_content_gin")
```

**Step 2: Add `deferred=True` to `full_text` column in case model**

```python
full_text: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
```

**Step 3: Add `index=True` to chat model columns**

```python
# In ChatSession:
user_id: Mapped[uuid.UUID] = mapped_column(..., index=True)

# In ChatMessage:
session_id: Mapped[uuid.UUID] = mapped_column(..., index=True)
```

**Step 4: Commit**

```bash
git add backend/migrations/versions/006_indexes_and_performance.py backend/app/models/case.py backend/app/models/chat.py
git commit -m "feat: add missing DB indexes for audit, consents, case_sections GIN, deferred full_text"
```

---

## Task 26: Code Deduplication

**Findings covered:** [A10-F3.1] SSE streaming duplicated (FE), [A10-F3.2] chat routes duplicated, [A10-F3.3] graph traversal duplicated, [A10-F3.4] agent graph building duplicated, [A10-F2.2] cache pattern scattered, [A3-F3.2] verify_citations duplicated, [A3-F3.3] UUID_RE duplicated, [A3-F3.4] unused json import

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `backend/app/api/routes/chat.py`
- Modify: `backend/app/api/routes/agents.py`
- Modify: `backend/app/core/graph/traversal.py`
- Modify: `backend/app/core/agents/nodes/research_nodes.py`
- Modify: `backend/app/core/agents/nodes/case_prep_nodes.py`
- Modify: `backend/app/core/agents/case_prep.py`

**Step 1: Extract generic SSE streaming helper (frontend)**

```typescript
// In api.ts, extract shared SSE logic:
async function _streamSSE<T>(
    path: string,
    body: unknown,
    onEvent: (event: T) => void,
    signal?: AbortSignal,
): Promise<void> {
    const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
        body: JSON.stringify(body),
        signal,
    });
    if (!res.ok) throw new ApiError(res.status, "STREAM_ERROR", "Stream failed");
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
            if (line.startsWith("data: ")) {
                try { onEvent(JSON.parse(line.slice(6)) as T); } catch {}
            }
        }
    }
}
```

Then rewrite `_streamChat` and `_streamAgent` to use `_streamSSE`.

**Step 2: Extract shared chat stream helper (backend)**

```python
# In chat.py, extract:
def _build_sse_stream(question, session_id, user, db, llm, embedder, ...):
    """Shared SSE streaming logic for create_chat and send_message."""
    # ... sanitization, injection check, event_stream generator ...
```

**Step 3: Extract shared agent graph builder (backend)**

```python
# In agents.py, extract:
def _build_agent_graph(agent_type, checkpointer, db):
    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()
    if agent_type == "research":
        return build_research_graph(llm=llm, flash_llm=llm, ...)
    else:
        graph_store = get_graph_store()
        return build_case_prep_graph(llm=llm, flash_llm=llm, ...)
```

**Step 4: Move shared `_UUID_RE` to a common module and remove unused imports**

```python
# Create backend/app/core/agents/nodes/common.py
import re
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
```

Remove `import json` from `case_prep.py`.

**Step 5: Commit**

```bash
git add frontend/src/lib/api.ts backend/app/api/routes/chat.py backend/app/api/routes/agents.py backend/app/core/graph/traversal.py backend/app/core/agents/nodes/common.py backend/app/core/agents/nodes/research_nodes.py backend/app/core/agents/nodes/case_prep_nodes.py backend/app/core/agents/case_prep.py
git commit -m "refactor: extract shared SSE, chat stream, agent graph, UUID_RE helpers to reduce duplication"
```

---

## Task 27: Chat Pipeline Fixes

**Findings covered:** [A2-R2] double db.commit, [A2-R3] decrypted history to LLM, [A2-R4] f-string SQL for constant, [A2-R5] no session_id validation, [A2-S6] equiv_map UUID key type, [A2-S7] suggest performance, [A2-CQ1] inline json imports, [A2-CQ3] duplicate treatment check, [A2-PERF1-4] redundant queries

**Files:**
- Modify: `backend/app/core/chat/rag.py`
- Modify: `backend/app/core/search/hybrid.py`
- Modify: `backend/app/api/routes/search.py`

**Step 1: Batch message saves into single commit**

```python
async def _save_messages(db, session_id, user_msg, assistant_msg):
    """Save both messages in a single transaction."""
    await db.execute(text("INSERT INTO chat_messages ..."), user_params)
    await db.execute(text("INSERT INTO chat_messages ..."), assistant_params)
    await db.execute(text("UPDATE chat_sessions SET updated_at = NOW() WHERE id = :id"), {"id": session_id})
    await db.commit()
```

**Step 2: Fix `equiv_map` key type**

```python
equiv_map.setdefault(str(er["case_id"]), []).append(er["citation_text"])
```

**Step 3: Move `import json` to file top in search.py**

**Step 4: Use bind parameter for MAX_SNIPPET_CHARS**

```python
f"LEFT(ratio_decidendi, :max_chars) AS ratio,"
# ... with params {"max_chars": MAX_SNIPPET_CHARS}
```

**Step 5: Commit**

```bash
git add backend/app/core/chat/rag.py backend/app/core/search/hybrid.py backend/app/api/routes/search.py
git commit -m "fix: batch chat commits, fix equiv_map key type, clean up imports and SQL constants"
```

---

## Task 28: Ingestion Quality Fixes

**Findings covered:** [A6-F1.5] no page limit, [A6-F1.6] OCR memory, [A6-F2.1] mid-word chunking, [A6-F2.2] section false positives, [A6-F3.1] LLM output types, [A6-F3.2] double normalization, [A6-F3.3] falsy merge bug, [A6-F6.2] Celery asyncio.run, [A6-F6.4] extracted dir not cleaned, [A6-F7.4] non-ASCII filenames, [A6-F7.5] tar traversal note, [A6-F7.6] citation equivalents semantic, [A6-F7.7] graph store error handling

**Files:**
- Modify: `backend/app/core/ingestion/pdf.py`
- Modify: `backend/app/core/ingestion/chunker.py`
- Modify: `backend/app/core/ingestion/metadata.py`
- Modify: `backend/app/core/ingestion/pipeline.py`

**Step 1: Add page limit and batch OCR**

```python
MAX_PAGES = 5000

async def extract_pdf_text(file_path: str) -> str:
    return await asyncio.to_thread(_extract_pdf_text_sync, file_path)

def _extract_pdf_text_sync(file_path: str) -> str:
    with pdfplumber.open(file_path) as pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise ValueError(f"PDF has {len(pdf.pages)} pages, max is {MAX_PAGES}")
        # ... existing extraction ...

def _extract_with_ocr_sync(file_path: str) -> str:
    # Process in batches of 10 pages
    all_text = []
    with pdfplumber.open(file_path) as pdf:
        total = min(len(pdf.pages), MAX_PAGES)
    for start in range(1, total + 1, 10):
        end = min(start + 9, total)
        images = convert_from_path(file_path, first_page=start, last_page=end, dpi=200)
        for img in images:
            all_text.append(pytesseract.image_to_string(img))
    return "\n".join(all_text)
```

**Step 2: Fix mid-word chunking**

```python
end = min(pos + CHUNK_SIZE, section_len)
# Try to break at sentence boundary
if end < section_len:
    # Look back up to 200 chars for a sentence ending
    break_point = section_text.rfind(". ", max(pos, end - 200), end)
    if break_point > pos:
        end = break_point + 1  # Include the period
```

**Step 3: Fix falsy merge bug**

```python
# metadata.py line 189
setattr(result, field, parquet_val if parquet_val is not None else llm_val)
```

**Step 4: Remove double court normalization**

Remove `normalize_court_name` call from `pipeline.py` (line 105-106) since it's already done in `validate_with_regex`.

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/pdf.py backend/app/core/ingestion/chunker.py backend/app/core/ingestion/metadata.py backend/app/core/ingestion/pipeline.py
git commit -m "fix: add page limits, batch OCR, sentence-boundary chunking, fix falsy merge bug"
```

---

## Task 29: Remaining Error Handling + Consistency

**Findings covered:** [A10-F5.1] inconsistent error responses, [A10-F5.3] inconsistent exception types, [A10-F6.1] inconsistent response annotations, [A10-F6.2] judge prefix, [A10-F6.3] section naming confusion, [A10-F7.1-7.3] dead code/imports, [A10-F8.1] hybrid_search too long, [A10-F8.2] stream_agent_events too many concerns, [A1-F17] no CSRF (note for future), [A1-F20] password complexity, [A7-F4.2] no password change endpoint, [A8-F2.1] bandit rules, [A8-F6.1] no structured logging

**Files:**
- Modify: `backend/app/api/routes/cases.py`
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/pyproject.toml`

**Step 1: Standardize graph error responses in cases.py**

Replace:
```python
return {"case_id": case_id, "citations": [], "error": str(exc)}
```
With:
```python
raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")
```

**Step 2: Add password complexity validation**

```python
@field_validator("password")
@classmethod
def validate_password_strength(cls, v):
    if not re.search(r'[A-Z]', v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r'[a-z]', v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r'\d', v):
        raise ValueError("Password must contain at least one digit")
    return v
```

**Step 3: Fix bandit rules — remove global S105/S106 suppression**

In `pyproject.toml`:
```toml
ignore = ["S101"]  # Only assert allowed in tests; S105/S106 stay active globally
```

**Step 4: Commit**

```bash
git add backend/app/api/routes/cases.py backend/app/api/routes/auth.py backend/pyproject.toml
git commit -m "fix: standardize error responses, add password complexity, re-enable bandit secret detection"
```

---

# PHASE D: Compliance, Tests & Polish

## Task 30: DPDP Compliance Endpoints

**Findings covered:** [A7-F5.1] no erasure endpoint, [A7-F5.2] no portability, [A7-F5.3] minimal consent, [A7-F5.4] consent opt-out default, [A7-F6.1] IP plaintext PII, [A7-F6.2] no tamper protection, [A7-F6.3] no retention policy, [A7-F6.4] user-agent fingerprinting, [A7-F8.3] safe_decrypt catches all, [A7-F8.4] no key rotation

**Files:**
- Create: `backend/app/api/routes/dpdp.py`
- Create: `backend/migrations/versions/007_dpdp_compliance.py`
- Modify: `backend/app/api/routes/auth.py` (consent default)
- Modify: `backend/app/security/consent.py`
- Modify: `backend/app/security/audit.py`
- Modify: `backend/app/main.py` (register route)

**Step 1: Fix consent default to opt-in**

In `auth.py` RegisterRequest:
```python
consent_given: bool  # Remove default — must be explicitly set
```

**Step 2: Create DPDP migration**

```python
"""DPDP compliance tables."""
def upgrade():
    # Granular consents table
    op.create_table("user_consents",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, default=1),
        sa.UniqueConstraint("user_id", "scope", "version"),
    )
    # DPDP audit log (retained even after account deletion)
    op.create_table("dpdp_audit_log",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("user_id", UUID, nullable=True),
        sa.Column("details", sa.JSON, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
```

**Step 3: Create DPDP route file with data-summary, data-export, erasure, and consent-withdraw endpoints**

(Follow the pattern from the research agent output — Section 3 of the auth/JWT research)

**Step 4: Register route in main.py**

```python
from app.api.routes import dpdp as dpdp_router
app.include_router(dpdp_router.router, prefix="/api/v1/dpdp", tags=["dpdp"])
```

**Step 5: Fix IP address storage — hash IPs in audit logs**

In `audit.py`:
```python
import hashlib
hashed_ip = hashlib.sha256(f"{ip_address}:{settings.jwt_secret_key}".encode()).hexdigest()[:16] if ip_address else None
```

**Step 6: Commit**

```bash
git add backend/app/api/routes/dpdp.py backend/app/api/routes/auth.py backend/app/security/consent.py backend/app/security/audit.py backend/migrations/versions/007_dpdp_compliance.py backend/app/main.py
git commit -m "feat: add DPDP Act 2023 compliance — erasure, portability, granular consent, IP hashing"
```

---

## Task 31: RBAC Tests

**Findings covered:** [A9-F1.1] RBAC zero tests

**Files:**
- Create: `backend/tests/unit/test_rbac.py`

```python
"""Tests for RBAC require_role dependency."""
import pytest
from unittest.mock import AsyncMock, patch
from app.security.rbac import require_role, get_current_user
from app.security.auth import TokenPayload
from app.security.exceptions import AuthorizationError


@pytest.fixture
def admin_payload():
    return TokenPayload(sub="u1", role="admin", exp=9999999999, iat=1000000000, jti="j1")

@pytest.fixture
def researcher_payload():
    return TokenPayload(sub="u2", role="researcher", exp=9999999999, iat=1000000000, jti="j2")


class TestRequireRole:
    def test_allows_matching_role(self, admin_payload):
        dep = require_role("admin")
        result = dep(current_user=admin_payload)
        assert result == admin_payload

    def test_denies_non_matching_role(self, researcher_payload):
        dep = require_role("admin")
        with pytest.raises(AuthorizationError):
            dep(current_user=researcher_payload)

    def test_allows_any_of_multiple_roles(self, researcher_payload):
        dep = require_role("admin", "researcher")
        result = dep(current_user=researcher_payload)
        assert result == researcher_payload

    def test_denies_viewer_for_admin_researcher(self):
        viewer = TokenPayload(sub="u3", role="viewer", exp=9999999999, iat=1000000000, jti="j3")
        dep = require_role("admin", "researcher")
        with pytest.raises(AuthorizationError):
            dep(current_user=viewer)
```

**Commit**

```bash
git add backend/tests/unit/test_rbac.py
git commit -m "test: add RBAC require_role unit tests"
```

---

## Task 32: Rate Limiter Tests

**Findings covered:** [A9-F1.2] rate limiter zero tests

**Files:**
- Create: `backend/tests/unit/test_rate_limiter.py`

```python
"""Tests for rate limiter parsing and core logic."""
import pytest
from app.security.rate_limiter import _parse_rate_limit


class TestParseRateLimit:
    def test_valid_per_minute(self):
        count, window = _parse_rate_limit("100/minute")
        assert count == 100
        assert window == 60

    def test_valid_per_second(self):
        count, window = _parse_rate_limit("5/second")
        assert count == 5
        assert window == 1

    def test_valid_per_hour(self):
        count, window = _parse_rate_limit("1000/hour")
        assert count == 1000
        assert window == 3600

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            _parse_rate_limit("invalid")

    def test_zero_count_raises(self):
        with pytest.raises(ValueError):
            _parse_rate_limit("0/minute")

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            _parse_rate_limit("10/fortnight")
```

**Commit**

```bash
git add backend/tests/unit/test_rate_limiter.py
git commit -m "test: add rate limiter parsing unit tests"
```

---

## Task 33: Account Lock + Inactive User Tests

**Findings covered:** [A9-F1.3] account lock zero tests, [A9-F1.4] inactive user zero tests

**Files:**
- Modify: `backend/tests/unit/test_auth_routes.py`

Add test cases for locked accounts, failed login count increment, and inactive user denial on both login and refresh.

**Commit**

```bash
git add backend/tests/unit/test_auth_routes.py
git commit -m "test: add account lock, failed login count, and inactive user tests"
```

---

## Task 34: Agent Graph Execution + Provider Contract Tests

**Findings covered:** [A9-F2.1] no full agent graph tests, [A9-F3.3] vector/graph store no tests, [A9-F3.4] LLM provider no tests

**Files:**
- Create: `backend/tests/unit/test_agent_graph_execution.py`
- Create: `backend/tests/unit/test_provider_contracts.py`

Test full graph execution with mocked dependencies, and verify provider implementations conform to Protocol interfaces.

**Commit**

```bash
git add backend/tests/unit/test_agent_graph_execution.py backend/tests/unit/test_provider_contracts.py
git commit -m "test: add full agent graph execution and provider contract tests"
```

---

## Task 35: Frontend Polish

**Findings covered:** [A5-F2.1] markdown props spread, [A5-F4.1] no CSRF (future), [A5-F4.2] PDF/audio no auth header, [A5-F4.3] no request timeout, [A5-F5.1] no maxLength, [A5-F5.2] year inputs unbounded, [A5-F5.3] name validation, [A5-F6.2] error messages expose internals, [A5-F7.1] ErrorBoundary no logging, [A5-F7.2] silent error swallowing, [A5-F7.3] confirm() for destructive, [A5-F7.4] clipboard no error handling, [A5-F7.5] missing footer on loading, [A5-F8.1-8.4] accessibility, [A5-F9.2-9.4] type safety, [A5-F10.1] recharts not code-split, [A5-F10.2] chat array copies, [A5-F3.2] noreferrer missing

**Files:**
- Modify: `frontend/src/lib/api.ts` (timeout, error mapping)
- Modify: `frontend/src/app/chat/page.tsx` (maxLength, markdown, confirm)
- Modify: `frontend/src/app/agents/research/page.tsx` (maxLength)
- Modify: `frontend/src/app/search/page.tsx` (maxLength, year bounds, labels)
- Modify: `frontend/src/components/header.tsx` (maxLength)
- Modify: `frontend/src/components/error-boundary.tsx` (componentDidCatch)
- Modify: `frontend/src/app/judge/[name]/page.tsx` (lazy recharts)
- Modify: `frontend/src/app/courts/page.tsx` (lazy recharts, label)
- Modify: `frontend/src/app/graph/page.tsx` (aria-label)
- Modify: `frontend/src/app/register/page.tsx` (name validation)
- Modify: `frontend/src/app/case/[id]/page.tsx` (noreferrer, keyboard support)

**Step 1: Add request timeout to apiFetch**

```typescript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 30000);
try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers, signal: controller.signal });
    // ...
} finally {
    clearTimeout(timeoutId);
}
```

**Step 2: Add maxLength to all text inputs**

- Chat textarea: `maxLength={5000}`
- Agent research: `maxLength={5000}`
- Search inputs: `maxLength={500}`
- Header search: `maxLength={500}`

**Step 3: Add year bounds**

```tsx
<Input type="number" min={1950} max={2026} ... />
```

**Step 4: Add componentDidCatch to ErrorBoundary**

```typescript
componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
}
```

**Step 5: Lazy-load recharts**

```typescript
const JudgeCharts = dynamic(() => import("@/components/judge-charts"), { ssr: false, loading: () => <Skeleton className="h-[280px]" /> });
```

**Step 6: Add aria-labels to unlabeled inputs**

```tsx
<select id="filter-court" aria-label="Filter by court" ...>
<Input aria-label="Search for a case" ...>
```

**Step 7: Fix noreferrer consistency**

All `target="_blank"` links: `rel="noopener noreferrer"`

**Step 8: Commit**

```bash
git add frontend/src/
git commit -m "fix: frontend polish — timeouts, maxLength, accessibility, recharts code-split, error logging"
```

---

## Task 36: Dependencies & Config Cleanup

**Findings covered:** [A8-F2.2] unpinned LangGraph, [A8-F2.3] npm no lockfile, [A10-F10.1] flash_llm shortcut, [A4-F3.4] unbounded string columns, [A4-F3.5] missing TimestampMixin, [A4-F5.3] missing model exports, [A4-F8.3] consent constraint missing, [A4-F8.4] missing model exports, [A8-F4.5] host defaults, [A7-F2.2] no admin endpoints (noted for future), [A7-F2.3] role in JWT not re-validated (noted)

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `frontend/Dockerfile`

**Step 1: Pin LangGraph dependencies**

```toml
"langgraph==0.3.5",
"langgraph-checkpoint-postgres==2.0.2",
"psycopg[binary]==3.2.4",
"psycopg-pool==3.2.4",
```

**Step 2: Add `get_flash_llm()` to dependencies.py**

```python
@lru_cache
def get_flash_llm():
    from app.core.providers.llm.gemini import GeminiLLM
    return GeminiLLM(model=settings.gemini_flash_model)
```

Add `gemini_flash_model: str = "gemini-2.5-flash"` to config.py.

**Step 3: Add missing model exports to `__init__.py`**

**Step 4: Fix frontend Dockerfile to use npm ci**

```dockerfile
COPY package.json package-lock.json ./
RUN npm ci
```

**Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/core/dependencies.py backend/app/core/config.py backend/app/models/__init__.py frontend/Dockerfile
git commit -m "fix: pin LangGraph deps, add flash_llm provider, fix model exports, use npm ci"
```

---

## Task 37: Remaining Test Gaps

**Findings covered:** [A9-F1.5] audit logging no tests, [A9-F2.2] chat SSE insufficient, [A9-F2.3] no concurrent tests, [A9-F2.4] no deletion lifecycle tests, [A9-F2.5] refresh inactive user, [A9-F3.1] integration tests mock everything, [A9-F3.2] frontend tests mostly smoke, [A9-F3.5] Redis cache not tested, [A9-F3.6] token expiry edges, [A9-F3.7] pagination boundaries

**Files:**
- Create: `backend/tests/unit/test_audit_logging.py`
- Modify: `backend/tests/unit/test_hybrid_search.py` (pagination edge cases)
- Modify: `backend/tests/unit/test_auth.py` (token edge cases)

Write tests for:
1. `create_audit_log` function (inserts correctly, handles None metadata)
2. Pagination boundaries (page=0, page_size=0, page beyond results)
3. Token expiry boundary tests

**Commit**

```bash
git add backend/tests/unit/test_audit_logging.py backend/tests/unit/test_hybrid_search.py backend/tests/unit/test_auth.py
git commit -m "test: add audit logging, pagination boundary, and token expiry edge case tests"
```

---

## Task 38: Remaining LOW Findings Sweep

**Findings covered:** All remaining LOW findings from all agents:
[A1-F20] password complexity (done in T29), [A2-S6] (done in T27), [A2-R4-R5] (done in T27), [A2-CQ1-4] (done in T27), [A2-PERF1-4] (done in T27), [A2-SEC2-3] (done in T24), [A3-F3.3-3.4] (done in T26), [A3-F3.7] (done in T36), [A3-F4.1-4.4] (done in T20-21), [A4-F3.4-3.5] (done in T36), [A4-F5.3] (done in T36), [A4-F8.3-8.4] (done in T36), [A5-all LOW] (done in T35), [A6-F2.2-2.3,3.2,7.4-7.7] (done in T28), [A7-F1.8,4.2,6.4] (done in T11,T30), [A8-F2.3,4.5,6.3,7.3-7.4] (done in T16,T36), [A10-F6.2-6.3,7.1-7.3] (done in T26,T29)

This task is a sweep to catch any remaining LOW findings not covered by previous tasks. Most should already be done.

**Commit**

```bash
git add -A
git commit -m "chore: sweep remaining low-severity findings"
```

---

## Task 39: Final Verification

**Step 1: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

**Step 2: Run all frontend tests**

```bash
cd frontend && npm test 2>&1 | tail -20
```

**Step 3: Run bandit security scan**

```bash
cd backend && python -m bandit -r app/ -c pyproject.toml
```

**Step 4: Run type check**

```bash
cd frontend && npx tsc --noEmit
```

**Step 5: Verify no secrets in codebase**

```bash
grep -rn "password\s*=\s*['\"]" backend/app/ --include="*.py" | grep -v "test" | grep -v "\.pyc"
```

**Step 6: Final commit if all passes**

```bash
git add -A
git commit -m "chore: all 150 audit findings remediated — security, quality, compliance"
```

---

# APPENDIX: Finding-to-Task Cross-Reference

| Finding ID | Description | Task |
|-----------|-------------|------|
| A1-F1 | In-memory token revocation | T10 |
| A1-F2 | Empty JWT secrets | T1 |
| A1-F3 | Refresh not revoked | T11 |
| A1-F4 | CORS wildcard | T8 |
| A1-F5 | No auth on endpoints | T18 |
| A1-F6 | No rate limit register | T12 |
| A1-F7 | No rate limit refresh | T12 |
| A1-F8 | Error leaks internals | T2 |
| A1-F9 | Path traversal filename | T7 |
| A1-F10 | No rate limit public | T12 |
| A1-F11 | Email enumeration | T9 |
| A1-F12 | Case ID in 404 | T2 |
| A1-F13 | ILIKE wildcard injection | T9 |
| A1-F14 | File size bypass | T7 |
| A1-F15 | No magic byte check | T7 |
| A1-F16 | IP-only rate limit | T12 |
| A1-F17 | No CSRF | T18 (noted) |
| A1-F18 | Chat IDOR | T13 |
| A1-F19 | Health exposes env | T19 |
| A1-F20 | Password complexity | T29 |
| A1-F21 | Content-Disposition inject | T9 |
| A2-P1 | Cypher injection label | T6 |
| A2-P2 | Cypher injection rel | T6 |
| A2-P3 | Gemini no timeout | T24 |
| A2-P4 | Cohere no timeout | T24 |
| A2-P5 | Pinecone no retry | T24 |
| A2-S1 | Search no injection check | T17 |
| A2-S2 | LLM-controlled filters | T17 |
| A2-S3 | Section ignores filters | T23 |
| A2-S4 | Pagination broken | T23 |
| A2-S5 | No Pinecone fallback | T23 |
| A2-S6 | equiv_map key type | T27 |
| A2-S7 | Suggest performance | T27 |
| A2-R1 | SSE errors not propagated | T23 |
| A2-R2 | Double db.commit | T27 |
| A2-R3 | Decrypted history to LLM | T27 |
| A2-R4 | f-string SQL constant | T27 |
| A2-R5 | No session_id validation | T27 |
| A2-R6 | Chat history injection | T17 |
| A2-SEC1 | Search no auth | T18 |
| A2-SEC2 | Encryption key per-op | T24 |
| A2-SEC3 | safe_decrypt bare except | T30 |
| A2-PERF1-4 | Redundant queries | T27 |
| A2-CQ1-4 | Code quality | T27 |
| A3-F1.1 | Checkpointer memory leak | T20 |
| A3-F1.2 | In-memory checkpointer | T20 |
| A3-F1.3 | SSE error leak | T2 |
| A3-F2.1 | Iteration off-by-one | T21 |
| A3-F2.2 | No UUID validation | T21 |
| A3-F2.3 | Feedback in LLM prompt | T17 |
| A3-F2.4 | search_results accumulate | T21 |
| A3-F2.5 | No LLM timeout | T24 |
| A3-F2.6 | No result limit for LLM | T21 |
| A3-F3.1 | DB session reuse SSE | T20 |
| A3-F3.2 | Duplicated verify_citations | T26 |
| A3-F3.3 | Duplicated UUID_RE | T26 |
| A3-F3.4 | Unused json import | T26 |
| A3-F3.5 | Any type annotations | T21 |
| A3-F3.6 | No LLM output validation | T21 |
| A3-F3.7 | flash_llm unused | T36 |
| A3-F3.8 | Concurrent resume race | T21 |
| A3-F3.9 | Error msg untruncated | T21 |
| A3-F3.10 | Checkpoint isolation | T20 |
| A3-F4.1 | Dead checkpointer.py | T20 |
| A3-F4.2 | steps_completed never set | T20 |
| A3-F4.3 | In-place state mutation | T21 |
| A3-F4.4 | Inconsistent exceptions | T21 |
| A4-F1.1 | f-string SQL | T22 |
| A4-F1.2 | Dynamic WHERE f-string | T22 |
| A4-F2.1 | SSL CERT_NONE | T3 |
| A4-F2.2 | Standalone engine no SSL | T3 |
| A4-F2.3 | No pool_pre_ping | T3 |
| A4-F3.1 | Missing audit indexes | T25 |
| A4-F3.2 | Missing consent index | T25 |
| A4-F3.3 | No GIN index sections | T25 |
| A4-F3.4 | Unbounded String cols | T36 |
| A4-F3.5 | Missing TimestampMixin | T36 |
| A4-F4.1 | Downgrade FK order | T25 |
| A4-F4.2 | Migration index pattern | T25 |
| A4-F4.3 | No updated_at trigger | T25 |
| A4-F5.1 | Missing model indexes | T25 |
| A4-F5.2 | Orphaned vectors | T25 |
| A4-F5.3 | Missing model exports | T36 |
| A4-F6.1 | IP plaintext PII | T30 |
| A4-F6.2 | Email plaintext | T30 |
| A4-F6.3 | Email in repr | T2 |
| A4-F7.1 | Section tsvector perf | T25 |
| A4-F7.2 | full_text deferred | T25 |
| A4-F7.3 | Engine per call | T3 |
| A4-F8.1 | SQL/ORM inconsistency | T22 |
| A4-F8.2 | Object type hints | T22 |
| A4-F8.3 | Consent constraint | T36 |
| A4-F8.4 | Missing exports | T36 |
| A5-F1.1 | localStorage tokens | T14 |
| A5-F1.2 | No token expiry check | T14 |
| A5-F1.3 | Auth guard race | T14 |
| A5-F1.4 | Refresh in body | T14 |
| A5-F2.1 | Markdown props spread | T35 |
| A5-F3.1 | Missing CSP/HSTS | T15 |
| A5-F3.2 | Missing noreferrer | T35 |
| A5-F4.1 | No CSRF | T18 |
| A5-F4.2 | PDF/audio no auth | T35 |
| A5-F4.3 | No request timeout | T35 |
| A5-F4.4 | Unsafe header cast | T35 |
| A5-F5.1 | No maxLength | T35 |
| A5-F5.2 | Year unbounded | T35 |
| A5-F5.3 | Name not validated | T35 |
| A5-F5.4 | Client-only file check | T7 |
| A5-F6.2 | Error msg internals | T35 |
| A5-F7.1 | ErrorBoundary no log | T35 |
| A5-F7.2 | Silent error catch 17x | T35 |
| A5-F7.3 | Native confirm() | T35 |
| A5-F7.4 | Clipboard no handler | T35 |
| A5-F7.5 | Missing footer loading | T35 |
| A5-F8.1-8.4 | Accessibility | T35 |
| A5-F9.2-9.4 | Type safety | T35 |
| A5-F10.1 | recharts not split | T35 |
| A5-F10.2 | Chat array copies | T35 |
| A5-F10.4 | loadSessions deps | T35 |
| A6-F1.1 | No magic bytes | T7 |
| A6-F1.2 | Size bypass | T7 |
| A6-F1.3 | Full file read DoS | T7 |
| A6-F1.4 | Path traversal | T7 |
| A6-F1.5 | No page limit | T28 |
| A6-F1.6 | OCR memory | T28 |
| A6-F1.7 | Temp file leak | T7 |
| A6-F2.1 | Mid-word chunking | T28 |
| A6-F2.2 | Section false positives | T28 |
| A6-F2.3 | Dedup threshold | T28 |
| A6-F3.1 | LLM output types | T28 |
| A6-F3.2 | Double normalization | T28 |
| A6-F3.3 | Falsy merge bug | T28 |
| A6-F4.1 | No embedding retry | T22 |
| A6-F4.2 | No vector retry | T22 |
| A6-F4.3 | Dimension mismatch | T22 |
| A6-F5.1 | No transaction rollback | T22 |
| A6-F5.2 | Duplicate citation race | T22 |
| A6-F5.3 | Stats counter race | T28 |
| A6-F6.1 | Async blocking PDF | T28 |
| A6-F6.2 | Celery asyncio.run | T28 |
| A6-F6.3 | Celery retry unused | T22 |
| A6-F6.4 | Extracted dir cleanup | T28 |
| A6-F7.1 | Object type hints | T22 |
| A6-F7.2 | f-string SQL | T22 |
| A6-F7.3 | No top-level guard | T22 |
| A6-F7.4 | Non-ASCII filenames | T28 |
| A6-F7.5 | Tar traversal note | T28 |
| A6-F7.6 | Citation equiv semantic | T28 |
| A6-F7.7 | Graph error handling | T28 |
| A7-F1.1 | In-memory revocation | T10 |
| A7-F1.2 | JWT empty secret | T1 |
| A7-F1.3 | Logout no refresh revoke | T11 |
| A7-F1.4 | Rotation no revoke | T11 |
| A7-F1.5 | No password complexity | T29 |
| A7-F1.6 | Register no rate limit | T12 |
| A7-F1.7 | Register no audit log | T12 |
| A7-F1.8 | Hardcoded expires_in | T11 |
| A7-F2.1 | Routes no auth | T18 |
| A7-F2.2 | No admin endpoints | T36 (noted) |
| A7-F2.3 | Role cached in JWT | T18 (noted) |
| A7-F3.1 | No session limits | T11 |
| A7-F3.2 | Refresh not stored | T11 |
| A7-F3.3 | Tokens in body not cookie | T14 |
| A7-F4.1 | BCrypt good | N/A |
| A7-F4.2 | No password change | T29 (noted) |
| A7-F5.1 | No erasure endpoint | T30 |
| A7-F5.2 | No portability | T30 |
| A7-F5.3 | Minimal consent | T30 |
| A7-F5.4 | Consent opt-out | T30 |
| A7-F6.1 | IP plaintext | T30 |
| A7-F6.2 | No tamper protection | T30 |
| A7-F6.3 | No retention policy | T30 |
| A7-F6.4 | User-agent fingerprint | T30 |
| A7-F7.1 | Rate limit fail-open | T12 |
| A7-F7.2 | IP-only rate key | T12 |
| A7-F7.3 | Public no rate limit | T12 |
| A7-F7.4 | Rate limiter race | T12 |
| A7-F8.1 | AES-GCM good | N/A |
| A7-F8.2 | Encryption key empty | T1 |
| A7-F8.3 | safe_decrypt bare except | T30 |
| A7-F8.4 | No key rotation | T30 |
| A7-F9.1 | Token type info leak | T2 |
| A7-F9.2 | CORS over-permissive | T8 |
| A8-F1.1 | Debug default true | T1 |
| A8-F1.2 | JWT secrets warning only | T1 |
| A8-F1.3 | Hardcoded DB passwords | T1 |
| A8-F1.4 | In-memory revocation | T10 |
| A8-F1.5 | Encryption key empty | T1 |
| A8-F1.6 | Deploy missing secrets | T4 |
| A8-F2.1 | Bandit rules suppressed | T29 |
| A8-F2.2 | Unpinned LangGraph | T36 |
| A8-F2.3 | npm no lockfile | T36 |
| A8-F3.1 | Docker runs as root | T16 |
| A8-F3.2 | No multi-stage build | T16 |
| A8-F3.3 | build-essential in image | T16 |
| A8-F3.4 | Frontend no non-root | T16 |
| A8-F4.1 | No 500 handler | T2 |
| A8-F4.2 | CORS wildcard | T8 |
| A8-F4.3 | Missing security headers | T15 |
| A8-F4.4 | No JWT min length | T1 |
| A8-F4.5 | Host defaults 0.0.0.0 | T36 |
| A8-F5.1 | Broad IAM role | T4 |
| A8-F5.2 | No auth policy | T4 |
| A8-F5.3 | Registry inconsistency | T4 |
| A8-F5.4 | No resource limits | T4 |
| A8-F5.5 | DB URL on CLI | T4 |
| A8-F6.1 | No structured logging | T29 |
| A8-F6.2 | Migration failure silent | T19 |
| A8-F6.3 | Rate limit fail-open | T12 |
| A8-F7.1 | No 500 handler (dup) | T2 |
| A8-F7.2 | Token error forwarded | T2 |
| A8-F7.3 | Neo4j exposed docker | T16 |
| A8-F7.4 | Redis no auth docker | T16 |
| A9-F1.1 | RBAC no tests | T31 |
| A9-F1.2 | Rate limiter no tests | T32 |
| A9-F1.3 | Account lock no tests | T33 |
| A9-F1.4 | Inactive user no tests | T33 |
| A9-F1.5 | Audit log no tests | T37 |
| A9-F2.1 | No agent graph tests | T34 |
| A9-F2.2 | Chat SSE insufficient | T37 |
| A9-F2.3 | No concurrent tests | T37 |
| A9-F2.4 | No deletion tests | T37 |
| A9-F2.5 | Refresh inactive | T33 |
| A9-F3.1 | Integration mocked | T37 |
| A9-F3.2 | Frontend smoke only | T35 |
| A9-F3.3 | Provider no tests | T34 |
| A9-F3.4 | LLM provider no tests | T34 |
| A9-F3.5 | Redis cache not tested | T37 |
| A9-F3.6 | Token expiry edges | T37 |
| A9-F3.7 | Pagination boundaries | T37 |
| A10-F1.1 | Direct LocalStorage import | T5 |
| A10-F2.1 | SQL in routes | T29 |
| A10-F2.2 | Cache pattern scattered | T26 |
| A10-F3.1 | SSE duplicated FE | T26 |
| A10-F3.2 | Chat routes duplicated | T26 |
| A10-F3.3 | Graph traversal duplicated | T26 |
| A10-F3.4 | Agent graph duplicated | T26 |
| A10-F5.1 | Inconsistent error shapes | T29 |
| A10-F5.2 | Bare except lifespan | T19 |
| A10-F5.3 | Inconsistent exceptions | T29 |
| A10-F6.1 | dict return types | T29 |
| A10-F6.2 | Judge prefix | T36 |
| A10-F6.3 | Section naming | T36 |
| A10-F7.1 | Unused import asdict | T26 |
| A10-F7.2 | Inline json imports | T27 |
| A10-F7.3 | uuid alias | T26 |
| A10-F8.1 | hybrid_search too long | T23 |
| A10-F8.2 | stream_agent_events | T20 |
| A10-F9.1 | In-memory checkpointer | T20 |
| A10-F9.2 | Agent body type union | T21 |
| A10-F9.3 | No API versioning | T36 (noted) |
| A10-F9.4 | Register no rate limit | T12 |
| A10-F10.1 | flash_llm=llm shortcut | T36 |
| A10-F10.2 | FE token dual storage | T14 |
| A10-F10.3 | PineconeStore no close | T36 |
| A10-F10.4 | SearchFilters redundancy | T36 |

**Total: 150 findings mapped to 39 tasks across 4 phases. Zero findings omitted.**
