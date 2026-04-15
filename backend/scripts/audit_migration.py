"""Deep audit: compare Supabase and VPS PostgreSQL databases."""

import asyncio
import hashlib
import os

from dotenv import load_dotenv

load_dotenv(".env")

SUPABASE_URL = os.environ["SUPABASE_DATABASE_URL"]
VPS_URL = os.environ["VPS_DATABASE_URL"]


async def audit():
    import asyncpg

    src = await asyncpg.connect(SUPABASE_URL, statement_cache_size=0)
    dst = await asyncpg.connect(VPS_URL)

    # ──────────────────────────────────────────────────
    # AUDIT 1: TABLE COMPARISON
    # ──────────────────────────────────────────────────

    src_tables = sorted(
        r["tablename"]
        for r in await src.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )
    )
    dst_tables = sorted(
        r["tablename"]
        for r in await dst.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )
    )

    all_tables = sorted(set(src_tables + dst_tables))
    for tbl in all_tables:
        in_src = tbl in src_tables
        in_dst = tbl in dst_tables
        if in_src and in_dst:
            pass  # both have it
        elif in_src:
            pass
        else:
            pass

    common_tables = [t for t in all_tables if t in src_tables and t in dst_tables]

    # ──────────────────────────────────────────────────
    # AUDIT 2: COLUMN-BY-COLUMN COMPARISON
    # ──────────────────────────────────────────────────

    col_mismatches = 0

    for tbl in common_tables:
        src_cols = await src.fetch(
            """
            SELECT column_name, data_type, udt_name, is_nullable, column_default,
                   character_maximum_length, numeric_precision
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=$1
            ORDER BY ordinal_position
        """,
            tbl,
        )

        dst_cols = await dst.fetch(
            """
            SELECT column_name, data_type, udt_name, is_nullable, column_default,
                   character_maximum_length, numeric_precision
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=$1
            ORDER BY ordinal_position
        """,
            tbl,
        )

        src_col_map = {c["column_name"]: c for c in src_cols}
        dst_col_map = {c["column_name"]: c for c in dst_cols}

        all_cols = sorted(set(list(src_col_map.keys()) + list(dst_col_map.keys())))
        issues = []

        for col in all_cols:
            if col not in src_col_map:
                issues.append(f"    {col}: VPS ONLY (extra column)")
            elif col not in dst_col_map:
                issues.append(f"    {col}: SUPABASE ONLY (missing on VPS)")
            else:
                s = src_col_map[col]
                d = dst_col_map[col]
                diffs = []
                if s["udt_name"] != d["udt_name"]:
                    diffs.append(f"type: {s['udt_name']} vs {d['udt_name']}")
                if s["is_nullable"] != d["is_nullable"]:
                    diffs.append(f"nullable: {s['is_nullable']} vs {d['is_nullable']}")
                # Normalize defaults
                s_def = str(s["column_default"] or "").replace("::regclass", "")
                d_def = str(d["column_default"] or "").replace("::regclass", "")
                # Skip sequence naming differences
                if "nextval" in s_def and "nextval" in d_def:
                    pass  # Both use sequences, names may differ
                elif s_def != d_def:
                    diffs.append(f"default: [{s_def[:60]}] vs [{d_def[:60]}]")
                if diffs:
                    issues.append(f"    {col}: {' | '.join(diffs)}")

        if issues:
            for i in issues:
                col_mismatches += 1

    if col_mismatches == 0:
        pass
    else:
        pass

    # ──────────────────────────────────────────────────
    # AUDIT 3: ROW COUNTS
    # ──────────────────────────────────────────────────

    for tbl in common_tables:
        src_count = await src.fetchval(f"SELECT COUNT(*) FROM {tbl}")
        dst_count = await dst.fetchval(f"SELECT COUNT(*) FROM {tbl}")
        "OK" if src_count == dst_count else f"MISMATCH (diff={dst_count - src_count})"

    # ──────────────────────────────────────────────────
    # AUDIT 4: INDEX COMPARISON
    # ──────────────────────────────────────────────────

    src_idx = await src.fetch(
        "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexname"
    )
    dst_idx = await dst.fetch(
        "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexname"
    )

    src_idx_map = {r["indexname"]: r["indexdef"] for r in src_idx}
    dst_idx_map = {r["indexname"]: r["indexdef"] for r in dst_idx}

    missing_on_vps = set(src_idx_map.keys()) - set(dst_idx_map.keys())
    extra_on_vps = set(dst_idx_map.keys()) - set(src_idx_map.keys())
    common_idx = set(src_idx_map.keys()) & set(dst_idx_map.keys())

    if missing_on_vps:
        for idx in sorted(missing_on_vps):
            pass
    if extra_on_vps:
        for idx in sorted(extra_on_vps):
            pass

    # Check if common indexes have same definition
    idx_diffs = 0
    for idx in sorted(common_idx):
        s_def = src_idx_map[idx]
        d_def = dst_idx_map[idx]
        if s_def != d_def:
            idx_diffs += 1

    if not missing_on_vps and not extra_on_vps and idx_diffs == 0:
        pass
    else:
        pass

    # ──────────────────────────────────────────────────
    # AUDIT 5: CONSTRAINT COMPARISON
    # ──────────────────────────────────────────────────

    constraint_query = """
        SELECT tc.table_name, tc.constraint_name, tc.constraint_type,
               kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
        ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position
    """

    src_constraints = await src.fetch(constraint_query)
    dst_constraints = await dst.fetch(constraint_query)

    # Group by constraint name
    def group_constraints(rows):
        result = {}
        for r in rows:
            key = (r["table_name"], r["constraint_name"])
            if key not in result:
                result[key] = {
                    "type": r["constraint_type"],
                    "columns": [],
                }
            result[key]["columns"].append(r["column_name"])
        return result

    src_c = group_constraints(src_constraints)
    dst_c = group_constraints(dst_constraints)

    missing_constraints = set(src_c.keys()) - set(dst_c.keys())
    set(dst_c.keys()) - set(dst_c.keys())

    if missing_constraints:
        for key in sorted(missing_constraints):
            c = src_c[key]
    else:
        pass

    # ──────────────────────────────────────────────────
    # AUDIT 6: TRIGGER COMPARISON
    # ──────────────────────────────────────────────────

    trigger_query = """
        SELECT trigger_name, event_object_table, event_manipulation, action_statement
        FROM information_schema.triggers
        WHERE trigger_schema = 'public'
        ORDER BY event_object_table, trigger_name
    """

    src_triggers = await src.fetch(trigger_query)
    dst_triggers = await dst.fetch(trigger_query)

    src_trig_set = set(
        (r["trigger_name"], r["event_object_table"], r["event_manipulation"])
        for r in src_triggers
    )
    dst_trig_set = set(
        (r["trigger_name"], r["event_object_table"], r["event_manipulation"])
        for r in dst_triggers
    )

    missing_trigs = src_trig_set - dst_trig_set
    extra_trigs = dst_trig_set - src_trig_set

    if missing_trigs:
        for _t in sorted(missing_trigs):
            pass
    if extra_trigs:
        for _t in sorted(extra_trigs):
            pass
    if not missing_trigs and not extra_trigs:
        pass

    # ──────────────────────────────────────────────────
    # AUDIT 7: ROW-LEVEL DATA INTEGRITY (checksums)
    # ──────────────────────────────────────────────────

    # For each table with data, compute MD5 of all rows sorted by PK
    tables_to_check = [
        ("cases", "id"),
        ("statutes", "id"),
        ("case_sections", "id"),
        ("case_citation_equivalents", "id"),
        ("legal_synonyms", "id"),
        ("users", "id"),
        ("agent_executions", "id"),
        ("audit_logs", "id"),
        ("consents", "id"),
    ]

    for tbl, pk in tables_to_check:
        try:
            # Get common columns (exclude generated tsvector columns which may differ)
            src_cols_raw = await src.fetch(
                """SELECT column_name, udt_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=$1
                   ORDER BY ordinal_position""",
                tbl,
            )
            dst_cols_raw = await dst.fetch(
                """SELECT column_name, udt_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=$1
                   ORDER BY ordinal_position""",
                tbl,
            )

            src_col_names = {c["column_name"] for c in src_cols_raw}
            dst_col_names = {c["column_name"] for c in dst_cols_raw}
            # Skip tsvector columns (generated, may differ) and created_at for legal_synonyms
            skip_cols = set()
            for c in src_cols_raw:
                if c["udt_name"] == "tsvector":
                    skip_cols.add(c["column_name"])

            common = sorted(
                (src_col_names & dst_col_names) - skip_cols
            )
            col_list = ", ".join(common)

            src_rows = await src.fetch(
                f"SELECT {col_list} FROM {tbl} ORDER BY {pk}"
            )
            dst_rows = await dst.fetch(
                f"SELECT {col_list} FROM {tbl} ORDER BY {pk}"
            )

            if len(src_rows) != len(dst_rows):
                # Show which rows are extra/missing
                src_ids = set(r[pk] for r in src_rows)
                dst_ids = set(r[pk] for r in dst_rows)
                extra = dst_ids - src_ids
                missing = src_ids - dst_ids
                if extra:
                    # Show first 5
                    for eid in sorted(list(extra))[:5]:
                        row = next(r for r in dst_rows if r[pk] == eid)
                        # Print identifying info
                        info = dict(row)
                        # Only show first few fields
                        {k: str(v)[:60] for k, v in list(info.items())[:4]}
                if missing:
                    pass
                continue

            # Compare row by row
            mismatched_rows = 0
            for i in range(len(src_rows)):
                src_hash = hashlib.md5(
                    str(dict(src_rows[i])).encode()
                ).hexdigest()
                dst_hash = hashlib.md5(
                    str(dict(dst_rows[i])).encode()
                ).hexdigest()
                if src_hash != dst_hash:
                    mismatched_rows += 1
                    if mismatched_rows <= 3:
                        src_rows[i][pk]
                        # Find differing columns
                        for col in common:
                            sv = src_rows[i][col]
                            dv = dst_rows[i][col]
                            if str(sv) != str(dv):
                                pass

            if mismatched_rows == 0:
                pass
            else:
                pass

        except Exception:
            pass

    # ──────────────────────────────────────────────────
    # AUDIT 8: EXTENSIONS
    # ──────────────────────────────────────────────────

    sorted(
        r["extname"]
        for r in await src.fetch("SELECT extname FROM pg_extension")
    )
    dst_exts = sorted(
        r["extname"]
        for r in await dst.fetch("SELECT extname FROM pg_extension")
    )


    required = {"uuid-ossp", "pgcrypto", "pg_trgm", "vector"}
    missing_ext = required - set(dst_exts)
    if missing_ext:
        pass
    else:
        pass

    await src.close()
    await dst.close()


if __name__ == "__main__":
    asyncio.run(audit())
