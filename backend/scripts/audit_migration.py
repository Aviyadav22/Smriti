"""Deep audit: compare Supabase and VPS PostgreSQL databases."""

import asyncio
import os
import json
import hashlib
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
    print("=" * 80)
    print("AUDIT 1: TABLE COMPARISON")
    print("=" * 80)

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
            print(f"  {tbl}: SUPABASE ONLY")
        else:
            print(f"  {tbl}: VPS ONLY")
    print(f"Total: Supabase={len(src_tables)}, VPS={len(dst_tables)}")

    common_tables = [t for t in all_tables if t in src_tables and t in dst_tables]

    # ──────────────────────────────────────────────────
    # AUDIT 2: COLUMN-BY-COLUMN COMPARISON
    # ──────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("AUDIT 2: COLUMN-BY-COLUMN COMPARISON (every table)")
    print("=" * 80)

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
            print(f"  {tbl}:")
            for i in issues:
                print(i)
                col_mismatches += 1

    if col_mismatches == 0:
        print("  All columns match perfectly!")
    else:
        print(f"\n  Total column mismatches: {col_mismatches}")

    # ──────────────────────────────────────────────────
    # AUDIT 3: ROW COUNTS
    # ──────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("AUDIT 3: ROW COUNTS")
    print("=" * 80)

    for tbl in common_tables:
        src_count = await src.fetchval(f"SELECT COUNT(*) FROM {tbl}")
        dst_count = await dst.fetchval(f"SELECT COUNT(*) FROM {tbl}")
        if src_count == dst_count:
            match = "OK"
        else:
            match = f"MISMATCH (diff={dst_count - src_count})"
        print(f"  {tbl:<35} Supabase={src_count:<8} VPS={dst_count:<8} {match}")

    # ──────────────────────────────────────────────────
    # AUDIT 4: INDEX COMPARISON
    # ──────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("AUDIT 4: INDEX COMPARISON")
    print("=" * 80)

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
        print(f"  Missing on VPS ({len(missing_on_vps)}):")
        for idx in sorted(missing_on_vps):
            print(f"    {idx}: {src_idx_map[idx][:100]}")
    if extra_on_vps:
        print(f"  Extra on VPS ({len(extra_on_vps)}):")
        for idx in sorted(extra_on_vps):
            print(f"    {idx}: {dst_idx_map[idx][:100]}")

    # Check if common indexes have same definition
    idx_diffs = 0
    for idx in sorted(common_idx):
        s_def = src_idx_map[idx]
        d_def = dst_idx_map[idx]
        if s_def != d_def:
            print(f"  INDEX DEF DIFF: {idx}")
            print(f"    Supabase: {s_def[:120]}")
            print(f"    VPS:      {d_def[:120]}")
            idx_diffs += 1

    if not missing_on_vps and not extra_on_vps and idx_diffs == 0:
        print("  All indexes match!")
    else:
        print(
            f"\n  Missing: {len(missing_on_vps)}, Extra: {len(extra_on_vps)}, Diffs: {idx_diffs}"
        )

    # ──────────────────────────────────────────────────
    # AUDIT 5: CONSTRAINT COMPARISON
    # ──────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("AUDIT 5: CONSTRAINTS (PK, FK, UNIQUE, CHECK)")
    print("=" * 80)

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
    extra_constraints = set(dst_c.keys()) - set(dst_c.keys())

    if missing_constraints:
        print(f"  Missing on VPS ({len(missing_constraints)}):")
        for key in sorted(missing_constraints):
            c = src_c[key]
            print(f"    {key[0]}.{key[1]} ({c['type']}): {c['columns']}")
    else:
        print("  All constraints present on VPS!")

    # ──────────────────────────────────────────────────
    # AUDIT 6: TRIGGER COMPARISON
    # ──────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("AUDIT 6: TRIGGERS")
    print("=" * 80)

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
        print(f"  Missing on VPS ({len(missing_trigs)}):")
        for t in sorted(missing_trigs):
            print(f"    {t[1]}.{t[0]} ({t[2]})")
    if extra_trigs:
        print(f"  Extra on VPS ({len(extra_trigs)}):")
        for t in sorted(extra_trigs):
            print(f"    {t[1]}.{t[0]} ({t[2]})")
    if not missing_trigs and not extra_trigs:
        print("  All triggers match!")

    # ──────────────────────────────────────────────────
    # AUDIT 7: ROW-LEVEL DATA INTEGRITY (checksums)
    # ──────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("AUDIT 7: ROW-LEVEL DATA CHECKSUMS")
    print("=" * 80)

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
                print(
                    f"  {tbl}: ROW COUNT MISMATCH src={len(src_rows)} dst={len(dst_rows)}"
                )
                # Show which rows are extra/missing
                src_ids = set(r[pk] for r in src_rows)
                dst_ids = set(r[pk] for r in dst_rows)
                extra = dst_ids - src_ids
                missing = src_ids - dst_ids
                if extra:
                    print(f"    Extra on VPS: {len(extra)} rows")
                    # Show first 5
                    for eid in sorted(list(extra))[:5]:
                        row = [r for r in dst_rows if r[pk] == eid][0]
                        # Print identifying info
                        info = dict(row)
                        # Only show first few fields
                        short = {k: str(v)[:60] for k, v in list(info.items())[:4]}
                        print(f"      {eid}: {short}")
                if missing:
                    print(f"    Missing on VPS: {len(missing)} rows")
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
                        row_id = src_rows[i][pk]
                        # Find differing columns
                        for col in common:
                            sv = src_rows[i][col]
                            dv = dst_rows[i][col]
                            if str(sv) != str(dv):
                                print(
                                    f"  {tbl} row {row_id}: col '{col}' differs"
                                )
                                print(f"    Supabase: {str(sv)[:80]}")
                                print(f"    VPS:      {str(dv)[:80]}")

            if mismatched_rows == 0:
                print(f"  {tbl}: {len(src_rows)} rows - ALL MATCH")
            else:
                print(
                    f"  {tbl}: {mismatched_rows}/{len(src_rows)} rows DIFFER"
                )

        except Exception as e:
            print(f"  {tbl}: ERROR - {e}")

    # ──────────────────────────────────────────────────
    # AUDIT 8: EXTENSIONS
    # ──────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("AUDIT 8: EXTENSIONS")
    print("=" * 80)

    src_exts = sorted(
        r["extname"]
        for r in await src.fetch("SELECT extname FROM pg_extension")
    )
    dst_exts = sorted(
        r["extname"]
        for r in await dst.fetch("SELECT extname FROM pg_extension")
    )

    print(f"  Supabase: {src_exts}")
    print(f"  VPS:      {dst_exts}")

    required = {"uuid-ossp", "pgcrypto", "pg_trgm", "vector"}
    missing_ext = required - set(dst_exts)
    if missing_ext:
        print(f"  MISSING REQUIRED: {missing_ext}")
    else:
        print("  All required extensions present!")

    await src.close()
    await dst.close()


if __name__ == "__main__":
    asyncio.run(audit())
