# Vaquill Provider + Per-Worker Toggles — Design

**Date:** 2026-04-16
**Status:** Design approved, implementation pending
**Scope:** Option A only (sibling retrieval worker). Options B (Citations in Challenge stage) and C (Acts in statute lookup) are deferred.

---

## 1. Motivation

Ingesting Indian case law is expensive and Smriti has no paying customers yet. Rather than continue to fund the Vertex AI batch pipeline, we want to validate the product using third-party legal data APIs. Vaquill exposes 20M+ Indian judgments, a citation graph, and a free developer tier — enough to validate retrieval quality without spending our own ingestion budget.

Alongside this, we need per-worker enable flags so we can turn any data source (Indian Kanoon, Vaquill, Pinecone, Neo4j, etc.) on or off from `.env` during validation and cost tuning.

## 2. Goals

1. Add `VaquillClient` as a second `ExternalDocProvider` alongside `IndianKanoonClient`.
2. Add `vaquill_search_worker` dispatched in parallel with existing Stage 3 Investigate workers.
3. Add startup-time enable flags for **all 7 research workers**. Defaults: all `true` (including Vaquill).
4. Preserve the existing architecture, Protocol, result shape, reconciliation, and reranking logic. Minimum blast radius.

## 3. Non-goals (YAGNI)

- Option B — Vaquill Citations graph inside `adversarial_search_node`. Deferred to a follow-up PR once we see real retrieval quality from Vaquill.
- Option C — Vaquill Acts endpoint feeding `statute_lookup_node`.
- Runtime toggle mutation via admin API. Env + restart is sufficient.
- `get_citation_graph` / `get_act` extensions to the `ExternalDocProvider` Protocol. No consumer yet.
- Auto-failover between IK and Vaquill. Workers are independent — no failover needed.
- Cost dashboards / reporting UIs. Log lines and Redis counters are sufficient.

## 4. Architecture

```
Stage 3 dispatch_workers()
        │
        ├── [if WORKER_IK_ENABLED]           → ik_search_worker        → IndianKanoonClient
        ├── [if WORKER_VAQUILL_ENABLED]      → vaquill_search_worker   → VaquillClient         ← NEW
        ├── [if WORKER_CASE_LAW_ENABLED]     → case_law_worker         → Pinecone + FTS + RRF
        ├── [if WORKER_GRAPH_ENABLED]        → graph_worker            → Neo4j
        ├── [if WORKER_NAMED_CASE_ENABLED]   → named_case_worker
        ├── [if WORKER_STATUTE_ENABLED]      → statute_worker          → statute Pinecone + PG
        └── [if WORKER_WEB_SEARCH_ENABLED]   → web_search_worker
```

- Toggle is enforced **at dispatch time** inside `dispatch_workers()`. Disabled workers never get a `Send()`, so there is zero cost and zero latency for off workers.
- Disabled workers are logged once at application startup, not per request.
- If **all** workers are disabled, `dispatch_workers()` raises `ValueError("No research workers enabled")` immediately — fail fast, not silent empty results.

## 5. Components

### 5.1 `VaquillClient` — new provider

**Path:** `backend/app/core/providers/external/vaquill.py` (~220 LOC, mirrors `indiankanoon.py`)

**Implements:** `ExternalDocProvider` (existing Protocol, no changes)

| Protocol method | Vaquill endpoint | Notes |
|---|---|---|
| `search(query, filters)` | `POST /api/v1/research/quick-search` (0.1 credits) | Boolean keyword search with `countryCode: "IN"`. Cheapest endpoint. Returns ranked cases with relevance scores. |
| `get_document(doc_id)` | `GET /api/v1/citations/case-lookup/{id}` (1 credit) | Full case text + metadata. |
| `get_fragment(doc_id, query)` | `POST /api/v1/ask` (0.5 credits) scoped to single source | Vaquill's `Ask` response returns `sources[].excerpt` (≤500 chars) with `charStart/charEnd/pageStart/pageEnd`. Extract excerpt for the source matching `doc_id`. Clean native solution — no client-side sentence extraction needed. |
| `get_metadata(doc_id)` | same as `get_document`, strip text client-side | Vaquill has no metadata-only endpoint documented. Cheaper to reuse case-lookup and strip. |
| `get_court_copy(doc_id)` | return `pdfUrl` from case-lookup response | Vaquill's differentiator — real court-copy PDFs. Returned as a signed URL, not base64 HTML as IK does. Shape normalized by the worker. |

