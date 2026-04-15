"""Tests for migration 011 (legal completeness) and updated Case model columns."""

import importlib
from unittest.mock import MagicMock

import pytest

from app.models.case import Case


class TestCaseModelColumns:
    """Verify the Case model declares all expected columns."""

    def _columns(self):
        return {c.name for c in Case.__table__.columns}

    # --- Migration 009 columns (C17) ---
    def test_case_number_column_exists(self):
        assert "case_number" in self._columns()

    def test_is_reportable_column_exists(self):
        assert "is_reportable" in self._columns()

    def test_headnotes_column_exists(self):
        assert "headnotes" in self._columns()

    def test_outcome_summary_column_exists(self):
        assert "outcome_summary" in self._columns()

    def test_ingestion_status_column_exists(self):
        assert "ingestion_status" in self._columns()

    # --- C1: Coram size ---
    def test_coram_size_column_exists(self):
        assert "coram_size" in self._columns()

    def test_coram_size_is_integer(self):
        col = Case.__table__.c.coram_size
        assert str(col.type) == "INTEGER"

    def test_coram_size_nullable(self):
        col = Case.__table__.c.coram_size
        assert col.nullable is True

    # --- C2: Appellate chain ---
    def test_lower_court_column_exists(self):
        assert "lower_court" in self._columns()

    def test_lower_court_case_number_column_exists(self):
        assert "lower_court_case_number" in self._columns()

    def test_appeal_from_column_exists(self):
        assert "appeal_from" in self._columns()

    def test_appellate_columns_nullable(self):
        for col_name in ("lower_court", "lower_court_case_number", "appeal_from"):
            col = Case.__table__.c[col_name]
            assert col.nullable is True, f"{col_name} should be nullable"

    # --- C3: Opinion type and split tracking ---
    def test_opinion_type_column_exists(self):
        assert "opinion_type" in self._columns()

    def test_dissenting_judges_column_exists(self):
        assert "dissenting_judges" in self._columns()

    def test_concurring_judges_column_exists(self):
        assert "concurring_judges" in self._columns()

    def test_split_ratio_column_exists(self):
        assert "split_ratio" in self._columns()

    def test_dissenting_judges_is_array(self):
        col = Case.__table__.c.dissenting_judges
        assert "ARRAY" in str(col.type).upper() or "VARCHAR[]" in str(col.type).upper()

    def test_concurring_judges_is_array(self):
        col = Case.__table__.c.concurring_judges
        assert "ARRAY" in str(col.type).upper() or "VARCHAR[]" in str(col.type).upper()

    # --- C10: Party type classification ---
    def test_petitioner_type_column_exists(self):
        assert "petitioner_type" in self._columns()

    def test_respondent_type_column_exists(self):
        assert "respondent_type" in self._columns()

    def test_is_pil_column_exists(self):
        assert "is_pil" in self._columns()

    def test_is_pil_is_boolean(self):
        col = Case.__table__.c.is_pil
        assert "BOOLEAN" in str(col.type).upper()

    # --- C11: Companion cases ---
    def test_companion_cases_column_exists(self):
        assert "companion_cases" in self._columns()

    def test_companion_cases_is_array(self):
        col = Case.__table__.c.companion_cases
        assert "ARRAY" in str(col.type).upper() or "VARCHAR[]" in str(col.type).upper()


class TestCaseModelInstantiation:
    """Verify new columns can be set on Case instances."""

    def test_set_coram_size(self):
        case = Case(title="Test", court="Supreme Court", coram_size=5)
        assert case.coram_size == 5

    def test_set_opinion_type(self):
        case = Case(title="Test", court="Supreme Court", opinion_type="majority")
        assert case.opinion_type == "majority"

    def test_set_appellate_chain(self):
        case = Case(
            title="Test",
            court="Supreme Court",
            lower_court="High Court of Delhi",
            lower_court_case_number="WP(C) 123/2020",
            appeal_from="High Court of Delhi",
        )
        assert case.lower_court == "High Court of Delhi"
        assert case.lower_court_case_number == "WP(C) 123/2020"
        assert case.appeal_from == "High Court of Delhi"

    def test_set_split_tracking(self):
        case = Case(
            title="Test",
            court="Supreme Court",
            dissenting_judges=["Justice A"],
            concurring_judges=["Justice B", "Justice C"],
            split_ratio="3:2",
        )
        assert case.dissenting_judges == ["Justice A"]
        assert case.concurring_judges == ["Justice B", "Justice C"]
        assert case.split_ratio == "3:2"

    def test_set_party_types(self):
        case = Case(
            title="Test",
            court="Supreme Court",
            petitioner_type="individual",
            respondent_type="government_central",
            is_pil=True,
        )
        assert case.petitioner_type == "individual"
        assert case.respondent_type == "government_central"
        assert case.is_pil is True

    def test_set_companion_cases(self):
        case = Case(
            title="Test",
            court="Supreme Court",
            companion_cases=["SLP(C) 123/2020", "SLP(C) 456/2020"],
        )
        assert case.companion_cases == ["SLP(C) 123/2020", "SLP(C) 456/2020"]

    def test_set_migration_009_columns(self):
        case = Case(
            title="Test",
            court="Supreme Court",
            case_number="WP(C) 123/2020",
            is_reportable=True,
            headnotes="Key headnotes here",
            outcome_summary="Appeal allowed",
        )
        assert case.case_number == "WP(C) 123/2020"
        assert case.is_reportable is True
        assert case.headnotes == "Key headnotes here"
        assert case.outcome_summary == "Appeal allowed"

    def test_new_columns_default_to_none(self):
        case = Case(title="Test", court="Supreme Court")
        assert case.coram_size is None
        assert case.lower_court is None
        assert case.opinion_type is None
        assert case.petitioner_type is None
        assert case.is_pil is None
        assert case.companion_cases is None
        assert case.dissenting_judges is None


