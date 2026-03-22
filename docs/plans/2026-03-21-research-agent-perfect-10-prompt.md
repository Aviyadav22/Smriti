# Ralph Loop Implementation Prompt

> Copy everything below the line into a new Claude Code terminal session.

---

You are implementing the Research Agent Perfect 10/10 Upgrade for the Smriti project at `d:\Startup\Smriti`.

## Your Reference Files (READ THESE FIRST — they are your bible)

1. **Implementation Plan** — `docs/plans/2026-03-21-research-agent-perfect-10-plan.md`
   - Contains the WHAT and WHY for every step
   - 5 categories (A: Statute/Data, B: Performance/Search, C: Synthesis/Safety, D: UX/HITL, E: Graph)
   - Cross-cutting concerns section — READ THIS CAREFULLY, it lists E2E constraints
   - Sprint sequence with dependency graph

2. **Implementation Tracker** — `docs/plans/2026-03-21-research-agent-perfect-10-tracker.md`
   - Contains the exact checkboxes for every sub-step
   - **YOU MUST UPDATE THIS FILE IN REAL-TIME** — check off `[x]` each sub-step as you complete it
   - This is how progress is tracked across sessions
   - Start by reading this file to find the FIRST unchecked `[ ]` item — that's your next task

3. **V2 Bible** (prior architecture context) — `docs/plans/research-agent-v2-bible.md`
   - Read Section 11 (Existing Code Reference) for exact function signatures
   - Read Section 10 (Key Design Decisions) for architectural constraints

4. **Project Rules** — `docs/CLAUDE.md` and `docs/DECISIONS.md`
   - NEVER violate these. Key rules: no raw SQL, no `any` types, all services behind interfaces, all prompts in prompts.py

## Your Workflow (Ralph Loop)

For EACH unchecked step in the tracker:

1. **READ** the tracker to find the next unchecked `[ ]` step
2. **READ** the plan for that step's full context (files, implementation, E2E impact)
3. **READ** all files that will be modified (understand before changing)
4. **IMPLEMENT** the step carefully:
   - Consider E2E impact on other components (the plan describes these)
   - Follow existing code patterns and conventions
   - Add tests for new functionality
   - Do NOT break existing tests
5. **TEST** after every step:
   - `cd backend && python -m pytest tests/ -x -q` (must pass, baseline: 1845)
   - If frontend was changed: `cd frontend && npm test` (must pass, baseline: 298)
   - If graph topology changed: mentally trace simple + complex query paths
6. **CHECK OFF** the step in the tracker file: change `[ ]` to `[x]`
7. **REPEAT** — go back to step 1

## Critical Rules

- **NEVER skip a step or do steps out of order** — the sprint sequence has dependency reasons
- **NEVER implement a step without reading the plan's E2E impact section for it**
- **NEVER proceed if tests are failing** — fix the failure first, then check off
- **Always check off steps as you complete them** — the tracker is the source of truth
- **If a step requires a migration**, always test `alembic downgrade -1` after `alembic upgrade head`
- **If a step CHANGES GRAPH TOPOLOGY** (marked in plan), test all conditional paths
- **State schema changes must use `NotRequired[]`** for backward compatibility
- **New imports**: check the import chain doesn't create circular dependencies
- **Prompt changes**: verify total prompt size stays within Gemini context limits
- **Sprint checkpoints**: when you reach a `S{N}.CHECK` item, run the full test suite and verify all sprint-specific targets before proceeding to the next sprint

## Quality Metrics to Monitor

After each step, mentally assess:
- **Code quality**: Did I follow existing patterns? Is the code clean and minimal?
- **Performance impact**: Did this make things faster or slower? By how much?
- **Test coverage**: Did I add tests for the new code paths?
- **Backward compatibility**: Will existing states/checkpoints/data still work?

## Start Now

1. Read the tracker file: `docs/plans/2026-03-21-research-agent-perfect-10-tracker.md`
2. Find the first unchecked `[ ]` item
3. Begin the implementation loop

Do NOT ask questions — the plan and tracker contain everything you need. If genuinely blocked, document the blocker in the tracker as a note under the step and move to the next independent step.
