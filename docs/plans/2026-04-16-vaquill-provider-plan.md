# Vaquill Provider + Per-Worker Toggles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `VaquillClient` as a second `ExternalDocProvider` dispatched as a sibling worker to Indian Kanoon in Stage 3 Investigate, plus per-worker enable flags for all 7 research workers.

**Architecture:** New provider implements the existing `ExternalDocProvider` Protocol unchanged. New worker mirrors `ik_search_worker`. A new `WorkerRegistry` reads `worker_*_enabled` settings from env and gates `Send()` dispatch inside `dispatch_workers()`. All 7 worker flags default to `true`. No RRF, reranker, or Neo4j changes.

**Tech Stack:** FastAPI, LangGraph, httpx, tenacity, pydantic-settings, pytest, pytest-asyncio, respx (HTTPX mocking), Redis (quota counter).

**Reference:** See [design doc](2026-04-16-vaquill-provider-design.md) for motivation, trade-offs, endpoint mapping, and cost guardrails.

---

## Task 0: Pre-implementation API verification (MANUAL, BLOCKING)

**Cannot be automated.** This must be done with a real Vaquill API key before any code is written.

**Files:**
- Create: `docs/plans/2026-04-16-vaquill-api-verification.md` (findings appendix)

**Steps:**

1. Sign up at vaquill.ai and obtain a free-tier API key (format `vq_key_...`).

2. Run these curl smoke tests from a shell. Record exact responses in the findings appendix.

   ```bash
   export VQ_KEY="vq_key_..."

   # 2a. Quick Search with countryCode=IN — verify Indian cases returned
   curl -sS -X POST https://api.vaquill.ai/v1/research/quick-search \
     -H "Authorization: Bearer $VQ_KEY" \
     -H "Content-Type: application/json" \
     -d '{"query":"Article 14 equality","countryCode":"IN","limit":5}' | jq .

   # 2b. Ask endpoint — verify sources[] shape with excerpt/charStart/pageStart/pdfUrl
   curl -sS -X POST https://api.vaquill.ai/v1/ask \
     -H "Authorization: Bearer $VQ_KEY" \
     -H "Content-Type: application/json" \
     -d '{"question":"What is the scope of Article 14?","mode":"standard","sources":true,"maxSources":5,"countryCode":"IN"}' | jq .

   # 2c. Case lookup — pick a case_id from 2a's response
   curl -sS https://api.vaquill.ai/v1/citations/case-lookup/<CASE_ID> \
     -H "Authorization: Bearer $VQ_KEY" | jq .

   # 2d. Trigger an error — missing auth
   curl -sS -X POST https://api.vaquill.ai/v1/research/quick-search \
     -H "Content-Type: application/json" \
     -d '{"query":"test","countryCode":"IN"}' | jq .
   ```

3. **Verification checklist** — every item must be confirmed in the findings doc:
   - [ ] `countryCode: "IN"` returns only Indian courts (Supreme Court, High Courts, tribunals). If any US courts appear, **STOP — abort integration**.
   - [ ] Exact Quick Search filter parameter names for court, date range, citation.
   - [ ] `Ask` response contains `data.sources[]` with fields `excerpt`, `charStart`, `charEnd`, `pageStart`, `pageEnd`, `pdfUrl`, `caseId` (or equivalent identifier).
   - [ ] Case lookup response includes full text, citation, court name, date, parties, judges, `pdfUrl`.
   - [ ] Error shape is `{ error: { type, message, code } }` with documented `type` enum.
   - [ ] Free-tier credit balance visible in response `meta.creditsRemaining`.
   - [ ] Base URL is `https://api.vaquill.ai/v1` (confirm — adjust all code if different).

4. Append the actual JSON response samples to the findings doc. These become the fixtures for Task 3+ tests.

5. Commit the findings doc:
   ```bash
   git add docs/plans/2026-04-16-vaquill-api-verification.md
   git commit -m "docs(plans): record Vaquill API verification findings"
   ```

