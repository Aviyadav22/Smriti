"""Add missing indexes for performance and audit queries.

Revision ID: 006
Revises: 005
Create Date: 2026-03-07

NOTE: The GIN index on case_sections uses CREATE INDEX CONCURRENTLY to avoid
holding an exclusive table lock on a potentially large table.  CONCURRENTLY
cannot run inside a transaction, so we disable the default Alembic
transaction wrapper for this migration.
"""

from alembic import op
from sqlalchemy import text

# revision identifiers
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # B-tree indexes on small lookup tables — these are fast and safe inside
    # the default transaction.
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_consents_user_id", "consents", ["user_id"])

    # GIN index on case_sections.content — use CONCURRENTLY to avoid table lock.
    # CONCURRENTLY cannot run inside a transaction, so we obtain a raw
    # connection with autocommit semantics.
    connection = op.get_bind()
    # For asyncpg/psycopg drivers behind SQLAlchemy, execution_options
    # with isolation_level="AUTOCOMMIT" exits the transaction context.
    connection = connection.execution_options(isolation_level="AUTOCOMMIT")
    connection.execute(
        text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_case_sections_content_gin "
            "ON case_sections USING gin(to_tsvector('english', content))"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at")
    op.drop_index("ix_audit_logs_user_id")
    op.drop_index("ix_audit_logs_action")
    op.drop_index("ix_consents_user_id")
    # DROP INDEX CONCURRENTLY also avoids locking but requires autocommit
    connection = op.get_bind()
    connection = connection.execution_options(isolation_level="AUTOCOMMIT")
    connection.execute(text("DROP INDEX CONCURRENTLY IF EXISTS ix_case_sections_content_gin"))
