"""Add strategy and drafting to agent_type check constraint.

Revision ID: 008
Revises: 007
Create Date: 2026-03-08
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_executions_agent_type", "agent_executions", type_="check")
    op.create_check_constraint(
        "ck_agent_executions_agent_type",
        "agent_executions",
        "agent_type IN ('research', 'case_prep', 'strategy', 'drafting')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agent_executions_agent_type", "agent_executions", type_="check")
    op.create_check_constraint(
        "ck_agent_executions_agent_type",
        "agent_executions",
        "agent_type IN ('research', 'case_prep')",
    )
