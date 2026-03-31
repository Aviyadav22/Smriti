# Product Evolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement 7 features that take Smriti from polished engine to user-ready product.

**Architecture:** Each feature is independent and can be built sequentially. Features 1-2 are quick wins. Features 3-6 add new analytics/visualization surfaces. Feature 7 adds personalization. All follow existing patterns: FastAPI routes with dependency injection, SQLAlchemy models, Alembic migrations, React components, Vitest tests.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Neo4j, LangGraph, Next.js 16, TypeScript, Tailwind CSS, shadcn/ui, Vitest, python-docx, reportlab

**Design doc:** `docs/plans/2026-04-01-product-evolution-design.md`

---

## Feature 1: Fix Session Restore (Memo Not Showing)

### Task 1.1: Move memo-as-message save to reliable location (backend)

**Files:**
- Modify: `backend/app/api/routes/agents.py:328-367` (inside `_stream_agent_events` completion block)
- Modify: `backend/app/api/routes/agents.py:1515-1542` (remove from `_session_stream` generator)

**Step 1: Read the current code**

Read `agents.py:310-370` (the completion block inside `_stream_agent_events` where `result_data` is saved) and `agents.py:1505-1545` (the `_session_stream` generator post-stream memo save).

**Step 2: Move memo message save into `_stream_agent_events` completion block**

After line 353 (where `result_data` is committed to DB), add the memo-as-message save. This code currently lives at lines 1516-1542 inside the `_session_stream` generator. Move it here so it runs reliably regardless of client connection.

The key change: after `await db.commit()` for the execution update (line 353), check if there's a `session_id` in the config metadata and save the memo as an `AgentMessage`:

```python
                # After result_data is saved (line 353), save memo as AgentMessage
                session_id = config.get("metadata", {}).get("session_id")
                if session_id and memo:
                    try:
                        async with async_session_factory() as msg_db:
                            asst_msg = AgentMessage(
                                session_id=uuid.UUID(session_id) if isinstance(session_id, str) else session_id,
                                execution_id=exec_id,
                                role="assistant",
                                content=encrypt_field(memo),
                                sources=result_data.get("footnotes"),
                                message_type="memo",
                            )
                            msg_db.add(asst_msg)
                            await msg_db.execute(
                                text("UPDATE agent_sessions SET updated_at = NOW() WHERE id = :id"),
                                {"id": asst_msg.session_id},
                            )
                            await msg_db.commit()
                    except Exception:
                        logger.exception("Failed to save memo as agent message for exec %s", exec_id)
```

**Step 3: Remove the duplicate memo save from `_session_stream` generator**

In the `create_agent_session` endpoint, remove lines 1515-1542 (the `try...except` block after the `async for event` loop that saves the memo). Replace with a comment:

```python
        # Memo message is now saved inside _stream_agent_events completion block
```

**Step 4: Verify `session_id` is passed in config metadata**

Check that `create_agent_session` passes `session_id` in the config. Look at how `config` is built before calling `_stream_agent_events`. If it's not there, add it:

```python
config = {
    "configurable": {"thread_id": thread_id},
    "metadata": {"session_id": str(session.id)},
}
```

**Step 5: Run existing agent session tests**

Run: `cd backend && python -m pytest tests/unit/test_agent_session_routes.py tests/unit/test_agent_routes.py -v --timeout=30`

Expected: All existing tests pass.

**Step 6: Commit**

```bash
git add backend/app/api/routes/agents.py
git commit -m "fix: move memo-as-message save to reliable location in _stream_agent_events"
```

---

### Task 1.2: Add `result_data` to session detail endpoint (backend)

**Files:**
- Modify: `backend/app/api/routes/agents.py:1906-1931` (the `get_session` endpoint)
- Test: `backend/tests/unit/test_agent_session_routes.py`

**Step 1: Write the failing test**

Add to `test_agent_session_routes.py`:

```python
async def test_get_session_detail_includes_result_data(client, auth_headers, mock_db):
    """Session detail should include result_data from completed executions."""
    # Setup: mock a session with a completed execution that has result_data
    session_id = str(uuid.uuid4())
    exec_id = str(uuid.uuid4())
    user_id = "test-user-id"

    mock_session = {
        "id": uuid.UUID(session_id),
        "user_id": uuid.UUID(user_id),
        "agent_type": "research",
        "title": "Test Session",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    mock_execution = {
        "id": uuid.UUID(exec_id),
        "status": "completed",
        "input_data": {"query": "test"},
        "result_data": {"memo": "# Test Memo\n\nThis is a test.", "confidence": 0.85, "footnotes": []},
        "created_at": datetime.now(),
        "completed_at": datetime.now(),
    }

    # Configure mock_db to return these
    # (Follow existing test patterns in the file for DB mocking)

    response = await client.get(f"/api/agents/sessions/{session_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["executions"]) == 1
    assert data["executions"][0]["result_data"]["memo"] == "# Test Memo\n\nThis is a test."
    assert data["executions"][0]["result_data"]["confidence"] == 0.85
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_agent_session_routes.py::test_get_session_detail_includes_result_data -v`

Expected: FAIL — `result_data` not in execution response.

**Step 3: Add `result_data` to the session detail query**

In `agents.py`, modify the `get_session` endpoint. Change the execution query at line 1907:

```python
    exec_result = await db.execute(
        text(
            "SELECT id, status, input_data, result_data, created_at, completed_at "
            "FROM agent_executions WHERE session_id = :sid ORDER BY created_at ASC"
        ),
        {"sid": sess_uuid},
    )
    executions = [
        {
            "id": str(e["id"]),
            "status": e["status"],
            "input_data": e["input_data"],
            "result_data": e["result_data"],
            "created_at": str(e["created_at"]),
            "completed_at": str(e["completed_at"]) if e["completed_at"] else None,
        }
        for e in exec_result.mappings().all()
    ]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_agent_session_routes.py::test_get_session_detail_includes_result_data -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/api/routes/agents.py backend/tests/unit/test_agent_session_routes.py
git commit -m "fix: include result_data in session detail endpoint response"
```

---

### Task 1.3: Update frontend `loadSession()` with execution fallback

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx:223-251` (the `loadSession` function)
- Modify: `frontend/src/lib/api.ts:1014-1018` (update return type for `getAgentSessionDetail`)
- Modify: `frontend/src/lib/types.ts` (add execution result_data type)

**Step 1: Update `getAgentSessionDetail` return type**

In `frontend/src/lib/types.ts`, add:

```typescript
export interface SessionDetailExecution {
    id: string;
    status: string;
    input_data: Record<string, unknown>;
    result_data: {
        memo?: string;
        confidence?: number;
        confidence_breakdown?: {
            data_confidence?: number;
            legal_confidence?: number;
            consistency_confidence?: number;
        };
        footnotes?: ResearchFootnote[];
        research_audit?: ResearchAudit;
    } | null;
    created_at: string;
    completed_at: string | null;
}

