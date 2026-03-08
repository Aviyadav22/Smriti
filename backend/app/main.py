"""Smriti API — AI-powered Indian legal research platform."""

import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.security.exceptions import (
    AuthenticationError,
    AuthorizationError,
    RateLimitExceededError,
)

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Run Alembic migrations on startup in production."""
    import subprocess
    import os

    if settings.app_env == "production":
        try:
            # In Docker, the app is at /app; locally it's at the backend dir
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=app_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            logger.error("Auto-migration failed: %s", e, exc_info=True)
            if settings.app_env == "production":
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
    _run_migrations()

    # Cleanup expired user-uploaded PDFs (DPDP: purpose-limited retention)
    if settings.user_upload_retention_days > 0:
        asyncio.create_task(_cleanup_expired_uploads())

    yield
    # Shutdown — with timeout guards to avoid blocking Cloud Run termination
    from app.db.redis_client import close_redis

    try:
        await asyncio.wait_for(close_redis(), timeout=10)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("Redis shutdown timeout or error: %s", exc)

    # Close graph store driver if it was initialised during this process
    from app.core.dependencies import get_graph_store

    try:
        info = get_graph_store.cache_info()
        if info.currsize > 0:
            graph_store = get_graph_store()
            if hasattr(graph_store, "close"):
                await asyncio.wait_for(graph_store.close(), timeout=10)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("Graph store shutdown timeout or error: %s", exc)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered Indian legal research platform",
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
    lifespan=lifespan,
)

# Middleware is added in reverse order (last added = outermost = runs first).
# Order: TrustedHost → CORS → RequestID

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
