"""Create amendment_maps table for dynamic old↔new code mappings.

Revision ID: 030
"""
from alembic import op
import sqlalchemy as sa

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "amendment_maps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("old_act", sa.String(100), nullable=False),
        sa.Column("new_act", sa.String(100), nullable=False),
        sa.Column("old_section", sa.String(20), nullable=False),
        sa.Column("new_section", sa.String(20), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_amendment_maps_old",
        "amendment_maps",
        ["old_act", "old_section"],
    )
    op.create_index(
        "ix_amendment_maps_new",
        "amendment_maps",
        ["new_act", "new_section"],
    )


def downgrade() -> None:
    op.drop_table("amendment_maps")
