# Known Issues & TODOs — Smriti

## TODOs in Source Code

| File | Line | Description |
|------|------|-------------|
| `backend/scripts/ingest_s3.py` | 1114 | `TODO: implement per-stage retry (requires stage-specific processing functions)` |
| `backend/app/core/graph/traversal.py` | 203 | `TODO: Enrich Case nodes with is_overruled during ingestion based on treatment relationships` |

## Configuration Discrepancies

1. **Model name mismatch**: `.env.example` says `gemini-3.1-pro-preview` / `gemini-3-flash-preview`, but `config.py` defaults to `gemini-2.5-pro` / `gemini-2.5-flash`. Clarify which models are currently in use.

2. **JWT expiry mismatch**: `.env.example` has `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15`, but `config.py` defaults to `60`. The `.env.example` value appears stale.

3. **Database pool size mismatch**: `.env.example` says `DATABASE_POOL_SIZE=10`, but `config.py` defaults to `30`.

4. **Redis password inconsistency**: `docker-compose.yml` sets Redis password to `dev_password`, but default `REDIS_URL` in `.env.example` has no password. Connection will fail unless manually corrected.

## Security Concerns

1. **CRITICAL: `ingestion/accounts/env_template` contains real production credentials** — database URLs, Pinecone API keys, and Neo4j passwords are hardcoded in a tracked file. **All exposed credentials must be rotated immediately.** The file should contain only placeholder values.

2. **In-memory rate limiter is per-instance only** — under Cloud Run auto-scaling, rate limits are not shared across instances. A user could bypass limits by hitting different instances. Consider a shared Redis-only approach for production.

3. **Prompt injection detection covers common patterns** but may need updates for new LLM-specific attack vectors as models evolve.

## Technical Debt

1. **No deployment step in CI** — The GitHub Actions pipeline only runs lint, audit, test, and build. There is no automated deployment to Cloud Run. Deployment is currently manual.

2. **No integration tests in CI** — Only unit tests run in CI. Integration tests exist but require running infrastructure (Docker services).

3. **Celery worker defined but underutilized** — `backend/app/worker.py` defines a Celery application, but most background work is done via `asyncio.create_task()` or FastAPI `BackgroundTasks`. The Celery infrastructure may be vestigial.

4. **`smriti-storybook/` is standalone** — Not integrated into CI or the main build. It's an experimental onboarding tool with 3D visualizations.

5. **No Docker build/push in CI** — Docker images are not built or pushed in CI. This needs to be added for automated deployments.

## Data Scale Limitations

1. **~35K cases ingested** vs competitors with millions — data scale is the biggest competitive gap.

2. **Pinecone free tier** limits vector count — plan to upgrade to Starter tier at 100K vectors.

3. **Neo4j AuraDB free tier** has storage limits — may need paid tier as citation graph grows.

## Missing Features (Identified from Code)

1. **Hindi support** — `next-intl` is configured but Hindi translations appear incomplete.

2. **Audio digest** — TTS infrastructure exists (Sarvam AI) but may not be fully wired up (falls back to MockTTS in dev).

3. **Document analysis** — `document_analyzer.py` and `precedent_mapper.py` exist but their integration level is unclear.

## Items Needing Clarification

These could not be fully determined from code alone:

1. **Production deployment process** — How are Docker images built and pushed to Cloud Run? Is there a deployment script?

2. **Data backup strategy** — How are PostgreSQL, Pinecone, and Neo4j data backed up?

3. **Monitoring/alerting** — Sentry is configured for error tracking. Is there any alerting (PagerDuty, etc.) set up?

4. **Domain status** — Is `smriti.legal` live? What's the current production state?

5. **API rate limits for external services** — What are the actual rate limits for Gemini, Pinecone, Cohere on the current plan tiers?