export interface SessionDetail {
    id: string;
    agent_type: string;
    title: string;
    created_at: string;
    updated_at: string;
    executions: SessionDetailExecution[];
}
```

**Step 2: Update `getAgentSessionDetail` in `api.ts`**

```typescript
export async function getAgentSessionDetail(
    sessionId: string,
): Promise<SessionDetail> {
    return apiFetch<SessionDetail>(`/agents/sessions/${sessionId}`);
}
```

**Step 3: Update `loadSession()` in `research/page.tsx`**

Replace the `loadSession` function (lines 223-251) with:

```typescript
const loadSession = useCallback(async (sid: string) => {
    setSessionId(sid);
    setIsFollowUp(true);
    setError(null);
    try {
        // Fetch messages and session detail in parallel
        const [messages, detail] = await Promise.all([
            getAgentSessionMessages(sid),
            getAgentSessionDetail(sid),
        ]);
        setSessionMessages(messages);

        // Try to get memo from messages first
        const lastMemo = [...messages].reverse().find(
            (m) => m.role === "assistant" && m.message_type === "memo",
        );

        if (lastMemo) {
            setMemo(lastMemo.content);
            if (lastMemo.sources && lastMemo.sources.length > 0) {
                setFootnotes(lastMemo.sources as ResearchFootnote[]);
            }
        }

        // Fallback: get memo from latest completed execution's result_data
        const completedExec = [...(detail.executions || [])].reverse().find(
            (e) => e.status === "completed" && e.result_data?.memo,
        );

        if (completedExec?.result_data) {
            const rd = completedExec.result_data;
            setExecutionId(completedExec.id);

            // Use execution data if messages didn't have the memo
            if (!lastMemo && rd.memo) {
                setMemo(rd.memo);
            }
            if (rd.footnotes && rd.footnotes.length > 0 && (!lastMemo?.sources || lastMemo.sources.length === 0)) {
                setFootnotes(rd.footnotes);
            }
            // Always restore these from execution (messages don't have them)
            if (rd.confidence !== undefined) {
                setConfidence(rd.confidence);
            }
            if (rd.confidence_breakdown) {
                setConfidenceBreakdown(rd.confidence_breakdown);
            }
            if (rd.research_audit) {
                setResearchAudit(rd.research_audit);
            }
        }

        // Set query from first user message
        const firstQuery = messages.find(
            (m) => m.role === "user" && m.message_type === "query",
        );
        if (firstQuery) setQuery(firstQuery.content);
    } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load session";
        setError(msg);
    }
}, []);
```

**Step 4: Add imports if needed**

Ensure `SessionDetail` and `SessionDetailExecution` are imported in `page.tsx`.

**Step 5: Run frontend tests**

Run: `cd frontend && npx vitest run --reporter=verbose 2>&1 | head -50`

Expected: All existing tests pass.

**Step 6: Commit**

```bash
git add frontend/src/app/agents/research/page.tsx frontend/src/lib/api.ts frontend/src/lib/types.ts
git commit -m "fix: restore full memo + metadata when loading previous sessions"
```

---

## Feature 2: Share Research Memo via Link

### Task 2.1: Database migration for `shared_memos` table

**Files:**
- Create: `backend/migrations/versions/037_shared_memos.py`

**Step 1: Create migration**

```python
"""Add shared_memos table for public memo sharing.

Revision ID: 037
Revises: 036
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "037"
down_revision = "036"


def upgrade() -> None:
    op.create_table(
        "shared_memos",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("execution_id", UUID(as_uuid=True), sa.ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("share_token", sa.String(32), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("view_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_shared_memos_token", "shared_memos", ["share_token"], postgresql_where=sa.text("is_active = true"))
    op.create_index("idx_shared_memos_user", "shared_memos", ["user_id"])
    op.create_index("idx_shared_memos_execution", "shared_memos", ["execution_id"], unique=True, postgresql_where=sa.text("is_active = true"))


def downgrade() -> None:
    op.drop_index("idx_shared_memos_execution", table_name="shared_memos")
    op.drop_index("idx_shared_memos_user", table_name="shared_memos")
    op.drop_index("idx_shared_memos_token", table_name="shared_memos")
    op.drop_table("shared_memos")
```

**Step 2: Run migration**

Run: `cd backend && alembic upgrade head`

Expected: Migration applies successfully.

**Step 3: Commit**

```bash
git add backend/migrations/versions/037_shared_memos.py
git commit -m "feat(db): add shared_memos table for public memo sharing"
```

---

### Task 2.2: SQLAlchemy model for `SharedMemo`

**Files:**
- Create: `backend/app/models/shared_memo.py`
- Modify: `backend/app/models/__init__.py` (add import)

**Step 1: Create the model**

```python
"""SharedMemo model for public memo sharing."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class SharedMemo(Base):
    __tablename__ = "shared_memos"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    execution_id = Column(UUID(as_uuid=True), ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    share_token = Column(String(32), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    view_count = Column(Integer, server_default=text("0"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
```

**Step 2: Add import to `__init__.py`**

Add `from app.models.shared_memo import SharedMemo` to `backend/app/models/__init__.py`.

**Step 3: Commit**

```bash
git add backend/app/models/shared_memo.py backend/app/models/__init__.py
git commit -m "feat(models): add SharedMemo SQLAlchemy model"
```

---

### Task 2.3: Backend share endpoints

**Files:**
- Create: `backend/app/api/routes/sharing.py`
- Modify: `backend/app/api/routes/__init__.py` or `backend/app/main.py` (register router)
- Test: `backend/tests/unit/test_sharing_routes.py`

**Step 1: Write failing tests**

Create `backend/tests/unit/test_sharing_routes.py`:

```python
"""Tests for memo sharing endpoints."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.routes.sharing import router


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


class TestCreateShare:
    async def test_create_share_returns_token(self, client, auth_headers, mock_db):
        exec_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/agents/research/{exec_id}/share",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "share_token" in data
        assert "share_url" in data

    async def test_create_share_requires_auth(self, client):
        exec_id = str(uuid.uuid4())
        response = await client.post(f"/api/agents/research/{exec_id}/share")
        assert response.status_code == 401

    async def test_create_share_rejects_non_owner(self, client, auth_headers, mock_db):
        # Execution owned by different user
        exec_id = str(uuid.uuid4())
        # Configure mock to return different user_id
        response = await client.post(
            f"/api/agents/research/{exec_id}/share",
            headers=auth_headers,
        )
        assert response.status_code == 403


class TestGetSharedMemo:
    async def test_get_shared_memo_public(self, client):
        """Public endpoint — no auth required."""
        response = await client.get("/api/shared/invalid-token")
        assert response.status_code == 404

    async def test_get_shared_memo_increments_view_count(self, client, mock_db):
        # Setup valid share in mock_db
        pass  # Fill based on existing test patterns


class TestRevokeShare:
    async def test_revoke_share(self, client, auth_headers, mock_db):
        exec_id = str(uuid.uuid4())
        response = await client.delete(
            f"/api/agents/research/{exec_id}/share",
            headers=auth_headers,
        )
        # Should succeed or 404 if no share exists
        assert response.status_code in (200, 404)
```

**Step 2: Implement the share routes**

Create `backend/app/api/routes/sharing.py`:

```python
"""Memo sharing routes — create, view (public), revoke shared memos."""
from __future__ import annotations

import json
import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.models.shared_memo import SharedMemo
from app.security.auth import TokenPayload, get_current_user
from app.security.encryption import safe_decrypt
from app.security.rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)

router = APIRouter()


class ShareRequest(BaseModel):
    expires_in_days: int | None = None


# ---- Create share ----

@router.post(
    "/agents/research/{execution_id}/share",
    dependencies=[Depends(rate_limit_dependency("20/minute"))],
)
async def create_share(
    execution_id: str,
    body: ShareRequest | None = None,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or return existing share link for a research memo."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid execution_id format.")

    # Verify ownership and completion
    result = await db.execute(
        text(
            "SELECT ae.user_id, ae.status, ae.result_data, ass.title "
            "FROM agent_executions ae "
            "JOIN agent_sessions ass ON ae.session_id = ass.id "
            "WHERE ae.id = :id"
        ),
        {"id": exec_uuid},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Execution not found.")
    if str(row["user_id"]) != user.sub:
        raise HTTPException(status_code=403, detail="Access denied.")
    if row["status"] != "completed":
        raise HTTPException(status_code=400, detail="Can only share completed research.")

    # Check for existing active share
    existing = await db.execute(
        text("SELECT id, share_token, expires_at FROM shared_memos WHERE execution_id = :eid AND is_active = true"),
        {"eid": exec_uuid},
    )
    existing_row = existing.mappings().one_or_none()
    if existing_row:
        return {
            "share_id": str(existing_row["id"]),
            "share_token": existing_row["share_token"],
            "share_url": f"/shared/{existing_row['share_token']}",
            "expires_at": str(existing_row["expires_at"]) if existing_row["expires_at"] else None,
        }

    # Create new share
    token = secrets.token_urlsafe(16)
    expires_at = None
    if body and body.expires_in_days:
        from datetime import datetime, timedelta, timezone
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    share = SharedMemo(
        execution_id=exec_uuid,
        user_id=uuid.UUID(user.sub),
        share_token=token,
        expires_at=expires_at,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)

    return {
        "share_id": str(share.id),
        "share_token": token,
        "share_url": f"/shared/{token}",
        "expires_at": str(expires_at) if expires_at else None,
    }


# ---- Get share status ----

@router.get(
    "/agents/research/{execution_id}/share",
    dependencies=[Depends(rate_limit_dependency("60/minute"))],
)
async def get_share_status(
    execution_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check if an active share exists for this execution."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid execution_id format.")

    result = await db.execute(
        text(
            "SELECT sm.id, sm.share_token, sm.expires_at, sm.view_count, sm.created_at "
            "FROM shared_memos sm "
            "JOIN agent_executions ae ON sm.execution_id = ae.id "
            "JOIN agent_sessions ass ON ae.session_id = ass.id "
            "WHERE sm.execution_id = :eid AND sm.is_active = true AND ass.user_id = :uid"
        ),
        {"eid": exec_uuid, "uid": uuid.UUID(user.sub)},
    )
    row = result.mappings().one_or_none()
    if row is None:
        return {"shared": False}

    return {
        "shared": True,
        "share_id": str(row["id"]),
        "share_token": row["share_token"],
        "share_url": f"/shared/{row['share_token']}",
        "expires_at": str(row["expires_at"]) if row["expires_at"] else None,
        "view_count": row["view_count"],
        "created_at": str(row["created_at"]),
    }


# ---- Revoke share ----

@router.delete(
    "/agents/research/{execution_id}/share",
    dependencies=[Depends(rate_limit_dependency("20/minute"))],
)
async def revoke_share(
    execution_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deactivate share for this execution."""
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid execution_id format.")

    result = await db.execute(
        text(
            "UPDATE shared_memos SET is_active = false "
            "WHERE execution_id = :eid AND is_active = true "
            "AND user_id = :uid "
            "RETURNING id"
        ),
        {"eid": exec_uuid, "uid": uuid.UUID(user.sub)},
    )
    row = result.mappings().one_or_none()
    await db.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="No active share found.")
    return {"revoked": True, "share_id": str(row["id"])}


# ---- Public memo viewer ----

@router.get("/shared/{token}", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_shared_memo(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public endpoint — view a shared research memo without authentication."""
    result = await db.execute(
        text(
            "SELECT sm.id, sm.execution_id, sm.expires_at, sm.view_count, "
            "ae.result_data, ass.title, ass.agent_type "
            "FROM shared_memos sm "
            "JOIN agent_executions ae ON sm.execution_id = ae.id "
            "JOIN agent_sessions ass ON ae.session_id = ass.id "
            "WHERE sm.share_token = :token AND sm.is_active = true"
        ),
        {"token": token},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Shared memo not found or expired.")

    # Check expiry
    if row["expires_at"]:
        from datetime import datetime, timezone
        if datetime.now(timezone.utc) > row["expires_at"]:
            raise HTTPException(status_code=404, detail="Shared memo has expired.")

    # Increment view count
    await db.execute(
        text("UPDATE shared_memos SET view_count = view_count + 1 WHERE id = :id"),
        {"id": row["id"]},
    )
    await db.commit()

    rd = row["result_data"] if isinstance(row["result_data"], dict) else json.loads(row["result_data"]) if row["result_data"] else {}

    return {
        "title": row["title"],
        "memo": rd.get("memo", ""),
        "footnotes": rd.get("footnotes", []),
        "confidence": rd.get("confidence"),
        "agent_type": row["agent_type"],
        "created_at": str(row.get("created_at", "")),
    }
```

**Step 3: Register the router**

In `backend/app/main.py`, add:

```python
from app.api.routes.sharing import router as sharing_router
app.include_router(sharing_router, prefix="/api", tags=["sharing"])
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_sharing_routes.py -v --timeout=30`

**Step 5: Commit**

```bash
git add backend/app/api/routes/sharing.py backend/app/main.py backend/tests/unit/test_sharing_routes.py
git commit -m "feat: add memo sharing endpoints (create, view, revoke)"
```

---

### Task 2.4: Frontend — Share button + public viewer page

**Files:**
- Modify: `frontend/src/components/agent-memo-viewer.tsx` (add share button)
- Modify: `frontend/src/lib/api.ts` (add share API functions)
- Create: `frontend/src/app/shared/[token]/page.tsx` (public viewer)

**Step 1: Add API functions**

In `frontend/src/lib/api.ts`, add:

```typescript
export async function createMemoShare(executionId: string): Promise<{ share_token: string; share_url: string; share_id: string }> {
    return apiFetch(`/agents/research/${executionId}/share`, { method: "POST" });
}

export async function getMemoShareStatus(executionId: string): Promise<{ shared: boolean; share_url?: string; share_token?: string; view_count?: number }> {
    return apiFetch(`/agents/research/${executionId}/share`);
}

export async function revokeMemoShare(executionId: string): Promise<{ revoked: boolean }> {
    return apiFetch(`/agents/research/${executionId}/share`, { method: "DELETE" });
}

export async function getSharedMemo(token: string): Promise<{ title: string; memo: string; footnotes: unknown[]; confidence: number | null; agent_type: string }> {
    // Public endpoint — no auth header
    const res = await fetch(`${API_BASE}/shared/${token}`);
    if (!res.ok) throw new Error("Memo not found or expired");
    return res.json();
}
```

**Step 2: Add share button to `AgentMemoViewer`**

Add a "Share" button next to the existing export buttons. When clicked, calls `createMemoShare(executionId)`, copies the share URL to clipboard, and shows a toast.

Props needed: `executionId` (already passed), add `onShare?: (url: string) => void` optional callback.

**Step 3: Create public viewer page**

Create `frontend/src/app/shared/[token]/page.tsx`:

```typescript
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { getSharedMemo } from "@/lib/api";

export default function SharedMemoPage() {
    const { token } = useParams<{ token: string }>();
    const [data, setData] = useState<{
        title: string;
        memo: string;
        footnotes: unknown[];
        confidence: number | null;
    } | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!token) return;
        getSharedMemo(token)
            .then(setData)
            .catch(() => setError("This memo is no longer available or the link has expired."))
            .finally(() => setLoading(false));
    }, [token]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Card className="max-w-md">
                    <CardContent className="pt-6 text-center">
                        <h2 className="text-xl font-semibold mb-2">Memo Not Found</h2>
                        <p className="text-muted-foreground">{error}</p>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background">
            <header className="border-b px-6 py-4">
                <h1 className="text-lg font-semibold">NeetiQ — Shared Research Memo</h1>
            </header>
            <main className="max-w-4xl mx-auto px-6 py-8">
                <h2 className="text-2xl font-bold mb-6">{data.title}</h2>
                <Card>
                    <CardContent className="pt-6">
                        <AgentMemoViewer
                            content={data.memo}
                            confidence={data.confidence ?? undefined}
                            maxFootnote={data.footnotes?.length ?? 0}
                            footnotes={data.footnotes as any[]}
                        />
                    </CardContent>
                </Card>
            </main>
            <footer className="border-t px-6 py-4 text-center text-sm text-muted-foreground">
                Powered by <strong>NeetiQ</strong> — AI Legal Research for India
            </footer>
        </div>
    );
}
```

**Step 4: Run frontend tests**

Run: `cd frontend && npx vitest run --reporter=verbose 2>&1 | head -50`

**Step 5: Commit**

```bash
git add frontend/src/components/agent-memo-viewer.tsx frontend/src/lib/api.ts frontend/src/app/shared/
git commit -m "feat: add memo sharing UI — share button, public viewer page"
```

---

## Feature 3: Judge Prediction Model

### Task 3.1: Prediction service

**Files:**
- Create: `backend/app/core/analytics/judge_prediction.py`
- Test: `backend/tests/unit/test_judge_prediction.py`

**Step 1: Write failing tests**

Create `backend/tests/unit/test_judge_prediction.py`:

```python
"""Tests for judge prediction service."""
import pytest
from unittest.mock import AsyncMock

from app.core.analytics.judge_prediction import predict_outcome, JudgePrediction


class TestPredictOutcome:
    async def test_basic_prediction(self, mock_db):
        """Returns prediction with probabilities when sufficient data."""
        # Mock DB to return disposal counts: 30 Dismissed, 15 Allowed, 5 Partly Allowed
        result = await predict_outcome(
            db=mock_db,
            judges=["Justice A"],
            case_type="Criminal Appeal",
        )
        assert isinstance(result, JudgePrediction)
        assert result.predicted_outcome in ("Dismissed", "Allowed", "Partly Allowed")
        assert 0.0 <= result.confidence <= 1.0
        assert result.sample_size > 0
        assert len(result.caveats) > 0

    async def test_low_sample_size_caveat(self, mock_db):
        """Low confidence when fewer than 10 cases."""
        # Mock DB to return only 5 cases
        result = await predict_outcome(
            db=mock_db,
            judges=["Justice B"],
            case_type="Writ Petition",
        )
        assert result.confidence < 0.5
        assert any("historical cases" in c.lower() for c in result.caveats)

    async def test_no_data_returns_none(self, mock_db):
        """Returns None when no matching cases found."""
        # Mock DB to return 0 cases
        result = await predict_outcome(
            db=mock_db,
            judges=["Justice Unknown"],
            case_type="Criminal Appeal",
        )
        assert result is None

    async def test_act_specific_factor(self, mock_db):
        """Act-specific patterns appear in factors."""
        result = await predict_outcome(
            db=mock_db,
            judges=["Justice A"],
            case_type="Criminal Appeal",
            acts=["NDPS Act"],
        )
        if result and result.sample_size >= 10:
            act_factor = [f for f in result.factors if "NDPS" in f.detail]
            assert len(act_factor) > 0

    async def test_multi_judge_bench(self, mock_db):
        """Bench composition is a factor when multiple judges."""
        result = await predict_outcome(
            db=mock_db,
            judges=["Justice A", "Justice B"],
            case_type="Criminal Appeal",
        )
        if result:
            bench_factor = [f for f in result.factors if "bench" in f.name.lower()]
            # May or may not have bench factor depending on data
            assert isinstance(result.factors, list)
```

**Step 2: Implement the prediction service**

Create `backend/app/core/analytics/judge_prediction.py`:

```python
"""Judge outcome prediction based on historical disposal patterns.

Statistical heuristic model — NOT machine learning. Uses existing case metadata
to compute weighted outcome probabilities for a given judge + case_type combination.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MIN_SAMPLE_SIZE = 3
LOW_CONFIDENCE_THRESHOLD = 10
TEMPORAL_DECAY_YEARS = 3
TEMPORAL_WEIGHT_MULTIPLIER = 2.0


@dataclass
class Factor:
    name: str
    impact: str  # "strong", "moderate", "weak"
    detail: str


@dataclass
class JudgePrediction:
    predicted_outcome: str
    outcome_probabilities: dict[str, float]
    confidence: float
    sample_size: int
    factors: list[Factor] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


async def predict_outcome(
    *,
    db: AsyncSession,
    judges: list[str],
    case_type: str,
    jurisdiction: str | None = None,
    acts: list[str] | None = None,
    bench_type: str | None = None,
) -> JudgePrediction | None:
    """Predict case outcome based on judge's historical disposal patterns.

    Returns None if no matching cases found.
    """
    if not judges or not case_type:
        return None

    factors: list[Factor] = []

    # Step 1: Base rate — disposal counts for judge + case_type
    base_query = (
        "SELECT disposal_nature, decision_date, COUNT(*) as cnt "
        "FROM cases WHERE :judge = ANY(judge) "
        "AND case_type = :case_type "
        "AND disposal_nature IS NOT NULL "
    )
    params: dict = {"judge": judges[0], "case_type": case_type}

    if jurisdiction:
        base_query += "AND jurisdiction = :jurisdiction "
        params["jurisdiction"] = jurisdiction

    base_query += "GROUP BY disposal_nature, decision_date"

    result = await db.execute(text(base_query), params)
    rows = result.mappings().all()

    if not rows:
        return None

    # Apply temporal weighting
    from datetime import date
    today = date.today()
    weighted_counts: dict[str, float] = {}
    total_weighted = 0.0
    raw_count = 0

    for row in rows:
        outcome = row["disposal_nature"]
        decision_date = row["decision_date"]
        count = row["cnt"]
        raw_count += count

        # Temporal decay: recent cases weighted more
        weight = 1.0
        if decision_date:
            years_ago = (today - decision_date).days / 365.25
            if years_ago <= TEMPORAL_DECAY_YEARS:
                weight = TEMPORAL_WEIGHT_MULTIPLIER

        weighted_counts[outcome] = weighted_counts.get(outcome, 0.0) + count * weight
        total_weighted += count * weight

    if raw_count < MIN_SAMPLE_SIZE:
        return None

    # Normalize to probabilities
    probabilities = {k: v / total_weighted for k, v in weighted_counts.items()}
    predicted = max(probabilities, key=probabilities.get)

    factors.append(Factor(
        name=f"Disposal pattern for {case_type}",
        impact="strong",
        detail=f"{probabilities.get(predicted, 0):.0%} {predicted.lower()} rate ({raw_count} cases)",
    ))

    # Step 2: Act-specific adjustment
    if acts:
        for act in acts[:3]:  # Cap at 3 acts
            act_result = await db.execute(
                text(
                    "SELECT disposal_nature, COUNT(*) as cnt "
                    "FROM cases WHERE :judge = ANY(judge) "
                    "AND :act = ANY(acts_cited) "
                    "AND disposal_nature IS NOT NULL "
                    "GROUP BY disposal_nature"
                ),
                {"judge": judges[0], "act": act},
            )
            act_rows = act_result.mappings().all()
            act_total = sum(r["cnt"] for r in act_rows)
            if act_total >= 5:
                act_probs = {r["disposal_nature"]: r["cnt"] / act_total for r in act_rows}
                act_predicted = max(act_probs, key=act_probs.get)
                factors.append(Factor(
                    name=f"{act} cases",
                    impact="moderate" if act_total >= 10 else "weak",
                    detail=f"{act_probs.get(act_predicted, 0):.0%} {act_predicted.lower()} ({act_total} cases)",
                ))
                # Blend: weighted average based on act sample size
                blend_weight = min(act_total / 30, 0.4)
                for outcome in set(list(probabilities.keys()) + list(act_probs.keys())):
                    base = probabilities.get(outcome, 0.0)
                    act_p = act_probs.get(outcome, 0.0)
                    probabilities[outcome] = base * (1 - blend_weight) + act_p * blend_weight

    # Step 3: Bench composition
    if len(judges) > 1:
        bench_result = await db.execute(
            text(
                "SELECT disposal_nature, COUNT(*) as cnt "
                "FROM cases WHERE judge @> :judges "
                "AND disposal_nature IS NOT NULL "
                "GROUP BY disposal_nature"
            ),
            {"judges": judges},
        )
        bench_rows = bench_result.mappings().all()
        bench_total = sum(r["cnt"] for r in bench_rows)
        if bench_total >= 5:
            bench_probs = {r["disposal_nature"]: r["cnt"] / bench_total for r in bench_rows}
            bench_pred = max(bench_probs, key=bench_probs.get)
            factors.append(Factor(
                name="Bench composition history",
                impact="moderate" if bench_total >= 10 else "weak",
                detail=f"This bench: {bench_probs.get(bench_pred, 0):.0%} {bench_pred.lower()} ({bench_total} cases)",
            ))

    # Recalculate predicted outcome after blending
    predicted = max(probabilities, key=probabilities.get)

    # Step 4: Confidence calculation
    consistency = probabilities.get(predicted, 0)
    size_factor = min(raw_count / 50, 1.0)
    confidence = round(consistency * 0.6 + size_factor * 0.4, 2)

    # Caveats
    caveats = [
        f"Based on {raw_count} historical cases from Supreme Court records.",
        "Past judicial patterns do not predict future outcomes.",
        "This is a statistical summary, not legal advice.",
    ]
    if raw_count < LOW_CONFIDENCE_THRESHOLD:
        caveats.insert(0, f"Low sample size ({raw_count} cases) — prediction reliability is limited.")
        confidence = min(confidence, 0.4)

    return JudgePrediction(
        predicted_outcome=predicted,
        outcome_probabilities={k: round(v, 3) for k, v in sorted(probabilities.items(), key=lambda x: -x[1])},
        confidence=confidence,
        sample_size=raw_count,
        factors=factors,
        caveats=caveats,
    )
```

**Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_judge_prediction.py -v`

**Step 4: Commit**

```bash
git add backend/app/core/analytics/judge_prediction.py backend/tests/unit/test_judge_prediction.py
git commit -m "feat: add judge prediction service with statistical heuristic model"
```

---

### Task 3.2: Prediction API endpoint

**Files:**
- Modify: `backend/app/api/routes/judges.py` (add prediction endpoint)
- Test: `backend/tests/unit/test_judge_routes.py` (add prediction test)

**Step 1: Add endpoint to judges router**

```python
@router.get("/judges/predict", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def predict_judge_outcome(
    judges: str = Query(..., description="Comma-separated judge names"),
    case_type: str = Query(..., description="Case type"),
    acts: str | None = Query(None, description="Comma-separated acts"),
    jurisdiction: str | None = Query(None),
    bench_type: str | None = Query(None),
    user: TokenPayload = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Predict likely outcome based on judge's historical patterns."""
    from app.core.analytics.judge_prediction import predict_outcome

    judge_list = [j.strip() for j in judges.split(",") if j.strip()]
    act_list = [a.strip() for a in acts.split(",") if a.strip()] if acts else None

    result = await predict_outcome(
        db=db,
        judges=judge_list,
        case_type=case_type,
        jurisdiction=jurisdiction,
        acts=act_list,
        bench_type=bench_type,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Insufficient data for prediction.")

    return {
        "predicted_outcome": result.predicted_outcome,
        "outcome_probabilities": result.outcome_probabilities,
        "confidence": result.confidence,
        "sample_size": result.sample_size,
        "factors": [{"name": f.name, "impact": f.impact, "detail": f.detail} for f in result.factors],
        "caveats": result.caveats,
    }
```

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_judge_routes.py -v`

**Step 3: Commit**

```bash
git add backend/app/api/routes/judges.py backend/tests/unit/test_judge_routes.py
git commit -m "feat: add judge prediction API endpoint"
```

---

### Task 3.3: Frontend prediction card

**Files:**
- Create: `frontend/src/components/judge-prediction-card.tsx`
- Modify: `frontend/src/app/judge/[name]/page.tsx` (integrate card)
- Modify: `frontend/src/lib/api.ts` (add prediction API call)

This is a UI component. Add an API function `getJudgePrediction(params)` in `api.ts`, create a `JudgePredictionCard` component that shows outcome probabilities as horizontal bars, factors as a list, and caveats in a muted section. Integrate it into the judge profile page.

**Commit:**

```bash
git commit -m "feat: add judge prediction card to judge profile page"
```

---

## Feature 4: Argument Builder (Strategy Agent Upgrade)

### Task 4.1: Update `StrategyState` with new fields

**Files:**
- Modify: `backend/app/core/agents/state.py:224-246`

**Step 1: Add new fields**

```python
class StrategyState(TypedDict):
    """State for the Strategy/Argument Builder Agent graph."""
    case_facts: str
    target_judge: str
    target_bench: str
    target_court: str
    desired_relief: str
    language: str
    # Produced by nodes:
    fact_analysis: dict
    legal_elements: list[dict]           # NEW: from element_decomposition
    judge_profile: dict
    search_results: list[dict]
    precedent_map: list[dict]
    strength_assessment: dict
    legal_arguments: list[dict]
    irac_arguments: list[dict]           # NEW: structured IRAC format
    counter_arguments: list[dict]
    adversarial_results: list[dict]      # NEW: evidence-backed counter-arguments
    judge_considerations: list[dict]
    procedural_suggestions: list[str]
    argument_order: list[int]            # NEW: optimal ordering indices
    strategy_memo: str
    confidence: float
    messages: Annotated[list[dict], operator.add]
    iteration: int
    error: str
```

**Step 2: Commit**

```bash
git add backend/app/core/agents/state.py
git commit -m "feat: add IRAC, adversarial, element decomposition fields to StrategyState"
```

---

### Task 4.2: Add IRAC argument generation prompts

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (add new prompts)

**Step 1: Add IRAC prompt and schema**

After the existing STRATEGY_ARGUMENTS constants, add:

```python
STRATEGY_IRAC_ARGUMENTS_SYSTEM: Final[str] = """\
You are an expert Indian litigation strategist constructing arguments in IRAC format \
(Issue, Rule, Application, Conclusion). Given case facts, legal elements, relevant \
precedents, and a strength assessment, generate structured legal arguments.

Rules:
- Each argument MUST follow IRAC structure strictly.
- Issue: State the specific legal question in one clear sentence.
- Rule: Cite the statute section AND binding precedent(s) from the provided context ONLY. \
Include bench strength. NEVER fabricate citations.
- Application: Show exactly how the client's facts satisfy or trigger the rule. Be specific.
- Conclusion: State the argued outcome in one sentence.
- Rank authorities: BINDING (Supreme Court) > PERSUASIVE (High Court) > DISTINGUISHABLE.
- Consider IPC→BNS and CrPC→BNSS transitions where applicable.
- Order arguments by effectiveness (strongest first).
"""

STRATEGY_IRAC_ARGUMENTS_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "irac_arguments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "issue": {"type": "string"},
                    "rule": {"type": "string"},
                    "rule_authorities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "citation": {"type": "string"},
                                "strength": {"type": "string", "enum": ["BINDING", "PERSUASIVE", "DISTINGUISHABLE"]},
                                "bench_size": {"type": "integer", "nullable": True},
                            },
                            "required": ["citation", "strength"],
                        },
                    },
                    "statutory_basis": {"type": "string"},
                    "application": {"type": "string"},
                    "conclusion": {"type": "string"},
                    "effectiveness_score": {"type": "integer"},
                },
                "required": ["title", "issue", "rule", "rule_authorities", "statutory_basis", "application", "conclusion", "effectiveness_score"],
            },
        },
    },
    "required": ["irac_arguments"],
}
```

Also add an adversarial strategy search prompt and argument ordering prompt.

**Step 2: Commit**

```bash
git add backend/app/core/legal/prompts.py
git commit -m "feat: add IRAC argument generation and adversarial search prompts"
```

---

### Task 4.3: Implement new strategy nodes

**Files:**
- Modify: `backend/app/core/agents/nodes/strategy_nodes.py`
- Test: `backend/tests/unit/test_strategy_nodes.py`

**Step 1: Add `generate_arguments_irac_node`**

Follow the existing `generate_arguments_node` pattern (lines 333-369). New version uses `STRATEGY_IRAC_ARGUMENTS_SYSTEM` and `STRATEGY_IRAC_ARGUMENTS_SCHEMA`, and outputs to `irac_arguments` state key.

**Step 2: Add `adversarial_search_strategy_node`**

Adapt the research agent's `adversarial_search_node` pattern. Takes `StrategyState`, uses the precedent_map and legal_arguments to generate counter-argument search queries, runs hybrid search, validates relevance. Returns `adversarial_results`.

**Step 3: Add `argument_ordering_node`**

Uses Pro LLM to reorder `irac_arguments` based on: (a) authority strength, (b) judge profile receptiveness, (c) procedural priority. Returns `argument_order: list[int]`.

**Step 4: Modify `synthesize_strategy_node` to include IRAC + adversarial data**

Update the prompt to include `irac_arguments` (ordered) and `adversarial_results` in the synthesis. Output a structured argument document with: executive summary, ordered IRAC arguments, evidence-backed counter-arguments with rebuttals, distinguishing adverse precedents, recommended strategy, authorities cited.

**Step 5: Write tests for each new node**

Follow existing test patterns in the test file.

**Step 6: Commit**

```bash
git add backend/app/core/agents/nodes/strategy_nodes.py backend/tests/unit/test_strategy_nodes.py
git commit -m "feat: add IRAC generation, adversarial search, and argument ordering nodes"
```

---

### Task 4.4: Update strategy graph with new nodes and edges

**Files:**
- Modify: `backend/app/core/agents/strategy.py`

**Step 1: Import new node functions and prompts**

Add imports for `element_decomposition_node` from `common.py`, and the three new strategy nodes.

**Step 2: Add node wrappers (closures)**

Following the existing pattern (lines 104-156), add closures for:
- `element_decomposition` — wraps `element_decomposition_node(state, flash_llm)`
- `generate_arguments_irac` — wraps new node
- `adversarial_search` — wraps new node with embedder, vector_store, reranker
- `argument_ordering` — wraps new node

**Step 3: Register new nodes**

```python
graph.add_node("element_decomposition", element_decomposition)
graph.add_node("generate_arguments_irac", generate_arguments_irac)
graph.add_node("adversarial_search", adversarial_search)
graph.add_node("argument_ordering", argument_ordering)
```

**Step 4: Update edges**

New flow:
```python
graph.add_edge(START, "analyze_facts")
graph.add_edge("analyze_facts", "element_decomposition")  # NEW
graph.add_edge("element_decomposition", "fetch_judge")     # Changed
graph.add_edge("fetch_judge", "checkpoint_analysis")

