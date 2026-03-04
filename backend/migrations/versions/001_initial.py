"""Initial database schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- cases ---
    op.create_table(
        "cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("citation", sa.String(), nullable=True),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("cnr", sa.String(), nullable=True),
        sa.Column("court", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("case_type", sa.String(), nullable=True),
        sa.Column("jurisdiction", sa.String(), nullable=True),
        sa.Column("bench_type", sa.String(), nullable=True),
        sa.Column("judge", ARRAY(sa.String()), nullable=True),
        sa.Column("author_judge", sa.String(), nullable=True),
        sa.Column("petitioner", sa.String(), nullable=True),
        sa.Column("respondent", sa.String(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=True),
        sa.Column("disposal_nature", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", ARRAY(sa.String()), nullable=True),
        sa.Column("acts_cited", ARRAY(sa.String()), nullable=True),
        sa.Column("cases_cited", ARRAY(sa.String()), nullable=True),
        sa.Column("ratio_decidendi", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("searchable_text", TSVECTOR(), nullable=True),
        sa.Column("pdf_storage_path", sa.String(), nullable=True),
        sa.Column("s3_source_path", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="aws_open_data"),
        sa.Column("language", sa.String(), nullable=False, server_default="english"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_languages", ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "year >= 1800 AND year <= 2200", name="ck_cases_year_range"
        ),
    )

    # Single-column indexes
    op.create_index("ix_cases_court", "cases", ["court"])
    op.create_index("ix_cases_year", "cases", ["year"])
    op.create_index("ix_cases_case_type", "cases", ["case_type"])
    op.create_index("ix_cases_jurisdiction", "cases", ["jurisdiction"])
    op.create_index("ix_cases_bench_type", "cases", ["bench_type"])
    op.create_index("ix_cases_source", "cases", ["source"])

    # Composite indexes
    op.create_index("ix_cases_court_year", "cases", ["court", "year"])
    op.create_index("ix_cases_year_case_type", "cases", ["year", "case_type"])
    op.create_index("ix_cases_court_case_type", "cases", ["court", "case_type"])

    # GIN indexes on arrays
    op.create_index(
        "ix_cases_keywords_gin", "cases", ["keywords"], postgresql_using="gin"
    )
    op.create_index(
        "ix_cases_acts_cited_gin", "cases", ["acts_cited"], postgresql_using="gin"
    )
    op.create_index(
        "ix_cases_cases_cited_gin", "cases", ["cases_cited"], postgresql_using="gin"
    )
    op.create_index(
        "ix_cases_judge_gin", "cases", ["judge"], postgresql_using="gin"
    )

    # GIN index on tsvector
    op.create_index(
        "ix_cases_searchable_text_gin",
        "cases",
        ["searchable_text"],
        postgresql_using="gin",
    )

    # Unique partial index on citation
    op.create_index(
        "ix_cases_citation_unique",
        "cases",
        ["citation"],
        unique=True,
        postgresql_where=sa.text("citation IS NOT NULL"),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column(
            "role", sa.String(), nullable=False, server_default="researcher"
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'researcher', 'viewer')", name="ck_users_role"
        ),
    )

    # --- chat_sessions ---
    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(),
            nullable=False,
            server_default="New Research Session",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- chat_messages ---
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", JSONB(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')", name="ck_chat_messages_role"
        ),
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column(
            "mime_type",
            sa.String(),
            nullable=False,
            server_default="application/pdf",
        ),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="pending"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_documents_status",
        ),
    )

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- consents ---
    op.create_table(
        "consents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("consent_type", sa.String(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(), nullable=False, server_default="1.0"),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- Full-text search trigger function and trigger ---
    op.execute("""
        CREATE OR REPLACE FUNCTION update_searchable_text() RETURNS TRIGGER AS $$
        BEGIN
            NEW.searchable_text :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.citation, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.court, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.judge, ' '), '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.petitioner, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.respondent, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D');
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trigger_update_searchable_text
            BEFORE INSERT OR UPDATE ON cases
            FOR EACH ROW EXECUTE FUNCTION update_searchable_text();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trigger_update_searchable_text ON cases;")
    op.execute("DROP FUNCTION IF EXISTS update_searchable_text();")

    op.drop_table("consents")
    op.drop_table("audit_logs")
    op.drop_table("documents")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("users")

    # Drop indexes before dropping table
    op.drop_index("ix_cases_citation_unique", table_name="cases")
    op.drop_index("ix_cases_searchable_text_gin", table_name="cases")
    op.drop_index("ix_cases_judge_gin", table_name="cases")
    op.drop_index("ix_cases_cases_cited_gin", table_name="cases")
    op.drop_index("ix_cases_acts_cited_gin", table_name="cases")
    op.drop_index("ix_cases_keywords_gin", table_name="cases")
    op.drop_index("ix_cases_court_case_type", table_name="cases")
    op.drop_index("ix_cases_year_case_type", table_name="cases")
    op.drop_index("ix_cases_court_year", table_name="cases")
    op.drop_index("ix_cases_source", table_name="cases")
    op.drop_index("ix_cases_bench_type", table_name="cases")
    op.drop_index("ix_cases_jurisdiction", table_name="cases")
    op.drop_index("ix_cases_case_type", table_name="cases")
    op.drop_index("ix_cases_year", table_name="cases")
    op.drop_index("ix_cases_court", table_name="cases")
    op.drop_table("cases")
