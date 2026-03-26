"""Generic circuit breaker — trips after consecutive failures to prevent cascade.

Supports two flavours:

* **CircuitBreaker** (async, 3-state: closed → open → half_open → closed)
  Used by Pinecone, Neo4j, Cohere and other async providers.

* **LLMCircuitBreaker** / **LLMCircuitBreakerOpen** — legacy synchronous aliases
  kept for backwards compatibility with the LLM provider layer.
"""
from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open (too many failures)."""

    def __init__(self, cooldown_remaining: float, *, service: str = "service") -> None:
        self.cooldown_remaining = cooldown_remaining
        super().__init__(
            f"{service} circuit breaker OPEN — {cooldown_remaining:.0f}s cooldown remaining. "
            f"Too many consecutive failures."
        )


# Legacy alias
LLMCircuitBreakerOpen = CircuitBreakerOpen


# ---------------------------------------------------------------------------
# Async circuit breaker (3-state: closed / open / half_open)
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Async circuit breaker with half-open recovery.

    States:
    - CLOSED: normal operation, counts consecutive failures.
    - OPEN: tripped after ``threshold`` failures, rejects immediately.
    - HALF_OPEN: after ``cooldown`` has elapsed since opening, allows
      one probe request. If it succeeds → CLOSED; if it fails → OPEN again.

    All state mutations are guarded by an asyncio.Lock for safety under
    concurrent callers.

    Usage::

        breaker = CircuitBreaker(threshold=5, cooldown=60.0, service="pinecone")

        if not await breaker.check():
            raise CircuitBreakerOpen(...)
        try:
            result = await provider.call(...)
            await breaker.record_success()
        except Exception:
            await breaker.record_failure()
            raise
    """

    def __init__(
        self,
        threshold: int = 5,
        cooldown: float = 60.0,
        *,
        cooldown_secs: float | None = None,
        service: str = "service",
    ) -> None:
        self._threshold = threshold
        # Accept both `cooldown` and legacy `cooldown_secs` kwarg
        self._cooldown = cooldown_secs if cooldown_secs is not None else cooldown
        self._failures = 0
        self._state = "closed"  # closed | open | half_open
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()
        self._service = service

    @property
    def is_tripped(self) -> bool:
        return self._state == "open"

    @property
    def failure_count(self) -> int:
        return self._failures

    async def check(self) -> bool:
        """Return True if the request should proceed, False to reject."""
        async with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open":
                if (time.monotonic() - self._opened_at) >= self._cooldown:
                    self._state = "half_open"
                    logger.info(
                        "%s circuit breaker entering half-open state (probing)",
                        self._service,
                    )
                    return True
                return False
            # half_open — only one probe at a time; lock ensures serialisation
            return True

    async def record_success(self) -> None:
        async with self._lock:
            if self._state == "half_open":
                logger.info("%s circuit breaker probe succeeded — closing", self._service)
            self._failures = 0
            self._state = "closed"

    async def record_failure(self) -> bool:
        """Returns True if the breaker just tripped open."""
        async with self._lock:
            self._failures += 1
            if self._state == "half_open":
                logger.warning(
                    "%s circuit breaker probe failed — reopening", self._service
                )
                self._state = "open"
                self._opened_at = time.monotonic()
                return True
            if self._failures >= self._threshold:
                self._state = "open"
                self._opened_at = time.monotonic()
                logger.critical(
                    "%s circuit breaker OPEN: %d consecutive failures",
                    self._service,
                    self._failures,
                )
                return True
            return False


# ---------------------------------------------------------------------------
# Sync circuit breaker (legacy LLM compat)
# ---------------------------------------------------------------------------

class LLMCircuitBreaker:
    """Synchronous circuit breaker for LLM API calls — trips after N consecutive failures.

    Kept for backwards compatibility. New code should prefer :class:`CircuitBreaker`.
    """

    def __init__(self, threshold: int = 5, cooldown: float = 60.0) -> None:
        self._consecutive_failures = 0
        self._threshold = threshold
        self._cooldown = cooldown
        self._open_until = 0.0

    def check(self) -> None:
        """Check if the circuit breaker is open. Raises if tripped."""
        if self._consecutive_failures >= self._threshold:
            now = time.monotonic()
            if now < self._open_until:
                raise LLMCircuitBreakerOpen(self._open_until - now)
            # Cooldown expired — reset and allow retry
            logger.info("LLM circuit breaker cooldown expired, allowing retry")
            self._consecutive_failures = 0

    def record_success(self) -> None:
        """Record a successful LLM call — resets failure counter."""
        self._consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed LLM call — increments counter and may trip breaker."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            self._open_until = time.monotonic() + self._cooldown
            logger.warning(
                "LLM circuit breaker TRIPPED after %d consecutive failures, "
                "cooldown %.0fs",
                self._consecutive_failures,
                self._cooldown,
            )

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is currently open."""
        return (
            self._consecutive_failures >= self._threshold
            and time.monotonic() < self._open_until
        )

    @property
    def failure_count(self) -> int:
        return self._consecutive_failures
