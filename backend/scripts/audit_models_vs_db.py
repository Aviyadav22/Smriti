"""Audit SQLAlchemy models against the live VPS PostgreSQL database.

Compares every table defined in models against the actual DB schema:
- Column names (missing/extra)
- Column types
- Nullable settings
- Primary keys
- Foreign keys
- Unique constraints
- Indexes
"""

import os
import sys

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, inspect

from app.models import Base  # triggers all model imports

DB_URL = os.environ["DATABASE_URL"]


def normalize_type(sa_type_str: str) -> str:
    """Normalize SQLAlchemy type string for comparison."""
    s = sa_type_str.upper()
    # Normalize common equivalences
    mapping = {
        "BIGINT": "BIGINT",
        "BIGSERIAL": "BIGINT",
        "INTEGER": "INTEGER",
        "INT": "INTEGER",
        "SMALLINT": "SMALLINT",
        "BOOLEAN": "BOOLEAN",
        "BOOL": "BOOLEAN",
        "DOUBLE PRECISION": "DOUBLE PRECISION",
        "DOUBLE_PRECISION": "DOUBLE PRECISION",
        "FLOAT": "DOUBLE PRECISION",
        "REAL": "REAL",
        "DATE": "DATE",
        "TEXT": "TEXT",
        "JSONB": "JSONB",
        "JSON": "JSON",
        "TSVECTOR": "TSVECTOR",
        "UUID": "UUID",
    }
    # Direct match
    if s in mapping:
        return mapping[s]
    # VARCHAR(N) -> VARCHAR(N)
    if s.startswith("VARCHAR"):
        return s
    # TIMESTAMP WITH TIME ZONE variants
    if "TIMESTAMP" in s and "TIME ZONE" in s:
        return "TIMESTAMP WITH TIME ZONE"
    if s == "TIMESTAMP WITHOUT TIME ZONE":
        return "TIMESTAMP WITHOUT TIME ZONE"
    # ARRAY types
    if "[]" in s or "ARRAY" in s:
        return "ARRAY"
    return s


def get_sa_type_name(col) -> str:
    """Get a normalized type name from a SQLAlchemy column type."""
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID

    col_type = col.type

    # Check specific PostgreSQL types
    if isinstance(col_type, TSVECTOR):
        return "TSVECTOR"
    if isinstance(col_type, JSONB):
        return "JSONB"
    if isinstance(col_type, PG_UUID):
        return "UUID"
    if isinstance(col_type, ARRAY):
        return "ARRAY"

    # Standard types
    type_name = type(col_type).__name__.upper()

    if type_name == "STRING":
        if col_type.length:
            return f"VARCHAR({col_type.length})"
        return "VARCHAR"
    if type_name == "TEXT":
        return "TEXT"
    if type_name == "INTEGER":
        return "INTEGER"
    if type_name == "BIGINTEGER":
        return "BIGINT"
    if type_name == "BOOLEAN":
        return "BOOLEAN"
    if type_name == "FLOAT":
        return "DOUBLE PRECISION"
    if type_name == "DATE":
        return "DATE"
    if type_name == "DATETIME":
        if getattr(col_type, "timezone", False):
            return "TIMESTAMP WITH TIME ZONE"
        return "TIMESTAMP WITHOUT TIME ZONE"

    return type_name


def compare_types(model_type: str, db_type: str) -> bool:
    """Compare a model type with a DB type, allowing known equivalences."""
    mt = model_type.upper().strip()
    dt = db_type.upper().strip()

    if mt == dt:
        return True

    # VARCHAR without length matches any VARCHAR
    if mt == "VARCHAR" and dt.startswith("VARCHAR"):
        return True
    if dt == "CHARACTER VARYING" and mt.startswith("VARCHAR"):
        return True
    if dt.startswith("CHARACTER VARYING") and mt.startswith("VARCHAR"):
        # Compare lengths if both have them
        import re

        m_len = re.search(r"\((\d+)\)", mt)
        d_len = re.search(r"\((\d+)\)", dt)
        if m_len and d_len:
            return m_len.group(1) == d_len.group(1)
        return True  # one has length, other doesn't — close enough

    # TIMESTAMP equivalences
    if "TIMESTAMP" in mt and "TIMESTAMP" in dt:
        mt_tz = "WITH TIME ZONE" in mt
        dt_tz = "WITH TIME ZONE" in dt
        return mt_tz == dt_tz

    # ARRAY types
    if mt == "ARRAY" and "[]" in dt:
        return True
    if "[]" in mt and "ARRAY" in dt:
        return True
    if mt == "ARRAY" and dt == "ARRAY":
        return True

    # DOUBLE PRECISION / FLOAT
    if mt == "DOUBLE PRECISION" and dt == "DOUBLE PRECISION":
        return True

    # BIGINT / BIGSERIAL
    return bool(mt == "BIGINT" and dt in ("BIGINT", "BIGSERIAL"))


