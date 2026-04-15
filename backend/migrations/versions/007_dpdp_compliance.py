"""DPDP compliance tables.

Revision ID: 007
Revises: 006
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "007"
down_revision = "006"


def upgrade():
    # dpdp_audit_log — compliance-mandated record of data operations
    op.create_table(
        "dpdp_audit_log",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("user_id", UUID, nullable=True),
        sa.Column("details", sa.JSON, default={}),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table("dpdp_audit_log")