class TestMigration011Structure:
    """Verify migration 011 module has correct revision chain and operations."""

    @pytest.fixture(autouse=True)
    def _load_migration(self):
        self.migration = importlib.import_module(
            "migrations.versions.011_legal_completeness"
        )

    def test_revision_id(self):
        assert self.migration.revision == "011"

    def test_down_revision(self):
        assert self.migration.down_revision == "010"

    def test_has_upgrade_function(self):
        assert callable(self.migration.upgrade)

    def test_has_downgrade_function(self):
        assert callable(self.migration.downgrade)

    def test_upgrade_adds_all_columns(self):
        mock_op = MagicMock()
        self.migration.op = mock_op
        try:
            self.migration.upgrade()
        finally:
            # Restore real op module
            from alembic import op
            self.migration.op = op

        add_column_calls = mock_op.add_column.call_args_list
        column_names = [c.args[1].name for c in add_column_calls]

        expected = [
            "coram_size",
            "lower_court",
            "lower_court_case_number",
            "appeal_from",
            "opinion_type",
            "dissenting_judges",
            "concurring_judges",
            "split_ratio",
            "petitioner_type",
            "respondent_type",
            "is_pil",
            "companion_cases",
        ]
        for col in expected:
            assert col in column_names, f"Missing column: {col}"

    def test_upgrade_adds_check_constraints(self):
        mock_op = MagicMock()
        self.migration.op = mock_op
        try:
            self.migration.upgrade()
        finally:
            from alembic import op
            self.migration.op = op

        check_calls = mock_op.create_check_constraint.call_args_list
        constraint_names = [c.args[0] for c in check_calls]

        assert "ck_cases_opinion_type" in constraint_names
        assert "ck_cases_petitioner_type" in constraint_names
        assert "ck_cases_respondent_type" in constraint_names
        assert "ck_cases_coram_size" in constraint_names
        assert "ck_cases_disposal_nature" in constraint_names

    def test_upgrade_expands_disposal_nature(self):
        """C13: disposal_nature constraint should include new values."""
        mock_op = MagicMock()
        self.migration.op = mock_op
        try:
            self.migration.upgrade()
        finally:
            from alembic import op
            self.migration.op = op

        check_calls = mock_op.create_check_constraint.call_args_list
        disposal_call = next(
            c for c in check_calls if c.args[0] == "ck_cases_disposal_nature"
        )
        constraint_expr = disposal_call.args[2]

        assert "Referred to Larger Bench" in constraint_expr
        assert "Abated" in constraint_expr
        assert "Not Pressed" in constraint_expr

    def test_downgrade_drops_all_columns(self):
        mock_op = MagicMock()
        self.migration.op = mock_op
        try:
            self.migration.downgrade()
        finally:
            from alembic import op
            self.migration.op = op

        drop_column_calls = mock_op.drop_column.call_args_list
        dropped = [c.args[1] for c in drop_column_calls]

        expected = [
            "coram_size",
            "lower_court",
            "lower_court_case_number",
            "appeal_from",
            "opinion_type",
            "dissenting_judges",
            "concurring_judges",
            "split_ratio",
            "petitioner_type",
            "respondent_type",
            "is_pil",
            "companion_cases",
        ]
        for col in expected:
            assert col in dropped, f"Missing drop for column: {col}"

    def test_downgrade_restores_original_disposal_nature(self):
        """Downgrade should restore the migration 009 disposal_nature constraint."""
        mock_op = MagicMock()
        self.migration.op = mock_op
        try:
            self.migration.downgrade()
        finally:
            from alembic import op
            self.migration.op = op

        check_calls = mock_op.create_check_constraint.call_args_list
        disposal_call = next(
            c for c in check_calls if c.args[0] == "ck_cases_disposal_nature"
        )
        constraint_expr = disposal_call.args[2]

        # Original should NOT have the new values
        assert "Referred to Larger Bench" not in constraint_expr
        assert "Abated" not in constraint_expr
        assert "Not Pressed" not in constraint_expr
        # But should have original values
        assert "Allowed" in constraint_expr
        assert "Dismissed" in constraint_expr