**Reliability stack** (copy from `indiankanoon.py`, same patterns):

- `httpx.AsyncClient` with 30s timeout
- Tenacity retry: 3 attempts, exponential backoff (1s → 4s → 9s)
- Token bucket rate limiter, default 2 req/s, configurable via `VAQUILL_RATE_LIMIT`
- Circuit breaker: 3 consecutive failures → 60s open state
- Bearer auth: `Authorization: Bearer {VAQUILL_API_TOKEN}` with `vq_key_...` format

**Error handling:**
- Vaquill errors match the documented shape `{ error: { type, message, code } }`. Map the `type` enum (`authentication_error`, `insufficient_credits`, `permission_error`, `validation_error`, `service_unavailable`) to existing exception classes.
- `insufficient_credits` → `QuotaExceededError` (new, or reuse existing). Worker short-circuits, logs warning, returns empty result with `error` field set.

### 5.2 `vaquill_search_worker` — new worker

**Path:** `backend/app/core/agents/nodes/worker_nodes.py`, mirrored from `ik_search_worker` at line 497.

- Same signature, same `WorkerResult` dict shape.
- Redis cache key includes `provider="vaquill"` so IK and Vaquill caches stay distinct.
- Normalizes Vaquill response to the worker-result schema used by IK today: `{case_id: "vaquill:{id}", title, citation, court, year, snippet, source: "vaquill", relevance_score, pdf_url, ...}`.
- Cost guardrails:
  - Hard fragment-call limit per query (copy IK pattern)
  - Monthly query budget tracked via Redis counter keyed by YYYY-MM (`vaquill:budget:2026-04`), default limit `VAQUILL_MONTHLY_QUERY_BUDGET=100` (free tier is 100 req/day; 100/month as a conservative ceiling during validation)
  - When budget exceeded: skip the Vaquill call, log warning, return empty `WorkerResult`, continue the pipeline

### 5.3 Worker registry — per-worker toggles

**Path:** `backend/app/core/agents/worker_registry.py` (new, ~60 LOC)

```python
class WorkerRegistry:
    def __init__(self, settings: Settings) -> None: ...
    def is_enabled(self, worker_name: str) -> bool: ...
    def enabled_workers(self) -> set[str]: ...
```

- Reads the `worker_*_enabled` fields from `Settings` at construction time.
- `dispatch_workers()` in `research.py` calls `registry.is_enabled("ik")`, `registry.is_enabled("vaquill")`, etc. before each `Send()`.
- Disabled workers logged once at startup: `"Worker 'graph' disabled via WORKER_GRAPH_ENABLED=false"`.
- If `enabled_workers()` is empty at dispatch time, raise `ValueError("No research workers enabled — check WORKER_*_ENABLED env flags")`.

### 5.4 Config additions

**Path:** `backend/app/core/config.py`

```python
# Vaquill provider
vaquill_api_token: str | None = None
vaquill_rate_limit: float = 2.0
vaquill_monthly_query_budget: int = 100

# Per-worker enable flags (all default to True)
worker_ik_enabled: bool = True
worker_vaquill_enabled: bool = True
worker_case_law_enabled: bool = True
worker_graph_enabled: bool = True
worker_named_case_enabled: bool = True
worker_statute_enabled: bool = True
worker_web_search_enabled: bool = True
```

