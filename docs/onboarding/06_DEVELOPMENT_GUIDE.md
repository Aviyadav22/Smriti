# Development Guide — Smriti

---

## Code Style & Conventions

### Python (Backend)
- **Formatter/Linter:** ruff (replaces flake8 + isort + black)
- **Type Checker:** mypy (strict mode, pydantic plugin)
- **Line Length:** 100 characters
- **Target:** Python 3.12
- **Import Order:** stdlib → third-party → local (auto-sorted by ruff)
- **Naming:** snake_case for functions/variables, PascalCase for classes
- **Type Hints:** Required on all function signatures
- **Exceptions:** Never use bare `Exception` — use specific types
- **No `any` in TypeScript, no bare `Exception` in Python**
- **Async by default:** All database operations, external API calls use `async/await`

### TypeScript (Frontend)
- **Framework:** Next.js 16 with App Router
- **Linter:** ESLint with Next.js config
- **Styling:** Tailwind CSS utility classes
- **Components:** shadcn/ui (Radix-based)
- **Testing:** vitest (NOT jest)
- **Package Manager:** npm (NOT yarn, NOT pnpm)

### Key Rules (from CLAUDE.md)
1. Never call external services directly from routes — use interfaces
2. Never hardcode secrets — all via `settings`
3. Never construct raw SQL strings — use SQLAlchemy `text()` with parameters
4. Never use `any` in TypeScript
5. Every external service behind an interface (Protocol class)
6. All LLM prompts in `PROMPT_LIBRARY.md` and `core/legal/prompts.py`

---

## How to Add a New API Endpoint

### 1. Create or modify a route file

Location: `backend/app/api/routes/`

```python
# backend/app/api/routes/my_feature.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_async_session
from app.security.rbac import get_current_user
from app.security.auth import TokenPayload

router = APIRouter()

@router.get("/my-endpoint")
async def my_endpoint(
    db: AsyncSession = Depends(get_async_session),
    user: TokenPayload = Depends(get_current_user),  # Auth required
) -> dict:
    # Use db for PostgreSQL queries
    # Use dependencies for external services:
    #   from app.core.dependencies import get_llm, get_vector_store
    return {"result": "ok"}
```

### 2. Register the router in main.py

```python
# backend/app/main.py
from app.api.routes.my_feature import router as my_feature_router
app.include_router(my_feature_router, prefix="/api/v1/my-feature", tags=["my-feature"])
```

### 3. Add rate limiting (if needed)

```python
from app.security.rate_limiter import rate_limit_dependency

@router.get("/my-endpoint", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def my_endpoint(...):
    ...
```

### 4. Add tests

Location: `backend/tests/unit/test_my_feature.py`

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_my_endpoint():
    # Tests use pytest-asyncio with auto mode (no decorator needed in newer versions)
    ...
```

---

## How to Add a New Frontend Page

### 1. Create the page component

Location: `frontend/src/app/my-page/page.tsx`

```tsx
"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";

export default function MyPage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/my-feature/my-endpoint")
      .then(res => res.json())
      .then(setData);
  }, []);

  return <div>{/* your content */}</div>;
}
```

### 2. Add error/loading states (optional)

```
frontend/src/app/my-page/
  page.tsx       # Main page
  error.tsx      # Error boundary
  loading.tsx    # Loading skeleton
```

### 3. Add to navigation (if needed)

Edit `frontend/src/components/header.tsx` to add a nav link.

---

## How to Add a New External Service Provider

### 1. Define the interface

```python
# backend/app/core/interfaces/my_service.py
from typing import Protocol

class MyServiceProvider(Protocol):
    async def do_something(self, input: str) -> str: ...
```

### 2. Export from interfaces __init__

```python
# backend/app/core/interfaces/__init__.py
from .my_service import MyServiceProvider
```

### 3. Implement the provider

```python
# backend/app/core/providers/my_service/implementation.py
from app.core.interfaces import MyServiceProvider
from tenacity import retry, stop_after_attempt, wait_exponential

class ConcreteMyService:
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=2, max=60))
    async def do_something(self, input: str) -> str:
        # Always use tenacity retry for external calls
        ...
```

### 4. Add dependency factory

```python
# backend/app/core/dependencies.py
@lru_cache
def get_my_service() -> MyServiceProvider:
    from app.core.providers.my_service.implementation import ConcreteMyService
    return ConcreteMyService()