**Do not proceed to Task 1 until every checklist item is confirmed.**

---

## Task 1: Config additions

**Files:**
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_config.py` (extend existing)

**Step 1: Write failing test for new settings**

Add to `test_config.py`:

```python
def test_vaquill_settings_defaults():
    from app.core.config import Settings
    s = Settings()
    assert s.vaquill_api_token is None
    assert s.vaquill_rate_limit == 2.0
    assert s.vaquill_monthly_query_budget == 100

def test_worker_enable_flags_default_true():
    from app.core.config import Settings
    s = Settings()
    assert s.worker_ik_enabled is True
    assert s.worker_vaquill_enabled is True
    assert s.worker_case_law_enabled is True
    assert s.worker_graph_enabled is True
    assert s.worker_named_case_enabled is True
    assert s.worker_statute_enabled is True
    assert s.worker_web_search_enabled is True

def test_worker_enable_flag_env_override(monkeypatch):
    monkeypatch.setenv("WORKER_VAQUILL_ENABLED", "false")
    from app.core.config import Settings
    s = Settings()
    assert s.worker_vaquill_enabled is False
```

**Step 2: Run — expect failures**

```bash
cd backend && pytest tests/unit/test_config.py::test_vaquill_settings_defaults tests/unit/test_config.py::test_worker_enable_flags_default_true tests/unit/test_config.py::test_worker_enable_flag_env_override -v
```
Expected: 3 failures, `AttributeError` on `vaquill_api_token` etc.

**Step 3: Implement**

Add to `backend/app/core/config.py` in the `Settings` class body:

```python
# Vaquill provider (see docs/plans/2026-04-16-vaquill-provider-design.md)
vaquill_api_token: str | None = None
vaquill_rate_limit: float = 2.0
vaquill_monthly_query_budget: int = 100

# Per-worker enable flags — all default to True, set *_ENABLED=false in env to disable
worker_ik_enabled: bool = True
worker_vaquill_enabled: bool = True
worker_case_law_enabled: bool = True
worker_graph_enabled: bool = True
worker_named_case_enabled: bool = True
worker_statute_enabled: bool = True
worker_web_search_enabled: bool = True
```

**Step 4: Run — expect pass**

```bash
cd backend && pytest tests/unit/test_config.py -v
```

**Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/unit/test_config.py
git commit -m "feat(config): add Vaquill settings and per-worker enable flags"
```

---

## Task 2: WorkerRegistry (TDD)

**Files:**
- Create: `backend/app/core/agents/worker_registry.py`
- Create: `backend/tests/unit/test_worker_registry.py`

**Step 1: Write failing tests**

`backend/tests/unit/test_worker_registry.py`:

```python
import pytest
from app.core.agents.worker_registry import WorkerRegistry, NoWorkersEnabledError
from app.core.config import Settings


def _settings(**overrides):
    defaults = dict(
        worker_ik_enabled=True,
        worker_vaquill_enabled=True,
        worker_case_law_enabled=True,
        worker_graph_enabled=True,
        worker_named_case_enabled=True,
        worker_statute_enabled=True,
        worker_web_search_enabled=True,
    )
    defaults.update(overrides)
    s = Settings()
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


def test_all_enabled_by_default():
    reg = WorkerRegistry(_settings())
    assert reg.enabled_workers() == {
        "ik", "vaquill", "case_law", "graph", "named_case", "statute", "web_search"
    }


def test_individual_disable():
    reg = WorkerRegistry(_settings(worker_ik_enabled=False))
    assert "ik" not in reg.enabled_workers()
    assert reg.is_enabled("ik") is False
    assert reg.is_enabled("vaquill") is True


def test_unknown_worker_name_raises():
    reg = WorkerRegistry(_settings())
    with pytest.raises(KeyError):
        reg.is_enabled("nonexistent")


def test_all_disabled_raises_on_assert():
    reg = WorkerRegistry(_settings(
        worker_ik_enabled=False,
        worker_vaquill_enabled=False,
        worker_case_law_enabled=False,
        worker_graph_enabled=False,
        worker_named_case_enabled=False,
        worker_statute_enabled=False,
        worker_web_search_enabled=False,
    ))
    assert reg.enabled_workers() == set()
    with pytest.raises(NoWorkersEnabledError):
        reg.assert_any_enabled()


def test_logs_disabled_workers_once_at_construction(caplog):
    import logging
    caplog.set_level(logging.INFO)
    WorkerRegistry(_settings(worker_graph_enabled=False, worker_ik_enabled=False))
    messages = [r.message for r in caplog.records]
    assert any("graph" in m and "disabled" in m for m in messages)
    assert any("ik" in m and "disabled" in m for m in messages)
```

