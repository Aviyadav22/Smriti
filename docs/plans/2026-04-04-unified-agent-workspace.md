# Unified Agent Workspace Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** All 4 agents share one workspace shell (session sidebar, live streaming, memo display, follow-up chat) while keeping their unique inputs, graph logic, and output formats completely independent.

**Architecture:** Composition over configuration. A single `AgentWorkspace` component provides the shell (sidebar + streaming + memo + chat). Each agent plugs in its own `InputForm` component and optional `ResultEnrichment` component. No agent logic changes. No backend graph changes.

**Tech Stack:** React (Next.js), TypeScript, existing `useAgentSession` hook, existing SSE streaming infrastructure.

---

## What's Shared vs What Stays Unique

| Shared (AgentWorkspace) | Agent-Specific (Pluggable) |
|---|---|
| Session sidebar | Input form (query, doc picker, facts form, template picker) |
| Live progress streaming | Graph steps list |
| Checkpoint display + resume | Checkpoint context rendering (section_drafts for drafting) |
| Memo viewer | Result enrichments (footnotes panel for research, export for drafting) |
| Follow-up chat | Request body builder |
| Error/cancel/retry | - |
| Session loading + deletion | - |

## Key Constraint

**Each agent's graph, nodes, state schema, prompts, and backend logic are UNTOUCHED.** This plan only changes the frontend page shell and adds streaming to agents that don't have it yet.

---

### Task 1: Create AgentWorkspace Shell Component

**Files:**
- Create: `frontend/src/components/agents/AgentWorkspace.tsx`

This is the shared wrapper. It accepts:

```typescript
interface AgentWorkspaceProps {
  agentType: "research" | "case_prep" | "strategy" | "drafting";
  title: string;
  description: string;
  steps: string[];  // Node names for step timeline

  /** The input form — rendered when no session is active */
  renderInput: (props: {
    onSubmit: (body: Record<string, unknown>) => void;
    disabled: boolean;
  }) => React.ReactNode;

  /** Optional: extra content after memo (e.g., footnotes panel, export buttons) */
  renderResultExtras?: (props: {
    memo: string;
    confidence?: number;
    checkpoint: { question: string; context: Record<string, unknown> } | null;
    executionId: string | null;
  }) => React.ReactNode;

  /** Optional: custom checkpoint renderer (e.g., drafting section viewer) */
  renderCheckpoint?: (props: {
    checkpoint: { question: string; context: Record<string, unknown> };
    onSubmit: (input: string) => void;
    disabled: boolean;
    error: string | null;
    onClearError: () => void;
  }) => React.ReactNode;
}
```

**What it renders:**
```
<div className="min-h-screen flex flex-col">
  <Header />
  <main className="flex-1 flex">
    <SessionSidebar />
    <div className="flex-1">
      <Title + Description />
      {showInput ? renderInput({ onSubmit, disabled }) : null}
      {showWorkspace ? (
        <StepTimeline />
        <LiveProgressFeed />   {/* The streaming ticker — shared */}
        {renderCheckpoint ? renderCheckpoint(...) : <AgentCheckpointPrompt />}
        <MemoViewer />
        {renderResultExtras?.(...)}
        <FollowUpChat />       {/* Shared for all agents */}
        <Error / Cancel / NewSession buttons />
      ) : null}
    </div>
  </main>
  <Footer />
</div>
```

**Step 1:** Write the component using `useAgentSession` hook internally. The event handler maps `status` → step updates, `checkpoint` / `memo` / `done` / `error` → hook state. Process events (progress/found/etc.) go into a `processEvents` array for the live feed.

**Step 2:** Verify it renders correctly with a simple test agent config.

**Step 3:** Commit.

---

### Task 2: Create Agent-Specific Input Forms as Standalone Components

**Files:**
- Create: `frontend/src/components/agents/inputs/ResearchInput.tsx`
- Create: `frontend/src/components/agents/inputs/CasePrepInput.tsx`
- Create: `frontend/src/components/agents/inputs/StrategyInput.tsx`
- Create: `frontend/src/components/agents/inputs/DraftingInput.tsx`

Each component handles ONLY its unique form logic. It receives `onSubmit(body)` and `disabled` as props.

**ResearchInput:** Query textarea + domain presets + example queries. Calls `onSubmit({ query })`.

**CasePrepInput:** Document dropdown (fetches from API). Calls `onSubmit({ document_id })`.

**StrategyInput:** Case facts textarea + desired relief + optional judge/bench. Calls `onSubmit({ case_facts, desired_relief, target_judge, target_bench })`.

**DraftingInput:** Template selector + case facts + target court + dynamic fields. Calls `onSubmit({ doc_type, case_facts, target_court, relevant_precedents, additional_context })`.

**Step 1:** Extract each form from the current page file into its own component.
**Step 2:** Verify props match.
**Step 3:** Commit.

---

### Task 3: Create Agent-Specific Result Extras

**Files:**
- Create: `frontend/src/components/agents/extras/ResearchExtras.tsx`
- Create: `frontend/src/components/agents/extras/DraftingExtras.tsx`

