"""LLM circuit breaker — trips after consecutive failures to prevent cascade."""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class LLMCircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open (too many failures)."""

    def __init__(self, cooldown_remaining: float) -> None:
        self.cooldown_remaining = cooldown_remaining
        super().__init__(
            f"LLM circuit breaker OPEN — {cooldown_remaining:.0f}s cooldown remaining. "
            f"Too many consecutive failures."
        )


class LLMCircuitBreaker:
    """Circuit breaker for LLM API calls — trips after N consecutive failures.

    Usage::

        breaker = LLMCircuitBreaker(threshold=5, cooldown=60.0)

        breaker.check()  # raises LLMCircuitBreakerOpen if tripped
        try:
            result = await llm.generate(...)
            breaker.record_success()
        except Exception:
            breaker.record_failure()
            raise
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
                self._consecutive_failures, self._cooldown,
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