**Step 2: Run — expect module not found**

```bash
cd backend && pytest tests/unit/test_worker_registry.py -v
```

**Step 3: Implement**

`backend/app/core/agents/worker_registry.py`:

```python
import logging
from app.core.config import Settings

logger = logging.getLogger(__name__)

_WORKER_NAMES = (
    "ik", "vaquill", "case_law", "graph", "named_case", "statute", "web_search",
)


class NoWorkersEnabledError(RuntimeError):
    """Raised at dispatch time when every research worker is disabled."""


class WorkerRegistry:
    def __init__(self, settings: Settings) -> None:
        self._flags: dict[str, bool] = {
            name: getattr(settings, f"worker_{name}_enabled") for name in _WORKER_NAMES
        }
        for name, enabled in self._flags.items():
            if not enabled:
                logger.info(
                    "Worker '%s' disabled via WORKER_%s_ENABLED=false",
                    name, name.upper(),
                )

    def is_enabled(self, worker_name: str) -> bool:
        if worker_name not in self._flags:
            raise KeyError(f"Unknown worker: {worker_name}")
        return self._flags[worker_name]

    def enabled_workers(self) -> set[str]:
        return {name for name, enabled in self._flags.items() if enabled}

    def assert_any_enabled(self) -> None:
        if not self.enabled_workers():
            raise NoWorkersEnabledError(
                "No research workers enabled — check WORKER_*_ENABLED env flags"
            )
```

**Step 4: Run — expect pass**

```bash
cd backend && pytest tests/unit/test_worker_registry.py -v
```

**Step 5: Commit**

```bash
git add backend/app/core/agents/worker_registry.py backend/tests/unit/test_worker_registry.py
git commit -m "feat(agents): add WorkerRegistry for per-worker enable flags"
```

---

## Task 3: VaquillClient scaffolding — auth, rate limiter, circuit breaker (TDD)

**Files:**
- Create: `backend/app/core/providers/external/vaquill.py`
- Create: `backend/tests/unit/test_vaquill_client.py`

Read [`backend/app/core/providers/external/indiankanoon.py`](../../backend/app/core/providers/external/indiankanoon.py) first to mirror its reliability stack — token bucket, tenacity decorators, circuit breaker — and reuse the same helper classes if they're extractable into `providers/external/_reliability.py`. If not already extracted, **extract them now** as a prerequisite sub-task and commit separately before writing Vaquill code. This avoids duplication.

**Step 1: Write failing tests — auth header + base URL**

```python
# backend/tests/unit/test_vaquill_client.py
import pytest
import respx
import httpx
from app.core.providers.external.vaquill import VaquillClient
from app.core.config import Settings


@pytest.fixture
def vaquill_client(monkeypatch):
    monkeypatch.setenv("VAQUILL_API_TOKEN", "vq_key_test")
    return VaquillClient()


@pytest.mark.asyncio
async def test_bearer_auth_header_sent(vaquill_client):
    with respx.mock(base_url="https://api.vaquill.ai") as mock:
        route = mock.post("/v1/research/quick-search").respond(
            200, json={"data": {"results": []}, "meta": {"creditsRemaining": 500}}
        )
        await vaquill_client.search("test", {})
        assert route.called
        req = route.calls[0].request
        assert req.headers["Authorization"] == "Bearer vq_key_test"


@pytest.mark.asyncio
async def test_missing_token_raises_at_construction(monkeypatch):
    monkeypatch.delenv("VAQUILL_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="VAQUILL_API_TOKEN"):
        VaquillClient()
```

