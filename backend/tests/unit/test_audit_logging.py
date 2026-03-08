"""Tests for audit logging functionality."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.security.audit import create_audit_log


class TestCreateAuditLog:
    """Tests for the create_audit_log function."""

    @pytest.mark.asyncio
    async def test_inserts_log_entry(self) -> None:
        """create_audit_log should execute an INSERT and commit."""
        mock_db = AsyncMock()

        await create_audit_log(
            db=mock_db,
            action="login.success",
            user_id="user-123",
            resource_type="auth",
            resource_id=None,
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0",
            metadata={"key": "value"},
        )

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_none_metadata(self) -> None:
        """create_audit_log should handle None metadata gracefully."""
        mock_db = AsyncMock()

        await create_audit_log(
            db=mock_db,
            action="search",
            user_id="user-456",
            resource_type="search_query",
            resource_id=None,
            metadata=None,
        )

        mock_db.execute.assert_called_once()
        # Verify metadata param is None
        call_args = mock_db.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("parameters", {})
        assert params["metadata"] is None

    @pytest.mark.asyncio
    async def test_handles_none_ip_address(self) -> None:
        """create_audit_log should handle None IP address (hashed_ip = None)."""
        mock_db = AsyncMock()

        await create_audit_log(
            db=mock_db,
            action="test",
            user_id="user-789",
            resource_type="test",
            resource_id=None,
            ip_address=None,
        )

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("parameters", {})
        assert params["ip_address"] is None

    @pytest.mark.asyncio
    async def test_ip_address_is_hashed(self) -> None:
        """IP addresses should be hashed for DPDP compliance."""
        mock_db = AsyncMock()

        await create_audit_log(
            db=mock_db,
            action="test",
            user_id="user-abc",
            resource_type="test",
            resource_id=None,
            ip_address="192.168.1.1",
        )

        call_args = mock_db.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("parameters", {})
        stored_ip = params["ip_address"]

        # Should not be the raw IP
        assert stored_ip != "192.168.1.1"
        # Should be a 16-char hex string (truncated SHA-256)
        assert stored_ip is not None
        assert len(stored_ip) == 16

    @pytest.mark.asyncio
    async def test_metadata_serialized_as_json(self) -> None:
        """Metadata dict should be serialized to JSON string."""
        mock_db = AsyncMock()

        await create_audit_log(
            db=mock_db,
            action="test",
            user_id="user-def",
            resource_type="test",
            resource_id=None,
            metadata={"reason": "test_reason", "count": 5},
        )

        call_args = mock_db.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("parameters", {})
        import json

        parsed = json.loads(params["metadata"])
        assert parsed["reason"] == "test_reason"
        assert parsed["count"] == 5