# ... checkpoint_analysis routing unchanged ...

graph.add_edge("search_precedents", "assess_strength")
graph.add_edge("assess_strength", "generate_arguments_irac")  # Changed
graph.add_edge("generate_arguments_irac", "checkpoint_arguments")

# ... checkpoint_arguments routing: proceed goes to adversarial_search
graph.add_edge("adversarial_search", "counter_and_judge")     # NEW
graph.add_edge("counter_and_judge", "argument_ordering")       # NEW
graph.add_edge("argument_ordering", "synthesize_strategy")     # NEW
graph.add_edge("synthesize_strategy", "verify")
graph.add_edge("verify", "checkpoint_memo")
```

**Step 5: Update conditional edge for checkpoint_arguments**

Change the routing to go to `adversarial_search` instead of `counter_and_judge`:

```python
route_after_arguments = make_feedback_router("arguments", "generate_arguments_irac", "adversarial_search", check_error=True)
```

**Step 6: Run strategy agent tests**

Run: `cd backend && python -m pytest tests/unit/test_strategy_nodes.py tests/unit/test_agent_graph_execution.py -v -k strategy`

**Step 7: Commit**

```bash
git add backend/app/core/agents/strategy.py
git commit -m "feat: rewire strategy graph with element decomposition, adversarial search, argument ordering"
```

---

## Feature 5: Opposing Counsel Analysis

### Task 5.1: Counsel analytics service

**Files:**
- Create: `backend/app/core/analytics/counsel_analytics.py`
- Test: `backend/tests/unit/test_counsel_analytics.py`

**Step 1: Implement counsel name normalization and analytics**

Follow the `judge_analytics.py` pattern — dataclass-based service with SQL queries.

Key functions:
- `normalize_counsel_name(name: str) -> str` — strip honorifics, normalize designations
- `get_counsel_profile(db, name) -> CounselProfile | None` — aggregate stats
- `get_counsel_cases(db, name, page, size, filters) -> list[CounselCaseItem]`
- `get_counsel_matchups(db, name, limit) -> list[Matchup]`
- `search_counsel(db, query, page, size) -> list[CounselListItem]`

Dataclasses:
```python
@dataclass
class CounselProfile:
    name: str
    normalized_name: str
    total_cases: int
    petitioner_cases: int
    respondent_cases: int
    win_rate: float  # favorable disposal %
    case_types: dict[str, int]
    acts_frequency: dict[str, int]
    designation: str  # senior_advocate, advocate, etc.
    active_years: tuple[int, int]  # first, last year
    bench_combinations: list[dict]
    top_matchups: list[dict]
