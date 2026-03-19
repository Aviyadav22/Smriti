"""Add indexes for medium-priority audit columns.

Revision ID: a1b2c3d4e5f6
Revises: 017
Create Date: 2026-03-19

Changes:
1. Index audit_logs(user_id) for user activity lookups
2. Index consent(user_id) for DPDP consent queries
3. Index agent_executions(user_id) for agent history lookups
4. Index documents(user_id) for user document listing
5. Index cases(decision_date) for date-range filtering
6. Index cases(text_hash) for deduplication checks
"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_consent_user_id ON consent(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_executions_user_id ON agent_executions(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cases_decision_date ON cases(decision_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cases_text_hash ON cases(text_hash)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cases_text_hash")
    op.execute("DROP INDEX IF EXISTS ix_cases_decision_date")
    op.execute("DROP INDEX IF EXISTS ix_documents_user_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_executions_user_id")
    op.execute("DROP INDEX IF EXISTS ix_consent_user_id")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_user_id")
