---
active: true
iteration: 20
session_id: 
max_iterations: 50
completion_promise: "COMPLETE"
started_at: "2026-03-23T08:11:20Z"
---

Read SMRITI_REFACTOR_PRD.md in the project root. This is your checklist. Work on EXACTLY ONE unchecked [ ] task — the first one you find.

For each task:
1. Read progress.txt first for context from previous iterations.
2. Do the work thoroughly. This is Smriti — a legal research platform for Indian lawyers. Every function serves a real legal workflow: finding precedents, citing judgments, preparing bail applications, analyzing judge patterns, drafting legal documents.
3. When wiring a function, understand its LEGAL PURPOSE first. Example: build_lookup() exists because Indian law underwent a massive reform — IPC became BNS, CrPC became BNSS, IEA became BSA. Lawyers need to search old AND new law simultaneously. Wire it where this cross-referencing happens.
4. Update SMRITI_REFACTOR_PRD.md: change [ ] to [x] for the completed task.
5. Append to progress.txt what you did, files changed, patterns learned.
6. Git add all changed files and commit: [SMRITI-REFACTOR] <description>

CRITICAL: Do NOT rush. Each task requires reading code, understanding context, making real changes, and verifying. If you finish in under 2 minutes you didnt do it properly.

ONLY WORK ON ONE TASK PER ITERATION. Then exit so the next iteration picks up the next task.

If ALL tasks in SMRITI_REFACTOR_PRD.md are checked [x], output <promise>COMPLETE</promise>. Not before.