Corresponding env vars: `VAQUILL_API_TOKEN`, `VAQUILL_RATE_LIMIT`, `VAQUILL_MONTHLY_QUERY_BUDGET`, `WORKER_IK_ENABLED`, `WORKER_VAQUILL_ENABLED`, etc.

### 5.5 Dependency injection

**Path:** `backend/app/core/dependencies.py`

```python
@lru_cache
def get_vaquill_client() -> ExternalDocProvider | None:
    if not settings.vaquill_api_token:
        return None
    return VaquillClient()
```

- Returns `None` if no token is configured — worker skips gracefully. This is belt + braces alongside the enable flag: you can set `WORKER_VAQUILL_ENABLED=true` but forget the token, and the system degrades safely instead of crashing.

## 6. Data flow

**No changes to how results merge.** Vaquill `WorkerResult` lists stay separate from IK and from Pinecone/FTS fused results, exactly as IK works today. Reconciliation happens at the synthesis stage via existing logic. No RRF changes. No reranker changes. No Neo4j changes.

## 7. Error handling

| Condition | Behavior |
|---|---|
| Vaquill 5xx / network error | Tenacity retry 3×. On final failure, circuit breaker increments. Worker returns empty `WorkerResult` with `error` field set. Pipeline continues with other workers. |
| Vaquill 401 / `authentication_error` | Raise at startup if token present but rejected on first call. Crash fast — misconfiguration should not be silent. |
| Vaquill 429 / rate limit | Token bucket already prevents this; if it still happens, retry with backoff. |
| `insufficient_credits` | Short-circuit current request, log warning, disable `vaquill_search_worker` for remainder of process lifetime via in-memory circuit breaker. Other workers continue. |
| Monthly budget Redis counter exceeded | Skip Vaquill call, return empty `WorkerResult`. Log one warning per hour (not per request) to avoid log spam. |
| Vaquill token missing | DI returns `None`. Worker detects and skips. |
| All workers disabled | `dispatch_workers()` raises `ValueError` immediately. |
| `countryCode=IN` returns non-Indian results | See §10 — this is the #1 pre-implementation verification item. If confirmed broken, abort implementation and escalate. |

## 8. Testing

**New test files:**
- `backend/tests/unit/test_vaquill_client.py` — mirror `test_indiankanoon_client.py`. Mocks HTTPX, covers: auth header, rate limiter, circuit breaker, retry on 5xx, response normalization for each of the 5 Protocol methods, error-type mapping (~15 tests).
- `backend/tests/unit/test_vaquill_worker.py` — mirror `test_ik_worker.py`. Covers: filter propagation, cache key includes `provider="vaquill"`, monthly budget enforcement, empty-result path, error path, `None` client path (~8 tests).
- `backend/tests/unit/test_worker_registry.py` — new. Covers: default all-enabled, per-worker env override, `enabled_workers()` set accuracy, empty-set detection (~6 tests).

**Extended tests:**
- `backend/tests/integration/test_research_agent_v3.py` — add two scenarios:
  - "Vaquill enabled alongside IK" — verifies both workers dispatch and both result lists appear in state.
  - "All workers except `case_law` disabled" — verifies `dispatch_workers()` only dispatches one worker and the pipeline still completes.
  - "All workers disabled" — verifies `ValueError` is raised at dispatch time.

## 9. Migration and rollout

No DB migration needed. No data backfill. No existing behavior changes when `WORKER_VAQUILL_ENABLED=true` but `VAQUILL_API_TOKEN` is unset — the DI factory returns `None` and the worker no-ops.

**Rollout sequence:**
1. Merge with `WORKER_VAQUILL_ENABLED=true` (default) but **no token set in prod**. Zero behavior change.
2. Obtain Vaquill free-tier API key locally, run integration tests, verify `countryCode=IN` actually returns Indian cases (§10).
3. Set `VAQUILL_API_TOKEN` in dev environment. Run real queries, compare retrieval quality vs IK manually for 10 representative queries (tax law, criminal law, constitutional law, etc.).
4. If quality is acceptable, set token in prod. Monitor Redis budget counter daily for first week.
5. Decide whether to pursue Option B (Citations graph in Challenge stage) based on observed quality.

