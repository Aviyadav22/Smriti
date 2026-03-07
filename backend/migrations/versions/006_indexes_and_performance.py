"""Add missing indexes for performance and audit queries.

Revision ID: 006
Revises: 005
Create Date: 2026-03-07
"""

from alembic import op

# revision identifiers
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_consents_user_id", "consents", ["user_id"])
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_case_sections_content_gin
        ON case_sections USING gin(to_tsvector('english', content))
        """
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at")
    op.drop_index("ix_audit_logs_user_id")
    op.drop_index("ix_audit_logs_action")
    op.drop_index("ix_consents_user_id")
    op.execute("DROP INDEX IF EXISTS ix_case_sections_content_gin")