```

---

## How to Modify the RAG Pipeline

### Search Pipeline (`core/search/`)
- `query.py` — Change query understanding (LLM prompt, entity extraction)
- `hybrid.py` — Change search fusion (RRF weights, filter logic)
- `fulltext.py` — Change PostgreSQL FTS behavior

### Chat Pipeline (`core/chat/`)
- `rag.py` — Change context building, prompt construction, response streaming

### Ingestion Pipeline (`core/ingestion/`)
- `pipeline.py` — Main pipeline orchestration
- `chunker.py` — Chunking strategy (sizes, overlap, section detection)
- `metadata.py` — LLM metadata extraction prompts
- `pdf.py` — PDF text extraction

### Prompts
- `core/legal/prompts.py` — All LLM prompts (system prompts, extraction prompts)
- `docs/PROMPT_LIBRARY.md` — Prompt documentation

---

## How to Run Tests

### Backend

```bash
cd backend

# All tests
pytest -v --cov=app

# Unit tests only (fast, no infrastructure needed)
pytest tests/unit/ -v

# Integration tests (needs Docker services running)
pytest tests/integration/ -v -m integration

# Security tests
pytest tests/security/ -v -m security

# Single test file
pytest tests/unit/test_chunker.py -v

# With coverage report
pytest -v --cov=app --cov-report=html
```

**Test conventions:**
- `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed
- Timeout: 30s per test in CI
- Mocks: `pytest-mock` for patching
- Fixtures: conftest.py files at each test level
- **Never mock the database in integration tests** — use real PostgreSQL

### Frontend

```bash
cd frontend

# Watch mode (development)
npm test

# Single run (CI)
npm test -- --run

# With coverage
npm test -- --run --coverage
```

**Test conventions:**
- Framework: vitest (NOT jest)
- DOM: jsdom
- Component testing: @testing-library/react
- User interactions: @testing-library/user-event

---

## How to Debug Common Issues

### "Search returns no results"
1. Check Pinecone has vectors: look at index stats in Pinecone console
2. Check PostgreSQL has cases: `SELECT count(*) FROM cases`
3. Test embedding: verify Gemini API key works
4. Check logs: backend logs show search pipeline steps

### "Agent hangs at checkpoint"
1. The agent uses HITL `interrupt()` — it's waiting for user input
2. Frontend should show a checkpoint prompt
3. In dev, check LangGraph MemorySaver state

### "LLM returns empty/bad responses"
1. Check Gemini API key and rate limits
2. Look at the prompt in `core/legal/prompts.py`
3. Check `settings.gemini_temperature` (default 0.1 for factual)

### "Database migration fails"
1. Check PostgreSQL is running: `docker compose ps postgres`
2. Look at migration file in `backend/migrations/versions/`
3. Try: `alembic history` to see migration chain
4. Manual fix: `alembic stamp <revision>` to mark as applied

---

## Database Migrations

### Create a new migration
```bash
cd backend
alembic revision --autogenerate -m "add my_column to cases"
# Or: make migration msg="add my_column to cases"
```

### Apply migrations
```bash
alembic upgrade head
```

### Rollback one step
```bash
alembic downgrade -1
```

### View migration history
```bash
alembic history
alembic current
```

---

## Git Workflow

- **Main branch:** `master`
- **No feature branches visible** in current state (single developer)
- **Pre-commit hooks:** ruff lint, ruff format, mypy, detect-secrets, whitespace fixes
- **CI:** GitHub Actions runs on push to master / PRs targeting master
  - Backend: lint → audit → unit tests
  - Frontend: audit → test → build

---

## Ingestion (Adding New Cases)

### Single year
```bash
cd backend
python scripts/ingest_s3.py --year 2023
# Or: make ingest year=2023
```

### All years
```bash
make ingest-all
```

### Vertex AI batch (50% cheaper)
```bash
cd backend
GEMINI_USE_VERTEXAI=true python scripts/batch_ingest_vertex.py --year 2023
```

### Resume failed ingestion
```bash
python scripts/batch_ingest_vertex.py --resume <run_id>
```

### Statute ingestion
```bash
python scripts/ingest_statutes.py
```

---

## Key File Locations

| What | Where |
|------|-------|
| Backend entry point | `backend/app/main.py` |
| Settings/config | `backend/app/core/config.py` |
| API routes | `backend/app/api/routes/` |
| Database models | `backend/app/models/` |
| Interfaces (Protocol) | `backend/app/core/interfaces/` |
| Providers (implementations) | `backend/app/core/providers/` |
| Search pipeline | `backend/app/core/search/` |
| RAG chat | `backend/app/core/chat/rag.py` |
| Agent graphs | `backend/app/core/agents/` |
| Legal domain logic | `backend/app/core/legal/` |
| Ingestion pipeline | `backend/app/core/ingestion/` |
| Security | `backend/app/security/` |
| Migrations | `backend/migrations/versions/` |
| Frontend pages | `frontend/src/app/` |
| Frontend components | `frontend/src/components/` |
| API client | `frontend/src/lib/api.ts` |
| Auth context | `frontend/src/lib/auth-context.tsx` |
| Type definitions | `frontend/src/lib/types.ts` |
