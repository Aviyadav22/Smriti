"""Async PostgreSQL engine and session factory."""

import logging
import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

_logger = logging.getLogger(__name__)

# Build connect_args for SSL if needed (Supabase, Neon, etc.)
_connect_args: dict = {}
_use_nullpool = False
if settings.app_env == "production" or "supabase" in settings.database_url:
    _ssl_ctx = ssl.create_default_context()
    if settings.app_env not in ("production", "staging"):
        # Local dev connecting to Supabase pooler: skip cert verification.
        # In production/staging, full SSL certificate validation is enforced.
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode = ssl.CERT_NONE
        _logger.warning(
            "PostgreSQL SSL certificate verification DISABLED (app_env=%s). "
            "This is acceptable for local development only.",
            settings.app_env,
        )
    _connect_args["ssl"] = _ssl_ctx
    # Supabase Supavisor (transaction pooling) doesn't support prepared statements.
    # statement_cache_size=0: disables asyncpg's internal statement cache
    # prepared_statement_cache_size=0: disables SQLAlchemy adapter's LRU cache
    # prepared_statement_name_func: uses anonymous (unnamed) prepared statements
    #   to avoid DuplicatePreparedStatementError with Supavisor
    _connect_args["statement_cache_size"] = 0
    _connect_args["prepared_statement_cache_size"] = 0
    _connect_args["prepared_statement_name_func"] = lambda: ""
    # Use NullPool when behind an external connection pooler (Supavisor)
    _use_nullpool = True

_pool_kwargs: dict = {}
if _use_nullpool:
    _pool_kwargs["poolclass"] = NullPool
else:
    _pool_kwargs["pool_size"] = settings.database_pool_size
    _pool_kwargs["max_overflow"] = settings.database_max_overflow
    _pool_kwargs["pool_recycle"] = settings.database_pool_recycle
    _pool_kwargs["pool_timeout"] = settings.database_pool_timeout
    _pool_kwargs["pool_pre_ping"] = True

engine = create_async_engine(
    settings.database_url,
    connect_args=_connect_args,
    **_pool_kwargs,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a standalone async session for use outside FastAPI requests.

    Reuses the module-level engine and session factory instead of creating
    a new engine each call.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
