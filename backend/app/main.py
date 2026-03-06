"""Smriti API — AI-powered Indian legal research platform."""

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
            import logging
            logging.getLogger("smriti").warning(f"Auto-migration skipped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup — run DB migrations
    _run_migrations()
    yield
    # Shutdown
    from app.db.redis_client import close_redis

    await close_redis()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered Indian legal research platform",
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


from app.api.routes.health import router as health_router  # noqa: E402
from app.api.routes.auth import router as auth_router  # noqa: E402
from app.api.routes.cases import router as cases_router  # noqa: E402
from app.api.routes.ingest import router as ingest_router  # noqa: E402
from app.api.routes.search import router as search_router  # noqa: E402

app.include_router(health_router, tags=["health"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(cases_router, prefix="/api/v1/cases", tags=["cases"])
app.include_router(ingest_router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