def get_db_type_name(db_type_obj) -> str:
    """Get a normalized type name from a DB column type object (from inspector)."""
    from sqlalchemy import types as sa_types
    from sqlalchemy.dialects.postgresql import (
        ARRAY as PG_ARRAY,
    )
    from sqlalchemy.dialects.postgresql import (
        JSONB as PG_JSONB,
    )
    from sqlalchemy.dialects.postgresql import (
        TSVECTOR as PG_TSVECTOR,
    )
    from sqlalchemy.dialects.postgresql import (
        UUID as PG_UUID,
    )

    # Check for TIMESTAMP with timezone attribute
    if isinstance(db_type_obj, sa_types.TIMESTAMP | sa_types.DateTime):
        if getattr(db_type_obj, "timezone", False):
            return "TIMESTAMP WITH TIME ZONE"
        return "TIMESTAMP WITHOUT TIME ZONE"

    if isinstance(db_type_obj, PG_TSVECTOR):
        return "TSVECTOR"
    if isinstance(db_type_obj, PG_JSONB):
        return "JSONB"
    if isinstance(db_type_obj, PG_UUID):
        return "UUID"
    if isinstance(db_type_obj, PG_ARRAY):
        return "ARRAY"

    if isinstance(db_type_obj, sa_types.Boolean):
        return "BOOLEAN"
    if isinstance(db_type_obj, sa_types.BigInteger):
        return "BIGINT"
    if isinstance(db_type_obj, sa_types.Integer):
        return "INTEGER"
    if isinstance(db_type_obj, sa_types.Float):
        return "DOUBLE PRECISION"
    if isinstance(db_type_obj, sa_types.Date):
        return "DATE"
    if isinstance(db_type_obj, sa_types.Text):
        return "TEXT"
    if isinstance(db_type_obj, sa_types.String | sa_types.VARCHAR):
        length = getattr(db_type_obj, "length", None)
        if length:
            return f"VARCHAR({length})"
        return "VARCHAR"

    return str(db_type_obj).upper()


