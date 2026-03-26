# Gemini Embedding 2 Upgrade — Tracker

> **Plan**: `docs/plans/2026-03-23-gemini-embedding-2-upgrade-plan.md`
> **Design**: `docs/plans/2026-03-23-gemini-embedding-2-upgrade-design.md`

## Progress

| Step | Description | Status | Notes |
|------|------------|--------|-------|
| 1 | EmbeddingProvider interface + task_type | DONE | Optional kwarg, backward compatible |
| 2 | GeminiEmbedder + task_type | DONE | Passes task_type to EmbedContentConfig |
| 3 | Config model name | DONE | gemini-embedding-2-preview in config.py + .env |
| 4 | Pipeline task_type (ingestion) | DONE | _embed_chunks, RAPTOR, proposition vectors |
| 5 | Search task_type (14 call sites) | DONE | All 14 sites + ingest_statutes.py, 1 mock fix |
| 6 | Dense chunk constants | DONE | 1200→1800, 300→400 |
| 7 | Section-level vectors | DONE | _upsert_section_vectors + chunker constants |
| 8 | Tests | DONE | +13 new tests (2172→2185), chunker + provider + task_type + section vector tests |
| 9 | Final verification | DONE | All imports OK, no bare embed calls, 2185 passing |

## Test Baseline

- Backend: 2172 passing (before) → 2185 passing (after)
- Frontend: not touched (no frontend changes in this plan)