## 10. Pre-implementation verification

**BEFORE writing any code**, confirm with a real API key:

1. **`countryCode: "IN"` actually scopes results to Indian corpus.** The Vaquill marketing page mentions "SCOTUS, federal circuits, state courts" (US courts). The API docs show `countryCode: "IN"` as a parameter. If Indian scoping is broken, Vaquill is unusable for Smriti — abort integration.
2. **Exact filter parameter names for Research/Quick Search** (court, date range, citation). The published OpenAPI excerpt mentioned "court/year filters" without parameter names.
3. **`Ask` endpoint `sources[]` shape is stable** — specifically that `excerpt`, `charStart`, `charEnd`, `pageStart`, `pageEnd`, `pdfUrl` are always present.
4. **Error response shape matches documentation** — `{ error: { type, message, code } }`.
5. **Free tier is actually 500 credits + 100 req/day** and resets on a known schedule.

These will be verified by (a) creating a Vaquill account, (b) running manual curl calls against each endpoint from the planned implementation set, (c) documenting the real shapes in an appendix to this design doc before coding begins.

## 11. Cost & budget guardrails

**Free tier math:**
- 500 credits = 5000 Quick Searches OR 1000 Asks OR 500 case lookups (or any mix)
- 100 requests/day cap regardless of credit balance
- Resets monthly (verify during §10)

**Per-query cost at Stage 3 dispatch:**
- 1 Quick Search per query = 0.1 credits
- Up to N `Ask` calls for fragments (bounded by existing IK fragment budget, typically ≤5 per query) = ≤2.5 credits
- Worst case: ~2.6 credits per user query
- 500-credit budget → ~190 user queries/month on free tier before paying

**In-process guards:**
1. `VAQUILL_MONTHLY_QUERY_BUDGET` (default 100) — Redis counter. When exceeded, worker no-ops.
2. Daily request guard — optional, skipped for v1 since the monthly guard will trip first.
3. Fragment call budget — copy IK's existing per-query limit.

## 12. Open questions (low priority — answer during implementation)

1. Should `vaquill_search_worker`'s Redis cache TTL match IK's, or be shorter given Vaquill's "24–48h ingestion" freshness claim? Default to matching IK unless there's a reason otherwise.
2. When both IK and Vaquill return the same case by citation, should synthesis dedupe by citation key? Current behavior is worker-level separation, so duplicates flow through. Decide based on observed synthesis output quality.
3. `get_court_copy` on IK returns base64 HTML; on Vaquill it returns a signed URL. Worker normalizes both into a unified `{type: "pdf_url" | "html_base64", value: str}` shape. Confirm no downstream consumer assumes one format.

## 13. Files touched (summary)

```
backend/app/core/
├── config.py                                 # +3 Vaquill settings, +7 worker flags
├── dependencies.py                           # +get_vaquill_client
├── providers/external/vaquill.py             # NEW ~220 LOC
├── agents/
│   ├── worker_registry.py                    # NEW ~60 LOC
│   ├── research.py                           # dispatch_workers() gates each Send() on registry
│   └── nodes/worker_nodes.py                 # +vaquill_search_worker ~120 LOC
backend/tests/
├── unit/test_vaquill_client.py               # NEW ~15 tests
├── unit/test_vaquill_worker.py               # NEW ~8 tests
├── unit/test_worker_registry.py              # NEW ~6 tests
└── integration/test_research_agent_v3.py     # +3 scenarios
.env.example                                  # document VAQUILL_* and WORKER_*_ENABLED
```

No existing file is deleted or renamed. The IK path is untouched at the code level — only guarded by a new flag that defaults to `true`.
