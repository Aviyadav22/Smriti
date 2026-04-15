"""Add primary_legal_issue column to cases table.

Revision ID: 039
Revises: 038
"""

import sqlalchemy as sa
from alembic import op

revision = "039"
down_revision = "038"


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("primary_legal_issue", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cases", "primary_legal_issue")
