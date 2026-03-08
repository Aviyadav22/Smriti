"""Async PostgreSQL engine and session factory."""

import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Build connect_args for SSL if needed (Supabase, Neon, etc.)
_connect_args: dict = {}
if settings.app_env == "production" or "supabase" in settings.database_url:
    _ssl_ctx = ssl.create_default_context()
    _connect_args["ssl"] = _ssl_ctx

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_recycle=settings.database_pool_recycle,
    pool_timeout=settings.database_pool_timeout,
    pool_pre_ping=True,
    connect_args=_connect_args,
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