**Step 2: Run — expect module not found**

```bash
cd backend && pytest tests/unit/test_vaquill_client.py -v
```

**Step 3: Implement minimal scaffold**

```python
# backend/app/core/providers/external/vaquill.py
import httpx
from app.core.config import settings
from app.core.interfaces.external_doc import ExternalDocProvider


class VaquillClient:
    BASE_URL = "https://api.vaquill.ai/v1"

    def __init__(self) -> None:
        token = settings.vaquill_api_token
        if not token:
            raise ValueError("VAQUILL_API_TOKEN not configured")
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    async def search(self, query: str, filters: dict) -> list[dict]:
        resp = await self._client.post(
            "/research/quick-search",
            json={"query": query, "countryCode": "IN", **filters},
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("results", [])
```

**Step 4: Run — expect pass**

```bash
cd backend && pytest tests/unit/test_vaquill_client.py -v
```

**Step 5: Commit**

```bash
git add backend/app/core/providers/external/vaquill.py backend/tests/unit/test_vaquill_client.py
git commit -m "feat(providers): add VaquillClient scaffold with auth"
```

---

## Task 4: VaquillClient.search() — filter mapping + response normalization (TDD)

**Files:**
- Modify: `backend/app/core/providers/external/vaquill.py`
- Modify: `backend/tests/unit/test_vaquill_client.py`

Use the real response shape captured in Task 0's verification doc as the fixture. Do NOT hand-invent the JSON.

**Step 1: Write failing tests**

Add to `test_vaquill_client.py`:

```python
@pytest.mark.asyncio
async def test_search_passes_filters(vaquill_client):
    with respx.mock(base_url="https://api.vaquill.ai") as mock:
        route = mock.post("/v1/research/quick-search").respond(
            200, json={"data": {"results": []}, "meta": {"creditsRemaining": 500}}
        )
        await vaquill_client.search(
            "dowry harassment",
            filters={"court": "supreme_court", "year_from": 2020, "year_to": 2024},
        )
        body = route.calls[0].request.content.decode()
        assert "dowry harassment" in body
        assert "supreme_court" in body
        assert "2020" in body


@pytest.mark.asyncio
async def test_search_normalizes_results(vaquill_client):
    # Fixture from Task 0 verification — replace with real Quick Search response
    fake_response = {
        "data": {
            "results": [
                {
                    "caseId": "vq_abc123",
                    "title": "State v. Kumar",
                    "citation": "2023 INSC 412",
                    "court": "Supreme Court of India",
                    "date": "2023-05-14",
                    "snippet": "Held that Section 498A applies where...",
                    "relevance": 0.87,
                    "pdfUrl": "https://cdn.vaquill.ai/cases/vq_abc123.pdf",
                },
            ],
        },
        "meta": {"creditsRemaining": 499},
    }
    with respx.mock(base_url="https://api.vaquill.ai") as mock:
        mock.post("/v1/research/quick-search").respond(200, json=fake_response)
        results = await vaquill_client.search("498A", {})
    assert len(results) == 1
    assert results[0]["case_id"] == "vaquill:vq_abc123"
    assert results[0]["title"] == "State v. Kumar"
    assert results[0]["citation"] == "2023 INSC 412"
    assert results[0]["source"] == "vaquill"
    assert results[0]["relevance_score"] == 0.87
    assert results[0]["pdf_url"].startswith("https://")
```

**Step 2: Run — expect fail on normalization**

```bash
cd backend && pytest tests/unit/test_vaquill_client.py -v
```

**Step 3: Implement normalization**

Update `search()` in `vaquill.py`:

