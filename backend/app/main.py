"""Smriti API — AI-powered Indian legal research platform."""

import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.security.exceptions import (
    AuthenticationError,
    AuthorizationError,
    RateLimitExceededError,
)

logger = logging.getLogger(__name__)


async def _run_migrations() -> None:
    """Run Alembic migrations on startup in production."""
    import os

    if settings.app_env == "production":
        try:
            # In Docker, the app is at /app; locally it's at the backend dir
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            proc = await asyncio.create_subprocess_exec(
                "alembic", "upgrade", "head",
                cwd=app_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Alembic migration failed (exit {proc.returncode}): {stderr.decode()}"
                )
            logger.info("Alembic migrations applied successfully")
        except RuntimeError:
            raise
        except Exception as e:
            logger.error("Auto-migration failed: %s", e, exc_info=True)
            raise


async def _cleanup_expired_uploads() -> None:
    """Delete user-uploaded PDF files older than retention period (DPDP compliance)."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import text as sa_text

    from app.core.dependencies import get_storage
    from app.db.postgres import get_async_session

    retention = settings.user_upload_retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention)

    try:
        async with get_async_session() as db:
            result = await db.execute(
                sa_text(
                    "SELECT id, storage_path FROM documents "
                    "WHERE storage_path IS NOT NULL AND created_at < :cutoff"
                ),
                {"cutoff": cutoff},
            )
            rows = result.mappings().all()

            if not rows:
                return

            storage = get_storage()
            cleaned = 0
            for row in rows:
                try:
                    await storage.delete(row["storage_path"])
                except (FileNotFoundError, OSError):
                    pass  # Already deleted or missing
                cleaned += 1

            await db.execute(
                sa_text(
                    "UPDATE documents SET storage_path = NULL "
                    "WHERE storage_path IS NOT NULL AND created_at < :cutoff"
                ),
                {"cutoff": cutoff},
            )
            await db.commit()
            logger.info("Cleaned up %d expired user-uploaded PDFs (>%d days)", cleaned, retention)
    except Exception:
        logger.warning("User upload cleanup failed", exc_info=True)


async def _validate_startup() -> None:
    """Run non-blocking startup health checks and log results.

    Each check is wrapped individually so a single failure does not
    prevent the remaining checks from running.  Failures are logged as
    warnings — they never block application startup.
    """
    checks_passed = 0
    checks_total = 4
    failures: list[str] = []

    # 1. PostgreSQL connectivity
    try:
        from app.db.postgres import engine
        from sqlalchemy import text as sa_text

        async with engine.connect() as conn:
            await conn.execute(sa_text("SELECT 1"))
        checks_passed += 1
        logger.info("Startup check: PostgreSQL OK")
    except Exception as exc:
        failures.append("PostgreSQL")
        logger.warning("Startup check: PostgreSQL unavailable — %s", exc)

    # 2. Redis connectivity
    try:
        from app.db.redis_client import get_redis

        redis = await get_redis()
        if redis is not None:
            await redis.ping()
            checks_passed += 1
            logger.info("Startup check: Redis OK")
        else:
            failures.append("Redis")
            logger.warning("Startup check: Redis unavailable — no connection")
    except Exception as exc:
        failures.append("Redis")
        logger.warning("Startup check: Redis unavailable — %s", exc)

    # 3. Pinecone dimension validation
    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=settings.pinecone_api_key)
        index = pc.Index(host=settings.pinecone_host)
        stats = index.describe_index_stats()
        dimension = stats.get("dimension") or getattr(stats, "dimension", None)
        expected_dim = 1536
        if dimension and int(dimension) != expected_dim:
            failures.append("Pinecone")
            logger.warning(
                "Startup check: Pinecone dimension mismatch — got %s, expected %d",
                dimension,
                expected_dim,
            )
        else:
            checks_passed += 1
            logger.info("Startup check: Pinecone OK (dimension=%s)", dimension)
    except Exception as exc:
        failures.append("Pinecone")
        logger.warning("Startup check: Pinecone unavailable — %s", exc)

    # 4. Gemini API key validation
    try:
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        client.models.list(config={"page_size": 1})
        checks_passed += 1
        logger.info("Startup check: Gemini OK")
    except Exception as exc:
        failures.append("Gemini")
        logger.warning("Startup check: Gemini unavailable — %s", exc)

    # Summary
    if checks_passed == checks_total:
        logger.info("Startup validation: %d/%d checks passed", checks_passed, checks_total)
    else:
        logger.warning(
            "Startup validation: %d/%d checks passed (%s unavailable)",
            checks_passed,
            checks_total,
            ", ".join(failures),
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["X-XSS-Protection"] = "0"
        # Apply no-store only to API responses, not static assets
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Configure structured logging
    from app.core.logging_config import configure_logging

    configure_logging()

    # Initialize Sentry if configured
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        def _before_send(event, hint):  # noqa: ANN001, ANN202
            """Strip sensitive headers before sending to Sentry."""
            if "request" in event and "headers" in event["request"]:
                headers = event["request"]["headers"]
                for key in ("authorization", "cookie", "x-csrf-token"):
                    headers.pop(key, None)
            return event

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            environment=settings.sentry_environment or settings.app_env,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            send_default_pii=False,
            before_send=_before_send,
        )
        logger.info("Sentry initialized for %s", settings.sentry_environment or settings.app_env)

    # Startup — run DB migrations
    await _run_migrations()

    # Run startup health validation (non-blocking, logs warnings only)
    await _validate_startup()

    # Cleanup expired user-uploaded PDFs (DPDP: purpose-limited retention)
    if settings.user_upload_retention_days > 0:
        asyncio.create_task(_cleanup_expired_uploads())

    yield
    # Shutdown — with timeout guards to avoid blocking Cloud Run termination

    # Dispose SQLAlchemy engine to release all DB connections
    try:
        from app.db.postgres import engine

        await asyncio.wait_for(engine.dispose(), timeout=10)
        logger.info("SQLAlchemy engine disposed")
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("SQLAlchemy engine disposal timeout or error: %s", exc)

    from app.db.redis_client import close_redis

    try:
        await asyncio.wait_for(close_redis(), timeout=10)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("Redis shutdown timeout or error: %s", exc)

    # Close cached provider connections (graph store, reranker, etc.)
    from app.core.dependencies import cleanup_providers

    try:
        await asyncio.wait_for(cleanup_providers(), timeout=10)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("Provider cleanup timeout or error: %s", exc)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered Indian legal research platform",
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
    lifespan=lifespan,
)

# Middleware is added in reverse order (last added = outermost = runs first).
# Order: TrustedHost → SecurityHeaders → CORS → RequestID

# Request ID middleware for tracing (innermost — runs last)
from app.core.middleware import RequestIDMiddleware  # noqa: E402

app.add_middleware(RequestIDMiddleware)

# CORS (middle)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-CSRF-Token"],
)

# Security headers (adds X-Content-Type-Options, HSTS, etc.)
app.add_middleware(SecurityHeadersMiddleware)

# Trusted Host middleware in production (outermost — runs first, rejects bad hosts early)
if settings.app_env == "production":
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    allowed_hosts = [h.replace("https://", "").replace("http://", "").split("/")[0]
                     for h in settings.cors_origin_list]
    allowed_hosts.append("localhost")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


# Exception handlers
@app.exception_handler(AuthenticationError)
async def authentication_error_handler(
    request: Request, exc: AuthenticationError
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": exc.detail, "code": "UNAUTHORIZED"},
    )


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(
    request: Request, exc: AuthorizationError
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": exc.detail, "code": "FORBIDDEN"},
    )


@app.exception_handler(RateLimitExceededError)
async def rate_limit_error_handler(
    request: Request, exc: RateLimitExceededError
) -> JSONResponse:
    headers = {}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=429,
        content={"error": exc.detail, "code": "RATE_LIMITED"},
        headers=headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except ImportError:
        pass
    return JSONResponse(
        status_code=500,
        content={"error": "An internal error occurred. Please try again.", "code": "INTERNAL_ERROR"},
    )


from app.api.routes.health import router as health_router  # noqa: E402
from app.api.routes.auth import router as auth_router  # noqa: E402
from app.api.routes.cases import router as cases_router  # noqa: E402
from app.api.routes.ingest import router as ingest_router  # noqa: E402
from app.api.routes.search import router as search_router  # noqa: E402
from app.api.routes.chat import router as chat_router  # noqa: E402
from app.api.routes.graph import router as graph_router  # noqa: E402
from app.api.routes.judges import router as judges_router  # noqa: E402
from app.api.routes.documents import router as documents_router  # noqa: E402
from app.api.routes.audio import router as audio_router  # noqa: E402
from app.api.routes.agents import router as agents_router
from app.api.routes.dpdp import router as dpdp_router  # noqa: E402
from app.api.routes.admin_review import router as admin_review_router  # noqa: E402
from app.api.routes.admin_corrections import router as admin_corrections_router  # noqa: E402
from app.api.routes.data_quality import router as data_quality_router  # noqa: E402

app.include_router(health_router, tags=["health"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(cases_router, prefix="/api/v1/cases", tags=["cases"])
app.include_router(ingest_router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(graph_router, prefix="/api/v1/graph", tags=["graph"])
app.include_router(judges_router, prefix="/api/v1", tags=["judges"])
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(audio_router, prefix="/api/v1/cases", tags=["audio"])
app.include_router(agents_router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(dpdp_router, prefix="/api/v1/dpdp", tags=["dpdp"])
app.include_router(admin_review_router, prefix="/api/v1/admin/review", tags=["admin"])
app.include_router(admin_corrections_router, prefix="/api/v1/admin/corrections", tags=["admin"])
app.include_router(data_quality_router, prefix="/api/v1/admin/data-quality", tags=["admin"])
