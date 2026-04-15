"""Ingestion V3: source_dataset, legal_propositions, statute_sections_interpreted, fact_pattern_summary, case_statute_interpretations table"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "035"
down_revision = "034"


def upgrade() -> None:
    # --- V3 columns on cases ---
    op.add_column(
        "cases", sa.Column("source_dataset", sa.String(50), server_default="aws_open_data_sc")
    )
    op.add_column("cases", sa.Column("legal_propositions", JSONB, nullable=True))
    op.add_column("cases", sa.Column("statute_sections_interpreted", JSONB, nullable=True))
    op.add_column("cases", sa.Column("fact_pattern_summary", sa.Text, nullable=True))
    op.create_index("ix_cases_source_dataset", "cases", ["source_dataset"])

    # --- case_statute_interpretations table ---
    op.create_table(
        "case_statute_interpretations",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_id",
            sa.dialects.postgresql.UUID,
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_text", sa.String(200), nullable=False),
        sa.Column("normalized_section", sa.String(200), nullable=False),
        sa.Column("act_name", sa.String(200), nullable=False),
        sa.Column("interpretation_summary", sa.Text, nullable=True),
        sa.Column("is_primary_holding", sa.Boolean, server_default="false"),
        sa.UniqueConstraint("case_id", "normalized_section", name="uq_case_statute_interp"),
    )
    op.create_index(
        "ix_csi_normalized_section", "case_statute_interpretations", ["normalized_section"]
    )
    op.create_index("ix_csi_case_id", "case_statute_interpretations", ["case_id"])
    op.create_index("ix_csi_act_name", "case_statute_interpretations", ["act_name"])


def downgrade() -> None:
    op.drop_table("case_statute_interpretations")
    op.drop_index("ix_cases_source_dataset")
    op.drop_column("cases", "fact_pattern_summary")
    op.drop_column("cases", "statute_sections_interpreted")
    op.drop_column("cases", "legal_propositions")
    op.drop_column("cases", "source_dataset")