```python
async def search(self, query: str, filters: dict) -> list[dict]:
    payload = {"query": query, "countryCode": "IN"}
    if "court" in filters:
        payload["court"] = filters["court"]
    if "year_from" in filters:
        payload["yearFrom"] = filters["year_from"]
    if "year_to" in filters:
        payload["yearTo"] = filters["year_to"]
    resp = await self._client.post("/research/quick-search", json=payload)
    resp.raise_for_status()
    raw = resp.json().get("data", {}).get("results", [])
    return [self._normalize_result(r) for r in raw]

def _normalize_result(self, raw: dict) -> dict:
    return {
        "case_id": f"vaquill:{raw['caseId']}",
        "title": raw.get("title", ""),
        "citation": raw.get("citation", ""),
        "court": raw.get("court", ""),
        "year": (raw.get("date") or "")[:4] or None,
        "snippet": raw.get("snippet", ""),
        "source": "vaquill",
        "relevance_score": float(raw.get("relevance", 0.0)),
        "pdf_url": raw.get("pdfUrl"),
        "vaquill_doc_id": raw["caseId"],
    }
```

**Step 4: Run — expect pass**

```bash
cd backend && pytest tests/unit/test_vaquill_client.py -v
```

**Step 5: Commit**

```bash
git add backend/app/core/providers/external/vaquill.py backend/tests/unit/test_vaquill_client.py
git commit -m "feat(vaquill): implement search with filter mapping and normalization"
```

---

## Task 5: VaquillClient.get_document() + get_metadata() (TDD)

Same TDD pattern. Test with fixture from Task 0. Implement both methods — `get_metadata` is `get_document` with text stripped client-side.

Commit: `feat(vaquill): implement get_document and get_metadata`

---

## Task 6: VaquillClient.get_fragment() via Ask endpoint (TDD)

**Key design point:** Map `get_fragment(doc_id, query)` → `POST /v1/ask` with the query, then pick the source in `data.sources[]` whose `caseId` matches `doc_id`. Return `{text: excerpt, char_start, char_end, page_start, page_end}`.

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_get_fragment_selects_matching_source(vaquill_client):
    ask_response = {
        "data": {
            "answer": "Article 14 guarantees...",
            "sources": [
                {"caseId": "vq_other", "excerpt": "wrong case", "charStart": 0, "charEnd": 10, "pageStart": 1, "pageEnd": 1, "pdfUrl": "x"},
                {"caseId": "vq_abc123", "excerpt": "The correct excerpt here", "charStart": 1000, "charEnd": 1024, "pageStart": 4, "pageEnd": 4, "pdfUrl": "y"},
            ],
            "mode": "standard",
        },
        "meta": {"creditsRemaining": 498, "creditsConsumed": 0.5},
    }
    with respx.mock(base_url="https://api.vaquill.ai") as mock:
        mock.post("/v1/ask").respond(200, json=ask_response)
        frag = await vaquill_client.get_fragment("vq_abc123", "What is Article 14?")
    assert frag["text"] == "The correct excerpt here"
    assert frag["char_start"] == 1000
    assert frag["page_start"] == 4


@pytest.mark.asyncio
async def test_get_fragment_returns_empty_when_no_match(vaquill_client):
    ask_response = {
        "data": {"answer": "...", "sources": [{"caseId": "vq_other", "excerpt": "nope", "charStart": 0, "charEnd": 1, "pageStart": 1, "pageEnd": 1, "pdfUrl": "x"}], "mode": "standard"},
        "meta": {"creditsRemaining": 498},
    }
    with respx.mock(base_url="https://api.vaquill.ai") as mock:
        mock.post("/v1/ask").respond(200, json=ask_response)
        frag = await vaquill_client.get_fragment("vq_abc123", "q")
    assert frag == {"text": "", "char_start": None, "char_end": None, "page_start": None, "page_end": None}
