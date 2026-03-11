"""Legal completeness: coram size, appellate chain, opinion tracking, party types, companion cases.

Adds columns for:
- C1: coram_size (integer)
- C2: lower_court, lower_court_case_number, appeal_from
- C3: opinion_type, dissenting_judges, concurring_judges, split_ratio
- C10: petitioner_type, respondent_type, is_pil
- C11: companion_cases
- C13: Expanded disposal_nature CHECK constraint

Revision ID: 011
Revises: 010
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # C1: Coram size
    op.add_column("cases", sa.Column("coram_size", sa.Integer(), nullable=True))

    # C2: Lower court / appellate chain
    op.add_column("cases", sa.Column("lower_court", sa.String(200), nullable=True))
    op.add_column(
        "cases", sa.Column("lower_court_case_number", sa.String(200), nullable=True)
    )
    op.add_column("cases", sa.Column("appeal_from", sa.String(200), nullable=True))

    # C3: Opinion type and split tracking
    op.add_column("cases", sa.Column("opinion_type", sa.String(30), nullable=True))
    op.add_column(
        "cases",
        sa.Column("dissenting_judges", ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column("concurring_judges", ARRAY(sa.String()), nullable=True),
    )
    op.add_column("cases", sa.Column("split_ratio", sa.String(20), nullable=True))

    # C10: Party type classification
    op.add_column(
        "cases", sa.Column("petitioner_type", sa.String(50), nullable=True)
    )
    op.add_column(
        "cases", sa.Column("respondent_type", sa.String(50), nullable=True)
    )
    op.add_column("cases", sa.Column("is_pil", sa.Boolean(), nullable=True))

    # C11: Companion cases
    op.add_column(
        "cases",
        sa.Column("companion_cases", ARRAY(sa.String()), nullable=True),
    )

    # C3: CHECK constraint for opinion_type
    op.create_check_constraint(
        "ck_cases_opinion_type",
        "cases",
        "opinion_type IN ('unanimous','majority','plurality','per_curiam') "
        "OR opinion_type IS NULL",
    )

    # C10: CHECK constraint for party types
    op.create_check_constraint(
        "ck_cases_petitioner_type",
        "cases",
        "petitioner_type IN ('individual','government_central','government_state',"
        "'PSU','company','NGO','statutory_body','other') "
        "OR petitioner_type IS NULL",
    )
    op.create_check_constraint(
        "ck_cases_respondent_type",
        "cases",
        "respondent_type IN ('individual','government_central','government_state',"
        "'PSU','company','NGO','statutory_body','other') "
        "OR respondent_type IS NULL",
    )

    # C1: CHECK constraint for coram_size (must be positive)
    op.create_check_constraint(
        "ck_cases_coram_size",
        "cases",
        "coram_size > 0 OR coram_size IS NULL",
    )

    # C13: Expand disposal_nature CHECK constraint to include new values
    # Drop the existing constraint from migration 009 and recreate with expanded values
    op.drop_constraint("ck_cases_disposal_nature", "cases")
    op.create_check_constraint(
        "ck_cases_disposal_nature",
        "cases",
        "disposal_nature IN ("
        "'Allowed','Dismissed','Partly Allowed','Withdrawn','Remanded',"
        "'Disposed Of','Settled','Transferred','Modified','Other',"
        "'Referred to Larger Bench','Abated','Not Pressed'"
        ") OR disposal_nature IS NULL",
    )

    # Useful indexes for new columns
    op.create_index("ix_cases_opinion_type", "cases", ["opinion_type"])
    op.create_index("ix_cases_is_pil", "cases", ["is_pil"])
    op.create_index("ix_cases_coram_size", "cases", ["coram_size"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_cases_coram_size", "cases")
    op.drop_index("ix_cases_is_pil", "cases")
    op.drop_index("ix_cases_opinion_type", "cases")

    # Restore original disposal_nature constraint from migration 009
    op.drop_constraint("ck_cases_disposal_nature", "cases")
    op.create_check_constraint(
        "ck_cases_disposal_nature",
        "cases",
        "disposal_nature IN ("
        "'Allowed','Dismissed','Partly Allowed','Withdrawn','Remanded',"
        "'Disposed Of','Settled','Transferred','Modified','Other'"
        ") OR disposal_nature IS NULL",
    )

    # Drop CHECK constraints
    op.drop_constraint("ck_cases_coram_size", "cases")
    op.drop_constraint("ck_cases_respondent_type", "cases")
    op.drop_constraint("ck_cases_petitioner_type", "cases")
    op.drop_constraint("ck_cases_opinion_type", "cases")

    # Drop columns in reverse order
    op.drop_column("cases", "companion_cases")
    op.drop_column("cases", "is_pil")
    op.drop_column("cases", "respondent_type")
    op.drop_column("cases", "petitioner_type")
    op.drop_column("cases", "split_ratio")
    op.drop_column("cases", "concurring_judges")
    op.drop_column("cases", "dissenting_judges")
    op.drop_column("cases", "opinion_type")
    op.drop_column("cases", "appeal_from")
    op.drop_column("cases", "lower_court_case_number")
    op.drop_column("cases", "lower_court")
    op.drop_column("cases", "coram_size")
