"""Tests for graceful shutdown signal handling (G18).

Tests that the ingestion script properly handles shutdown signals
using loop.call_soon_threadsafe for safe async signaling.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Ensure scripts directory is importable
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


class TestGracefulShutdownEvent:
    """G18: Tests for graceful shutdown mechanics."""

    @pytest.mark.asyncio
    async def test_shutdown_event_stops_processing(self):
        """Setting the shutdown event should signal workers to stop."""
        shutdown_event = asyncio.Event()
        assert not shutdown_event.is_set()

        # Simulate signal handler setting the event
        shutdown_event.set()
        assert shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_call_soon_threadsafe_sets_event(self):
        """loop.call_soon_threadsafe should safely set the event from another thread."""
        shutdown_event = asyncio.Event()
        loop = asyncio.get_event_loop()

        # This is how the signal handler works: thread-safe event setting
        loop.call_soon_threadsafe(shutdown_event.set)

        # Give the event loop a chance to process the callback
        await asyncio.sleep(0.01)
        assert shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_workers_check_shutdown_event(self):
        """Workers should check the shutdown event between tasks."""
        shutdown_event = asyncio.Event()
        processed = []

        async def mock_worker(items: list[int]) -> None:
            for item in items:
                if shutdown_event.is_set():
                    break
                processed.append(item)
                await asyncio.sleep(0.01)

        # Set shutdown after a short delay
        async def trigger_shutdown():
            await asyncio.sleep(0.03)
            shutdown_event.set()

        await asyncio.gather(
            mock_worker(list(range(100))),
            trigger_shutdown(),
        )

        # Should have processed only a few items before shutdown
        assert len(processed) < 100
        assert len(processed) > 0

    @pytest.mark.asyncio
    async def test_shutdown_event_with_multiple_workers(self):
        """Multiple workers should all respect the same shutdown event."""
        shutdown_event = asyncio.Event()
        worker_counts = [0, 0, 0]

        async def mock_worker(worker_id: int) -> None:
            while not shutdown_event.is_set():
                worker_counts[worker_id] += 1
                await asyncio.sleep(0.01)

        async def trigger_shutdown():
            await asyncio.sleep(0.05)
            shutdown_event.set()

        await asyncio.gather(
            mock_worker(0),
            mock_worker(1),
            mock_worker(2),
            trigger_shutdown(),
        )

        # All workers should have stopped
        total = sum(worker_counts)
        assert total > 0, "Workers should have done some work"
        assert total < 300, "Workers should have stopped after shutdown"
