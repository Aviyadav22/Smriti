"""Verify lowered pool defaults for Cloud Run scale-out."""

from unittest.mock import patch
import pytest


class TestPoolDefaults:
    def test_pool_size_lowered(self):
        with patch.dict("os.environ", {}, clear=False):
            from importlib import reload
            import app.core.config as config_mod
            reload(config_mod)
            s = config_mod.Settings(database_url="postgresql+asyncpg://x:x@localhost/db")
            assert s.database_pool_size == 10

    def test_max_overflow_lowered(self):
        with patch.dict("os.environ", {}, clear=False):
            from importlib import reload
            import app.core.config as config_mod
            reload(config_mod)
            s = config_mod.Settings(database_url="postgresql+asyncpg://x:x@localhost/db")
            assert s.database_max_overflow == 20
