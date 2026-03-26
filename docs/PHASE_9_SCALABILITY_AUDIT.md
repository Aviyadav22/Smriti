# Phase 9: Production Scalability Audit & Hardening Plan

## Context
Before launching Smriti to real users, we need to understand: how many concurrent users can the current system handle, what are the bottlenecks, what will break first, and is this a good base to scale from?

**Answer: The architecture is solid (async FastAPI, provider pattern, proper separation). But configuration/deployment gaps will cause failures at ~10-20 concurrent users. These are fixable in 2-3 days — we're NOT building toward a dead end.**

---

## Current Capacity Estimate

| Scenario | Can Handle? | Bottleneck |
|----------|------------|------------|
| 1-2 users (demo) | Yes | None |
| 5-10 users | Mostly | Supabase free tier (3 connections), in-memory checkpointers |
| 20-50 users | No | DB connections exhaust, Redis free tier (10k cmds/day), agent resume breaks across instances |
| 100+ users | No | Everything below + thread pool exhaustion, no monitoring |
| 1000+ users | No | Pinecone free tier, Cloud Run scaling, no CDN |

---

## Findings by Severity

### CRITICAL (Blocks production launch)

#### C1. Secrets exposed in git history
- **File:** `backend/.env` — DATABASE_URL, API keys, passwords all committed
- **Risk:** Anyone with repo access has full DB/service access
- **Fix:** Rotate ALL keys immediately. Use Cloud Run Secret Manager for prod.

#### C2. `_active_checkpointers` is in-memory — breaks horizontal scaling
- **File:** `backend/app/api/routes/agents.py:53`
- **Risk:** Cloud Run routes requests to different instances. Instance A stores checkpointer, Instance B gets resume request → 410 error. Also memory leak if SSE drops.
- **Fix:** Use `AsyncPostgresSaver` in production (code already exists in `dependencies.py:109-113`, just needs env toggle). Keep MemorySaver for dev only.

#### C3. Supabase free tier: only 3 DB connections
- **Risk:** 1-2 concurrent users max. Any streaming (chat/agent) holds a connection for 30-60 seconds.
- **Fix:** Upgrade to Supabase Starter ($25/mo) — gets proper Supavisor pooling with higher limits.

#### C4. Dockerfile hardcodes `--workers 2`
- **File:** `backend/Dockerfile:18`
- **Risk:** Doesn't scale with CPU allocation. 4 vCPU Cloud Run instance still runs 2 workers = 50% waste. Also, 2 workers = double memory for LRU-cached singletons.
- **Fix:** Remove `--workers` flag entirely (Cloud Run scales horizontally, not with workers). Or use `$(nproc)`.

#### C5. Redis has no connection limits or timeouts
- **File:** `backend/app/db/redis_client.py`
- **Risk:** Can hang indefinitely on network issues. No max_connections = unbounded.
- **Also:** 3 separate Redis singletons (`redis_client.py`, `auth.py:43`, `rate_limiter.py:107`) — connection pool fragmentation.
- **Fix:** Add `max_connections=50, socket_timeout=10, retry_on_timeout=True`. Consolidate to single client.

#### C6. Upstash Redis free tier: 10k commands/day
- **Risk:** At 50+ active users doing search+chat, you'll hit 10k commands within hours.
- **Fix:** Upgrade to Upstash Pay-as-you-go ($0.2/100k commands).

### HIGH (Issues at ~100 users)

#### ~~H1. Rate limiter fallback is per-instance (not distributed)~~ — **FIXED**
- **File:** `backend/app/security/rate_limiter.py`
- Falls back to in-memory sliding window (asyncio.Lock) when Redis is unavailable; logs a warning. Per-instance limits during fallback are accepted as a trade-off (ADR-021). See `DECISIONS.md` ADR-021.

#### H2. Sync Pinecone SDK wrapped in `asyncio.to_thread()`
- **File:** `backend/app/core/providers/vector/pinecone_store.py:28-52`
- **Risk:** Default thread pool (5 threads per CPU core). 100 concurrent searches = thread pool exhaustion, 10-100x latency spike.
- **Fix:** Increase thread pool size. Or migrate to Pinecone async SDK when available.