def audit_table(inspector, table_name: str, model_table) -> list[str]:
    """Audit a single table. Returns list of issues (empty = PASS)."""
    issues = []

    # Check if table exists in DB
    db_tables = inspector.get_table_names()
    if table_name not in db_tables:
        return [f"TABLE MISSING: '{table_name}' does not exist in database"]

    # --- Columns ---
    db_columns = {c["name"]: c for c in inspector.get_columns(table_name)}
    model_columns = {c.name: c for c in model_table.columns}

    model_col_names = set(model_columns.keys())
    db_col_names = set(db_columns.keys())

    missing_in_db = model_col_names - db_col_names
    extra_in_db = db_col_names - model_col_names

    for col_name in sorted(missing_in_db):
        issues.append(f"  MISSING COLUMN in DB: '{col_name}'")

    for col_name in sorted(extra_in_db):
        issues.append(f"  EXTRA COLUMN in DB (not in model): '{col_name}'")

    # Compare common columns
    common_cols = model_col_names & db_col_names
    for col_name in sorted(common_cols):
        model_col = model_columns[col_name]
        db_col = db_columns[col_name]

        # Type comparison
        model_type = get_sa_type_name(model_col)
        db_type_obj = db_col["type"]
        db_type = get_db_type_name(db_type_obj)

        if not compare_types(model_type, db_type):
            issues.append(f"  TYPE MISMATCH '{col_name}': model={model_type}, db={db_type}")

        # Nullable
        model_nullable = model_col.nullable if model_col.nullable is not None else True
        db_nullable = db_col.get("nullable", True)
        # Primary keys are never nullable
        if model_col.primary_key:
            model_nullable = False
        if model_nullable != db_nullable:
            issues.append(
                f"  NULLABLE MISMATCH '{col_name}': model={model_nullable}, db={db_nullable}"
            )

    # --- Primary Keys ---
    db_pk = inspector.get_pk_constraint(table_name)
    db_pk_cols = set(db_pk.get("constrained_columns", []))
    model_pk_cols = {c.name for c in model_table.primary_key.columns}

    if model_pk_cols != db_pk_cols:
        issues.append(f"  PK MISMATCH: model={sorted(model_pk_cols)}, db={sorted(db_pk_cols)}")

    # --- Foreign Keys ---
    db_fks = inspector.get_foreign_keys(table_name)
    db_fk_set = set()
    for fk in db_fks:
        for cc, rc in zip(fk["constrained_columns"], fk["referred_columns"], strict=False):
            db_fk_set.add((cc, fk["referred_table"], rc))

    model_fk_set = set()
    for fk in model_table.foreign_keys:
        model_fk_set.add((fk.parent.name, fk.column.table.name, fk.column.name))

    missing_fks = model_fk_set - db_fk_set
    extra_fks = db_fk_set - model_fk_set

    for fk in sorted(missing_fks):
        issues.append(f"  MISSING FK in DB: {fk[0]} -> {fk[1]}.{fk[2]}")
    for fk in sorted(extra_fks):
        issues.append(f"  EXTRA FK in DB: {fk[0]} -> {fk[1]}.{fk[2]}")

    # --- Unique Constraints ---
    db_uniques = inspector.get_unique_constraints(table_name)
    db_unique_col_sets = set()
    for uc in db_uniques:
        db_unique_col_sets.add(frozenset(uc["column_names"]))

    # Also check unique indexes (PG often implements unique constraints as unique indexes)
    db_indexes = inspector.get_indexes(table_name)
    for idx in db_indexes:
        if idx.get("unique", False):
            db_unique_col_sets.add(frozenset(idx["column_names"]))

    model_unique_col_sets = set()
    for constraint in model_table.constraints:
        from sqlalchemy import UniqueConstraint

        if isinstance(constraint, UniqueConstraint):
            cols = frozenset(c.name for c in constraint.columns)
            if cols:  # skip empty
                model_unique_col_sets.add(cols)

    # Also check column-level unique=True
    for col in model_table.columns:
        if col.unique:
            model_unique_col_sets.add(frozenset([col.name]))

    # Check model unique indexes defined in __table_args__
    for idx in model_table.indexes:
        if idx.unique:
            cols = frozenset(c.name for c in idx.columns if hasattr(c, "name"))
            if cols:
                model_unique_col_sets.add(cols)

    missing_uniques = model_unique_col_sets - db_unique_col_sets
    for uc in sorted(missing_uniques, key=lambda x: sorted(x)):
        issues.append(f"  MISSING UNIQUE CONSTRAINT in DB: {sorted(uc)}")

    # --- Indexes ---
    db_index_col_sets = {}
    for idx in db_indexes:
        col_names = tuple(sorted(idx["column_names"])) if idx["column_names"] else ()
        if col_names:
            db_index_col_sets[col_names] = idx

    model_index_info = []
    for idx in model_table.indexes:
        col_names = []
        for expr in idx.expressions:
            if hasattr(expr, "name"):
                col_names.append(expr.name)
            elif hasattr(expr, "element") and hasattr(expr.element, "name"):
                col_names.append(expr.element.name)
        if col_names:
            model_index_info.append((idx.name, tuple(sorted(col_names))))

    missing_indexes = []
    for idx_name, col_tuple in model_index_info:
        if col_tuple not in db_index_col_sets:
            missing_indexes.append((idx_name, col_tuple))

    for idx_name, cols in missing_indexes:
        issues.append(f"  MISSING INDEX in DB: {idx_name} on {list(cols)}")

    return issues


def main() -> None:
    engine = create_engine(DB_URL)
    inspector = inspect(engine)

    db_tables = set(inspector.get_table_names())

    model_tables = Base.metadata.tables

    overall_pass = True
    results = {}

    for table_name in sorted(model_tables.keys()):
        model_table = model_tables[table_name]
        issues = audit_table(inspector, table_name, model_table)
        results[table_name] = issues

        if issues:
            overall_pass = False
            for _issue in issues:
                pass
        else:
            pass

    # Check for DB tables not in models (informational)
    model_table_names = set(model_tables.keys())
    extra_db_tables = db_tables - model_table_names
    # Filter out alembic and internal tables
    extra_db_tables = {
        t for t in extra_db_tables if not t.startswith("alembic") and not t.startswith("_")
    }
    if extra_db_tables:
        for _t in sorted(extra_db_tables):
            pass

    if overall_pass:
        pass
    else:
        sum(1 for v in results.values() if v)
        len(results)

    engine.dispose()


if __name__ == "__main__":
    main()