```

**Step 2–5:** run/implement/run/commit.

```python
async def get_fragment(self, doc_id: str, query: str) -> dict:
    resp = await self._client.post(
        "/ask",
        json={
            "question": query,
            "mode": "standard",
            "sources": True,
            "maxSources": 10,
            "countryCode": "IN",
        },
    )
    resp.raise_for_status()
    sources = resp.json().get("data", {}).get("sources", [])
    for s in sources:
        if s.get("caseId") == doc_id:
            return {
                "text": s.get("excerpt", ""),
                "char_start": s.get("charStart"),
                "char_end": s.get("charEnd"),
                "page_start": s.get("pageStart"),
                "page_end": s.get("pageEnd"),
            }
    return {"text": "", "char_start": None, "char_end": None, "page_start": None, "page_end": None}
```

Commit: `feat(vaquill): implement get_fragment via Ask endpoint`

---

## Task 7: VaquillClient.get_court_copy() (TDD)

Returns the PDF URL from case-lookup as `{"type": "pdf_url", "value": <url>}`. Also update `IndianKanoonClient.get_court_copy()` return shape to `{"type": "html_base64", "value": <base64>}` **in the same commit** so downstream consumers can switch on `type`. Add a test for the IK change to prevent regression.

Commit: `refactor(external-doc): unify get_court_copy return shape across providers`

---

## Task 8: VaquillClient retry + circuit breaker wiring (TDD)

Mirror the IK reliability harness. Use `respx` to simulate consecutive 500s and assert: (a) 3 retries via tenacity, (b) circuit opens after 3 failures, (c) while open, calls short-circuit without hitting HTTP.

Commit: `feat(vaquill): add tenacity retry and circuit breaker`

---

## Task 9: VaquillClient error type mapping (TDD)

Map Vaquill error response `type` values to Python exceptions:
- `authentication_error` → raise at startup, not per-call (validate token on `__aenter__` or first call)
- `insufficient_credits` → `QuotaExceededError`
- `validation_error` → `ValueError`
- `service_unavailable` → trigger circuit breaker
- anything else → generic `VaquillAPIError`

Test each mapping with `respx`.

Commit: `feat(vaquill): map API error types to Python exceptions`

---

## Task 10: Protocol conformance test

**File:** `backend/tests/unit/test_vaquill_client.py` (extend)

```python
def test_vaquill_implements_external_doc_protocol():
    from app.core.interfaces.external_doc import ExternalDocProvider
    from app.core.providers.external.vaquill import VaquillClient
    assert isinstance.__wrapped__ if False else True  # runtime check
    assert issubclass(VaquillClient, ExternalDocProvider) or isinstance(
        VaquillClient.__new__(VaquillClient), ExternalDocProvider
    )
```

Or simpler — `@runtime_checkable` Protocol + `isinstance` check on an instance.

Commit: `test(vaquill): verify ExternalDocProvider Protocol conformance`

---

## Task 11: DI factory with None handling (TDD)

**Files:**
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/tests/unit/test_dependencies.py` (or create)

**Test:**

```python
def test_get_vaquill_client_returns_none_without_token(monkeypatch):
    monkeypatch.delenv("VAQUILL_API_TOKEN", raising=False)
    from app.core.dependencies import get_vaquill_client
    get_vaquill_client.cache_clear()
    assert get_vaquill_client() is None

def test_get_vaquill_client_returns_instance_with_token(monkeypatch):
    monkeypatch.setenv("VAQUILL_API_TOKEN", "vq_key_test")
    from app.core.dependencies import get_vaquill_client
    get_vaquill_client.cache_clear()
    client = get_vaquill_client()
    assert client is not None
```

**Implementation:**

```python
@lru_cache
def get_vaquill_client() -> ExternalDocProvider | None:
    if not settings.vaquill_api_token:
        return None
    from app.core.providers.external.vaquill import VaquillClient
    return VaquillClient()
```

Commit: `feat(di): add get_vaquill_client factory with graceful None`

---

