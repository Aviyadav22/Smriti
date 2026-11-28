#!/usr/bin/env python3
"""Download Supreme Court judgment PDFs into local storage.

Ingestion recorded each case's pdf_storage_path on the machine it ran on, so
those files never reached the server. Every case also has s3_source_path, the
file stem in the public AWS Open Data bucket "indian-supreme-court-judgments"
(CC-BY 4.0). This fetches each PDF from there to the storage key the PDF
endpoint falls back to (see sc_pdf_key in app/api/routes/cases.py).

Skips files already present, so it can be re-run safely.

Usage (inside the backend container, scripts mounted):
    python scripts/fetch_sc_pdfs.py                 # all cases
    python scripts/fetch_sc_pdfs.py --limit 20      # try a few first
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
import httpx

from app.api.routes.cases import sc_pdf_key
from app.core.config import settings

BUCKET = "https://indian-supreme-court-judgments.s3.amazonaws.com"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fetch_sc_pdfs")


async def main(limit: int | None, concurrency: int) -> None:
    conn = await asyncpg.connect(settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))
    rows = await conn.fetch(
        "SELECT id::text, s3_source_path FROM cases WHERE s3_source_path IS NOT NULL ORDER BY year DESC"
    )
    await conn.close()
    base = Path(settings.local_storage_path)
    todo = []
    for r in rows:
        key = sc_pdf_key(r["s3_source_path"])
        if key and not (base / key).exists():
            todo.append((r["s3_source_path"], base / key))
    if limit:
        todo = todo[:limit]
    logger.info("%d cases with a source path; %d PDFs to fetch", len(rows), len(todo))

    sem = asyncio.Semaphore(concurrency)
    done = failed = 0

    async def fetch(client: httpx.AsyncClient, stem: str, dest: Path) -> None:
        nonlocal done, failed
        url = f"{BUCKET}/data/pdf/year={stem[:4]}/english/{stem}_EN.pdf"
        async with sem:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                if not resp.content.startswith(b"%PDF"):
                    raise ValueError("not a PDF")
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(".part")
                tmp.write_bytes(resp.content)
                tmp.rename(dest)
                done += 1
            except Exception as exc:
                failed += 1
                logger.warning("Failed %s: %s", stem, exc)
        if (done + failed) % 200 == 0:
            logger.info("Progress: %d fetched, %d failed of %d", done, failed, len(todo))

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        await asyncio.gather(*(fetch(client, s, d) for s, d in todo))
    logger.info("COMPLETE: %d fetched, %d failed", done, failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.concurrency))