**ResearchExtras:** Footnotes panel + verification banner + research audit trail. These already exist as components — this just composes them.

**DraftingExtras:** Section draft viewer + export buttons (DOCX/PDF). Already exists as `DraftSectionViewer` — this wraps it with export logic.

Case Prep and Strategy have NO extras (just memo + confidence).

**Step 1:** Extract from current pages.
**Step 2:** Commit.

---

### Task 4: Rewrite Each Agent Page as Thin Wrappers

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx` (~1200 lines → ~80 lines)
- Modify: `frontend/src/app/agents/case-prep/page.tsx` (~280 lines → ~40 lines)
- Modify: `frontend/src/app/agents/strategy/page.tsx` (~250 lines → ~40 lines)
- Modify: `frontend/src/app/agents/drafting/page.tsx` (~400 lines → ~60 lines)

Each page becomes:

```tsx
// case-prep/page.tsx — ENTIRE FILE
"use client";
import { AgentWorkspace } from "@/components/agents/AgentWorkspace";
import { CasePrepInput } from "@/components/agents/inputs/CasePrepInput";

const STEPS = ["load_analysis", "prioritize", "checkpoint_issues", ...];

export default function CasePrepPage() {
  return (
    <AgentWorkspace
      agentType="case_prep"
      title="Case Prep Agent"
      description="Select an analyzed document to generate a strategy memo."
      steps={STEPS}
      renderInput={({ onSubmit, disabled }) => (
        <CasePrepInput onSubmit={onSubmit} disabled={disabled} />
      )}
    />
  );
}
```

Research page is slightly larger because it passes `renderResultExtras` and has the custom progress component.

**Step 1:** Rewrite case-prep page.
**Step 2:** Verify it works (load sessions, run agent, see memo).
**Step 3:** Rewrite strategy page. Verify.
**Step 4:** Rewrite drafting page (with renderCheckpoint for section_drafts). Verify.
**Step 5:** Rewrite research page (with renderResultExtras for footnotes + streaming). Verify.
**Step 6:** Commit.

---

### Task 5: Add Live Streaming to All Agents

The backend `_stream_agent_events` already has the progress ticker that sends events every 5 seconds during silence. The `status` events already fire for all agents. The frontend `ResearchProgress` component already handles these.

**What to do:** Make `AgentWorkspace` include a simplified version of `ResearchProgress` (the activity feed with live events) for ALL agents. For research, use the full version with the 5-stage stepper. For others, use a simpler version (just the activity feed, no stepper).

**Files:**
- Modify: `frontend/src/components/research-progress.tsx` — Extract the activity feed into a reusable `ActivityFeed` component
- The 5-stage stepper remains research-only

**Step 1:** Extract `ActivityFeed` from `ResearchProgress`.
**Step 2:** Use `ActivityFeed` in `AgentWorkspace` for all agent types.
**Step 3:** Research page passes the full `ResearchProgress` (stepper + feed) via its extras.
**Step 4:** Commit.

---

### Task 6: Add Follow-Up Chat to All Agents

Currently only research has follow-up. The backend endpoint `/sessions/{id}/follow-up` uses `build_follow_up_graph` which is research-specific (expects memo + footnotes).

**Backend change:** Make follow-up work for any agent by reading the memo from the generic `result_data.memo` field (which all agents populate).

**Files:**
- Modify: `backend/app/core/agents/follow_up.py` — Accept memo from any agent's result_data
- Modify: `backend/app/api/routes/agents.py` — Remove "No completed research" assumption

**Frontend:** `AgentWorkspace` already includes `AgentFollowUpThread` + `AgentFollowUpInput` for all agents.

**Step 1:** Fix backend follow-up to be agent-agnostic.
**Step 2:** Verify follow-up works for strategy agent.
**Step 3:** Commit.

---

### Task 7: Run Full Test Suite + Manual Verification

**Step 1:** Run `npx vitest run` — all frontend tests pass.
**Step 2:** Run `pytest tests/ -k "research or agent" --ignore=tests/quality` — all backend tests pass.
**Step 3:** Manual test each agent:
  - Research: run query → see streaming → approve plan → see workers → get memo → follow-up
  - Case Prep: select doc → run → checkpoints → memo → session history
  - Strategy: enter facts → run → checkpoints → memo → session history
  - Drafting: select template → run → section drafts → export → session history
**Step 4:** Verify session sidebar works identically across all 4 agent pages.
**Step 5:** Commit + tag.

---

## File Count Summary

| Action | Count | Description |
|--------|-------|-------------|
| Create | 7 | AgentWorkspace, 4 inputs, 2 extras |
| Modify | 6 | 4 page files (shrink), follow_up.py, agents.py |
| Delete | 0 | Old components stay (used by AgentWorkspace internally) |

## Risk Assessment

- **Low risk:** Input forms are pure extraction (no logic change)
- **Low risk:** AgentWorkspace composes existing components (no new logic)
- **Medium risk:** Research page refactor (most complex, has streaming/footnotes/follow-up)
- **Low risk:** Follow-up generalization (simple — just read memo from result_data)
- **Zero risk to backend:** No graph/node/state changes
