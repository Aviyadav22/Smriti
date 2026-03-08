"""Tests for structured logging configuration."""

from __future__ import annotations

import json
import logging
from unittest.mock import patch

import pytest

from app.core.logging_config import JSONFormatter, configure_logging


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def _make_record(self, msg: str = "test message", **kwargs: object) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for key, value in kwargs.items():
            setattr(record, key, value)
        return record

    def test_produces_valid_json(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_includes_severity(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert parsed["severity"] == "INFO"

    def test_includes_message(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record("hello world")
        parsed = json.loads(formatter.format(record))
        assert parsed["message"] == "hello world"

    def test_includes_module(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "module" in parsed

    def test_includes_timestamp(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "timestamp" in parsed
        # ISO format should contain 'T'
        assert "T" in parsed["timestamp"]

    def test_includes_exception_info(self) -> None:
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        parsed = json.loads(formatter.format(record))
        assert "exception" in parsed
        assert "boom" in parsed["exception"]

    def test_includes_request_id_when_set(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record(request_id="req-12345")
        parsed = json.loads(formatter.format(record))
        assert parsed["request_id"] == "req-12345"

    def test_excludes_request_id_when_not_set(self) -> None:
        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "request_id" not in parsed


class TestConfigureLogging:
    """Tests for configure_logging function."""

    @patch("app.core.logging_config.settings")
    def test_sets_correct_level(self, mock_settings: object) -> None:
        mock_settings.log_level = "DEBUG"
        mock_settings.app_env = "development"
        configure_logging()
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    @patch("app.core.logging_config.settings")
    def test_uses_json_formatter_in_production(self, mock_settings: object) -> None:
        mock_settings.log_level = "INFO"
        mock_settings.app_env = "production"
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    @patch("app.core.logging_config.settings")
    def test_uses_text_formatter_in_development(self, mock_settings: object) -> None:
        mock_settings.log_level = "INFO"
        mock_settings.app_env = "development"
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert not isinstance(root.handlers[0].formatter, JSONFormatter)

    @patch("app.core.logging_config.settings")
    def test_silences_noisy_loggers(self, mock_settings: object) -> None:
        mock_settings.log_level = "DEBUG"
        mock_settings.app_env = "development"
        configure_logging()
        for name in ("httpx", "httpcore", "urllib3", "asyncio"):
            assert logging.getLogger(name).level == logging.WARNING
