# Overnight Documentation Update — Ralph Loop Prompt

**Run this as a ralph-loop command in Claude Code.**

---

## How to run

Paste this into Claude Code:

```
/ralph-loop:ralph-loop --max-iterations 30 --completion-promise 'All documentation files updated and tracker complete' Update all outdated Smriti documentation files to match actual codebase state. GROUND TRUTH file: ~/.claude/projects/d--Startup-Smriti/memory/doc-update-ground-truth.md — read this for verified codebase state. TRACKER file: docs/plans/2026-03-23-doc-update-tracker.md — read this for the checkbox list of what needs fixing. WORKFLOW: 1. Read the tracker, find the FIRST unchecked item. 2. Read the target doc file. 3. Read the relevant source code to VERIFY claims before writing. 4. Edit the doc to fix that item. Be surgical, change only what is wrong, preserve existing structure and tone. 5. Mark that checkbox done in the tracker. 6. Repeat from step 1. CRITICAL RULES: Never blindly copy from memory, always verify against source code. Preserve each doc formatting style. One checkbox at a time so progress saves. Do NOT change code, only docs. Do NOT update docs/plans/ historical records. For DECISIONS.md new ADRs use ADR format with Date 2026-03-23, Status Accepted, Context, Decision, Alternatives, Consequences. Test counts are approximate, use ~2185 backend ~311 frontend. KEY SOURCE FILES to read as needed: backend/app/core/config.py for settings, backend/app/core/ingestion/pipeline.py for pipeline, backend/app/core/ingestion/chunker.py for chunking, backend/app/core/agents/research.py for agent graph, backend/app/core/agents/nodes/ for nodes, backend/app/core/search/hybrid.py for search, backend/app/core/legal/prompts.py for prompts, backend/app/core/legal/constants.py for constants, backend/app/models/ for ORM models, backend/migrations/versions/ for migrations, backend/app/api/routes/ for routes, frontend/package.json for deps, frontend/src/lib/api.ts for API client, frontend/src/components/ for components. When ALL checkboxes in the tracker are done, output the completion promise.
```

---

## What happens

1. Ralph loop activates and feeds the same prompt each iteration
2. Each iteration: reads tracker → finds first `[ ]` → reads doc + source code → edits doc → marks `[x]`
3. Progress is checkpointed in `docs/plans/2026-03-23-doc-update-tracker.md` after every item
4. When all ~80 checkboxes are `[x]`, it outputs `<promise>All documentation files updated and tracker complete</promise>` and the loop exits
5. Max 30 iterations as safety limit

## Recovery

If something goes wrong or it hits max iterations before finishing:
- Check tracker for progress: `grep -c "\[x\]" docs/plans/2026-03-23-doc-update-tracker.md`
- Re-run the same `/ralph-loop` command — it resumes from the first unchecked `[ ]`

## Files created for this task

| File | Purpose |
|------|---------|
| `~/.claude/projects/d--Startup-Smriti/memory/doc-update-ground-truth.md` | Verified codebase state (tech stack, config, architecture, models, routes, tests) |
| `docs/plans/2026-03-23-doc-update-tracker.md` | Checkbox tracker — 5 phases, ~80 items |
| `docs/plans/2026-03-23-doc-update-prompt.md` | This file — the ralph loop prompt |

## Tracker phases

- **Phase 1 CRITICAL** (~40 items): CLAUDE.md, ARCHITECTURE.md, LLD.md, HLD.md, PROMPT_LIBRARY.md
- **Phase 2 HIGH** (~15 items): DECISIONS.md, PHASE_PLAN.md, DATA_SOURCES.md, FRONTEND_ARCHITECTURE.md
- **Phase 3 MEDIUM** (~15 items): ENV_SETUP.md, TESTING_STRATEGY.md, SECURITY_AUDIT.md, PHASE_9_SCALABILITY_AUDIT.md, PRD.md
- **Phase 4 LOW** (~5 items): LEGAL_DOMAIN.md, STRATEGY.md, GCP_DEPLOYMENT_CREDENTIALS.md
- **Phase 5**: MEMORY.md update
