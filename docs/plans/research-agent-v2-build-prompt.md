# RESEARCH AGENT V2 — BUILD PROMPT

Copy the section below and paste it into a fresh Claude Code terminal to start building.

---

## THE PROMPT

```
You are building the Research Agent V2 for Smriti — an AI-powered Indian legal research platform. You have two critical reference documents:

1. **BIBLE** (single source of truth): `docs/plans/research-agent-v2-bible.md`
   - Contains EVERYTHING: architecture, state schemas, prompts, node code, worker code, graph wiring, tests, design decisions
   - Every code snippet, TypedDict, prompt, and wiring instruction is in here
   - When in doubt, the bible is correct

2. **TRACKER** (your checklist): `docs/plans/research-agent-v2-tracker.md`
   - Phase-by-phase checkbox list with task IDs (1A.1, 1B.2, etc.)
   - Each task references the exact bible section to follow
   - Check off tasks AS YOU COMPLETE THEM (edit the tracker, replace `- [ ]` with `- [x]`)
   - Never skip a phase gate — all gate items must pass before moving to the next phase

## RULES

1. **Read before write**: Before modifying ANY file, read the existing file AND the relevant bible section. The bible Section 11 lists all existing files and their roles.

2. **Phase order matters**:
   - Phases 1 and 2 can run in parallel (they're independent)
   - Phase 3 REQUIRES both Phase 1 and Phase 2 complete
   - Phase 4 REQUIRES Phase 3 complete
   - Phase 5 REQUIRES Phase 4 complete

3. **Test after every sub-section**: After completing each lettered group (1A, 1B, 1C, etc.), run `cd backend && python -m pytest tests/ -x -q` and verify no regressions. If tests break, fix before proceeding.

4. **Use existing patterns**: The codebase follows Interface + Provider pattern (Protocol classes in `core/interfaces/`, implementations in `core/providers/`). Follow this. Never call external services directly from routes.

5. **Enhancement IDs**: The bible uses IDs like [Q1], [S10], [T4]. The tracker maps these to specific tasks. When implementing a task tagged with an enhancement ID, find ALL references to that ID in the bible for full context.

6. **No guessing**: Every prompt, schema, TypedDict, node function, and graph edge is specified in the bible. Copy the code from the bible, adapt it to fit the existing codebase patterns, but don't invent new behavior.

7. **Commit at phase gates**: After each phase gate passes, create a commit with the message format shown in the tracker.

## HOW TO START

1. Read the bible Sections 0-3 (competitive intel, vision, current arch, target arch) to understand what you're building
2. Read Section 11 (existing code reference) to understand what exists
3. Read the tracker to see the full task list
4. Start with Phase 1, task 1A.1 (or Phase 2 task 2A.1 if you prefer — they're parallel)
5. Work through tasks sequentially within each phase
6. Check off each task in the tracker as you complete it
7. At each phase gate, verify ALL gate items pass before proceeding

## CRITICAL CONTEXT

- Backend: FastAPI (Python 3.12), in `backend/` directory
- Tests: pytest (1411 existing tests), run with `cd backend && python -m pytest tests/ -x -q`
- Frontend: Next.js 15, in `frontend/` directory
- Frontend tests: vitest (298 existing tests), NOT jest
- LLM: Gemini 2.5 Pro (synthesis) + Gemini 2.5 Flash (everything else)
- Agent framework: LangGraph with Send() for parallel fan-out
- All prompts go in `backend/app/core/legal/prompts.py` AND `docs/PROMPT_LIBRARY.md`
- All TypedDicts go in `backend/app/core/agents/state.py`
- Never use `any` in TypeScript or bare `Exception` in Python
- Never hardcode secrets — use `core/config.py` settings

## START NOW

Read the bible (Sections 0-3 and 11), read the tracker, then begin Phase 1 task 1A.1. Update the tracker checkbox as you complete each task.
```
