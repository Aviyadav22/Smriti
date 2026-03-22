---
active: true
iteration: 1
max_iterations: 50
completion_promise: "COMPLETE"
started_at: "2026-03-22T21:35:40Z"
---

Read SMRITI_REFACTOR_PRD.md in the project root. This is your task list. Work through it ONE TASK AT A TIME, starting from the first unchecked item ([ ]). For each task:

1. Read progress.txt first to understand what previous iterations did and what codebase patterns were discovered.
2. Do the work for that ONE task thoroughly. Think like an Indian litigation lawyer — every function in this codebase exists to help lawyers find precedents, cite judgments in SCC/AIR format, prepare bail arguments, or research statutory provisions faster. Understand the legal purpose before deciding how to wire things.
3. When the task is done, update SMRITI_REFACTOR_PRD.md — change [ ] to [x] for that task.
4. Append to progress.txt: what you did, what files you changed, what you learned about the codebase structure, any patterns the next iteration should know.
5. Git commit with message: [SMRITI-REFACTOR] <description of what was done>
6. Move to the NEXT unchecked task.

IMPORTANT CODEBASE RULES:
- All external services (Gemini, Pinecone, Neo4j, Cohere, Sarvam, Indian Kanoon, Tavily) MUST go through Protocol interfaces in backend/app/core/interfaces/ — never call providers directly from routes
- All LLM prompts MUST live in backend/app/core/legal/prompts.py — never inline prompts in route handlers or node functions
- Never use bare Exception in Python — always catch specific exceptions
- Never use any type in TypeScript — use proper types from frontend/src/lib/types.ts
- Never construct raw SQL — use SQLAlchemy ORM or parameterized text() queries
- Tests are pytest (backend, 2102+ tests) and vitest (frontend, 311+ tests) — NOT jest
- Package managers: pip (backend), npm (frontend) — NOT yarn or bun
- Vector DB is Pinecone (1536-dim, Gemini embeddings) — NOT Qdrant, NOT pgvector in prod
- Graph DB is Neo4j AuraDB — use MERGE (not CREATE) for idempotent operations
- Agent framework is LangGraph with StateGraph — nodes are pure async functions returning partial state dicts
- Search uses RRF (k=60) to merge Pinecone vector search + PostgreSQL FTS (websearch_to_tsquery)
- acts_cited stores canonical short codes (IPC, CrPC, COI) — never full act names

IMPORTANT WIRING RULES:
- If a function exists but isnt called: find where it SHOULD be called based on its name, params, and the legal workflow. Wire it there. Add comment: // WIRED_BY_REFACTOR: [reasoning]
- If two functions do the same thing (e.g., two different case search implementations): keep the BETTER one (more complete, better error handling, handles Hindi text). Redirect all callers to it. Add the old one to DEPRECATED section in progress.txt with explanation.
- If you genuinely cannot determine where a function belongs: do NOT delete it. Add comment: // NEEDS_HUMAN_REVIEW: [what this function does] [why you couldnt wire it] and log it in DISCONNECTED_FUNCTIONS.md.
- NEVER delete .env, config files, docker configs, or anything in .git/
- NEVER touch API keys or secrets — all come from environment variables via backend/app/core/config.py
- NEVER modify migration files in backend/migrations/versions/ — they are immutable history

If ALL tasks in SMRITI_REFACTOR_PRD.md are checked [x], output <promise>COMPLETE</promise>. Do NOT output this until every single checkbox is checked.
