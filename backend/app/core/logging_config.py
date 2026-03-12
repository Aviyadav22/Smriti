"""Structured logging configuration for production (Cloud Logging) and development."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

from app.core.config import settings

# Patterns to redact from log output
_PII_PATTERNS = re.compile(
    r"("
    # Email addresses
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    r"|"
    # API keys / tokens (common patterns)
    r"(?:api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*\S+"
    r"|"
    # JWT tokens (three base64 segments separated by dots)
    r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"
    r"|"
    # Aadhaar numbers (12 digits, optionally space-separated in groups of 4)
    r"\b\d{4}\s?\d{4}\s?\d{4}\b"
    r"|"
    # PAN numbers (AAAAA9999A format)
    r"\b[A-Z]{5}\d{4}[A-Z]\b"
    r"|"
    # Indian mobile numbers (10 digits starting 6-9, optional +91/91/0 prefix)
    r"(?:\+91[\s-]?|91[\s-]?|0)?[6-9]\d{9}\b"
    r")",
    re.IGNORECASE,
)


def _redact(text: str) -> str:
    """Replace PII patterns with [REDACTED]."""
    return _PII_PATTERNS.sub("[REDACTED]", text)


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for Google Cloud Logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "severity": record.levelname,
            "message": _redact(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
        }
        # Add request_id from context if available
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_entry["request_id"] = request_id
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = _redact(self.formatException(record.exc_info))
        return json.dumps(log_entry, default=str)


class _RedactingFormatter(logging.Formatter):
    """Human-readable formatter with PII redaction for development."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        return _redact(super().format(record))


def configure_logging() -> None:
    """Configure logging based on environment."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Clear existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if settings.app_env in ("production", "staging"):
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(_RedactingFormatter())
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
