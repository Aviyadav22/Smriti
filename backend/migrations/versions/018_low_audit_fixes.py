"""Low-severity audit fixes: dpdp_audit_log JSON → JSONB.

Revision ID: 018
Revises: 017
Create Date: 2026-03-19

Changes:
1. Convert dpdp_audit_log.details from JSON to JSONB for indexing support
"""

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE dpdp_audit_log "
        "ALTER COLUMN details TYPE jsonb USING details::jsonb"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE dpdp_audit_log "
        "ALTER COLUMN details TYPE json USING details::json"
    )