#### H3. Cohere reranker: 30s timeout, no circuit breaker
- **File:** `backend/app/core/providers/rerankers/cohere_reranker.py:36-59`
- **Risk:** If Cohere API is slow, every search waits 30 seconds before fallback. Cascading slowness.
- **Fix:** Reduce timeout to 10s. Add simple circuit breaker (skip reranking for 60s after 3 consecutive failures).

#### H4. Agent execution migration has outdated constraint
- **File:** `backend/migrations/versions/005_agent_executions.py:50-52`
- **Risk:** CHECK constraint allows only `('research', 'case_prep')`, but model has 4 types including `strategy` and `drafting`. INSERT will fail for strategy/drafting agents.
- **Fix:** ALTER TABLE to update constraint to include all 4 types.

#### H5. No monitoring enabled
- **Risk:** Sentry DSN is empty string in `.env`. No error tracking, no performance monitoring, no alerting.
- **Fix:** Set `SENTRY_DSN` in production. Already integrated in `main.py:100-120`.

#### H6. Frontend token refresh race condition
- **File:** `frontend/src/lib/api.ts:131-145`
- **Risk:** 10 concurrent 401s all call `tryRefresh()` simultaneously. First succeeds, others may fail or get stale tokens.
- **Fix:** Use singleton Promise pattern — first caller initiates refresh, others await same Promise.

### MEDIUM (Issues at ~1000 users)

#### M1. No frontend concurrency limits
#### M2. Chat messages not virtualized
#### M3. No code splitting for heavy pages
#### M4. Health check creates fresh connections
#### M5. Missing `audio_digests` indexes
#### M6. Document uploads use local filesystem temp

### LOW (Optimizations for later)
- L1. No CDN for static assets
- L2. Redis cache stampede risk
- L3. SSE has no backpressure
- L4. No distributed tracing
- L5. Per-IP rate limiting (NAT issue)
- L6. No API versioning

---

## Cost Projection

| Users | Supabase | Pinecone | Upstash | Cloud Run | Gemini | Cohere | Total |
|-------|----------|----------|---------|-----------|--------|--------|-------|
| 10 | Free ($0) | Free ($0) | Free ($0) | Free ($0) | Free ($0) | Free ($0) | **$0** |
| 100 | Starter ($25) | Free ($0) | Starter ($10) | ~$20 | Free ($0) | ~$5 | **~$60/mo** |
| 1,000 | Starter ($25) | Starter ($99) | Pro ($20) | ~$200 | ~$25 | ~$50 | **~$420/mo** |
| 10,000 | Pro ($75) | Standard ($249) | Enterprise ($100) | ~$1000 | ~$250 | ~$200 | **~$1,875/mo** |

---

## Is This a Good Base? (Architectural Assessment)

### Strengths (keep these)
- **Async-first**: FastAPI + SQLAlchemy async + async Redis — scales well vertically
- **Provider pattern**: All external services behind Protocol interfaces — easy to swap
- **LangGraph agents**: Proper graph-based workflow, interrupt() for HITL — production-ready pattern
- **Security foundations**: JWT + RBAC, rate limiting, input sanitization, prompt injection detection
- **Modular monolith**: Clear module boundaries, easy to extract into microservices later

### NOT a dead end because:
1. NullPool + Supavisor already configured for connection pooling at scale
2. AsyncPostgresSaver already implemented for distributed checkpointing
3. GCS storage provider already built alongside local provider
4. Redis caching layer already in place, just needs tuning
5. The fixes are all **configuration changes**, not architectural rewrites

---

## Implementation Phases

### Phase A: Critical fixes (Day 1)
1. Rotate all secrets, move to Cloud Run Secret Manager
2. Fix `_active_checkpointers` → use AsyncPostgresSaver in prod
3. Fix Redis client: add timeouts, max_connections, consolidate singletons
4. Fix Dockerfile: remove `--workers 2`
5. Fix agent_executions CHECK constraint
6. Enable Sentry error tracking

### Phase B: High-priority fixes (Day 2)
7. Upgrade Supabase to Starter ($25/mo)
8. Upgrade Upstash Redis to paid tier
9. Add circuit breaker to Cohere reranker
10. Fix token refresh race condition in frontend
11. ~~Fix rate limiter: asyncio.Lock instead of threading.Lock~~ — DONE (ADR-021)

### Phase C: Medium-priority (Day 3)
12-16. Indexes, code splitting, caching, virtualization

### Phase D: Post-launch optimizations (Week 2+)
17-20. Load testing, CDN, tracing, async Pinecone