## Task 12: vaquill_search_worker — cache + normalization (TDD)

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py`
- Create: `backend/tests/unit/test_vaquill_worker.py` (mirror `test_ik_worker.py`)

**Step 1: Write failing tests.** Mirror `test_ik_worker.py` structure. Cover:
- Happy path — dispatches to VaquillClient.search, returns `WorkerResult`
- Cache hit — second call with same filters does not hit VaquillClient
- Cache key includes `provider="vaquill"` (so IK and Vaquill caches don't collide)
- Filter propagation — court, date, boolean query flow from agent state to VaquillClient
- `None` client — worker short-circuits to empty `WorkerResult` with warning log
- `QuotaExceededError` — worker returns empty `WorkerResult` with `error` field set, pipeline continues

**Step 2: Run — expect fail**

**Step 3: Implement.** Copy `ik_search_worker` at [worker_nodes.py:497](../../backend/app/core/agents/nodes/worker_nodes.py#L497) wholesale, then:
- Replace `get_ik_client()` with `get_vaquill_client()`
- Replace `"ik"` with `"vaquill"` in cache key, source tag, log messages
- Remove any IK-specific fields (e.g., sentiment tags) from normalization
- Keep the per-query fragment budget identical to IK

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/tests/unit/test_vaquill_worker.py
git commit -m "feat(agents): add vaquill_search_worker with cache and budget"
```

---

## Task 13: Monthly query budget via Redis counter (TDD)

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py` (vaquill_search_worker)
- Modify: `backend/tests/unit/test_vaquill_worker.py`

Use `fakeredis` for tests. Key format `vaquill:budget:YYYY-MM`. TTL = 32 days. Increment before the Vaquill call. If `>= settings.vaquill_monthly_query_budget`, short-circuit.

**Test cases:**
- Under budget → call succeeds, counter increments
- At budget → call short-circuits, counter does not increment further
- New month → new key, fresh counter

Commit: `feat(vaquill): enforce monthly query budget via Redis counter`

---

## Task 14: Wire vaquill into dispatch_workers() gated by WorkerRegistry (TDD)

**Files:**
- Modify: `backend/app/core/agents/research.py`
- Modify: `backend/tests/integration/test_research_agent_v3.py`

**Step 1: Write failing integration tests**

```python
@pytest.mark.asyncio
async def test_dispatch_includes_vaquill_when_enabled(monkeypatch, minimal_agent_state):
    monkeypatch.setenv("VAQUILL_API_TOKEN", "vq_key_test")
    # ... build graph, drive through Stage 3 ...
    # Assert Send list contains both "ik_search_worker" and "vaquill_search_worker"

@pytest.mark.asyncio
async def test_dispatch_excludes_disabled_workers(monkeypatch, minimal_agent_state):
    monkeypatch.setenv("WORKER_IK_ENABLED", "false")
    monkeypatch.setenv("WORKER_GRAPH_ENABLED", "false")
    # ... assert Send list has no ik or graph workers ...

@pytest.mark.asyncio
async def test_dispatch_raises_when_all_disabled(monkeypatch, minimal_agent_state):
    for flag in ("IK", "VAQUILL", "CASE_LAW", "GRAPH", "NAMED_CASE", "STATUTE", "WEB_SEARCH"):
        monkeypatch.setenv(f"WORKER_{flag}_ENABLED", "false")
    with pytest.raises(NoWorkersEnabledError):
        # ... run dispatch_workers ...
```

**Step 2: Run — expect fail**

**Step 3: Implement**

In `research.py`, at the top of `dispatch_workers`, build the registry once and gate every `Send()`:

```python
from app.core.agents.worker_registry import WorkerRegistry
from app.core.config import settings as _settings

_registry = WorkerRegistry(_settings)

def dispatch_workers(state):
    _registry.assert_any_enabled()
    sends = []
    if _registry.is_enabled("ik"):
        sends.append(Send("ik_search_worker", ...))
    if _registry.is_enabled("vaquill"):
        sends.append(Send("vaquill_search_worker", ...))
    if _registry.is_enabled("case_law"):
        sends.append(Send("case_law_worker", ...))
    # ... etc for graph, named_case, statute, web_search
    return sends
