"""Search excellence: section FTS, cited_by_count, legal synonyms.

Adds:
- D2: searchable_content tsvector + GIN index on case_sections
- D4: cited_by_count column on cases for ranking boost
- D8: Legal abbreviation synonym dictionary for FTS

Revision ID: 012
Revises: 011
Create Date: 2026-03-11
"""

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # D2: Add tsvector column to case_sections for pre-computed FTS
    # ---------------------------------------------------------------
    op.execute(
        "ALTER TABLE case_sections "
        "ADD COLUMN IF NOT EXISTS searchable_content tsvector"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_case_sections_fts "
        "ON case_sections USING gin (searchable_content)"
    )

    # Trigger to auto-populate searchable_content on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION case_sections_searchable_update() RETURNS trigger AS $$
        BEGIN
            NEW.searchable_content :=
                to_tsvector('english', COALESCE(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER case_sections_searchable_trigger
        BEFORE INSERT OR UPDATE ON case_sections
        FOR EACH ROW EXECUTE FUNCTION case_sections_searchable_update();
    """)

    # Backfill existing rows
    op.execute(
        "UPDATE case_sections SET searchable_content = "
        "to_tsvector('english', COALESCE(content, '')) "
        "WHERE searchable_content IS NULL"
    )

    # ---------------------------------------------------------------
    # D4: Add cited_by_count for citation-based ranking boost
    # ---------------------------------------------------------------
    op.add_column(
        "cases",
        sa.Column("cited_by_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cases_cited_by_count "
        "ON cases (cited_by_count DESC)"
    )

    # ---------------------------------------------------------------
    # D8: Legal abbreviation synonym configuration for FTS
    # ---------------------------------------------------------------
    # Use a simple_dict approach — PostgreSQL synonym dictionaries
    # We create a custom text search configuration that includes synonyms
    # for common legal abbreviations.
    #
    # NOTE: Full thesaurus requires file-system access on the PG server.
    # Instead, we use a materialized view approach: expand search queries
    # at the application level (already done in query.py expand_statute_references).
    # Here we just add the synonym mappings table for app-level expansion.
    op.execute("""
        CREATE TABLE IF NOT EXISTS legal_synonyms (
            id SERIAL PRIMARY KEY,
            term TEXT NOT NULL UNIQUE,
            synonyms TEXT[] NOT NULL
        )
    """)
    # Seed with common legal abbreviation mappings
    op.execute("""
        INSERT INTO legal_synonyms (term, synonyms) VALUES
        ('IPC', ARRAY['Indian Penal Code', 'BNS', 'Bharatiya Nyaya Sanhita']),
        ('BNS', ARRAY['Bharatiya Nyaya Sanhita', 'IPC', 'Indian Penal Code']),
        ('CrPC', ARRAY['Code of Criminal Procedure', 'Cr.P.C.', 'BNSS', 'Bharatiya Nagarik Suraksha Sanhita']),
        ('BNSS', ARRAY['Bharatiya Nagarik Suraksha Sanhita', 'CrPC', 'Code of Criminal Procedure']),
        ('CPC', ARRAY['Code of Civil Procedure', 'C.P.C.']),
        ('IEA', ARRAY['Indian Evidence Act', 'Evidence Act', 'BSA', 'Bharatiya Sakshya Adhiniyam']),
        ('BSA', ARRAY['Bharatiya Sakshya Adhiniyam', 'IEA', 'Indian Evidence Act']),
        ('SC', ARRAY['Supreme Court', 'Supreme Court of India']),
        ('HC', ARRAY['High Court']),
        ('AIR', ARRAY['All India Reporter']),
        ('SCC', ARRAY['Supreme Court Cases']),
        ('MANU', ARRAY['Manupatra']),
        ('NLT', ARRAY['National Lok Adalat', 'Lok Adalat']),
        ('NCLAT', ARRAY['National Company Law Appellate Tribunal']),
        ('NCLT', ARRAY['National Company Law Tribunal']),
        ('DRT', ARRAY['Debt Recovery Tribunal']),
        ('SAT', ARRAY['Securities Appellate Tribunal']),
        ('ITAT', ARRAY['Income Tax Appellate Tribunal']),
        ('CESTAT', ARRAY['Customs Excise and Service Tax Appellate Tribunal']),
        ('CAT', ARRAY['Central Administrative Tribunal']),
        ('NGT', ARRAY['National Green Tribunal']),
        ('RERA', ARRAY['Real Estate Regulatory Authority', 'Real Estate (Regulation and Development) Act']),
        ('POCSO', ARRAY['Protection of Children from Sexual Offences Act']),
        ('PMLA', ARRAY['Prevention of Money Laundering Act']),
        ('NDPS', ARRAY['Narcotic Drugs and Psychotropic Substances Act']),
        ('NIA', ARRAY['National Investigation Agency Act']),
        ('RTI', ARRAY['Right to Information Act']),
        ('PIL', ARRAY['Public Interest Litigation']),
        ('FIR', ARRAY['First Information Report']),
        ('SLP', ARRAY['Special Leave Petition'])
        ON CONFLICT (term) DO NOTHING
    """)


def downgrade() -> None:
    # D8: Drop synonyms table
    op.execute("DROP TABLE IF EXISTS legal_synonyms")

    # D4: Drop cited_by_count
    op.execute("DROP INDEX IF EXISTS idx_cases_cited_by_count")
    op.drop_column("cases", "cited_by_count")

    # D2: Drop case_sections FTS
    op.execute("DROP TRIGGER IF EXISTS case_sections_searchable_trigger ON case_sections")
    op.execute("DROP FUNCTION IF EXISTS case_sections_searchable_update()")
    op.execute("DROP INDEX IF EXISTS idx_case_sections_fts")
    op.execute("ALTER TABLE case_sections DROP COLUMN IF EXISTS searchable_content")
