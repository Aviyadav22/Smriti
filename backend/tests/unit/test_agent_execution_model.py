"""Tests for AgentExecution ORM model."""

import uuid

from app.models.agent_execution import AgentExecution, AgentStatus, AgentType


class TestAgentType:
    def test_enum_values(self) -> None:
        assert AgentType.research.value == "research"
        assert AgentType.case_prep.value == "case_prep"

    def test_enum_members(self) -> None:
        assert set(AgentType) == {AgentType.research, AgentType.case_prep}


class TestAgentStatus:
    def test_enum_values(self) -> None:
        assert AgentStatus.running.value == "running"
        assert AgentStatus.waiting_input.value == "waiting_input"
        assert AgentStatus.completed.value == "completed"
        assert AgentStatus.failed.value == "failed"
        assert AgentStatus.cancelled.value == "cancelled"

    def test_enum_members(self) -> None:
        assert set(AgentStatus) == {
            AgentStatus.running,
            AgentStatus.waiting_input,
            AgentStatus.completed,
            AgentStatus.failed,
            AgentStatus.cancelled,
        }


class TestAgentExecutionModel:
    def test_table_name(self) -> None:
        assert AgentExecution.__tablename__ == "agent_executions"

    def test_has_required_columns(self) -> None:
        cols = {c.name for c in AgentExecution.__table__.columns}
        expected = {
            "id",
            "user_id",
            "agent_type",
            "status",
            "input_data",
            "result_data",
            "thread_id",
            "current_step",
            "steps_completed",
            "total_steps",
            "completed_at",
            "error_message",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(cols)

    def test_agent_type_check_constraint(self) -> None:
        constraint = next(
            c
            for c in AgentExecution.__table_args__
            if hasattr(c, "name") and c.name == "ck_agent_executions_agent_type"
        )
        text = str(constraint.sqltext)
        assert "research" in text
        assert "case_prep" in text

    def test_status_check_constraint(self) -> None:
        constraint = next(
            c
            for c in AgentExecution.__table_args__
            if hasattr(c, "name") and c.name == "ck_agent_executions_status"
        )
        text = str(constraint.sqltext)
        for status in ("running", "waiting_input", "completed", "failed", "cancelled"):
            assert status in text

    def test_repr(self) -> None:
        uid = uuid.uuid4()
        execution = AgentExecution(
            id=uid, agent_type="research", status="running"
        )
        r = repr(execution)
        assert "AgentExecution" in r
        assert "research" in r
        assert "running" in r
