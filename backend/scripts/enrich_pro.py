"""Pass 2 enrichment: re-extract complex fields using Gemini Pro.

Usage:
    python scripts/enrich_pro.py --judge "D.Y. Chandrachud"
    python scripts/enrich_pro.py --section "302 IPC"
    python scripts/enrich_pro.py --case-type "Criminal Appeal"
    python scripts/enrich_pro.py --all --limit 100
    python scripts/enrich_pro.py --case-id <uuid>
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text as sa_text

from app.core.dependencies import get_llm
from app.core.legal.prompts import METADATA_OUTPUT_SCHEMA
from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)

# Only the 8 complex fields that benefit from Pro
PRO_FIELDS = [
    "arguments_raised",
    "citation_treatments",
    "judicial_tone",
    "legal_principles_applied",
    "procedural_history",
    "issue_classification",
    "fact_pattern_tags",
    "operative_order",
]

PRO_EXTRACTION_SYSTEM = """You are re-analyzing a previously processed Indian court judgment.
Focus ONLY on extracting these 8 fields with maximum accuracy:
1. arguments_raised — every distinct argument with accepted/rejected classification
2. citation_treatments — HOW each cited case was treated (followed/distinguished/overruled etc)
3. judicial_tone — overall tone classification
4. legal_principles_applied — named legal doctrines
5. procedural_history — chain of courts
6. issue_classification — hierarchical legal issue tags
7. fact_pattern_tags — factual pattern categories
8. operative_order — verbatim operative portion

Use the full judgment text provided. Be thorough and precise."""

# Build a reduced schema with only PRO_FIELDS
PRO_SCHEMA = {
    "type": "object",
    "properties": {
        k: v for k, v in METADATA_OUTPUT_SCHEMA["properties"].items() if k in PRO_FIELDS
    },
    "required": PRO_FIELDS,
}


async def enrich_case(full_text: str, llm) -> dict:
    """Re-extract 8 complex fields using Pro."""
    return await llm.generate_structured(
        prompt=full_text,
        system=PRO_EXTRACTION_SYSTEM,
        output_schema=PRO_SCHEMA,
        temperature=0.1,
    )


async def run(args):
    llm = get_llm()  # Gets the configured LLM (Pro in production)

    async with async_session_factory() as db:
        # Build filter query using parameterized conditions
        conditions = ["enrichment_status = 'flash_only'"]
        params: dict = {}

        if args.judge:
            conditions.append("EXISTS (SELECT 1 FROM unnest(judge) AS j WHERE j ILIKE :judge)")
            params["judge"] = f"%{args.judge}%"
        if args.section:
            conditions.append(
                "EXISTS (SELECT 1 FROM unnest(acts_cited) AS a WHERE a ILIKE :section)"
            )
            params["section"] = f"%{args.section}%"
        if args.case_type:
            conditions.append("case_type = :case_type")
            params["case_type"] = args.case_type
        if args.case_id:
            conditions.append("id = :case_id")
            params["case_id"] = args.case_id

        where = " AND ".join(conditions)
        limit = args.limit or 100

        result = await db.execute(
            sa_text(f"SELECT id, full_text FROM cases WHERE {where} LIMIT :limit"),
            {**params, "limit": limit},
        )
        rows = result.fetchall()
        logger.info("Found %d cases to enrich", len(rows))

        success = 0
        for row in rows:
            case_id, full_text = str(row[0]), row[1]
            if not full_text:
                logger.warning("Case %s has no full_text, skipping", case_id)
                continue

            try:
                enriched = await enrich_case(full_text, llm)

                # Build UPDATE SET clause for non-None fields
                updates = []
                update_params: dict = {"case_id": case_id}
                for field_name in PRO_FIELDS:
                    value = enriched.get(field_name)
                    if value is not None:
                        if isinstance(value, dict | list):
                            update_params[field_name] = json.dumps(value)
                        else:
                            update_params[field_name] = value
                        updates.append(f"{field_name} = :{field_name}")

                updates.append("enrichment_status = 'pro_enriched'")

                if updates:
                    await db.execute(
                        sa_text(f"UPDATE cases SET {', '.join(updates)} WHERE id = :case_id"),
                        update_params,
                    )
                    await db.commit()
                    success += 1
                    logger.info("Enriched case %s (%d/%d)", case_id, success, len(rows))

            except Exception as e:
                logger.error("Failed to enrich case %s: %s", case_id, e)
                await db.execute(
                    sa_text("UPDATE cases SET enrichment_status = 'failed' WHERE id = :case_id"),
                    {"case_id": case_id},
                )
                await db.commit()

        logger.info("Done: %d/%d cases enriched", success, len(rows))


def main():
    parser = argparse.ArgumentParser(description="Pass 2: Enrich cases with Gemini Pro")
    parser.add_argument("--judge", help="Filter by judge name (ILIKE)")
    parser.add_argument("--section", help="Filter by section/act in acts_cited (ILIKE)")
    parser.add_argument("--case-type", help="Filter by exact case_type")
    parser.add_argument("--case-id", help="Enrich a single case by UUID")
    parser.add_argument("--all", action="store_true", help="Enrich all flash_only cases")
    parser.add_argument(
        "--limit", type=int, default=100, help="Max cases to process (default: 100)"
    )
    args = parser.parse_args()

    if not (args.judge or args.section or args.case_type or args.case_id or args.all):
        parser.error(
            "Specify at least one filter: --judge, --section, --case-type, --case-id, or --all"
        )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