```

**Step 2: Run tests**

**Step 3: Commit**

```bash
git commit -m "feat: add counsel analytics service with name normalization"
```

---

### Task 5.2: Counsel API routes

**Files:**
- Create: `backend/app/api/routes/counsel.py`
- Register in `backend/app/main.py`

**Endpoints:**
- `GET /counsel?search=name&page=1&size=20` — search counsels
- `GET /counsel/{name}` — full profile (cached 1hr)
- `GET /counsel/{name}/cases?page=1&size=20&year_from=&case_type=` — paginated cases
- `GET /counsel/{name}/matchups?limit=10` — head-to-head records

Follow the `judges.py` route pattern.

**Commit:**

```bash
git commit -m "feat: add counsel analytics API routes"
```

---

### Task 5.3: Frontend counsel profile page

**Files:**
- Create: `frontend/src/app/counsel/[name]/page.tsx`
- Modify: `frontend/src/lib/api.ts` (add counsel API functions)

Follow the judge profile page pattern (`frontend/src/app/judge/[name]/page.tsx`). Stats cards, case type pie chart, matchup table.

**Commit:**

```bash
git commit -m "feat: add counsel profile page with analytics"
```

---

## Feature 6: Case Timeline Visualization

### Task 6.1: Procedural timeline endpoint

**Files:**
- Modify: `backend/app/api/routes/cases.py` (add timeline endpoint)
- Test: `backend/tests/unit/test_case_routes.py`

**Step 1: Add endpoint**

```python
@router.get("/{case_id}/timeline", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_case_timeline(
    case_id: str,
    user: TokenPayload = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get procedural timeline for a case."""
    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format.")

    result = await db.execute(
        text(
            "SELECT title, filing_date, decision_date, procedural_history, "
            "interim_orders, lower_court, appeal_from, disposal_nature, court "
            "FROM cases WHERE id = :id"
        ),
        {"id": case_uuid},
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    events = _build_timeline_events(row)
    return {"case_title": row["title"], "events": events}


def _build_timeline_events(row) -> list[dict]:
    """Build chronological timeline from case metadata."""
    events = []

    # Filing date
    if row["filing_date"]:
        events.append({
            "date": str(row["filing_date"]),
            "type": "filing",
            "court": row.get("lower_court") or row["court"],
            "detail": "Case filed",
        })

    # Procedural history entries
    proc_history = row["procedural_history"]
    if isinstance(proc_history, list):
        for entry in proc_history:
            if isinstance(entry, dict) and entry.get("date"):
                events.append({
                    "date": str(entry["date"]),
                    "type": entry.get("type", "judgment"),
                    "court": entry.get("court", "Unknown"),
                    "detail": entry.get("outcome", entry.get("detail", "")),
                })

    # Interim orders
    interim_orders = row["interim_orders"]
    if isinstance(interim_orders, list):
        for order in interim_orders:
            if isinstance(order, dict) and order.get("date"):
                events.append({
                    "date": str(order["date"]),
                    "type": "interim_order",
                    "court": order.get("court", row["court"]),
                    "detail": order.get("detail", order.get("order", "Interim order")),
                })
            elif isinstance(order, str):
                events.append({
                    "date": "",
                    "type": "interim_order",
                    "court": row["court"],
                    "detail": order,
                })

    # Final judgment
    if row["decision_date"]:
        events.append({
            "date": str(row["decision_date"]),
            "type": "judgment",
            "court": row["court"],
            "detail": row.get("disposal_nature") or "Judgment delivered",
        })

    # Sort by date (entries without dates go to end)
    events.sort(key=lambda e: e["date"] or "9999")
    return events
```

**Step 2: Commit**

```bash
git commit -m "feat: add procedural timeline endpoint for cases"
```

---

### Task 6.2: Citation evolution endpoint

**Files:**
- Modify: `backend/app/api/routes/graph.py` (add evolution endpoint)

**Step 1: Add endpoint**

```python
@router.get("/{case_id}/evolution", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_citation_evolution(
    case_id: str,
    max_depth: int = Query(3, ge=1, le=5, description="Max hops to traverse"),
    direction: str = Query("forward", pattern="^(forward|backward)$"),
    graph_store: GraphStore = Depends(get_graph_store),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get how a legal principle evolved through citations over time."""
    # Get root case info from DB
    root_result = await db.execute(
        text("SELECT id, title, year, citation, court, ratio_decidendi FROM cases WHERE id = :id"),
        {"id": uuid.UUID(case_id)},
    )
    root = root_result.mappings().one_or_none()
    if root is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    # Traverse citation graph
    if direction == "forward":
        # Cases that cite this one (incoming CITES)
        cypher = (
            "MATCH (root:Case {id: $case_id})<-[r:CITES]-(citing:Case) "
            "RETURN citing.id AS id, citing.title AS title, citing.year AS year, "
            "citing.citation AS citation, citing.court AS court, "
            "r.treatment AS treatment, citing.ratio AS ratio "
            "ORDER BY citing.year ASC LIMIT 50"
        )
    else:
        # Cases this one cites (outgoing CITES)
        cypher = (
            "MATCH (root:Case {id: $case_id})-[r:CITES]->(cited:Case) "
            "RETURN cited.id AS id, cited.title AS title, cited.year AS year, "
            "cited.citation AS citation, cited.court AS court, "
            "r.treatment AS treatment, cited.ratio AS ratio "
            "ORDER BY cited.year ASC LIMIT 50"
        )

    try:
        records = await graph_store.query(cypher, {"case_id": str(case_id)})
    except Exception:
        records = []

    evolution = [
        {
            "case_id": r.get("id", ""),
            "title": r.get("title", ""),
            "year": r.get("year"),
            "citation": r.get("citation", ""),
            "court": r.get("court", ""),
            "treatment": r.get("treatment", "followed"),
            "ratio_snippet": (r.get("ratio", "") or "")[:200],
        }
        for r in records
    ]

    return {
        "root_case": {
            "id": str(root["id"]),
            "title": root["title"],
            "year": root["year"],
            "citation": root["citation"],
        },
        "evolution": evolution,
        "direction": direction,
    }
```

**Step 2: Commit**

```bash
git commit -m "feat: add citation evolution timeline endpoint"
```

---

### Task 6.3: Frontend timeline component

**Files:**
- Create: `frontend/src/components/case-timeline.tsx`
- Modify: `frontend/src/app/case/[id]/page.tsx` (add Timeline tab)
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add API functions**

```typescript
export async function getCaseTimeline(caseId: string): Promise<{ case_title: string; events: TimelineEvent[] }> {
    return apiFetch(`/cases/${caseId}/timeline`);
}

export async function getCitationEvolution(caseId: string, direction: "forward" | "backward" = "forward"): Promise<{ root_case: Record<string, unknown>; evolution: EvolutionEntry[] }> {
    return apiFetch(`/graph/${caseId}/evolution?direction=${direction}`);
}
```

**Step 2: Create timeline component**

A vertical timeline with color-coded event cards. filing=blue, judgment=green/red, interim_order=yellow. Each event shows date, court, and detail. For citation evolution, show treatment badges (FOLLOWED=green, DISTINGUISHED=amber, OVERRULED=red). Cases link to their detail pages.

**Step 3: Add "Timeline" tab to case detail page**

In `case/[id]/page.tsx`, add a new tab after existing tabs.

**Step 4: Commit**

```bash
git commit -m "feat: add case timeline visualization component and tab"
```

---

## Feature 7: Smriti Learning Over Time (Layer 1 — User Preferences)

### Task 7.1: Database migration for user preferences

**Files:**
- Create: `backend/migrations/versions/038_user_preferences.py`

**Step 1: Create migration**

```python
"""Add preferences JSONB column to users table.

Revision ID: 038
Revises: 037
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "038"
down_revision = "037"


def upgrade() -> None:
    op.add_column("users", sa.Column("preferences", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False))


def downgrade() -> None:
    op.drop_column("users", "preferences")
```

**Step 2: Run migration, commit**

```bash
git commit -m "feat(db): add preferences JSONB column to users table"
```

---

### Task 7.2: Preferences API endpoints

**Files:**
- Modify: `backend/app/api/routes/auth.py` or create `backend/app/api/routes/preferences.py`

**Endpoints:**
- `GET /users/me/preferences` — return current preferences
- `PUT /users/me/preferences` — manual override (merge with existing)
- `POST /users/me/preferences/refresh` — analyze search history and auto-populate

**Step 1: Implement refresh logic**

```python
async def _compute_preferences_from_history(db: AsyncSession, user_id: str) -> dict:
    """Analyze last 30 days of search history to build preferences."""
    # Query search history
    result = await db.execute(
        text(
            "SELECT query, filters FROM search_history "
            "WHERE user_id = :uid AND created_at > NOW() - INTERVAL '30 days' "
            "ORDER BY created_at DESC LIMIT 200"
        ),
        {"uid": uuid.UUID(user_id)},
    )
    rows = result.mappings().all()

    # Aggregate patterns
    acts_counter: dict[str, int] = {}
    jurisdictions_counter: dict[str, int] = {}
    case_types_counter: dict[str, int] = {}
    courts_counter: dict[str, int] = {}

    for row in rows:
        filters = row["filters"] or {}
        if filters.get("jurisdiction"):
            jurisdictions_counter[filters["jurisdiction"]] = jurisdictions_counter.get(filters["jurisdiction"], 0) + 1
        if filters.get("case_type"):
            case_types_counter[filters["case_type"]] = case_types_counter.get(filters["case_type"], 0) + 1
        if filters.get("court"):
            courts_counter[filters["court"]] = courts_counter.get(filters["court"], 0) + 1
        # Extract acts from queries (simple keyword matching)
        # Could also query agent session inputs for richer data

    from datetime import datetime, timezone
    return {
        "frequent_acts": sorted(acts_counter, key=acts_counter.get, reverse=True)[:10],
        "preferred_jurisdictions": sorted(jurisdictions_counter, key=jurisdictions_counter.get, reverse=True)[:5],
        "common_case_types": sorted(case_types_counter, key=case_types_counter.get, reverse=True)[:5],
        "preferred_courts": sorted(courts_counter, key=courts_counter.get, reverse=True)[:5],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
```

**Step 2: Commit**

```bash
git commit -m "feat: add user preferences API with auto-refresh from search history"
```

---

### Task 7.3: Apply preferences in search

**Files:**
- Modify: `backend/app/api/routes/search.py` (read preferences, pre-fill defaults)
- Modify: `frontend/src/app/search/page.tsx` (fetch preferences on load, pre-fill filters)

**Step 1: Backend — read user preferences**

In the search endpoint, after authentication, load user preferences and use them to provide default filter values when none are explicitly set.

**Step 2: Frontend — fetch and apply preferences**

On search page load, call `GET /users/me/preferences` and use the response to pre-populate filter dropdowns.

**Step 3: Commit**

```bash
git commit -m "feat: apply user preferences as default search filters"
```

---

## Summary: All Tasks

| # | Feature | Task | Est. Effort |
|---|---------|------|-------------|
| 1.1 | Session Fix | Move memo save to reliable location | 30 min |
| 1.2 | Session Fix | Add result_data to session detail | 30 min |
| 1.3 | Session Fix | Frontend loadSession() fallback | 45 min |
| 2.1 | Share Memo | Migration for shared_memos | 15 min |
| 2.2 | Share Memo | SQLAlchemy model | 10 min |
| 2.3 | Share Memo | Backend share endpoints | 1.5 hr |
| 2.4 | Share Memo | Frontend share button + public page | 1.5 hr |
| 3.1 | Judge Prediction | Prediction service | 2 hr |
| 3.2 | Judge Prediction | API endpoint | 30 min |
| 3.3 | Judge Prediction | Frontend prediction card | 1 hr |
| 4.1 | Argument Builder | Update StrategyState | 15 min |
| 4.2 | Argument Builder | IRAC prompts + schemas | 1 hr |
| 4.3 | Argument Builder | New strategy nodes | 3 hr |
| 4.4 | Argument Builder | Rewire strategy graph | 1 hr |
| 5.1 | Counsel Analysis | Analytics service | 2 hr |
| 5.2 | Counsel Analysis | API routes | 1 hr |
| 5.3 | Counsel Analysis | Frontend profile page | 2 hr |
| 6.1 | Case Timeline | Procedural timeline endpoint | 1 hr |
| 6.2 | Case Timeline | Citation evolution endpoint | 1 hr |
| 6.3 | Case Timeline | Frontend timeline component | 2 hr |
| 7.1 | User Prefs | Migration | 15 min |
| 7.2 | User Prefs | Preferences API | 1 hr |
| 7.3 | User Prefs | Apply in search | 1 hr |

**Total estimated: ~24 hours of implementation**

**Execution order:** 1.1 → 1.2 → 1.3 → 2.1 → 2.2 → 2.3 → 2.4 → 6.1 → 6.2 → 6.3 → 5.1 → 5.2 → 5.3 → 3.1 → 3.2 → 3.3 → 4.1 → 4.2 → 4.3 → 4.4 → 7.1 → 7.2 → 7.3
