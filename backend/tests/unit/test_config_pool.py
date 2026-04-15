"""Verify DB pool defaults for Cloud Run scale-out."""

from app.core.config import Settings


class TestPoolDefaults:
    def test_pool_size_default(self):
        # Pool size default is tuned for Cloud Run's auto-scaling model.
        # Isolated from .env via _env_file=None so this matches both
        # dev machines (with .env) and CI (without).
        s = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/db",
            _env_file=None,
        )
        assert s.database_pool_size == 30

    def test_max_overflow_default(self):
        s = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/db",
            _env_file=None,
        )
        assert s.database_max_overflow == 20
