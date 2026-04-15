"""Tests for CircuitBreaker reset behavior (G17).

Tests the three-state circuit breaker: closed → open → half_open → closed.
Verifies thread safety, cooldown, and probe mechanics.
"""
from __future__ import annotations

import asyncio

# The CircuitBreaker is in scripts/ingest_s3.py — we need to import carefully
import sys
from pathlib import Path

import pytest

# Ensure scripts directory is importable
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from ingest_s3 import CircuitBreaker


class TestCircuitBreakerClosedState:
    """Tests for the CLOSED (normal) state."""

    @pytest.mark.asyncio
    async def test_new_breaker_is_closed(self):
        """A fresh breaker should be in closed state."""
        breaker = CircuitBreaker(threshold=3)
        assert not breaker.is_tripped
        assert await breaker.check() is True

    @pytest.mark.asyncio
    async def test_failures_below_threshold_stay_closed(self):
        """Failures below threshold should keep the breaker closed."""
        breaker = CircuitBreaker(threshold=5)
        for _ in range(4):
            tripped = await breaker.record_failure()
            assert tripped is False
        assert not breaker.is_tripped
        assert await breaker.check() is True

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        """A success should reset the consecutive failure counter."""
        breaker = CircuitBreaker(threshold=5)
        for _ in range(4):
            await breaker.record_failure()
        await breaker.record_success()
        # Now 4 more failures should not trip (counter was reset)
        for _ in range(4):
            await breaker.record_failure()
        assert not breaker.is_tripped


class TestCircuitBreakerOpenState:
    """Tests for the OPEN (tripped) state."""

    @pytest.mark.asyncio
    async def test_trips_at_threshold(self):
        """Reaching the failure threshold should trip the breaker open."""
        breaker = CircuitBreaker(threshold=3)
        for i in range(3):
            tripped = await breaker.record_failure()
        assert tripped is True
        assert breaker.is_tripped

    @pytest.mark.asyncio
    async def test_open_rejects_requests(self):
        """An open breaker should reject requests (return False from check)."""
        breaker = CircuitBreaker(threshold=2, cooldown_secs=60.0)
        await breaker.record_failure()
        await breaker.record_failure()
        assert breaker.is_tripped
        assert await breaker.check() is False

    @pytest.mark.asyncio
    async def test_record_failure_returns_true_on_trip(self):
        """record_failure should return True on the exact failure that trips."""
        breaker = CircuitBreaker(threshold=3)
        assert await breaker.record_failure() is False  # 1st
        assert await breaker.record_failure() is False  # 2nd
        assert await breaker.record_failure() is True   # 3rd — trips


class TestCircuitBreakerHalfOpenState:
    """Tests for the HALF_OPEN (probe) state."""

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_cooldown(self):
        """After cooldown, an open breaker should transition to half_open."""
        breaker = CircuitBreaker(threshold=2, cooldown_secs=0.1)
        await breaker.record_failure()
        await breaker.record_failure()
        assert breaker.is_tripped

        # Wait for cooldown
        await asyncio.sleep(0.15)

        # check() should now transition to half_open and return True
        result = await breaker.check()
        assert result is True
        assert breaker._state == "half_open"

    @pytest.mark.asyncio
    async def test_half_open_success_closes_breaker(self):
        """A success in half_open state should close the breaker."""
        breaker = CircuitBreaker(threshold=2, cooldown_secs=0.1)
        await breaker.record_failure()
        await breaker.record_failure()

        await asyncio.sleep(0.15)
        await breaker.check()  # transitions to half_open

        await breaker.record_success()
        assert breaker._state == "closed"
        assert not breaker.is_tripped

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_breaker(self):
        """A failure in half_open state should reopen the breaker."""
        breaker = CircuitBreaker(threshold=2, cooldown_secs=0.1)
        await breaker.record_failure()
        await breaker.record_failure()

        await asyncio.sleep(0.15)
        await breaker.check()  # transitions to half_open

        await breaker.record_failure()
        assert breaker._state == "open"
        assert breaker.is_tripped


class TestCircuitBreakerEdgeCases:
    """Edge cases and concurrency safety."""

    @pytest.mark.asyncio
    async def test_multiple_successes_in_closed_state(self):
        """Multiple successes in closed state should be no-ops."""
        breaker = CircuitBreaker(threshold=5)
        for _ in range(10):
            await breaker.record_success()
        assert breaker._state == "closed"
        assert breaker._failures == 0

    @pytest.mark.asyncio
    async def test_check_before_cooldown_stays_open(self):
        """Checking before cooldown expires should stay open and reject."""
        breaker = CircuitBreaker(threshold=2, cooldown_secs=100.0)
        await breaker.record_failure()
        await breaker.record_failure()
        # No sleep — cooldown hasn't expired
        assert await breaker.check() is False
        assert breaker.is_tripped

    @pytest.mark.asyncio
    async def test_custom_threshold_and_cooldown(self):
        """Custom threshold and cooldown should be respected."""
        breaker = CircuitBreaker(threshold=1, cooldown_secs=0.05)
        await breaker.record_failure()
        assert breaker.is_tripped

        await asyncio.sleep(0.1)
        result = await breaker.check()
        assert result is True  # half_open probe

    @pytest.mark.asyncio
    async def test_concurrent_checks_are_serialized(self):
        """Concurrent check() calls should be serialized by the lock."""
        breaker = CircuitBreaker(threshold=2, cooldown_secs=0.01)
        await breaker.record_failure()
        await breaker.record_failure()

        await asyncio.sleep(0.05)

        # Fire multiple concurrent checks
        results = await asyncio.gather(
            breaker.check(),
            breaker.check(),
            breaker.check(),
        )
        # At least one should get True (the probe); the lock serializes them
        assert any(results)
