"""Fix CHECK constraints and column types.

Revision ID: 022
Revises: 021
Create Date: 2026-03-21

Changes:
1. Fix jurisdiction CHECK: 'IP/commercial' → 'ip/commercial' (match pipeline lowercase)
2. Add 'rejected' to ingestion_status CHECK (admin_review endpoint uses it)
3. Fix graph_build_queue.case_id: String → UUID (FK to cases.id which is UUID)
"""

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Fix jurisdiction CHECK constraint — lowercase 'ip/commercial'
    op.execute("ALTER TABLE cases DROP CONSTRAINT IF EXISTS ck_cases_jurisdiction")
    op.execute("""
        ALTER TABLE cases ADD CONSTRAINT ck_cases_jurisdiction
        CHECK (
            jurisdiction IN (
                'civil','criminal','constitutional','tax','labor','company',
                'family','environmental','arbitration','consumer','election',
                'service','ip/commercial','other'
            ) OR jurisdiction IS NULL
        )
    """)

    # 2. Add 'rejected' to ingestion_status CHECK constraint
    op.execute("ALTER TABLE cases DROP CONSTRAINT IF EXISTS ck_cases_ingestion_status")
    op.execute("""
        ALTER TABLE cases ADD CONSTRAINT ck_cases_ingestion_status
        CHECK (ingestion_status IN (
            'pending', 'processing', 'complete',
            'failed', 'vectors_failed', 'needs_review', 'rejected'
        ))
    """)

    # 3. Fix graph_build_queue.case_id: String → UUID
    #    Drop and recreate the column with correct type to match cases.id (UUID)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'graph_build_queue') THEN
                ALTER TABLE graph_build_queue
                    ALTER COLUMN case_id TYPE uuid USING case_id::uuid;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Revert graph_build_queue.case_id back to text
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'graph_build_queue') THEN
                ALTER TABLE graph_build_queue
                    ALTER COLUMN case_id TYPE text USING case_id::text;
            END IF;
        END $$;
    """)

    # Revert ingestion_status CHECK (remove 'rejected')
    op.execute("ALTER TABLE cases DROP CONSTRAINT IF EXISTS ck_cases_ingestion_status")
    op.execute("""
        ALTER TABLE cases ADD CONSTRAINT ck_cases_ingestion_status
        CHECK (ingestion_status IN (
            'pending', 'processing', 'complete',
            'failed', 'vectors_failed', 'needs_review'
        ))
    """)

    # Revert jurisdiction CHECK (restore 'IP/commercial')
    op.execute("ALTER TABLE cases DROP CONSTRAINT IF EXISTS ck_cases_jurisdiction")
    op.execute("""
        ALTER TABLE cases ADD CONSTRAINT ck_cases_jurisdiction
        CHECK (
            jurisdiction IN (
                'civil','criminal','constitutional','tax','labor','company',
                'family','environmental','arbitration','consumer','election',
                'service','IP/commercial','other'
            ) OR jurisdiction IS NULL
        )
    """)
