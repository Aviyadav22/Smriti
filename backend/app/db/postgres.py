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
    import os
    _ssl_ctx = ssl.create_default_context()
    _insecure = os.environ.get("DATABASE_SSL_INSECURE", "").lower() in ("1", "true", "yes")
    if settings.app_env not in ("production", "staging") or _insecure:
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode = ssl.CERT_NONE
        _logger.warning(
            "PostgreSQL SSL certificate verification DISABLED (app_env=%s, insecure=%s).",
            settings.app_env,
            _insecure,
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

# Pool monitoring — log warnings when pool is under pressure
if not _use_nullpool:
    from sqlalchemy import event as sa_event

    @sa_event.listens_for(engine.sync_engine, "checkout")
    def _on_checkout(dbapi_conn, connection_record, connection_proxy):  # noqa: ARG001
        pool = engine.pool
        _logger.debug(
            "DB pool checkout: size=%s, checked_in=%s, overflow=%s",
            pool.size(), pool.checkedin(), pool.overflow(),
        )

    @sa_event.listens_for(engine.sync_engine, "checkin")
    def _on_checkin(dbapi_conn, connection_record):  # noqa: ARG001
        pool = engine.pool
        if pool.overflow() > pool.size() // 2:
            _logger.warning(
                "DB pool pressure: overflow=%s exceeds half of pool_size=%s",
                pool.overflow(), pool.size(),
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
