"""Tests for agent execution API routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.agents import router
from app.db.postgres import get_db
from app.models.agent_execution import AgentExecution, AgentStatus
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEST_USER_ID = str(uuid.uuid4())
_OTHER_USER_ID = str(uuid.uuid4())


def _make_token(user_id: str = _TEST_USER_ID) -> TokenPayload:
    now = datetime.now(UTC)
    return TokenPayload(
        sub=user_id,
        role="user",
        exp=now,
        iat=now,
        jti=str(uuid.uuid4()),
    )


def _make_execution(
    user_id: str = _TEST_USER_ID,
    status: str = "running",
    agent_type: str = "research",
) -> AgentExecution:
    """Create a mock AgentExecution with sensible defaults."""
    exec_obj = MagicMock(spec=AgentExecution)
    exec_obj.id = uuid.uuid4()
    exec_obj.user_id = uuid.UUID(user_id)
    exec_obj.agent_type = agent_type
    exec_obj.status = status
    exec_obj.input_data = {"query": "test query"}
    exec_obj.result_data = None
    exec_obj.thread_id = uuid.uuid4()
    exec_obj.current_step = None
    exec_obj.steps_completed = 0
    exec_obj.total_steps = None
    exec_obj.error_message = None
    exec_obj.created_at = datetime.now(UTC)
    exec_obj.updated_at = datetime.now(UTC)
    exec_obj.completed_at = None
    return exec_obj


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/agents")
    return test_app


@pytest.fixture
def authed_client(app: FastAPI) -> TestClient:
    """Client with auth dependency overridden to return a test user."""

    async def _override_user() -> TokenPayload:
        return _make_token()

    app.dependency_overrides[get_current_user] = _override_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(app: FastAPI) -> TestClient:
    """Client with NO auth override (will trigger 401)."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Route registration tests
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    def test_routes_registered(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/{agent_type}/run" in paths
        assert "/executions" in paths
        assert "/executions/{execution_id}" in paths
        assert "/executions/{execution_id}/resume" in paths

    def test_run_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{agent_type}/run":
                assert "POST" in route.methods

    def test_list_executions_is_get(self) -> None:
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/executions"
                and hasattr(route, "methods")
            ):
                if "GET" in route.methods:
                    return
        pytest.fail("GET /executions route not found")

    def test_resume_is_post(self) -> None:
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/executions/{execution_id}/resume"
            ):
                assert "POST" in route.methods

    def test_cancel_is_delete(self) -> None:
        found = False
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/executions/{execution_id}"
                and hasattr(route, "methods")
            ):
                if "DELETE" in route.methods:
                    found = True
        assert found, "DELETE /executions/{execution_id} route not found"


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestRunAgentValidation:
    def test_invalid_agent_type_returns_422(self, authed_client: TestClient) -> None:
        mock_db = AsyncMock()

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db
        resp = authed_client.post(
            "/api/v1/agents/invalid_type/run",
            json={"query": "test query"},
        )
        assert resp.status_code == 422
        authed_client.app.dependency_overrides.pop(get_db, None)

    def test_missing_auth_returns_401(self, unauthed_client: TestClient) -> None:
        resp = unauthed_client.post(
            "/api/v1/agents/research/run",
            json={"query": "test query"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Execution listing tests
# ---------------------------------------------------------------------------


class TestListExecutions:
    def test_returns_empty_list_for_new_user(
        self, authed_client: TestClient
    ) -> None:
        mock_db = AsyncMock()
        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0
        # Mock list query
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_list_result]
        )

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db

        resp = authed_client.get("/api/v1/agents/executions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["executions"] == []
        assert data["total"] == 0
        assert data["page"] == 1

        authed_client.app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Get execution tests
# ---------------------------------------------------------------------------


class TestGetExecution:
    def test_returns_404_for_nonexistent(self, authed_client: TestClient) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db

        fake_id = str(uuid.uuid4())
        resp = authed_client.get(f"/api/v1/agents/executions/{fake_id}")
        assert resp.status_code == 404

        authed_client.app.dependency_overrides.pop(get_db, None)

    def test_returns_403_for_other_user(self, authed_client: TestClient) -> None:
        mock_db = AsyncMock()
        execution = _make_execution(user_id=_OTHER_USER_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db

        resp = authed_client.get(
            f"/api/v1/agents/executions/{execution.id}"
        )
        assert resp.status_code == 403

        authed_client.app.dependency_overrides.pop(get_db, None)

    def test_returns_execution_detail(self, authed_client: TestClient) -> None:
        mock_db = AsyncMock()
        execution = _make_execution(user_id=_TEST_USER_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db

        resp = authed_client.get(
            f"/api/v1/agents/executions/{execution.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(execution.id)
        assert data["agent_type"] == "research"

        authed_client.app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Cancel execution tests
# ---------------------------------------------------------------------------


class TestCancelExecution:
    def test_cancel_updates_status(self, authed_client: TestClient) -> None:
        mock_db = AsyncMock()
        execution = _make_execution(
            user_id=_TEST_USER_ID, status=AgentStatus.running.value
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db

        resp = authed_client.delete(
            f"/api/v1/agents/executions/{execution.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

        authed_client.app.dependency_overrides.pop(get_db, None)

    def test_cancel_already_completed_returns_400(
        self, authed_client: TestClient
    ) -> None:
        mock_db = AsyncMock()
        execution = _make_execution(
            user_id=_TEST_USER_ID, status=AgentStatus.completed.value
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db

        resp = authed_client.delete(
            f"/api/v1/agents/executions/{execution.id}"
        )
        assert resp.status_code == 400

        authed_client.app.dependency_overrides.pop(get_db, None)

    def test_cancel_returns_404_for_nonexistent(
        self, authed_client: TestClient
    ) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db

        fake_id = str(uuid.uuid4())
        resp = authed_client.delete(f"/api/v1/agents/executions/{fake_id}")
        assert resp.status_code == 404

        authed_client.app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Resume execution tests
# ---------------------------------------------------------------------------


class TestResumeExecution:
    def test_resume_returns_400_when_not_waiting(
        self, authed_client: TestClient
    ) -> None:
        mock_db = AsyncMock()
        execution = _make_execution(
            user_id=_TEST_USER_ID, status=AgentStatus.running.value
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = execution
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db

        resp = authed_client.post(
            f"/api/v1/agents/executions/{execution.id}/resume",
            json={"input": "proceed"},
        )
        assert resp.status_code == 400

        authed_client.app.dependency_overrides.pop(get_db, None)

    def test_get_checkpointer_returns_singleton(self) -> None:
        """get_checkpointer() returns the same instance on repeated calls."""
        from app.core.dependencies import get_checkpointer

        cp1 = get_checkpointer()
        cp2 = get_checkpointer()
        assert cp1 is not None
        assert cp1 is cp2

    def test_resume_returns_404_for_nonexistent(
        self, authed_client: TestClient
    ) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _override_db():
            return mock_db

        authed_client.app.dependency_overrides[get_db] = _override_db

        fake_id = str(uuid.uuid4())
        resp = authed_client.post(
            f"/api/v1/agents/executions/{fake_id}/resume",
            json={"input": "proceed"},
        )
        assert resp.status_code == 404

        authed_client.app.dependency_overrides.pop(get_db, None)