```

Also register the new node in the LangGraph `StateGraph`:

```python
graph.add_node("vaquill_search_worker", vaquill_search_worker)
```

And add to `WORKER_TIMEOUTS`:

```python
WORKER_TIMEOUTS["vaquill_search_worker"] = 30.0
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add backend/app/core/agents/research.py backend/tests/integration/test_research_agent_v3.py
git commit -m "feat(agents): gate worker dispatch via WorkerRegistry"
```

---

## Task 15: Document env vars

**Files:**
- Modify: `.env.example` (or `backend/.env.example`)
- Modify: `docs/CLAUDE.md` (if it documents settings)

Add:

```bash
# --- Vaquill legal API (alternative/supplementary to Indian Kanoon) ---
# Get a free-tier key at https://www.vaquill.ai (500 credits, 100 req/day)
VAQUILL_API_TOKEN=
VAQUILL_RATE_LIMIT=2.0
VAQUILL_MONTHLY_QUERY_BUDGET=100

# --- Per-worker toggles for Stage 3 Investigate (all default true) ---
# Set any to "false" to disable that worker without code changes.
WORKER_IK_ENABLED=true
WORKER_VAQUILL_ENABLED=true
WORKER_CASE_LAW_ENABLED=true
WORKER_GRAPH_ENABLED=true
WORKER_NAMED_CASE_ENABLED=true
WORKER_STATUTE_ENABLED=true
WORKER_WEB_SEARCH_ENABLED=true
```

Commit: `docs: document Vaquill and worker toggle env vars`

---

## Task 16: Manual smoke test in dev

**Not automated.** After all above tasks merge:

1. Set `VAQUILL_API_TOKEN` in dev `.env`.
2. Start backend: `cd backend && uvicorn app.main:app --reload`.
3. Run 5 representative legal queries through the Research Agent end-to-end. Compare Vaquill vs IK worker output side-by-side in logs.
4. Verify:
   - Both workers execute in parallel
   - Vaquill returns Indian cases (re-confirm §Task 0 finding under real load)
   - Redis key `vaquill:budget:YYYY-MM` increments
   - Setting `WORKER_VAQUILL_ENABLED=false` + restart → Vaquill worker is silent, no errors
   - Setting all 7 flags false + restart → first request raises `NoWorkersEnabledError`
5. Record findings in `docs/plans/2026-04-16-vaquill-smoke-test-results.md` and commit.

---

## Task 17: Run full test suite + commit checkpoint

```bash
cd backend && pytest -xvs
```

Expected: all ~2185 existing tests still pass, plus ~30 new tests from Tasks 1–14.

If anything flakes, @superpowers:systematic-debugging before claiming done.

---

## Done criteria

- [ ] Task 0 verification findings doc committed and Indian scoping confirmed
- [ ] All 17 tasks complete with green tests
- [ ] `backend && pytest` passes on the full suite
- [ ] Feature flag `WORKER_VAQUILL_ENABLED=false` reverts to pure IK behavior
- [ ] Dev smoke test documented
- [ ] Design doc and plan doc both committed on the same branch

---

## What NOT to do (YAGNI guardrails)

- ❌ Do not implement `get_citation_graph()` — that's Option B, deferred.
- ❌ Do not touch `adversarial_search_node`.
- ❌ Do not touch `statute_lookup_node`.
- ❌ Do not add Protocol methods beyond the existing 5.
- ❌ Do not add a runtime admin toggle endpoint.
- ❌ Do not build a cost dashboard — log lines and Redis counters are enough.
- ❌ Do not refactor IK internals "while we're in there" — only touch `get_court_copy` return shape in Task 7, nothing else.
- ❌ Do not mock the database in any test — integration tests hit real PG/Redis per the project's feedback memory.
