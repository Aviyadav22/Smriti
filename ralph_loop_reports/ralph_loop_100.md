# RALPH LOOP AUDIT REPORT — SMRITI CODEBASE
## Recursive Audit Loop for Programmatic Health

**Generated:** 2026-03-27 11:54:41
**Runtime:** 8.10 hours (29165 seconds)
**Iterations Completed:** 100 / 1

---

## 1. EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| Files Scanned | 643 |
| Total Lines of Code | 1,245,236 |
| Functions Analyzed | 4153 |
| Classes Analyzed | 694 |
| Total Unique Issues | 4111 |
| Critical Issues | 22 |
| High Issues | 150 |
| Medium Issues | 2099 |
| Low Issues | 1738 |
| Info | 102 |

### Codebase Health Score: 94.5 / 100

> ✅ **GOOD** — Codebase is in healthy shape with minor issues

---

## 2. ISSUES BY CATEGORY

### DOCUMENTATION_GAP (1568 issues)

**MEDIUM:**
- `backend\app\api\routes\agents.py:152` — Public function 'validate_precedents_length' has no docstring
- `backend\app\api\routes\agents.py:159` — Public function 'validate_additional_context' has no docstring
- `backend\app\api\routes\audio.py:126` — Public function 'audio_generator' has no docstring
- `backend\app\api\routes\auth.py:42` — Public function 'validate_password_strength' has no docstring
- `backend\app\api\routes\chat.py:80` — Public function 'event_stream' has no docstring
- `backend\app\api\routes\chat.py:157` — Public function 'event_stream' has no docstring
- `backend\app\core\agents\case_prep.py:99` — Public function 'load_analysis' has no docstring
- `backend\app\core\agents\case_prep.py:103` — Public function 'prioritize' has no docstring
- `backend\app\core\agents\case_prep.py:113` — Public function 'deep_search' has no docstring
- `backend\app\core\agents\case_prep.py:119` — Public function 'argument_order' has no docstring
- `backend\app\core\agents\case_prep.py:122` — Public function 'strategy_memo' has no docstring
- `backend\app\core\agents\case_prep.py:125` — Public function 'verify' has no docstring
- `backend\app\core\agents\drafting.py:104` — Public function 'resolve_template' has no docstring
- `backend\app\core\agents\drafting.py:107` — Public function 'gather_provisions' has no docstring
- `backend\app\core\agents\drafting.py:118` — Public function 'verify_precedents' has no docstring
- `backend\app\core\agents\drafting.py:122` — Public function 'draft_sections' has no docstring
- `backend\app\core\agents\drafting.py:125` — Public function 'assemble' has no docstring
- `backend\app\core\agents\drafting.py:128` — Public function 'revise_section' has no docstring
- `backend\app\core\agents\drafting.py:138` — Public function 'verify_final' has no docstring
- `backend\app\core\agents\follow_up.py:104` — Public function 'reformulate' has no docstring
- _...and 1548 more_


### TYPE_SAFETY_ISSUES (981 issues)

**MEDIUM:**
- `frontend\src\__tests__\test-utils.tsx:7` — TypeScript 'any' type — reduces type safety
- `frontend\src\app\chat\page.tsx:204` — TypeScript 'any' type — reduces type safety
- `frontend\src\app\privacy\page.tsx:54` — TypeScript 'any' type — reduces type safety
- `frontend\src\app\privacy\page.tsx:76` — TypeScript 'any' type — reduces type safety
- `frontend\src\app\search\page.tsx:70` — TypeScript 'any' type — reduces type safety
- `frontend\src\app\terms\page.tsx:56` — TypeScript 'any' type — reduces type safety
- `frontend\src\app\terms\page.tsx:79` — TypeScript 'any' type — reduces type safety
- `frontend\src\app\terms\page.tsx:129` — TypeScript 'any' type — reduces type safety
- `frontend\src\app\terms\page.tsx:130` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:322` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:328` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:334` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:338` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:408` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:412` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:416` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:422` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:426` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:430` — TypeScript 'any' type — reduces type safety
- `frontend\src\components\agent-memo-viewer.tsx:436` — TypeScript 'any' type — reduces type safety
- _...and 5 more_

**LOW:**
- `backend\app\api\routes\audio.py:126` — Function 'audio_generator' has no type hints
- `backend\app\api\routes\chat.py:80` — Function 'event_stream' has no type hints
- `backend\app\api\routes\chat.py:157` — Function 'event_stream' has no type hints
- `backend\migrations\versions\007_dpdp_compliance.py:16` — Function 'upgrade' has no type hints
- `backend\migrations\versions\007_dpdp_compliance.py:34` — Function 'downgrade' has no type hints
- `backend\scripts\audit_migration.py:15` — Function 'audit' has no type hints
- `backend\scripts\audit_migration.py:218` — Function 'group_constraints' has no type hints
- `backend\scripts\e2e_test_apis.py:376` — Function 'main' has no type hints
- `backend\scripts\enrich_pro.py:68` — Function 'run' has no type hints
- `backend\scripts\enrich_pro.py:149` — Function 'main' has no type hints
- `backend\scripts\monitor_ingestion.py:81` — Function 'monitor_loop' has no type hints
- `backend\scripts\poll_batch_test.py:16` — Function 'main' has no type hints
- `backend\scripts\populate_neo4j.py:59` — Function 'get_neo4j_driver' has no type hints
- `backend\scripts\populate_neo4j.py:795` — Function 'main' has no type hints
- `backend\scripts\reset_all_data.py:18` — Function 'reset_postgresql' has no type hints
- `backend\scripts\reset_all_data.py:46` — Function 'reset_pinecone' has no type hints
- `backend\scripts\reset_all_data.py:76` — Function 'reset_neo4j' has no type hints
- `backend\scripts\reset_all_data.py:113` — Function 'reset_sqlite_tracker' has no type hints
- `backend\scripts\reset_all_data.py:125` — Function 'reset_local_pdfs' has no type hints
- `backend\scripts\reset_all_data.py:139` — Function 'main' has no type hints
- _...and 936 more_


### LOGIC_FLOW_TRACE (496 issues)

**MEDIUM:**
- `backend\app\api\routes\admin_corrections.py:93` — Function 'correct_metadata' is 94 lines long — consider splitting
- `backend\app\api\routes\admin_review.py:32` — Function 'list_review_queue' is 79 lines long — consider splitting
- `backend\app\api\routes\agents.py:181` — Function '_stream_agent_events' is 222 lines long — consider splitting
- `backend\app\api\routes\agents.py:412` — Function 'run_agent' is 245 lines long — consider splitting
- `backend\app\api\routes\agents.py:767` — Function 'resume_execution' is 175 lines long — consider splitting
- `backend\app\api\routes\agents.py:1028` — Function 'export_draft' is 61 lines long — consider splitting
- `backend\app\api\routes\agents.py:1104` — Function 'revise_research_section' is 99 lines long — consider splitting
- `backend\app\api\routes\agents.py:1211` — Function 'export_research_memo' is 66 lines long — consider splitting
- `backend\app\api\routes\agents.py:1291` — Function 'create_agent_session' is 227 lines long — consider splitting
- `backend\app\api\routes\agents.py:1527` — Function 'session_follow_up' is 259 lines long — consider splitting
- `backend\app\api\routes\agents.py:1795` — Function 'list_sessions' is 51 lines long — consider splitting
- `backend\app\api\routes\agents.py:207` — Function '_run_graph' is 152 lines long — consider splitting
- `backend\app\api\routes\agents.py:1666` — Function '_follow_up_stream' is 114 lines long — consider splitting
- `backend\app\api\routes\agents.py:1684` — Function '_producer' is 71 lines long — consider splitting
- `backend\app\api\routes\auth.py:75` — Function 'register' is 68 lines long — consider splitting
- `backend\app\api\routes\auth.py:147` — Function 'login' is 86 lines long — consider splitting
- `backend\app\api\routes\auth.py:304` — Function 'delete_account' is 89 lines long — consider splitting
- `backend\app\api\routes\cases.py:36` — Function 'get_case' is 52 lines long — consider splitting
- `backend\app\api\routes\cases.py:278` — Function 'get_similar' is 54 lines long — consider splitting
- `backend\app\api\routes\chat.py:61` — Function 'create_chat' is 54 lines long — consider splitting
- _...and 253 more_

**LOW:**
- `frontend\src\__tests__\case-prep-workspace.test.tsx:71` — Loose equality (==) — use strict equality (===)
- `frontend\src\__tests__\drafting-agent-workspace.test.tsx:176` — Loose equality (==) — use strict equality (===)
- `frontend\src\__tests__\login-page.test.tsx:86` — Loose equality (==) — use strict equality (===)
- `frontend\src\__tests__\research-workspace.test.tsx:60` — Loose equality (==) — use strict equality (===)
- `frontend\src\__tests__\strategy-agent-workspace.test.tsx:171` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:87` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:118` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:120` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:125` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:142` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:158` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:183` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:246` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:247` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\case-prep\page.tsx:282` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\drafting\page.tsx:62` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\drafting\page.tsx:148` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\drafting\page.tsx:150` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\drafting\page.tsx:155` — Loose equality (==) — use strict equality (===)
- `frontend\src\app\agents\drafting\page.tsx:165` — Loose equality (==) — use strict equality (===)
- _...and 203 more_


### ERROR_HANDLING_GAPS (465 issues)

**HIGH:**
- `backend\app\api\routes\agents.py:389` — try block with no except handlers
- `backend\app\api\routes\agents.py:1768` — try block with no except handlers
- `backend\app\api\routes\documents.py:73` — try block with no except handlers
- `backend\app\core\ingestion\pdf.py:394` — try block with no except handlers
- `backend\app\core\middleware.py:45` — try block with no except handlers
- `backend\app\db\postgres.py:78` — try block with no except handlers
- `backend\scripts\ingest_s3.py:982` — try block with no except handlers
- `backend\scripts\populate_neo4j.py:620` — try block with no except handlers
- `backend\scripts\populate_neo4j.py:776` — try block with no except handlers
- `backend\tests\unit\test_migration_011.py:208` — try block with no except handlers
- `backend\tests\unit\test_migration_011.py:238` — try block with no except handlers
- `backend\tests\unit\test_migration_011.py:257` — try block with no except handlers
- `backend\tests\unit\test_migration_011.py:276` — try block with no except handlers
- `backend\tests\unit\test_migration_011.py:306` — try block with no except handlers
- `frontend\next.config.ts:16` — Async function 'rewrites' has no try/catch — unhandled promise rejection risk
- `frontend\next.config.ts:26` — Async function 'headers' has no try/catch — unhandled promise rejection risk
- `frontend\src\app\agents\research\page.tsx:617` — Async function 'handleFollowUp' has no try/catch — unhandled promise rejection risk
- `frontend\src\components\audio-player.tsx:68` — Async function 'load' has no try/catch — unhandled promise rejection risk
- `frontend\src\lib\api.ts:251` — Async function '_doRefresh' has no try/catch — unhandled promise rejection risk
- `frontend\src\lib\api.ts:335` — Async function 'searchFacets' has no try/catch — unhandled promise rejection risk
- _...and 13 more_

**MEDIUM:**
- `backend\app\api\routes\agents.py:355` — Broad Exception catch — be more specific
- `backend\app\api\routes\agents.py:378` — Broad Exception catch — be more specific
- `backend\app\api\routes\agents.py:523` — Broad Exception catch — be more specific
- `backend\app\api\routes\agents.py:549` — Broad Exception catch — be more specific
- `backend\app\api\routes\agents.py:1511` — Broad Exception catch — be more specific
- `backend\app\api\routes\agents.py:1639` — Broad Exception catch — be more specific
- `backend\app\api\routes\agents.py:1751` — Broad Exception catch — be more specific
- `backend\app\api\routes\chat.py:103` — Broad Exception catch — be more specific
- `backend\app\api\routes\chat.py:180` — Broad Exception catch — be more specific
- `backend\app\api\routes\documents.py:86` — Empty pass statement — silent failure
- `backend\app\api\routes\ingest.py:99` — Broad Exception catch — be more specific
- `backend\app\api\routes\search.py:211` — Broad Exception catch — be more specific
- `backend\app\api\routes\search.py:215` — Broad Exception catch — be more specific
- `backend\app\core\agents\nodes\common.py:224` — Broad Exception catch — be more specific
- `backend\app\core\agents\nodes\common.py:448` — Broad Exception catch — be more specific
- `backend\app\core\agents\nodes\common.py:469` — Broad Exception catch — be more specific
- `backend\app\core\agents\nodes\common.py:603` — Empty pass statement — silent failure
- `backend\app\core\agents\nodes\common.py:610` — Empty pass statement — silent failure
- `backend\app\core\agents\nodes\common.py:619` — Empty pass statement — silent failure
- `backend\app\core\agents\nodes\common.py:790` — Broad Exception catch — be more specific
- _...and 134 more_

**LOW:**
- `backend\app\api\routes\admin_corrections.py:143` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\admin_corrections.py:216` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:1637` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:363` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:511` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:515` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:521` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:527` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:827` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:831` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:1177` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:1410` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:1414` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:1486` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:391` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:1758` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:341` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:368` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:1770` — try/except without finally or re-raise — errors may be silently swallowed
- `backend\app\api\routes\agents.py:1741` — try/except without finally or re-raise — errors may be silently swallowed
- _...and 258 more_


### LOGGING_GAPS (290 issues)

**LOW:**
- `backend\scripts\audit_migration.py:24` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:25` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:26` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:48` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:50` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:51` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:58` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:59` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:60` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:61` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:119` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:121` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:125` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:127` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:132` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:133` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:134` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:135` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:144` — print() used — should use proper logging
- `backend\scripts\audit_migration.py:149` — print() used — should use proper logging
- _...and 259 more_

**INFO:**
- `frontend\src\app\agents\case-prep\page.tsx:90` — console.error found — verify error reporting
- `frontend\src\app\chat\page.tsx:173` — console.error found — verify error reporting
- `frontend\src\app\chat\page.tsx:194` — console.error found — verify error reporting
- `frontend\src\app\chat\page.tsx:230` — console.error found — verify error reporting
- `frontend\src\app\chat\page.tsx:673` — console.error found — verify error reporting
- `frontend\src\app\graph\page.tsx:83` — console.error found — verify error reporting
- `frontend\src\app\graph\page.tsx:131` — console.error found — verify error reporting
- `frontend\src\app\graph\page.tsx:137` — console.error found — verify error reporting
- `frontend\src\app\graph\page.tsx:140` — console.error found — verify error reporting
- `frontend\src\app\search\page.tsx:108` — console.error found — verify error reporting
- `frontend\src\components\error-boundary.tsx:15` — console.error found — verify error reporting


### PERFORMANCE_BOTTLENECKS (121 issues)

**HIGH:**
- `backend\app\api\routes\agents.py:181` — Function '_stream_agent_events' has high cyclomatic complexity: 35
- `backend\app\api\routes\agents.py:412` — Function 'run_agent' has high cyclomatic complexity: 37
- `backend\app\api\routes\agents.py:767` — Function 'resume_execution' has high cyclomatic complexity: 16
- `backend\app\api\routes\agents.py:1104` — Function 'revise_research_section' has high cyclomatic complexity: 19
- `backend\app\api\routes\agents.py:1291` — Function 'create_agent_session' has high cyclomatic complexity: 35
- `backend\app\api\routes\agents.py:1527` — Function 'session_follow_up' has high cyclomatic complexity: 21
- `backend\app\api\routes\agents.py:207` — Function '_run_graph' has high cyclomatic complexity: 29
- `backend\app\api\routes\agents.py:1666` — Function '_follow_up_stream' has high cyclomatic complexity: 12
- `backend\app\api\routes\search.py:44` — Function 'search' has high cyclomatic complexity: 20
- `backend\app\core\agents\nodes\case_prep_nodes.py:159` — Function 'deep_precedent_search_node' has high cyclomatic complexity: 14
- `backend\app\core\agents\nodes\common.py:104` — Function '_fetch_statute_from_db' has high cyclomatic complexity: 17
- `backend\app\core\agents\nodes\common.py:291` — Function 'format_search_results_for_llm' has high cyclomatic complexity: 11
- `backend\app\core\agents\nodes\common.py:374` — Function 'deduplicate_with_diversity' has high cyclomatic complexity: 14
- `backend\app\core\agents\nodes\common.py:425` — Function '_search_by_title' has high cyclomatic complexity: 12
- `backend\app\core\agents\nodes\common.py:520` — Function 'enrich_results_with_ratio' has high cyclomatic complexity: 15
- `backend\app\core\agents\nodes\common.py:710` — Function 'verify_memo_citations' has high cyclomatic complexity: 15
- `backend\app\core\agents\nodes\common.py:812` — Function '_check_holding_accuracy' has high cyclomatic complexity: 17
- `backend\app\core\agents\nodes\research_nodes.py:421` — Function 'synthesize_memo_node' has high cyclomatic complexity: 14
- `backend\app\core\agents\nodes\research_nodes.py:643` — Function 'plan_research_node' has high cyclomatic complexity: 18
- `backend\app\core\agents\nodes\research_nodes.py:759` — Function 'gather_worker_results_node' has high cyclomatic complexity: 14
- _...and 85 more_

**MEDIUM:**
- `frontend\src\app\case\[id]\page.tsx:246` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\app\case\[id]\page.tsx:272` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\app\courts\page.tsx:194` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\app\documents\[id]\page.tsx:99` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\app\documents\[id]\page.tsx:398` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\app\judge\[name]\page.tsx:189` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\agent-checkpoint-prompt.tsx:62` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\agent-memo-viewer.tsx:555` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\agent-step-timeline.tsx:67` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\equivalent-citations.tsx:58` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\plan-review.tsx:155` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\plan-review.tsx:301` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\plan-review.tsx:336` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\research-process-panel.tsx:79` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\research-progress-bar.tsx:123` — Array index used as key — causes rendering bugs on reorder
- `frontend\src\components\skeleton.tsx:13` — Array index used as key — causes rendering bugs on reorder


### STATE_MANAGEMENT_BUGS (91 issues)

**INFO:**
- `frontend\src\app\agents\case-prep\page.tsx:53` — useState found — verify state update patterns
- `frontend\src\app\agents\case-prep\page.tsx:55` — useState found — verify state update patterns
- `frontend\src\app\agents\case-prep\page.tsx:63` — useState found — verify state update patterns
- `frontend\src\app\agents\case-prep\page.tsx:64` — useState found — verify state update patterns
- `frontend\src\app\agents\case-prep\page.tsx:71` — useState found — verify state update patterns
- `frontend\src\app\agents\drafting\page.tsx:60` — useState found — verify state update patterns
- `frontend\src\app\agents\drafting\page.tsx:61` — useState found — verify state update patterns
- `frontend\src\app\agents\drafting\page.tsx:65` — useState found — verify state update patterns
- `frontend\src\app\agents\drafting\page.tsx:66` — useState found — verify state update patterns
- `frontend\src\app\agents\drafting\page.tsx:73` — useState found — verify state update patterns
- `frontend\src\app\agents\drafting\page.tsx:74` — useState found — verify state update patterns
- `frontend\src\app\agents\drafting\page.tsx:81` — useState found — verify state update patterns
- `frontend\src\app\agents\history\page.tsx:125` — useState found — verify state update patterns
- `frontend\src\app\agents\history\page.tsx:126` — useState found — verify state update patterns
- `frontend\src\app\agents\history\page.tsx:127` — useState found — verify state update patterns
- `frontend\src\app\agents\history\page.tsx:135` — useState found — verify state update patterns
- `frontend\src\app\agents\history\page.tsx:136` — useState found — verify state update patterns
- `frontend\src\app\agents\history\page.tsx:137` — useState found — verify state update patterns
- `frontend\src\app\agents\research\page.tsx:106` — useState found — verify state update patterns
- `frontend\src\app\agents\research\page.tsx:109` — useState found — verify state update patterns
- _...and 71 more_


### FUNCTION_SIGNATURE_AUDIT (57 issues)

**MEDIUM:**
- `backend\app\api\routes\admin_review.py:32` — Function 'list_review_queue' has 7 parameters — consider using a config object
- `backend\app\api\routes\judges.py:159` — Function 'get_judge_cases' has 6 parameters — consider using a config object
- `backend\app\api\routes\search.py:44` — Function 'search' has 15 parameters — consider using a config object
- `backend\app\core\agents\confidence.py:135` — Function 'calculate_confidence_detailed' has 6 parameters — consider using a config object
- `backend\app\core\agents\nodes\case_prep_nodes.py:159` — Function 'deep_precedent_search_node' has 7 parameters — consider using a config object
- `backend\app\core\agents\nodes\common.py:925` — Function 'parallel_hybrid_search' has 7 parameters — consider using a config object
- `backend\app\core\agents\nodes\research_nodes.py:256` — Function 'parallel_search_node' has 6 parameters — consider using a config object
- `backend\app\core\agents\nodes\research_nodes.py:1359` — Function 'fast_path_search_node' has 7 parameters — consider using a config object
- `backend\app\core\agents\nodes\strategy_nodes.py:183` — Function 'search_precedents_node' has 7 parameters — consider using a config object
- `backend\app\core\agents\nodes\worker_nodes.py:197` — Function 'named_case_worker' has 6 parameters — consider using a config object
- `backend\app\core\analysis\document_analyzer.py:107` — Function 'generate_research_memo' has 7 parameters — consider using a config object
- `backend\app\core\analysis\precedent_mapper.py:30` — Function '__init__' has 6 parameters — consider using a config object
- `backend\app\core\analytics\judge_analytics.py:302` — Function 'get_judge_cases' has 6 parameters — consider using a config object
- `backend\app\core\ingestion\contextual_embeddings.py:89` — Function 'batch_contextualize_chunks' has 6 parameters — consider using a config object
- `backend\app\core\ingestion\pipeline.py:619` — Function '_insert_case' has 6 parameters — consider using a config object
- `backend\app\core\legal\precedent_strength.py:68` — Function 'classify_precedent_strength' has 7 parameters — consider using a config object
- `backend\app\security\audit.py:17` — Function 'create_audit_log' has 8 parameters — consider using a config object
- `backend\scripts\backfill_contextual_embeddings.py:27` — Function 'backfill_case' has 6 parameters — consider using a config object
- `backend\scripts\batch_state.py:63` — Function 'insert_doc' has 9 parameters — consider using a config object
- `backend\scripts\ingest_statutes.py:278` — Function 'ingest_statute_file' has 8 parameters — consider using a config object
- _...and 37 more_


### HARDCODED_SECRETS (27 issues)

**CRITICAL:**
- `backend\tests\load\locustfile.py:56` — Hardcoded password detected
- `backend\tests\unit\test_hindi_search.py:16` — Hardcoded API key detected
- `backend\tests\unit\test_pinecone_store_tenant.py:27` — Hardcoded API key detected
- `backend\tests\unit\test_pinecone_store_tenant.py:43` — Hardcoded API key detected
- `backend\tests\unit\test_pinecone_store_tenant.py:59` — Hardcoded API key detected
- `backend\tests\unit\test_provider_switching.py:36` — Hardcoded API key detected
- `backend\tests\unit\test_provider_switching.py:78` — Hardcoded password detected
- `backend\tests\unit\test_research_v2_phase3.py:230` — Hardcoded API key detected
- `backend\tests\unit\test_research_v2_phase3.py:254` — Hardcoded API key detected
- `backend\tests\unit\test_research_v2_phase5.py:478` — Hardcoded API key detected
- `backend\tests\unit\test_research_v2_phase5.py:483` — Hardcoded API key detected
- `backend\tests\unit\test_tavily_client.py:20` — Hardcoded API key detected
- `backend\tests\unit\test_tavily_client.py:29` — Hardcoded API key detected
- `backend\tests\unit\test_tavily_client.py:106` — Hardcoded API key detected
- `docker-compose.prod.yml:8` — Potential password in YAML config
- `docker-compose.yml:7` — Potential password in YAML config

**HIGH:**
- `backend\app\core\config.py:40` — Hardcoded database connection string
- `backend\app\core\config.py:43` — Hardcoded database connection string
- `backend\app\core\config.py:44` — Hardcoded database connection string
- `backend\tests\unit\test_auth.py:30` — Hardcoded database connection string
- `frontend\package-lock.json:0` — JSON key '@csstools/css-tokenizer' may contain a secret in package-lock.json
- `frontend\package-lock.json:0` — JSON key 'js-tokens' may contain a secret in package-lock.json
- `frontend\package-lock.json:0` — JSON key 'comma-separated-tokens' may contain a secret in package-lock.json
- `frontend\package-lock.json:0` — JSON key 'space-separated-tokens' may contain a secret in package-lock.json
- `frontend\package-lock.json:0` — JSON key 'micromark-util-subtokenize' may contain a secret in package-lock.json
- `frontend\package-lock.json:0` — JSON key '@radix-ui/react-one-time-password-field' may contain a secret in package-lock.json
- `frontend\package-lock.json:0` — JSON key '@radix-ui/react-password-toggle-field' may contain a secret in package-lock.json


### SECURITY_VULNERABILITIES (13 issues)

**CRITICAL:**
- `backend\app\main.py:32` — Use of exec() — potential code injection
- `backend\tests\unit\test_research_v2_phase3.py:506` — Use of eval() — potential code injection
- `backend\tests\unit\test_research_v2_phase3.py:541` — Use of eval() — potential code injection
- `ralph_loop_scanner.py:278` — Use of eval() — potential code injection
- `ralph_loop_scanner.py:279` — Use of exec() — potential code injection
- `ralph_loop_scanner.py:477` — Use of eval() — potential code injection

**HIGH:**
- `ralph_loop_scanner.py:281` — os.system() used — prefer subprocess with shell=False

**MEDIUM:**
- `frontend\src\components\cookie-consent.tsx:14` — localStorage used — sensitive data should not be stored client-side
- `frontend\src\components\cookie-consent.tsx:21` — localStorage used — sensitive data should not be stored client-side
- `frontend\src\lib\api.ts:52` — localStorage used — sensitive data should not be stored client-side
- `frontend\src\lib\api.ts:53` — localStorage used — sensitive data should not be stored client-side
- `frontend\src\lib\api.ts:68` — localStorage used — sensitive data should not be stored client-side
- `frontend\src\lib\api.ts:69` — localStorage used — sensitive data should not be stored client-side


### DEAD_CODE_DETECTION (2 issues)

**LOW:**
- `backend\app\core\graph\traversal.py:181` — TODO comment found — incomplete implementation
- `backend\scripts\ingest_s3.py:1092` — TODO comment found — incomplete implementation


---

## 3. HOTSPOT FILES (Most Issues)

| File | Issues |
|------|--------|
| `backend\tests\unit\test_extractor.py` | 103 |
| `backend\tests\unit\test_metadata.py` | 99 |
| `backend\tests\unit\test_chunker.py` | 91 |
| `backend\tests\unit\test_migration_011.py` | 85 |
| `backend\scripts\audit_migration.py` | 77 |
| `backend\app\core\agents\nodes\research_nodes.py` | 73 |
| `backend\tests\unit\test_acts_normalization.py` | 71 |
| `backend\tests\unit\test_research_v2_phase5.py` | 69 |
| `backend\scripts\e2e_test_apis.py` | 64 |
| `frontend\src\app\agents\research\page.tsx` | 51 |
| `backend\app\core\ingestion\pipeline.py` | 50 |
| `backend\tests\unit\test_35k_hardening.py` | 50 |
| `backend\app\api\routes\agents.py` | 49 |
| `backend\tests\unit\test_statute_expansion.py` | 48 |
| `backend\tests\unit\test_follow_up_nodes.py` | 47 |
| `backend\tests\unit\test_strategy_nodes.py` | 47 |
| `backend\tests\unit\test_research_nodes.py` | 42 |
| `backend\app\core\agents\nodes\common.py` | 40 |
| `ralph_loop_scanner.py` | 40 |
| `backend\tests\unit\test_courts.py` | 38 |
| `backend\tests\unit\test_pg_graph_store.py` | 38 |
| `backend\tests\unit\test_sanitizer.py` | 38 |
| `backend\scripts\ingest_s3.py` | 37 |
| `backend\tests\unit\test_anonymizer.py` | 37 |
| `backend\tests\unit\test_common_nodes.py` | 37 |
| `backend\app\core\agents\nodes\worker_nodes.py` | 36 |
| `backend\tests\unit\test_admin_routes.py` | 36 |
| `backend\tests\unit\test_hybrid_search.py` | 36 |
| `frontend\src\lib\api.ts` | 35 |
| `backend\tests\unit\test_agent_prompts.py` | 34 |

---

## 4. ITERATION TIMELINE

| Iteration | Focus | New Issues | Duration (s) | Timestamp |
|-----------|-------|------------|--------------|-----------|
| 1 | SURFACE_SCAN | 4111 | 5.0 | 2026-03-27T11:54:41 |
| 2 | SURFACE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 3 | SURFACE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 4 | SURFACE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 5 | SURFACE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 6 | SURFACE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 7 | SURFACE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 8 | SURFACE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 9 | SURFACE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 10 | SURFACE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 11 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 12 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 13 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 14 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 15 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 16 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 17 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 18 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 19 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 20 | LOGIC_TRACE | 0 | 5.0 | 2026-03-27T11:54:41 |
| 21 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 22 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 23 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 24 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 25 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 26 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 27 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 28 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 29 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 30 | ERROR_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 31 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 32 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 33 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 34 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 35 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 36 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 37 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 38 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 39 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 40 | SECURITY_SWEEP | 0 | 5.0 | 2026-03-27T11:54:41 |
| 41 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 42 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 43 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 44 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 45 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 46 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 47 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 48 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 49 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 50 | PERFORMANCE_SCAN | 0 | 5.0 | 2026-03-27T11:54:41 |
| 51 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 52 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 53 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 54 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 55 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 56 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 57 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 58 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 59 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 60 | STATE_ANALYSIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 61 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 62 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 63 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 64 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 65 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 66 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 67 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 68 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 69 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 70 | DEPENDENCY_AUDIT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 71 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 72 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 73 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 74 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 75 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 76 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 77 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 78 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 79 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 80 | DEAD_CODE_HUNT | 0 | 5.0 | 2026-03-27T11:54:41 |
| 81 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 82 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 83 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 84 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 85 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 86 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 87 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 88 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 89 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 90 | API_CONTRACT_CHECK | 0 | 5.0 | 2026-03-27T11:54:41 |
| 91 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 92 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 93 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 94 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 95 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 96 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 97 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 98 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 99 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |
| 100 | FINAL_SYNTHESIS | 0 | 5.0 | 2026-03-27T11:54:41 |

---

## 5. CRITICAL ISSUES — FULL DETAIL

### Critical #1
- **Category:** SECURITY_VULNERABILITIES
- **File:** `backend\app\main.py`
- **Line:** 32
- **Message:** Use of exec() — potential code injection
```
proc = await asyncio.create_subprocess_exec(
```

### Critical #2
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\load\locustfile.py`
- **Line:** 56
- **Message:** Hardcoded password detected
```
password = "LoadTest1234"...[REDACTED]
```

### Critical #3
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_hindi_search.py`
- **Line:** 16
- **Message:** Hardcoded API key detected
```
mock_settings.gemini_api_key = "test-key"...[REDACTED]
```

### Critical #4
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_pinecone_store_tenant.py`
- **Line:** 27
- **Message:** Hardcoded API key detected
```
mock_settings.pinecone_api_key = "test-key"...[REDACTED]
```

### Critical #5
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_pinecone_store_tenant.py`
- **Line:** 43
- **Message:** Hardcoded API key detected
```
mock_settings.pinecone_api_key = "test-key"...[REDACTED]
```

### Critical #6
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_pinecone_store_tenant.py`
- **Line:** 59
- **Message:** Hardcoded API key detected
```
mock_settings.pinecone_api_key = "test-key"...[REDACTED]
```

### Critical #7
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_provider_switching.py`
- **Line:** 36
- **Message:** Hardcoded API key detected
```
mock_settings.pinecone_api_key = "test-key"...[REDACTED]
```

### Critical #8
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_provider_switching.py`
- **Line:** 78
- **Message:** Hardcoded password detected
```
mock_settings.neo4j_password = "test"...[REDACTED]
```

### Critical #9
- **Category:** SECURITY_VULNERABILITIES
- **File:** `backend\tests\unit\test_research_v2_phase3.py`
- **Line:** 506
- **Message:** Use of eval() — potential code injection
```
async def test_semantic_retrieval(self) -> None:
```

### Critical #10
- **Category:** SECURITY_VULNERABILITIES
- **File:** `backend\tests\unit\test_research_v2_phase3.py`
- **Line:** 541
- **Message:** Use of eval() — potential code injection
```
async def test_graph_overlap_retrieval(self) -> None:
```

### Critical #11
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_research_v2_phase3.py`
- **Line:** 230
- **Message:** Hardcoded API key detected
```
client = TavilySearchClient(api_key="test-key")...[REDACTED]
```

### Critical #12
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_research_v2_phase3.py`
- **Line:** 254
- **Message:** Hardcoded API key detected
```
client = TavilySearchClient(api_key="test-key")...[REDACTED]
```

### Critical #13
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_research_v2_phase5.py`
- **Line:** 478
- **Message:** Hardcoded API key detected
```
s = Settings(gemini_api_key="test", _env_file=None)...[REDACTED]
```

### Critical #14
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_research_v2_phase5.py`
- **Line:** 483
- **Message:** Hardcoded API key detected
```
s = Settings(gemini_api_key="test", _env_file=None)...[REDACTED]
```

### Critical #15
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_tavily_client.py`
- **Line:** 20
- **Message:** Hardcoded API key detected
```
s.tavily_api_key = "test-key"...[REDACTED]
```

### Critical #16
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_tavily_client.py`
- **Line:** 29
- **Message:** Hardcoded API key detected
```
return TavilySearchClient(api_key="test-key")...[REDACTED]
```

### Critical #17
- **Category:** HARDCODED_SECRETS
- **File:** `backend\tests\unit\test_tavily_client.py`
- **Line:** 106
- **Message:** Hardcoded API key detected
```
client = TavilySearchClient(api_key="test-key")...[REDACTED]
```

### Critical #18
- **Category:** HARDCODED_SECRETS
- **File:** `docker-compose.prod.yml`
- **Line:** 8
- **Message:** Potential password in YAML config
```
POSTGRES_PASSWORD: [REDACTED]
```

### Critical #19
- **Category:** HARDCODED_SECRETS
- **File:** `docker-compose.yml`
- **Line:** 7
- **Message:** Potential password in YAML config
```
POSTGRES_PASSWORD: [REDACTED]
```

### Critical #20
- **Category:** SECURITY_VULNERABILITIES
- **File:** `ralph_loop_scanner.py`
- **Line:** 278
- **Message:** Use of eval() — potential code injection
```
(r'eval\s*\(', "SECURITY_VULNERABILITIES", "CRITICAL", "Use of eval() — potential code injection"),
```

### Critical #21
- **Category:** SECURITY_VULNERABILITIES
- **File:** `ralph_loop_scanner.py`
- **Line:** 279
- **Message:** Use of exec() — potential code injection
```
(r'exec\s*\(', "SECURITY_VULNERABILITIES", "CRITICAL", "Use of exec() — potential code injection"),
```

### Critical #22
- **Category:** SECURITY_VULNERABILITIES
- **File:** `ralph_loop_scanner.py`
- **Line:** 477
- **Message:** Use of eval() — potential code injection
```
(r'eval\s*\(', "SECURITY_VULNERABILITIES", "CRITICAL", "eval() used — code injection risk"),
```

---

## 6. COMPLETE FUNCTION REGISTRY

Every function discovered across all files:

### `backend\app\api\routes\admin_corrections.py`
- **correct_metadata**(`case_id, body, user, db`) — Line 93, Complexity: 10
- **correction_history**(`case_id, user, db`) — Line 191, Complexity: 5
- **_serialize**(`value`) — Line 228, Complexity: 3

### `backend\app\api\routes\admin_review.py`
- **_validate_uuid**(`value, name`) — Line 22, Complexity: 2
- **list_review_queue**(`status, sort_by, order, page, page_size, user, db`) — Line 32, Complexity: 2
- **get_review_detail**(`case_id, user, db`) — Line 115, Complexity: 3
- **approve_case**(`case_id, user, db`) — Line 143, Complexity: 2
- **reject_case**(`case_id, user, db`) — Line 170, Complexity: 2

### `backend\app\api\routes\agents.py`
- **_categorize_error**(`exc`) — Line 62, Complexity: 10
- **_stream_agent_events**(`graph, initial_input, config, exec_id, graph_kwargs`) — Line 181, Complexity: 35
- **run_agent**(`agent_type, user, db, request_body`) — Line 412, Complexity: 37
- **list_executions**(`page, page_size, user, db`) — Line 666, Complexity: 1
- **get_execution**(`execution_id, user, db`) — Line 723, Complexity: 4
- **resume_execution**(`execution_id, body, user, db`) — Line 767, Complexity: 16
- **cancel_execution**(`execution_id, user, db`) — Line 951, Complexity: 5
- **get_drafting_templates**(`user`) — Line 1004, Complexity: 1
- **export_draft**(`execution_id, format, user, db`) — Line 1028, Complexity: 10
- **revise_research_section**(`execution_id, body, user, db`) — Line 1104, Complexity: 19
- **export_research_memo**(`execution_id, format, user, db`) — Line 1211, Complexity: 10
- **create_agent_session**(`agent_type, request_body, user, db`) — Line 1291, Complexity: 35
- **session_follow_up**(`session_id, body, user, db`) — Line 1527, Complexity: 21
- **list_sessions**(`agent_type, page, page_size, user, db`) — Line 1795, Complexity: 2
- **get_session**(`session_id, user, db`) — Line 1855, Complexity: 4
- **get_session_messages**(`session_id, user, db`) — Line 1910, Complexity: 4
- **delete_session**(`session_id, user, db`) — Line 1960, Complexity: 4
- **validate_document_id_as_uuid**(`cls, v`) — Line 120, Complexity: 2
- **validate_precedents_length**(`cls, v`) — Line 152, Complexity: 2
- **validate_additional_context**(`cls, v`) — Line 159, Complexity: 4
- **_run_graph**(`0 args`) — Line 207, Complexity: 29
- **_run_graph_with_timeout**(`0 args`) — Line 361, Complexity: 3
- **_stream_revision**(`0 args`) — Line 1174, Complexity: 4
- **_session_stream**(`0 args`) — Line 1475, Complexity: 5
- **_follow_up_stream**(`0 args`) — Line 1666, Complexity: 12
- **_memo_stream_cb**(`chunk`) — Line 1675, Complexity: 1
- **_producer**(`0 args`) — Line 1684, Complexity: 7
- **_producer_with_timeout**(`0 args`) — Line 1757, Complexity: 2
- **_memo_stream_cb**(`chunk`) — Line 215, Complexity: 3
- **_cached_stream**(`0 args`) — Line 555, Complexity: 3
- **_cached_stream_semantic**(`0 args`) — Line 534, Complexity: 3

### `backend\app\api\routes\audio.py`
- **_validate_uuid**(`value, name`) — Line 18, Complexity: 2
- **generate_audio_digest**(`case_id, language, db, current_user`) — Line 28, Complexity: 6
- **get_audio_status**(`case_id, db`) — Line 70, Complexity: 1
- **stream_audio**(`case_id, language, db`) — Line 98, Complexity: 4
- **audio_generator**(`0 args`) — Line 126, Complexity: 1

### `backend\app\api\routes\auth.py`
- **register**(`body, db`) — Line 75, Complexity: 3
- **login**(`body, request, db`) — Line 147, Complexity: 9
- **refresh_token**(`body, request, db`) — Line 237, Complexity: 3
- **logout**(`body, current_user`) — Line 282, Complexity: 4
- **delete_account**(`request, current_user, db`) — Line 304, Complexity: 5
- **validate_password_strength**(`cls, v`) — Line 42, Complexity: 5

### `backend\app\api\routes\cases.py`
- **get_case**(`case_id, db`) — Line 36, Complexity: 8
- **get_case_summary**(`case_id, language, user, db`) — Line 97, Complexity: 6
- **get_case_pdf**(`case_id, db`) — Line 144, Complexity: 6
- **get_citations**(`case_id, db`) — Line 198, Complexity: 4
- **get_cited_by**(`case_id, db`) — Line 239, Complexity: 4
- **get_similar**(`case_id, limit, db, _current_user`) — Line 278, Complexity: 9
- **_is_valid_uuid**(`val`) — Line 340, Complexity: 2
- **_enrich_graph_nodes**(`neighbors, db`) — Line 349, Complexity: 10
- **_enrich_similar_results**(`similar_ids, db`) — Line 392, Complexity: 3

### `backend\app\api\routes\chat.py`
- **_validate_uuid**(`value, name`) — Line 37, Complexity: 2
- **create_chat**(`body, user, db`) — Line 61, Complexity: 4
- **send_message**(`session_id, body, user, db`) — Line 124, Complexity: 6
- **list_sessions**(`user, db, page, page_size`) — Line 201, Complexity: 1
- **get_history**(`session_id, user, db`) — Line 252, Complexity: 3
- **delete_session**(`session_id, request, user, db`) — Line 301, Complexity: 3
- **event_stream**(`0 args`) — Line 80, Complexity: 3
- **event_stream**(`0 args`) — Line 157, Complexity: 3

### `backend\app\api\routes\data_quality.py`
- **data_quality_dashboard**(`user, db`) — Line 23, Complexity: 4

### `backend\app\api\routes\documents.py`
- **_sanitize_filename**(`filename`) — Line 29, Complexity: 3
- **_validate_pdf_content**(`content`) — Line 40, Complexity: 3
- **upload_document**(`file, db, current_user`) — Line 52, Complexity: 6
- **list_documents**(`page, page_size, db, current_user`) — Line 116, Complexity: 2
- **get_document**(`document_id, db, current_user`) — Line 153, Complexity: 5
- **delete_document**(`document_id, request, db, current_user`) — Line 196, Complexity: 4
- **get_research_memo**(`document_id, db, current_user`) — Line 246, Complexity: 5

### `backend\app\api\routes\dpdp.py`
- **data_summary**(`user, db`) — Line 25, Complexity: 1
- **request_erasure**(`user, db`) — Line 62, Complexity: 5
- **withdraw_consent**(`user, db`) — Line 143, Complexity: 1
- **consent_status**(`user, db`) — Line 167, Complexity: 1

### `backend\app\api\routes\graph.py`
- **neighborhood**(`case_id, depth, _current_user`) — Line 32, Complexity: 2
- **chain**(`case_id, max_depth, _current_user`) — Line 52, Complexity: 2
- **authorities**(`case_id, limit, _current_user`) — Line 72, Complexity: 2
- **stats**(`_current_user`) — Line 93, Complexity: 2

### `backend\app\api\routes\health.py`
- **_timed_check**(`name, coro`) — Line 25, Complexity: 2
- **_check_postgres**(`0 args`) — Line 34, Complexity: 2
- **_check_redis**(`0 args`) — Line 57, Complexity: 2
- **_check_pinecone**(`0 args`) — Line 78, Complexity: 2
- **_check_neo4j**(`0 args`) — Line 100, Complexity: 2
- **_check_gemini**(`0 args`) — Line 121, Complexity: 2
- **_compute_overall_status**(`deps`) — Line 143, Complexity: 6
- **health_check**(`current_user`) — Line 161, Complexity: 2

### `backend\app\api\routes\ingest.py`
- **_sanitize_filename**(`filename`) — Line 28, Complexity: 3
- **upload_document**(`file, db, current_user`) — Line 41, Complexity: 9
- **get_ingest_status**(`document_id, db, current_user`) — Line 110, Complexity: 3
- **data_completeness_dashboard**(`db, current_user`) — Line 137, Complexity: 5
- **list_review_queue**(`limit, offset, db, current_user`) — Line 218, Complexity: 2
- **update_case_metadata**(`case_id, body, db, current_user`) — Line 259, Complexity: 6
- **approve_case**(`case_id, db, current_user`) — Line 342, Complexity: 3
- **retry_failed_case**(`case_id, db, current_user`) — Line 373, Complexity: 3

### `backend\app\api\routes\judges.py`
- **_get_cached_or_compute**(`redis_client, cache_key, compute_fn, ttl`) — Line 30, Complexity: 7
- **list_judges**(`search, page, page_size, db`) — Line 69, Complexity: 1
- **compare_judges**(`names, db`) — Line 96, Complexity: 2
- **get_judge_profile**(`judge_name, db`) — Line 124, Complexity: 3
- **get_judge_cases**(`judge_name, page, page_size, year, case_type, db`) — Line 159, Complexity: 1
- **get_court_stats**(`court_name, db`) — Line 201, Complexity: 3

### `backend\app\api\routes\search.py`
- **search**(`response, q, court, year_from, year_to, case_type, bench_type, judge, act, judgment_section, page, page_size, language, db, _current_user`) — Line 44, Complexity: 20
- **suggest**(`q, limit, db`) — Line 227, Complexity: 6
- **facets**(`db`) — Line 287, Complexity: 9
- **search_history**(`page, page_size, user, db`) — Line 350, Complexity: 1
- **toggle_search_bookmark**(`history_id, user, db`) — Line 397, Complexity: 4
- **delete_search_history_entry**(`history_id, user, db`) — Line 437, Complexity: 4
- **_serialize_response**(`response`) — Line 474, Complexity: 1
- **_translate_snippet**(`snippet`) — Line 161, Complexity: 1
- **_save_search_history**(`0 args`) — Line 195, Complexity: 2

### `backend\app\core\agents\case_prep.py`
- **route_after_load**(`state`) — Line 40, Complexity: 2
- **build_case_prep_graph**(`0 args`) — Line 61, Complexity: 2
- **load_analysis**(`state`) — Line 99, Complexity: 1
- **prioritize**(`state`) — Line 103, Complexity: 2
- **deep_search**(`state`) — Line 113, Complexity: 1
- **argument_order**(`state`) — Line 119, Complexity: 1
- **strategy_memo**(`state`) — Line 122, Complexity: 1
- **verify**(`state`) — Line 125, Complexity: 1

### `backend\app\core\agents\checkpointer.py`
- **get_checkpointer_connection_string**(`0 args`) — Line 7, Complexity: 2

### `backend\app\core\agents\confidence.py`
- **_compute_source_diversity**(`worker_types`) — Line 36, Complexity: 1
- **_compute_gap_coverage**(`initial_gap_count, remaining_gap_count`) — Line 51, Complexity: 2
- **calculate_confidence**(`reranker_scores, cross_ref_ratio, precedent_strengths, contradiction_count, total_results`) — Line 65, Complexity: 6
- **calculate_confidence_detailed**(`reranker_scores, cross_ref_ratio, precedent_strengths, contradiction_count, total_results, effective_strengths`) — Line 135, Complexity: 7

### `backend\app\core\agents\drafting.py`
- **route_after_template**(`state`) — Line 45, Complexity: 2
- **build_drafting_graph**(`0 args`) — Line 66, Complexity: 3
- **resolve_template**(`state`) — Line 104, Complexity: 1
- **gather_provisions**(`state`) — Line 107, Complexity: 2
- **verify_precedents**(`state`) — Line 118, Complexity: 1
- **draft_sections**(`state`) — Line 122, Complexity: 1
- **assemble**(`state`) — Line 125, Complexity: 1
- **revise_section**(`state`) — Line 128, Complexity: 2
- **verify_final**(`state`) — Line 138, Complexity: 1

### `backend\app\core\agents\follow_up.py`
- **build_follow_up_graph**(`0 args`) — Line 66, Complexity: 1
- **reformulate**(`state`) — Line 104, Complexity: 1
- **search**(`state`) — Line 107, Complexity: 1
- **synthesize**(`state`) — Line 118, Complexity: 1

### `backend\app\core\agents\nodes\case_prep_nodes.py`
- **load_analysis_node**(`state, db`) — Line 47, Complexity: 4
- **prioritize_issues_node**(`state, llm`) — Line 106, Complexity: 6
- **deep_precedent_search_node**(`state, llm, embedder, vector_store, reranker, graph_store, db`) — Line 159, Complexity: 14
- **build_argument_order_node**(`state, llm`) — Line 293, Complexity: 8
- **generate_strategy_memo_node**(`state, llm`) — Line 359, Complexity: 7
- **verify_citations_node**(`state, db`) — Line 417, Complexity: 6
- **_parse_json_field**(`value`) — Line 81, Complexity: 3
- **_search_issue**(`issue`) — Line 181, Complexity: 2

### `backend\app\core\agents\nodes\citation_verifier.py`
- **extract_citations_from_text**(`text_content`) — Line 64, Complexity: 3
- **verify_citations_against_db**(`citations, db`) — Line 88, Complexity: 6
- **check_grounding**(`memo_citations, search_result_citations`) — Line 152, Complexity: 3

### `backend\app\core\agents\nodes\common.py`
- **_extract_statute_refs**(`text_input`) — Line 68, Complexity: 4
- **_expand_refs**(`refs`) — Line 90, Complexity: 5
- **_fetch_statute_from_db**(`db, refs`) — Line 104, Complexity: 17
- **statute_lookup_node**(`state, db, embedder, vector_store`) — Line 173, Complexity: 6
- **element_decomposition_node**(`state, llm`) — Line 230, Complexity: 7
- **format_search_results_for_llm**(`results, max_snippet_len, max_ratio_len`) — Line 291, Complexity: 11
- **format_search_results_for_llm_extended**(`results, max_snippet_len, max_ratio_len`) — Line 335, Complexity: 1
- **_normalize_title_for_dedup**(`t`) — Line 348, Complexity: 1
- **_normalize_score**(`result`) — Line 356, Complexity: 6
- **deduplicate_with_diversity**(`results, max_chunks_per_case`) — Line 374, Complexity: 14
- **_search_by_title**(`title, db`) — Line 425, Complexity: 12
- **format_extracted_passages**(`passages`) — Line 489, Complexity: 3
- **format_community_summaries**(`summaries`) — Line 505, Complexity: 3
- **enrich_results_with_ratio**(`results, db, max_ratio_len`) — Line 520, Complexity: 15
- **verify_case_ids**(`case_ids, db`) — Line 574, Complexity: 2
- **safe_json_parse**(`raw, default`) — Line 590, Complexity: 8
- **safe_json_parse_list**(`raw`) — Line 623, Complexity: 2
- **check_citation_density**(`section_text, section_name`) — Line 671, Complexity: 3
- **verify_memo_citations**(`memo, db, grounding_citations, embedder`) — Line 710, Complexity: 15
- **_check_holding_accuracy**(`memo, citations, db, embedder`) — Line 812, Complexity: 17
- **collect_grounding_citations**(`results`) — Line 907, Complexity: 4
- **parallel_hybrid_search**(`queries, llm, embedder, vector_store, reranker, db, precomputed_embeddings`) — Line 925, Complexity: 6
- **detect_overruled_cases**(`results`) — Line 988, Complexity: 8
- **get_citation_neighbors**(`graph_store, top_results, seen_ids, max_results`) — Line 1006, Complexity: 9
- **deduplicate_by_case_id**(`results`) — Line 1062, Complexity: 5
- **get_latest_feedback**(`messages, step`) — Line 1080, Complexity: 4
- **get_message_data**(`messages, msg_type`) — Line 1088, Complexity: 4
- **apply_language_suffix**(`system, language`) — Line 1101, Complexity: 2
- **cached_embed_text**(`embedder, text_input`) — Line 1108, Complexity: 3
- **_search_one**(`sq`) — Line 954, Complexity: 2
- **_fetch_one**(`case_id`) — Line 1018, Complexity: 5

### `backend\app\core\agents\nodes\drafting_nodes.py`
- **resolve_template_node**(`state`) — Line 64, Complexity: 6
- **gather_provisions_node**(`state, llm, db`) — Line 93, Complexity: 7
- **verify_precedents_node**(`state, db`) — Line 179, Complexity: 10
- **draft_sections_node**(`state, llm`) — Line 228, Complexity: 9
- **assemble_document_node**(`state, llm`) — Line 322, Complexity: 8
- **revise_section_node**(`state, llm`) — Line 390, Complexity: 10
- **verify_final_node**(`state, db`) — Line 470, Complexity: 2
- **_draft_one**(`section_name`) — Line 273, Complexity: 3

### `backend\app\core\agents\nodes\follow_up_nodes.py`
- **reformulate_with_context_node**(`state, flash_llm`) — Line 25, Complexity: 2
- **targeted_search_node**(`state`) — Line 72, Complexity: 3
- **synthesize_follow_up_node**(`state, llm, memo_stream_callback`) — Line 129, Complexity: 4
- **_format_conversation_history**(`history, max_messages`) — Line 224, Complexity: 3
- **_format_footnotes**(`footnotes, max_footnotes`) — Line 240, Complexity: 3
- **_format_search_results**(`results`) — Line 255, Complexity: 3

### `backend\app\core\agents\nodes\research_nodes.py`
- **emit_status**(`event_type, data`) — Line 92, Complexity: 1
- **_is_degenerate_output**(`text, min_useful_length`) — Line 111, Complexity: 9
- **classify_query_node**(`state, llm`) — Line 140, Complexity: 8
- **decompose_query_node**(`state, llm`) — Line 188, Complexity: 9
- **parallel_search_node**(`state, llm, embedder, vector_store, reranker, db`) — Line 256, Complexity: 2
- **gather_results_node**(`state`) — Line 298, Complexity: 7
- **detect_contradictions_node**(`state, llm`) — Line 358, Complexity: 3
- **synthesize_memo_node**(`state, llm`) — Line 421, Complexity: 14
- **verify_citations_node**(`state, db`) — Line 564, Complexity: 2
- **rewrite_query_node**(`state, llm`) — Line 605, Complexity: 2
- **plan_research_node**(`state, llm`) — Line 643, Complexity: 18
- **gather_worker_results_node**(`state`) — Line 759, Complexity: 14
- **batch_worker_cot_with_reflection_node**(`state, llm`) — Line 878, Complexity: 8
- **_chunked**(`iterable, n`) — Line 955, Complexity: 1
- **evaluate_and_extract_node**(`state, llm, db`) — Line 960, Complexity: 34
- **gap_analysis_node**(`state, llm`) — Line 1195, Complexity: 22
- **fast_path_search_node**(`state, llm, flash_llm, embedder, vector_store, reranker, db`) — Line 1359, Complexity: 8
- **fast_path_synthesis_node**(`state, llm`) — Line 1419, Complexity: 8
- **pre_warm_embeddings_node**(`state, embedder`) — Line 1480, Complexity: 6
- **speculative_synthesis_with_contradictions_node**(`state, llm, flash_llm, stream_callback`) — Line 1510, Complexity: 26
- **_infer_source_label**(`source_type`) — Line 1903, Complexity: 1
- **_normalize_citation**(`text`) — Line 1912, Complexity: 1
- **_fuzzy_lookup**(`citation_text, citation_lookup, _norm_index`) — Line 1921, Complexity: 17
- **_build_source_url**(`case_id, ik_doc_id, url`) — Line 1979, Complexity: 5
- **format_footnotes_node**(`state`) — Line 1991, Complexity: 40
- **verify_citations_v2_node**(`state, db, graph_store, ik_client`) — Line 2221, Complexity: 22
- **_deterministic_verify**(`memo, footnotes, extracted_passages, db, graph_store`) — Line 2370, Complexity: 24
- **_verify_citations_against_sources**(`footnotes, db, ik_client, graph_store`) — Line 2476, Complexity: 22
- **_matches_indian_citation_pattern**(`citation`) — Line 2573, Complexity: 1
- **_fuzzy_match**(`quote, passage, threshold`) — Line 2588, Complexity: 7
- **legal_quality_check_node**(`state, llm`) — Line 2629, Complexity: 10
- **_build_source_attribution**(`all_results`) — Line 2731, Complexity: 7
- **_build_research_audit**(`state, all_results`) — Line 2756, Complexity: 2
- **_run_adversarial_search**(`counter_args, llm, embedder, vector_store, reranker`) — Line 2790, Complexity: 3
- **adversarial_search_node**(`state, llm, embedder, vector_store, reranker`) — Line 2839, Complexity: 15
- **_text_similarity**(`a, b`) — Line 2936, Complexity: 3
- **temporal_validation_node**(`state`) — Line 2945, Complexity: 7
- **deep_read_sections**(`case_id`) — Line 993, Complexity: 6
- **process_batch**(`batch`) — Line 1027, Complexity: 1
- **generate_draft**(`strategy_name, evidence_subset`) — Line 1608, Complexity: 4
- **_verify_one**(`fn`) — Line 2508, Complexity: 17
- **_trigrams**(`s`) — Line 2614, Complexity: 1
- **_search_one**(`ca`) — Line 2804, Complexity: 3

### `backend\app\core\agents\nodes\strategy_nodes.py`
- **analyze_facts_node**(`state, llm`) — Line 63, Complexity: 3
- **fetch_judge_profile_node**(`state, db`) — Line 95, Complexity: 4
- **search_precedents_node**(`state, llm, embedder, vector_store, reranker, graph_store, db`) — Line 183, Complexity: 11
- **assess_strength_node**(`state, llm`) — Line 297, Complexity: 3
- **generate_arguments_node**(`state, llm`) — Line 333, Complexity: 4
- **counter_arguments_node**(`state, llm`) — Line 376, Complexity: 3
- **judge_considerations_node**(`state, llm`) — Line 415, Complexity: 7
- **synthesize_strategy_node**(`state, llm`) — Line 489, Complexity: 4
- **verify_citations_node**(`state, db`) — Line 575, Complexity: 2

### `backend\app\core\agents\nodes\worker_nodes.py`
- **case_law_worker**(`state, llm, embedder, vector_store, reranker`) — Line 55, Complexity: 23
- **named_case_worker**(`state, llm, embedder, vector_store, reranker, ik_client`) — Line 197, Complexity: 25
- **statute_worker**(`state, embedder, vector_store`) — Line 323, Complexity: 9
- **func_websearch_to_tsquery**(`query`) — Line 425, Complexity: 1
- **_strip_html_tags**(`text`) — Line 442, Complexity: 2
- **ik_search_worker**(`state, ik_client`) — Line 450, Complexity: 27
- **web_search_worker**(`state, web_search`) — Line 680, Complexity: 4
- **graph_worker**(`state, graph_store`) — Line 746, Complexity: 15
- **_detect_communities**(`G, resolution`) — Line 901, Complexity: 7
- **graph_community_worker**(`state, embedder, vector_store, graph_store`) — Line 929, Complexity: 19

### `backend\app\core\agents\research.py`
- **build_research_graph**(`0 args`) — Line 105, Complexity: 46
- **_progress_event**(`stage, progress, detail`) — Line 146, Complexity: 1
- **rewrite**(`state`) — Line 150, Complexity: 1
- **classify**(`state`) — Line 157, Complexity: 4
- **plan**(`state`) — Line 170, Complexity: 2
- **fast_path_search**(`state`) — Line 182, Complexity: 1
- **fast_path_synthesis**(`state`) — Line 188, Complexity: 1
- **statute_lookup**(`state`) — Line 192, Complexity: 1
- **element_decomposition**(`state`) — Line 197, Complexity: 1
- **adversarial_search**(`state`) — Line 206, Complexity: 1
- **temporal_validation**(`state`) — Line 216, Complexity: 1
- **pre_warm**(`state`) — Line 220, Complexity: 1
- **dispatch_workers**(`state`) — Line 238, Complexity: 12
- **gather**(`state`) — Line 307, Complexity: 1
- **batch_cot**(`state`) — Line 314, Complexity: 1
- **evaluate_extract**(`state`) — Line 317, Complexity: 1
- **gap_analysis**(`state`) — Line 323, Complexity: 1
- **speculative_synthesis**(`state`) — Line 327, Complexity: 1
- **moderate_synthesis**(`state`) — Line 334, Complexity: 1
- **format_footnotes**(`state`) — Line 340, Complexity: 1
- **verify_v2**(`state`) — Line 343, Complexity: 1
- **quality_check**(`state`) — Line 351, Complexity: 1
- **_timed_worker**(`name, coro, state`) — Line 361, Complexity: 3
- **_case_law_worker**(`state`) — Line 392, Complexity: 1
- **_named_case_worker**(`state`) — Line 399, Complexity: 1
- **_statute_worker**(`state`) — Line 406, Complexity: 1
- **_ik_search_worker**(`state`) — Line 413, Complexity: 1
- **_web_search_worker**(`state`) — Line 420, Complexity: 1
- **_graph_worker**(`state`) — Line 427, Complexity: 1
- **_graph_community_worker**(`state`) — Line 434, Complexity: 1
- **checkpoint_plan**(`state`) — Line 443, Complexity: 7
- **checkpoint_findings**(`state`) — Line 529, Complexity: 10
- **checkpoint_memo**(`state`) — Line 610, Complexity: 5
- **route_by_complexity**(`state`) — Line 649, Complexity: 2
- **route_after_evaluate**(`state`) — Line 658, Complexity: 2
- **should_refine**(`state`) — Line 665, Complexity: 3
- **route_after_fast_path**(`state`) — Line 674, Complexity: 2
- **route_after_temporal**(`state`) — Line 680, Complexity: 2
- **route_after_quality**(`state`) — Line 687, Complexity: 4

### `backend\app\core\agents\research_cache.py`
- **normalize_cache_key**(`query`) — Line 38, Complexity: 1
- **get_cached_memo**(`redis, query`) — Line 51, Complexity: 4
- **set_cached_memo**(`redis, query, memo`) — Line 68, Complexity: 3
- **get_memo_cache_hash**(`query`) — Line 81, Complexity: 1
- **get_cached_search**(`redis, query`) — Line 90, Complexity: 4
- **set_cached_search**(`redis, query, results`) — Line 107, Complexity: 3
- **get_cached_ik_search**(`redis, query`) — Line 124, Complexity: 4
- **set_cached_ik_search**(`redis, query, results`) — Line 145, Complexity: 4
- **get_cached_ik_fragment**(`redis, doc_id, query`) — Line 160, Complexity: 4
- **set_cached_ik_fragment**(`redis, doc_id, query, fragment`) — Line 177, Complexity: 3
- **get_cached_embedding**(`redis, text`) — Line 194, Complexity: 4
- **set_cached_embedding**(`redis, text, vector`) — Line 211, Complexity: 3
- **get_cached_community**(`redis, community_id`) — Line 228, Complexity: 4
- **set_cached_community**(`redis, community_id, summary`) — Line 245, Complexity: 3

### `backend\app\core\agents\routing_utils.py`
- **is_proceed**(`content`) — Line 25, Complexity: 9
- **make_feedback_router**(`step, loop_back, proceed, max_iterations, check_error`) — Line 58, Complexity: 9
- **make_checkpoint_node**(`step, question, state_fields, extra_return`) — Line 112, Complexity: 6
- **compile_graph**(`graph, checkpointer`) — Line 159, Complexity: 2
- **route**(`state`) — Line 80, Complexity: 9
- **checkpoint**(`state`) — Line 133, Complexity: 6

### `backend\app\core\agents\strategy.py`
- **build_strategy_graph**(`0 args`) — Line 63, Complexity: 4
- **analyze_facts**(`state`) — Line 104, Complexity: 2
- **fetch_judge**(`state`) — Line 114, Complexity: 1
- **search_precedents**(`state`) — Line 118, Complexity: 1
- **assess_strength**(`state`) — Line 124, Complexity: 1
- **generate_arguments**(`state`) — Line 127, Complexity: 2
- **counter_and_judge**(`state`) — Line 137, Complexity: 1
- **synthesize_strategy**(`state`) — Line 144, Complexity: 2
- **verify**(`state`) — Line 154, Complexity: 1

### `backend\app\core\analysis\document_analyzer.py`
- **__init__**(`self, llm`) — Line 56, Complexity: 1
- **extract_issues**(`self, document_text`) — Line 59, Complexity: 1
- **generate_counter_arguments**(`self, document_type, issues_with_precedents`) — Line 88, Complexity: 1
- **generate_research_memo**(`self, document_type, parties, relief_sought, key_facts, issues_analysis, counter_arguments`) — Line 107, Complexity: 2
- **_parse_counter_arguments**(`response`) — Line 134, Complexity: 10

### `backend\app\core\analysis\precedent_mapper.py`
- **__init__**(`self, llm, embedder, vector_store, reranker, db`) — Line 30, Complexity: 1
- **map_precedents**(`self, issues, acts_referenced, max_per_issue`) — Line 44, Complexity: 1
- **_search_for_issue**(`self, issue, acts_referenced, max_per_issue`) — Line 57, Complexity: 3

### `backend\app\core\analytics\judge_analytics.py`
- **calculate_disposal_rates**(`judge_name, db`) — Line 645, Complexity: 1
- **calculate_temporal_trends**(`judge_name, db`) — Line 656, Complexity: 1
- **calculate_sentencing_stats**(`judge_name, db`) — Line 667, Complexity: 1
- **__init__**(`self, session`) — Line 81, Complexity: 1
- **list_judges**(`self, search, page, page_size`) — Line 84, Complexity: 3
- **get_judge_profile**(`self, judge_name`) — Line 157, Complexity: 5
- **_get_bench_combinations_fallback**(`self, judge_name`) — Line 274, Complexity: 5
- **get_judge_cases**(`self, judge_name, page, page_size, year, case_type`) — Line 302, Complexity: 4
- **compare_judges**(`self, judge_names`) — Line 371, Complexity: 4
- **calculate_disposal_rates**(`self, judge_name`) — Line 394, Complexity: 4
- **calculate_temporal_trends**(`self, judge_name`) — Line 444, Complexity: 3
- **calculate_sentencing_stats**(`self, judge_name`) — Line 517, Complexity: 4
- **get_court_stats**(`self, court`) — Line 564, Complexity: 3

### `backend\app\core\chat\rag.py`
- **check_treatment_from_graph**(`case_ids, graph_store`) — Line 82, Complexity: 3
- **rag_respond**(`question`) — Line 107, Complexity: 20
- **_reformulate_query**(`question, chat_history, llm`) — Line 330, Complexity: 3
- **_generate_title**(`question`) — Line 370, Complexity: 2
- **_create_session**(`db, session_id, user_id, title`) — Line 378, Complexity: 1
- **_verify_session_ownership**(`db, session_id, user_id`) — Line 392, Complexity: 3
- **_load_chat_history**(`db, session_id`) — Line 409, Complexity: 1
- **_build_sources**(`search_results, db`) — Line 426, Complexity: 12
- **_format_context**(`sources`) — Line 490, Complexity: 17
- **_format_history**(`messages`) — Line 543, Complexity: 4
- **_save_user_message**(`db, session_id, content`) — Line 560, Complexity: 1
- **_save_assistant_message**(`db, session_id, content, sources`) — Line 574, Complexity: 1

### `backend\app\core\config.py`
- **validate_critical_settings**(`self`) — Line 148, Complexity: 20
- **cors_origin_list**(`self`) — Line 234, Complexity: 1

### `backend\app\core\dependencies.py`
- **get_llm**(`0 args`) — Line 32, Complexity: 2
- **get_flash_llm**(`0 args`) — Line 42, Complexity: 2
- **get_embedder**(`0 args`) — Line 52, Complexity: 2
- **get_vector_store**(`0 args`) — Line 62, Complexity: 3
- **get_graph_store**(`0 args`) — Line 76, Complexity: 3
- **get_reranker**(`0 args`) — Line 90, Complexity: 2
- **get_translator**(`0 args`) — Line 100, Complexity: 2
- **get_storage**(`0 args`) — Line 110, Complexity: 3
- **get_tts**(`0 args`) — Line 124, Complexity: 3
- **get_checkpointer**(`0 args`) — Line 136, Complexity: 2
- **get_web_search**(`0 args`) — Line 154, Complexity: 1
- **get_ik_client**(`0 args`) — Line 162, Complexity: 1
- **cleanup_providers**(`0 args`) — Line 169, Complexity: 13

### `backend\app\core\drafting\export.py`
- **_is_heading**(`line`) — Line 27, Complexity: 4
- **_clean_heading**(`line`) — Line 38, Complexity: 1
- **_parse_sections**(`content`) — Line 43, Complexity: 3
- **export_to_docx**(`content, template`) — Line 71, Complexity: 11
- **export_to_pdf**(`content, template`) — Line 167, Complexity: 8
- **export_research_memo_docx**(`content`) — Line 276, Complexity: 13
- **export_research_memo_pdf**(`content`) — Line 352, Complexity: 10

### `backend\app\core\drafting\templates.py`
- **get_template**(`doc_type`) — Line 192, Complexity: 2

### `backend\app\core\graph\traversal.py`
- **get_neighborhood**(`case_id`) — Line 18, Complexity: 9
- **get_citation_chain**(`case_id`) — Line 104, Complexity: 7
- **get_authorities**(`case_id`) — Line 169, Complexity: 2
- **get_graph_stats**(`0 args`) — Line 221, Complexity: 7

### `backend\app\core\ingestion\anonymizer.py`
- **anonymize_text**(`full_text`) — Line 65, Complexity: 1
- **detect_sensitive_case**(`full_text, metadata`) — Line 86, Complexity: 14

### `backend\app\core\ingestion\chunker.py`
- **_compute_legal_signal**(`text`) — Line 56, Complexity: 2
- **_detect_opinion_authors**(`text`) — Line 82, Complexity: 4
- **_detect_paragraph_range**(`text`) — Line 107, Complexity: 3
- **_is_heading_position**(`text, match_start`) — Line 294, Complexity: 5
- **_is_abbreviation**(`text, period_pos`) — Line 332, Complexity: 1
- **_find_break_point**(`text, start, end, min_chunk`) — Line 339, Complexity: 9
- **detect_judgment_sections**(`text`) — Line 372, Complexity: 15
- **chunk_judgment**(`text, sections, case_id`) — Line 440, Complexity: 16

### `backend\app\core\ingestion\contextual_embeddings.py`
- **generate_contextual_prefix**(`chunk_text, document_metadata, flash_llm, document_type`) — Line 48, Complexity: 3
- **batch_contextualize_chunks**(`chunks, document_metadata, flash_llm, document_type, batch_size, rate_limiter`) — Line 89, Complexity: 5
- **_build_case_law_prompt**(`chunk_text, meta`) — Line 149, Complexity: 6
- **_build_statute_prompt**(`chunk_text, meta`) — Line 167, Complexity: 5
- **_contextualize_one**(`chunk_text`) — Line 118, Complexity: 2

### `backend\app\core\ingestion\graph_retry.py`
- **record_graph_failure**(`db, case_id, error`) — Line 12, Complexity: 1
- **get_pending_retries**(`db, max_retries`) — Line 28, Complexity: 1
- **mark_retry_success**(`db, case_id`) — Line 43, Complexity: 1
- **increment_retry_count**(`db, case_id`) — Line 52, Complexity: 1

### `backend\app\core\ingestion\metadata.py`
- **_truncate_for_llm**(`text`) — Line 18, Complexity: 2
- **_parse_judge_names**(`raw`) — Line 29, Complexity: 19
- **extract_metadata_llm**(`text, llm`) — Line 167, Complexity: 9
- **compute_extraction_confidence**(`metadata`) — Line 246, Complexity: 7
- **validate_with_regex**(`metadata`) — Line 286, Complexity: 63
- **cross_validate_propositions**(`metadata`) — Line 511, Complexity: 7
- **validate_cross_fields**(`metadata`) — Line 538, Complexity: 15
- **normalize_case_type**(`raw`) — Line 637, Complexity: 2
- **validate_parquet_data**(`parquet_meta`) — Line 649, Complexity: 18
- **merge_metadata**(`parquet_meta, llm_meta`) — Line 709, Complexity: 21

### `backend\app\core\ingestion\pdf.py`
- **clean_extracted_text**(`text`) — Line 130, Complexity: 2
- **reattach_footnotes**(`text`) — Line 176, Complexity: 8
- **_remove_repeated_headers_footers**(`text`) — Line 213, Complexity: 14
- **_remove_repeated_headers_footers_pages**(`pages`) — Line 267, Complexity: 15
- **_smart_page_join**(`pages`) — Line 320, Complexity: 10
- **_ocr_single_page**(`file_path, page_num`) — Line 366, Complexity: 4
- **_build_page_map**(`page_texts, joined_text`) — Line 411, Complexity: 5
- **_extract_pdf_text_sync**(`file_path`) — Line 452, Complexity: 17
- **extract_pdf_text**(`file_path`) — Line 533, Complexity: 1
- **extract_with_ocr**(`file_path`) — Line 552, Complexity: 8
- **score_text_quality**(`text, ocr_used, page_count`) — Line 625, Complexity: 10
- **assess_extraction_quality**(`text`) — Line 670, Complexity: 2
- **extract_and_score**(`file_path`) — Line 699, Complexity: 5
- **extract_tables**(`file_path`) — Line 733, Complexity: 10
- **_ocr_sync**(`0 args`) — Line 579, Complexity: 7

### `backend\app\core\ingestion\pipeline.py`
- **get_cited_by_count**(`case_id, graph_store`) — Line 67, Complexity: 2
- **ingest_judgment**(`pdf_path, parquet_metadata`) — Line 81, Complexity: 66
- **_compute_text_hash**(`text`) — Line 588, Complexity: 1
- **_parse_date_str**(`val`) — Line 594, Complexity: 5
- **_safe_filename**(`parquet_meta`) — Line 611, Complexity: 2
- **_insert_case**(`db, case_id, metadata, full_text, storage_path, parquet_meta`) — Line 619, Complexity: 15
- **_record_ingestion_failure**(`case_id, pdf_path, error_message`) — Line 914, Complexity: 2
- **_embed_chunks**(`chunks, embedder, max_retries`) — Line 939, Complexity: 6
- **_upsert_vectors**(`case_id, chunks, embeddings, metadata, vector_store`) — Line 973, Complexity: 25
- **_upsert_proposition_vectors**(`case_id, metadata, embedder, vector_store`) — Line 1056, Complexity: 29
- **_persist_statute_interpretations**(`case_id, metadata, db`) — Line 1179, Complexity: 6
- **_build_citation_graph**(`case_id, metadata, full_text, graph_store`) — Line 1218, Complexity: 31
- **_link_citation_equivalents**(`case_id, primary_citation, equivalents, graph_store`) — Line 1369, Complexity: 5
- **_extract_citation_equivalents**(`full_text, case_id`) — Line 1406, Complexity: 3
- **_persist_sections**(`case_id, sections, db`) — Line 1428, Complexity: 2
- **_persist_citation_equivalents**(`equivalents, db`) — Line 1456, Complexity: 2
- **bulk_upsert_cases**(`cases_data, db`) — Line 1502, Complexity: 5
- **bulk_insert_sections**(`sections_data, db`) — Line 1747, Complexity: 5
- **bulk_insert_citations**(`citations_data, db`) — Line 1789, Complexity: 5
- **ingest_batch**(`judgments, db`) — Line 1831, Complexity: 16
- **_llm_extract_with_retry**(`0 args`) — Line 191, Complexity: 2
- **_store_pdf**(`0 args`) — Line 202, Complexity: 2
- **_upsert_with_retry**(`0 args`) — Line 391, Complexity: 1
- **_cleanup_stale_vectors**(`0 args`) — Line 423, Complexity: 2

### `backend\app\core\ingestion\rate_limiter.py`
- **__init__**(`self, max_per_minute`) — Line 44, Complexity: 2
- **max_per_minute**(`self`) — Line 53, Complexity: 1
- **acquire**(`self`) — Line 56, Complexity: 5
- **release**(`self`) — Line 85, Complexity: 1
- **__aenter__**(`self`) — Line 88, Complexity: 1
- **__aexit__**(`self, exc_type, exc, tb`) — Line 92, Complexity: 1
- **__init__**(`self, rpm_per_key`) — Line 108, Complexity: 2
- **get**(`self, key`) — Line 114, Complexity: 2
- **rpm_per_key**(`self`) — Line 126, Complexity: 1

### `backend\app\core\ingestion\section_summarizer.py`
- **generate_section_summaries**(`case_id, sections, flash_llm`) — Line 34, Complexity: 4
- **build_pinecone_summary_vectors**(`case_id, summaries, embeddings, base_metadata`) — Line 91, Complexity: 3

### `backend\app\core\interfaces\document_parser.py`
- **extract_text**(`self, file_path`) — Line 12, Complexity: 1
- **extract_text_with_ocr**(`self, file_path`) — Line 14, Complexity: 1

### `backend\app\core\interfaces\embedder.py`
- **embed_text**(`self, text`) — Line 12, Complexity: 1
- **embed_batch**(`self, texts`) — Line 14, Complexity: 1
- **dimension**(`self`) — Line 17, Complexity: 1

### `backend\app\core\interfaces\external_doc.py`
- **search**(`self, query`) — Line 12, Complexity: 1
- **get_document**(`self, doc_id`) — Line 30, Complexity: 1
- **get_fragment**(`self, doc_id, query`) — Line 32, Complexity: 1
- **get_metadata**(`self, doc_id`) — Line 34, Complexity: 1
- **get_court_copy**(`self, doc_id`) — Line 36, Complexity: 1

### `backend\app\core\interfaces\graph_store.py`
- **create_node**(`self, label, properties`) — Line 12, Complexity: 1
- **get_node**(`self, node_id`) — Line 16, Complexity: 1
- **query**(`self, cypher`) — Line 18, Complexity: 1
- **get_neighbors**(`self, node_id`) — Line 25, Complexity: 1
- **ensure_constraints**(`self`) — Line 34, Complexity: 1
- **batch_create_nodes**(`self, nodes`) — Line 36, Complexity: 1
- **batch_create_citation_edges**(`self, edges`) — Line 43, Complexity: 1
- **delete_node**(`self, node_id`) — Line 50, Complexity: 1

### `backend\app\core\interfaces\llm.py`
- **generate**(`self, prompt`) — Line 13, Complexity: 1
- **generate_structured**(`self, prompt`) — Line 22, Complexity: 1
- **generate_structured_from_pdf**(`self, pdf_path`) — Line 31, Complexity: 1
- **stream**(`self, prompt`) — Line 41, Complexity: 1

### `backend\app\core\interfaces\reranker.py`
- **rerank**(`self, query, documents`) — Line 22, Complexity: 1

### `backend\app\core\interfaces\storage.py`
- **store**(`self, file_path, destination`) — Line 13, Complexity: 1
- **retrieve**(`self, storage_path`) — Line 17, Complexity: 1
- **retrieve_chunked**(`self, storage_path, chunk_size`) — Line 19, Complexity: 1
- **delete**(`self, storage_path`) — Line 25, Complexity: 1
- **exists**(`self, storage_path`) — Line 27, Complexity: 1

### `backend\app\core\interfaces\translator.py`
- **translate**(`self, text`) — Line 11, Complexity: 1
- **detect_language**(`self, text`) — Line 30, Complexity: 1

### `backend\app\core\interfaces\tts.py`
- **synthesize**(`self, text`) — Line 12, Complexity: 1
- **get_supported_languages**(`self`) — Line 16, Complexity: 1

### `backend\app\core\interfaces\vector_store.py`
- **upsert**(`self, vectors`) — Line 22, Complexity: 1
- **search**(`self, query_vector`) — Line 26, Complexity: 1
- **delete_by_metadata**(`self, filter`) — Line 35, Complexity: 1

### `backend\app\core\interfaces\web_search.py`
- **search**(`self, query`) — Line 12, Complexity: 1

### `backend\app\core\legal\amendment_service.py`
- **seed_amendment_maps**(`db`) — Line 37, Complexity: 4
- **_load_all**(`db`) — Line 72, Complexity: 2
- **get_amendment_maps**(`db, redis`) — Line 99, Complexity: 6
- **build_lookup**(`entries`) — Line 123, Complexity: 2
- **get_amendment_lookups**(`db, redis`) — Line 141, Complexity: 1
- **build_lookup_from_constants**(`0 args`) — Line 157, Complexity: 3

### `backend\app\core\legal\courts.py`
- **normalize_court_name**(`name`) — Line 254, Complexity: 13
- **get_court_level**(`court`) — Line 308, Complexity: 8

### `backend\app\core\legal\extractor.py`
- **get_act_display_name**(`short_code`) — Line 420, Complexity: 3
- **get_acts_cited_display**(`short_codes`) — Line 442, Complexity: 1
- **normalize_act_name**(`raw`) — Line 453, Complexity: 4
- **_is_valid_act_citation**(`name`) — Line 532, Complexity: 11
- **normalize_acts_cited_list**(`raw_acts`) — Line 564, Complexity: 15
- **_parse_section_list**(`section_str`) — Line 740, Complexity: 7
- **extract_citations**(`text`) — Line 771, Complexity: 31
- **extract_acts_cited**(`text`) — Line 1084, Complexity: 16
- **normalize_citation**(`citation`) — Line 1241, Complexity: 1
- **_add**(`citation, match`) — Line 788, Complexity: 3
- **_add**(`ref`) — Line 1102, Complexity: 2

### `backend\app\core\legal\precedent_strength.py`
- **_bench_rank**(`bench, coram_size`) — Line 39, Complexity: 7
- **classify_precedent_strength**(`source_court, source_bench, target_court, target_bench, overruled, source_coram_size, target_coram_size`) — Line 68, Complexity: 19
- **recency_weight**(`year`) — Line 151, Complexity: 2
- **compute_effective_strength**(`base_strength, overruled, treatment_confidence, year, is_reportable`) — Line 170, Complexity: 3

### `backend\app\core\legal\statute_enrichment.py`
- **enrich_statute_cross_references**(`acts_cited`) — Line 27, Complexity: 4

### `backend\app\core\legal\treatment.py`
- **detect_treatment_in_text**(`text`) — Line 82, Complexity: 7
- **has_overruling_language**(`text`) — Line 136, Complexity: 1
- **classify_treatment_llm**(`text_context, llm`) — Line 160, Complexity: 3

### `backend\app\core\logging_config.py`
- **_redact**(`text`) — Line 38, Complexity: 1
- **configure_logging**(`0 args`) — Line 75, Complexity: 3
- **format**(`self, record`) — Line 46, Complexity: 4
- **__init__**(`self`) — Line 68, Complexity: 1
- **format**(`self, record`) — Line 71, Complexity: 1

### `backend\app\core\middleware.py`
- **filter**(`self, record`) — Line 25, Complexity: 1
- **dispatch**(`self, request, call_next`) — Line 37, Complexity: 1

### `backend\app\core\providers\circuit_breaker.py`
- **__init__**(`self, cooldown_remaining`) — Line 27, Complexity: 1
- **__init__**(`self, threshold, cooldown`) — Line 69, Complexity: 1
- **is_tripped**(`self`) — Line 87, Complexity: 1
- **failure_count**(`self`) — Line 91, Complexity: 1
- **check**(`self`) — Line 94, Complexity: 4
- **record_success**(`self`) — Line 111, Complexity: 2
- **record_failure**(`self`) — Line 118, Complexity: 3
- **__init__**(`self, threshold, cooldown`) — Line 151, Complexity: 1
- **check**(`self`) — Line 157, Complexity: 3
- **record_success**(`self`) — Line 167, Complexity: 1
- **record_failure**(`self`) — Line 171, Complexity: 2
- **is_open**(`self`) — Line 184, Complexity: 2
- **failure_count**(`self`) — Line 192, Complexity: 1

### `backend\app\core\providers\document_parsers\pdf_parser.py`
- **extract_text**(`self, file_path`) — Line 23, Complexity: 2
- **extract_text_with_ocr**(`self, file_path`) — Line 40, Complexity: 1

### `backend\app\core\providers\embeddings\gemini.py`
- **__init__**(`self`) — Line 60, Complexity: 4
- **dimension**(`self`) — Line 72, Complexity: 1
- **embed_text**(`self, text`) — Line 76, Complexity: 1
- **embed_batch**(`self, texts`) — Line 91, Complexity: 1

### `backend\app\core\providers\external\indiankanoon.py`
- **__init__**(`self, token`) — Line 118, Complexity: 4
- **_check_circuit_breaker**(`self`) — Line 135, Complexity: 3
- **_rate_limited_post**(`self, url, data`) — Line 146, Complexity: 4
- **search**(`self, query`) — Line 177, Complexity: 11
- **get_document**(`self, doc_id`) — Line 248, Complexity: 1
- **get_fragment**(`self, doc_id, query`) — Line 254, Complexity: 1
- **get_metadata**(`self, doc_id`) — Line 260, Complexity: 1
- **get_court_copy**(`self, doc_id`) — Line 266, Complexity: 1
- **close**(`self`) — Line 275, Complexity: 1

### `backend\app\core\providers\graph\neo4j_store.py`
- **_validate_label**(`label`) — Line 46, Complexity: 2
- **_validate_relationship**(`rel_type`) — Line 52, Complexity: 2
- **__init__**(`self`) — Line 65, Complexity: 6
- **create_node**(`self, label, properties`) — Line 91, Complexity: 4
- **_create_node_inner**(`self, label, properties`) — Line 106, Complexity: 3
- **get_node**(`self, node_id`) — Line 125, Complexity: 4
- **_get_node_inner**(`self, node_id`) — Line 139, Complexity: 3
- **query**(`self, cypher`) — Line 155, Complexity: 4
- **_query_inner**(`self, cypher`) — Line 174, Complexity: 5
- **get_neighbors**(`self, node_id`) — Line 198, Complexity: 4
- **_get_neighbors_inner**(`self, node_id`) — Line 221, Complexity: 7
- **ensure_constraints**(`self`) — Line 272, Complexity: 5
- **_seed_doctrines**(`self, session`) — Line 348, Complexity: 3
- **batch_create_nodes**(`self, nodes`) — Line 412, Complexity: 5
- **batch_create_citation_edges**(`self, edges`) — Line 462, Complexity: 5
- **delete_node**(`self, node_id`) — Line 517, Complexity: 4
- **close**(`self`) — Line 532, Complexity: 1
- **_run**(`0 args`) — Line 182, Complexity: 2
- **_run**(`0 args`) — Line 249, Complexity: 1

### `backend\app\core\providers\graph\pg_graph_store.py`
- **_validate_label**(`label`) — Line 32, Complexity: 2
- **_validate_relationship**(`rel_type`) — Line 38, Complexity: 2
- **create_node**(`self, label, properties`) — Line 51, Complexity: 5
- **get_node**(`self, node_id`) — Line 97, Complexity: 3
- **query**(`self, cypher`) — Line 116, Complexity: 3
- **get_neighbors**(`self, node_id`) — Line 136, Complexity: 7
- **ensure_constraints**(`self`) — Line 221, Complexity: 1
- **batch_create_nodes**(`self, nodes`) — Line 226, Complexity: 6
- **batch_create_citation_edges**(`self, edges`) — Line 264, Complexity: 5
- **delete_node**(`self, node_id`) — Line 322, Complexity: 2

### `backend\app\core\providers\llm\gemini.py`
- **_normalize_schema**(`schema`) — Line 62, Complexity: 11
- **__init__**(`self`) — Line 94, Complexity: 5
- **_get_or_create_synthesis_cache**(`self, system_prompt`) — Line 104, Complexity: 4
- **generate**(`self, prompt`) — Line 132, Complexity: 5
- **generate_structured**(`self, prompt`) — Line 167, Complexity: 3
- **generate_structured_from_pdf**(`self, pdf_path`) — Line 207, Complexity: 3
- **_start_stream**(`self, prompt, config`) — Line 252, Complexity: 1
- **stream**(`self, prompt`) — Line 265, Complexity: 5

### `backend\app\core\providers\rerankers\cohere_reranker.py`
- **__init__**(`self`) — Line 41, Complexity: 3
- **rerank**(`self, query, documents`) — Line 54, Complexity: 4
- **_rerank_inner**(`self, query, documents`) — Line 83, Complexity: 2
- **close**(`self`) — Line 116, Complexity: 3

### `backend\app\core\providers\storage\gcs_storage.py`
- **__init__**(`self`) — Line 33, Complexity: 1
- **_parse_gs_path**(`self, storage_path`) — Line 37, Complexity: 3
- **store**(`self, file_path, destination`) — Line 53, Complexity: 2
- **retrieve**(`self, storage_path`) — Line 70, Complexity: 1
- **retrieve_chunked**(`self, storage_path, chunk_size`) — Line 76, Complexity: 3
- **delete**(`self, storage_path`) — Line 90, Complexity: 2
- **exists**(`self, storage_path`) — Line 101, Complexity: 1

### `backend\app\core\providers\storage\local_storage.py`
- **__init__**(`self`) — Line 16, Complexity: 1
- **_safe_path**(`self, destination`) — Line 20, Complexity: 3
- **store**(`self, file_path, destination`) — Line 41, Complexity: 1
- **retrieve**(`self, storage_path`) — Line 47, Complexity: 1
- **retrieve_chunked**(`self, storage_path, chunk_size`) — Line 51, Complexity: 4
- **delete**(`self, storage_path`) — Line 65, Complexity: 2
- **exists**(`self, storage_path`) — Line 70, Complexity: 1

### `backend\app\core\providers\translation\gemini_translator.py`
- **__init__**(`self, model`) — Line 18, Complexity: 4
- **translate**(`self, text`) — Line 28, Complexity: 4
- **detect_language**(`self, text`) — Line 72, Complexity: 7

### `backend\app\core\providers\tts\mock_tts.py`
- **synthesize**(`self, text`) — Line 14, Complexity: 2
- **get_supported_languages**(`self`) — Line 22, Complexity: 1

### `backend\app\core\providers\tts\sarvam.py`
- **_wait_for_rate_limit**(`retry_state`) — Line 30, Complexity: 3
- **__init__**(`self, retry_after`) — Line 25, Complexity: 1
- **__init__**(`self`) — Line 61, Complexity: 2
- **synthesize**(`self, text`) — Line 68, Complexity: 13
- **get_supported_languages**(`self`) — Line 145, Complexity: 1

### `backend\app\core\providers\vector\pgvector_store.py`
- **_build_filter_clause**(`filters, params`) — Line 33, Complexity: 13
- **__init__**(`self`) — Line 96, Complexity: 1
- **upsert**(`self, vectors`) — Line 99, Complexity: 5
- **search**(`self, query_vector`) — Line 143, Complexity: 4
- **delete**(`self, ids`) — Line 186, Complexity: 4
- **delete_by_metadata**(`self, filter`) — Line 207, Complexity: 4

### `backend\app\core\providers\vector\pinecone_store.py`
- **__init__**(`self`) — Line 40, Complexity: 4
- **upsert**(`self, vectors`) — Line 57, Complexity: 4
- **_upsert_inner**(`self, vectors`) — Line 74, Complexity: 4
- **search**(`self, query_vector`) — Line 92, Complexity: 4
- **_search_inner**(`self, query_vector`) — Line 121, Complexity: 6
- **delete**(`self, ids`) — Line 157, Complexity: 4
- **_delete_inner**(`self, ids`) — Line 171, Complexity: 3
- **delete_by_metadata**(`self, filter`) — Line 181, Complexity: 4
- **_delete_by_metadata_inner**(`self, filter`) — Line 205, Complexity: 6

### `backend\app\core\providers\web_search\tavily.py`
- **__init__**(`self, api_key`) — Line 67, Complexity: 4
- **search**(`self, query`) — Line 78, Complexity: 6
- **close**(`self`) — Line 143, Complexity: 1

### `backend\app\core\search\fulltext.py`
- **search_fulltext**(`query`) — Line 39, Complexity: 5
- **_build_tsquery_expr**(`query, params`) — Line 115, Complexity: 6
- **_search_sections**(`query`) — Line 159, Complexity: 2
- **_escape_ilike**(`value`) — Line 215, Complexity: 1
- **_build_filter_clauses**(`filters, table_alias`) — Line 220, Complexity: 12

### `backend\app\core\search\hybrid.py`
- **rrf_merge**(`ranked_lists`) — Line 79, Complexity: 5
- **hybrid_search**(`query`) — Line 126, Complexity: 19
- **_exact_citation_search**(`query, db`) — Line 373, Complexity: 3
- **_vector_search**(`query`) — Line 432, Complexity: 17
- **_build_snippets_map**(`fts_results, vector_results`) — Line 494, Complexity: 7
- **_merge_filters**(`explicit, llm_extracted`) — Line 516, Complexity: 9
- **_enrich_results**(`case_ids, scores, snippets_map, db, vector_chunk_map`) — Line 541, Complexity: 17
- **_build_facets**(`case_ids, db`) — Line 646, Complexity: 8
- **_check_outcome_bias**(`query, case_ids, db`) — Line 700, Complexity: 6
- **invalidate_search_cache**(`redis_client`) — Line 755, Complexity: 8
- **_make_cache_key**(`query, filters, page, page_size, language`) — Line 789, Complexity: 1
- **_get_cached**(`redis_client, key`) — Line 810, Complexity: 3
- **_set_cached**(`redis_client, key, response`) — Line 823, Complexity: 2
- **_serialize_response**(`response`) — Line 836, Complexity: 1
- **_deserialize_response**(`data`) — Line 849, Complexity: 1

### `backend\app\core\search\query.py`
- **expand_statute_references**(`query`) — Line 175, Complexity: 9
- **understand_query**(`raw_query, llm`) — Line 226, Complexity: 2
- **_parse_llm_result**(`raw_query, data`) — Line 252, Complexity: 1
- **_passthrough**(`raw_query`) — Line 285, Complexity: 1

### `backend\app\core\search\semantic_cache.py`
- **_float_list_to_bytes**(`vec`) — Line 33, Complexity: 1
- **_bytes_to_float_list**(`raw`) — Line 38, Complexity: 1
- **__init__**(`self, redis, embedder`) — Line 47, Complexity: 1
- **_ensure_index**(`self`) — Line 52, Complexity: 4
- **get**(`self, query`) — Line 86, Complexity: 8
- **put**(`self, query, memo_hash`) — Line 150, Complexity: 3

### `backend\app\db\postgres.py`
- **get_db**(`0 args`) — Line 65, Complexity: 1
- **get_async_session**(`0 args`) — Line 71, Complexity: 1

### `backend\app\db\redis_client.py`
- **get_redis**(`0 args`) — Line 17, Complexity: 4
- **close_redis**(`0 args`) — Line 35, Complexity: 2

### `backend\app\main.py`
- **_run_migrations**(`0 args`) — Line 24, Complexity: 5
- **_cleanup_expired_uploads**(`0 args`) — Line 51, Complexity: 5
- **_validate_startup**(`0 args`) — Line 99, Complexity: 10
- **lifespan**(`app`) — Line 235, Complexity: 11
- **authentication_error_handler**(`request, exc`) — Line 346, Complexity: 1
- **authorization_error_handler**(`request, exc`) — Line 356, Complexity: 1
- **rate_limit_error_handler**(`request, exc`) — Line 366, Complexity: 2
- **unhandled_exception_handler**(`request, exc`) — Line 380, Complexity: 2
- **dispatch**(`self, request, call_next`) — Line 192, Complexity: 3
- **dispatch**(`self, request, call_next`) — Line 207, Complexity: 2
- **_before_send**(`event, hint`) — Line 247, Complexity: 4

### `backend\app\models\agent_execution.py`
- **__repr__**(`self`) — Line 76, Complexity: 1

### `backend\app\models\agent_session.py`
- **__repr__**(`self`) — Line 42, Complexity: 1
- **__repr__**(`self`) — Line 89, Complexity: 1

### `backend\app\models\audio_digest.py`
- **__repr__**(`self`) — Line 38, Complexity: 1

### `backend\app\models\audit.py`
- **__repr__**(`self`) — Line 38, Complexity: 1

### `backend\app\models\case.py`
- **__repr__**(`self`) — Line 247, Complexity: 1

### `backend\app\models\chat.py`
- **__repr__**(`self`) — Line 30, Complexity: 1
- **__repr__**(`self`) — Line 62, Complexity: 1

### `backend\app\models\consent.py`
- **__repr__**(`self`) — Line 36, Complexity: 1

### `backend\app\models\document.py`
- **__repr__**(`self`) — Line 54, Complexity: 1

### `backend\app\models\document_analysis.py`
- **__repr__**(`self`) — Line 29, Complexity: 1

### `backend\app\models\search_history.py`
- **__repr__**(`self`) — Line 33, Complexity: 1

### `backend\app\models\statute.py`
- **__repr__**(`self`) — Line 47, Complexity: 1

### `backend\app\models\user.py`
- **__repr__**(`self`) — Line 43, Complexity: 1

### `backend\app\security\audit.py`
- **create_audit_log**(`db, action, user_id, resource_type, resource_id, ip_address, user_agent, metadata`) — Line 17, Complexity: 1

### `backend\app\security\auth.py`
- **_get_revocation_redis**(`0 args`) — Line 45, Complexity: 2
- **revoke_token**(`jti, exp_timestamp`) — Line 54, Complexity: 3
- **is_token_revoked**(`jti`) — Line 65, Complexity: 2
- **clear_revoked_tokens**(`0 args`) — Line 75, Complexity: 1
- **create_access_token**(`user_id, role, expires_delta`) — Line 87, Complexity: 1
- **create_refresh_token**(`user_id, expires_delta`) — Line 122, Complexity: 1
- **_decode_token**(`token, secret, expected_type`) — Line 162, Complexity: 8
- **verify_access_token**(`token`) — Line 212, Complexity: 1
- **verify_refresh_token**(`token`) — Line 227, Complexity: 1
- **hash_password**(`password`) — Line 247, Complexity: 1
- **verify_password**(`plain, hashed`) — Line 261, Complexity: 1

### `backend\app\security\encryption.py`
- **_get_key**(`0 args`) — Line 18, Complexity: 5
- **encrypt_field**(`plaintext`) — Line 54, Complexity: 1
- **decrypt_field**(`ciphertext`) — Line 80, Complexity: 4
- **safe_decrypt**(`value`) — Line 116, Complexity: 2

### `backend\app\security\exceptions.py`
- **__init__**(`self, detail`) — Line 15, Complexity: 1
- **__init__**(`self, detail`) — Line 27, Complexity: 1
- **__init__**(`self, detail, retry_after`) — Line 39, Complexity: 1

### `backend\app\security\rate_limiter.py`
- **_get_rate_limiter**(`0 args`) — Line 108, Complexity: 3
- **_in_memory_check**(`key, limit, window_seconds`) — Line 133, Complexity: 3
- **_parse_rate_limit**(`limit_str`) — Line 155, Complexity: 4
- **rate_limit_dependency**(`limit`) — Line 193, Complexity: 6
- **__init__**(`self, redis_client`) — Line 49, Complexity: 1
- **check_rate_limit**(`self, key, limit, window_seconds`) — Line 52, Complexity: 2
- **_check_rate**(`request`) — Line 212, Complexity: 6

### `backend\app\security\rbac.py`
- **get_current_user**(`token`) — Line 23, Complexity: 1
- **get_current_user_optional**(`token`) — Line 43, Complexity: 3
- **require_role**(`0 args`) — Line 60, Complexity: 2
- **_role_checker**(`current_user`) — Line 87, Complexity: 2

### `backend\app\security\sanitizer.py`
- **sanitize_input**(`text`) — Line 71, Complexity: 1
- **sanitize_search_query**(`query`) — Line 98, Complexity: 1
- **detect_prompt_injection**(`text`) — Line 125, Complexity: 5

### `backend\app\tasks\audio_tasks.py`
- **generate_audio**(`self, case_id, language`) — Line 18, Complexity: 1
- **_generate_audio_async**(`case_id, language`) — Line 24, Complexity: 13
- **_get_tts_provider**(`0 args`) — Line 161, Complexity: 1

### `backend\app\tasks\document_tasks.py`
- **analyze_document**(`self, document_id`) — Line 17, Complexity: 1
- **_analyze_document_async**(`document_id`) — Line 23, Complexity: 6
- **_update_doc_status**(`db, document_id, status, step`) — Line 167, Complexity: 8
- **_chunk_embed_and_index**(`document_id, extracted_text, embedder, vector_store, db`) — Line 222, Complexity: 5
- **_format_issues_with_precedents**(`issues, precedent_results`) — Line 283, Complexity: 7

### `backend\migrations\env.py`
- **_get_connect_args**(`0 args`) — Line 27, Complexity: 3
- **run_migrations_offline**(`0 args`) — Line 42, Complexity: 1
- **do_run_migrations**(`connection`) — Line 54, Complexity: 1
- **run_async_migrations**(`0 args`) — Line 60, Complexity: 1
- **run_migrations_online**(`0 args`) — Line 77, Complexity: 1

### `backend\migrations\versions\001_initial.py`
- **upgrade**(`0 args`) — Line 19, Complexity: 1
- **downgrade**(`0 args`) — Line 351, Complexity: 1

### `backend\migrations\versions\002_documents_audio.py`
- **upgrade**(`0 args`) — Line 18, Complexity: 1
- **downgrade**(`0 args`) — Line 112, Complexity: 1

### `backend\migrations\versions\003_citation_equivalents.py`
- **upgrade**(`0 args`) — Line 18, Complexity: 1
- **downgrade**(`0 args`) — Line 37, Complexity: 1

### `backend\migrations\versions\004_case_sections.py`
- **upgrade**(`0 args`) — Line 18, Complexity: 1
- **downgrade**(`0 args`) — Line 37, Complexity: 1

### `backend\migrations\versions\005_agent_executions.py`
- **upgrade**(`0 args`) — Line 18, Complexity: 1
- **downgrade**(`0 args`) — Line 80, Complexity: 1

### `backend\migrations\versions\006_indexes_and_performance.py`
- **upgrade**(`0 args`) — Line 23, Complexity: 1
- **downgrade**(`0 args`) — Line 46, Complexity: 1

### `backend\migrations\versions\007_dpdp_compliance.py`
- **upgrade**(`0 args`) — Line 16, Complexity: 1
- **downgrade**(`0 args`) — Line 34, Complexity: 1

### `backend\migrations\versions\008_strategy_drafting_agents.py`
- **upgrade**(`0 args`) — Line 15, Complexity: 1
- **downgrade**(`0 args`) — Line 24, Complexity: 1

### `backend\migrations\versions\009_ingestion_improvements.py`
- **upgrade**(`0 args`) — Line 17, Complexity: 1
- **downgrade**(`0 args`) — Line 79, Complexity: 1

### `backend\migrations\versions\010_weighted_fts.py`
- **upgrade**(`0 args`) — Line 16, Complexity: 1
- **downgrade**(`0 args`) — Line 57, Complexity: 1

### `backend\migrations\versions\011_legal_completeness.py`
- **upgrade**(`0 args`) — Line 26, Complexity: 1
- **downgrade**(`0 args`) — Line 114, Complexity: 1

### `backend\migrations\versions\012_search_excellence.py`
- **upgrade**(`0 args`) — Line 22, Complexity: 1
- **downgrade**(`0 args`) — Line 125, Complexity: 1

### `backend\migrations\versions\013_enterprise_readiness.py`
- **upgrade**(`0 args`) — Line 23, Complexity: 1
- **downgrade**(`0 args`) — Line 57, Complexity: 1

### `backend\migrations\versions\014_fix_triggers_and_constraints.py`
- **upgrade**(`0 args`) — Line 31, Complexity: 1
- **downgrade**(`0 args`) — Line 88, Complexity: 1

### `backend\migrations\versions\015_graph_build_queue.py`
- **upgrade**(`0 args`) — Line 21, Complexity: 1
- **downgrade**(`0 args`) — Line 32, Complexity: 1

### `backend\migrations\versions\016_india_audit_fixes.py`
- **upgrade**(`0 args`) — Line 22, Complexity: 1
- **downgrade**(`0 args`) — Line 72, Complexity: 1

### `backend\migrations\versions\017_pgvector_and_citations.py`
- **upgrade**(`0 args`) — Line 21, Complexity: 1
- **downgrade**(`0 args`) — Line 98, Complexity: 1

### `backend\migrations\versions\018_low_audit_fixes.py`
- **upgrade**(`0 args`) — Line 19, Complexity: 1
- **downgrade**(`0 args`) — Line 26, Complexity: 1

### `backend\migrations\versions\019_medium_audit_indexes.py`
- **upgrade**(`0 args`) — Line 24, Complexity: 1
- **downgrade**(`0 args`) — Line 46, Complexity: 1

### `backend\migrations\versions\020_create_statutes_table.py`
- **upgrade**(`0 args`) — Line 21, Complexity: 1
- **downgrade**(`0 args`) — Line 70, Complexity: 1

### `backend\migrations\versions\021_statutes_updated_at.py`
- **upgrade**(`0 args`) — Line 19, Complexity: 1
- **downgrade**(`0 args`) — Line 26, Complexity: 1

### `backend\migrations\versions\022_fix_constraints_and_types.py`
- **upgrade**(`0 args`) — Line 21, Complexity: 1
- **downgrade**(`0 args`) — Line 57, Complexity: 1

### `backend\migrations\versions\023_ingestion_v2_fields.py`
- **upgrade**(`0 args`) — Line 21, Complexity: 1
- **downgrade**(`0 args`) — Line 97, Complexity: 2

### `backend\migrations\versions\024_fix_fts_trigger_v2.py`
- **upgrade**(`0 args`) — Line 25, Complexity: 1
- **downgrade**(`0 args`) — Line 55, Complexity: 1

### `backend\migrations\versions\025_fix_fts_trigger_v3.py`
- **upgrade**(`0 args`) — Line 21, Complexity: 1
- **downgrade**(`0 args`) — Line 54, Complexity: 1

### `backend\migrations\versions\026_statutes_amendment_fields.py`
- **upgrade**(`0 args`) — Line 21, Complexity: 1
- **downgrade**(`0 args`) — Line 27, Complexity: 1

### `backend\migrations\versions\027_pg_trgm_fuzzy_search.py`
- **upgrade**(`0 args`) — Line 18, Complexity: 1
- **downgrade**(`0 args`) — Line 26, Complexity: 1

### `backend\migrations\versions\028_coram_size.py`
- **upgrade**(`0 args`) — Line 17, Complexity: 1
- **downgrade**(`0 args`) — Line 21, Complexity: 1

### `backend\migrations\versions\029_schema_hardening.py`
- **upgrade**(`0 args`) — Line 22, Complexity: 1
- **downgrade**(`0 args`) — Line 45, Complexity: 1

### `backend\migrations\versions\030_amendment_maps.py`
- **upgrade**(`0 args`) — Line 14, Complexity: 1
- **downgrade**(`0 args`) — Line 42, Complexity: 1

### `backend\migrations\versions\032_fts_trigger_optimization.py`
- **upgrade**(`0 args`) — Line 22, Complexity: 1
- **downgrade**(`0 args`) — Line 65, Complexity: 1

### `backend\migrations\versions\033_text_hash_unique_index.py`
- **upgrade**(`0 args`) — Line 23, Complexity: 1
- **downgrade**(`0 args`) — Line 44, Complexity: 1

### `backend\migrations\versions\034_ingestion_status_index.py`
- **upgrade**(`0 args`) — Line 21, Complexity: 1
- **downgrade**(`0 args`) — Line 37, Complexity: 1

### `backend\migrations\versions\035_ingestion_v3_fields.py`
- **upgrade**(`0 args`) — Line 11, Complexity: 1
- **downgrade**(`0 args`) — Line 36, Complexity: 1

### `backend\migrations\versions\036_agent_conversation_history.py`
- **upgrade**(`0 args`) — Line 11, Complexity: 1
- **downgrade**(`0 args`) — Line 110, Complexity: 1

### `backend\scripts\audit_migration.py`
- **audit**(`0 args`) — Line 15, Complexity: 56
- **group_constraints**(`rows`) — Line 218, Complexity: 3

### `backend\scripts\audit_models_vs_db.py`
- **normalize_type**(`sa_type_str`) — Line 26, Complexity: 8
- **get_sa_type_name**(`col`) — Line 66, Complexity: 15
- **compare_types**(`model_type, db_type`) — Line 110, Complexity: 22
- **get_db_type_name**(`db_type_obj`) — Line 157, Complexity: 15
- **audit_table**(`inspector, table_name, model_table`) — Line 201, Complexity: 37
- **main**(`0 args`) — Line 347, Complexity: 8

### `backend\scripts\backfill_contextual_embeddings.py`
- **backfill_case**(`case_id, db, embedder, vector_store, flash_llm, dry_run`) — Line 27, Complexity: 16
- **main**(`args`) — Line 121, Complexity: 8

### `backend\scripts\backfill_pinecone_metadata.py`
- **main**(`args`) — Line 27, Complexity: 8

### `backend\scripts\batch_ingest.py`
- **_normalize_doc_key**(`year, pdf_path`) — Line 81, Complexity: 1
- **_upload_pdf**(`client, pdf_path`) — Line 90, Complexity: 1
- **_build_batch_request_entry**(`doc_key, file_uri`) — Line 98, Complexity: 1
- **_load_existing_text_hashes**(`0 args`) — Line 134, Complexity: 1
- **submit_year**(`year, api_keys, state_db, data_dir`) — Line 148, Complexity: 16
- **poll_jobs**(`api_keys, state_db`) — Line 312, Complexity: 9
- **_collect_results**(`client, job, state_db`) — Line 365, Complexity: 12
- **_process_result_entry**(`entry, state_db`) — Line 404, Complexity: 8
- **process_completed**(`api_keys, state_db`) — Line 448, Complexity: 8
- **main**(`0 args`) — Line 585, Complexity: 5
- **_process_one**(`doc`) — Line 498, Complexity: 5
- **_process_pdf**(`pdf_path`) — Line 212, Complexity: 5

### `backend\scripts\batch_llm.py`
- **__init__**(`self, result`) — Line 32, Complexity: 1
- **generate_structured_from_pdf**(`self, pdf_path`) — Line 35, Complexity: 1
- **generate_structured**(`self, prompt`) — Line 46, Complexity: 1
- **generate**(`self, prompt`) — Line 56, Complexity: 1
- **stream**(`self, prompt`) — Line 66, Complexity: 1

### `backend\scripts\batch_state.py`
- **__init__**(`self, db_path`) — Line 23, Complexity: 1
- **_create_tables**(`self`) — Line 32, Complexity: 1
- **insert_doc**(`self, doc_key, year, file_uri, text_hash, full_text_len, parquet_meta, pdf_path, api_key_index`) — Line 63, Complexity: 1
- **get_doc**(`self, doc_key`) — Line 84, Complexity: 1
- **update_doc_status**(`self, doc_key, status`) — Line 91, Complexity: 2
- **store_result**(`self, doc_key, result`) — Line 107, Complexity: 1
- **mark_error**(`self, doc_key, error`) — Line 115, Complexity: 1
- **get_docs_by_status**(`self, status`) — Line 123, Complexity: 2
- **insert_job**(`self, job_name, api_key_index, doc_count`) — Line 138, Complexity: 1
- **get_job**(`self, job_name`) — Line 146, Complexity: 1
- **update_job_status**(`self, job_name, status`) — Line 153, Complexity: 1
- **get_pending_jobs**(`self`) — Line 162, Complexity: 1

### `backend\scripts\benchmark_extraction.py`
- **_normalize**(`value`) — Line 77, Complexity: 2
- **_compare_scalar**(`gold, predicted`) — Line 84, Complexity: 6
- **_compare_list**(`gold, predicted`) — Line 100, Complexity: 4
- **evaluate_case**(`gold, predicted, results, fields_filter`) — Line 114, Complexity: 12
- **run_benchmark**(`gold_dir, llm, fields_filter`) — Line 153, Complexity: 9
- **print_results**(`results`) — Line 214, Complexity: 5
- **main**(`0 args`) — Line 244, Complexity: 4
- **precision**(`self`) — Line 53, Complexity: 1
- **recall**(`self`) — Line 58, Complexity: 1
- **f1**(`self`) — Line 63, Complexity: 1

### `backend\scripts\build_citation_communities.py`
- **export_citation_graph**(`graph_store`) — Line 34, Complexity: 2
- **summarize_community**(`community_id, case_ids, db, flash_llm`) — Line 60, Complexity: 3
- **store_communities**(`communities, case_communities, graph_store`) — Line 111, Complexity: 3
- **embed_community_summaries**(`communities, embedder, vector_store`) — Line 154, Complexity: 2
- **build_communities**(`graph_store, flash_llm, embedder, vector_store, resolution`) — Line 193, Complexity: 5
- **main**(`0 args`) — Line 248, Complexity: 1

### `backend\scripts\daily_ingest.py`
- **_run_ingest**(`args`) — Line 37, Complexity: 4
- **_run_neo4j_populate**(`args`) — Line 59, Complexity: 1
- **main**(`0 args`) — Line 72, Complexity: 4

### `backend\scripts\download_and_convert_statutes.py`
- **fetch_json**(`url`) — Line 143, Complexity: 1
- **fetch_pdf_bytes**(`url`) — Line 151, Complexity: 1
- **convert_ipc**(`data`) — Line 164, Complexity: 2
- **convert_crpc**(`data`) — Line 192, Complexity: 2
- **convert_cpc**(`data`) — Line 220, Complexity: 2
- **convert_iea**(`data`) — Line 249, Complexity: 2
- **convert_constitution**(`data`) — Line 282, Complexity: 3
- **extract_sections_from_pdf**(`pdf_bytes, act_config`) — Line 324, Complexity: 6
- **save_json**(`sections, filename`) — Line 780, Complexity: 1
- **download_github_acts**(`only`) — Line 789, Complexity: 5
- **download_pdf_acts**(`only, batch_codes`) — Line 816, Complexity: 9
- **main**(`0 args`) — Line 858, Complexity: 8

### `backend\scripts\e2e_research_pipeline.py`
- **run_component_e2e**(`0 args`) — Line 18, Complexity: 16

### `backend\scripts\e2e_test_apis.py`
- **test_ik_basic_search**(`token`) — Line 23, Complexity: 3
- **test_ik_boolean_search**(`token`) — Line 46, Complexity: 3
- **test_ik_date_filter**(`token`) — Line 73, Complexity: 3
- **test_ik_fragment**(`token`) — Line 101, Complexity: 4
- **test_ik_pagination**(`token`) — Line 134, Complexity: 2
- **test_tavily_basic**(`api_key`) — Line 157, Complexity: 3
- **test_tavily_country_india**(`api_key`) — Line 182, Complexity: 3
- **test_tavily_time_range**(`api_key`) — Line 207, Complexity: 3
- **test_tavily_raw_content**(`api_key`) — Line 233, Complexity: 4
- **test_ik_title_filter**(`token`) — Line 264, Complexity: 3
- **test_ik_author_filter**(`token`) — Line 286, Complexity: 3
- **test_ik_maxcites**(`token`) — Line 307, Complexity: 3
- **test_ik_maxpages**(`token`) — Line 330, Complexity: 2
- **test_ik_rich_fields**(`token`) — Line 349, Complexity: 2
- **main**(`0 args`) — Line 376, Complexity: 7

### `backend\scripts\enrich_pro.py`
- **enrich_case**(`full_text, llm`) — Line 58, Complexity: 1
- **run**(`args`) — Line 68, Complexity: 13
- **main**(`0 args`) — Line 149, Complexity: 3

### `backend\scripts\generate_statute_json.py`
- **_sort_key**(`sec`) — Line 120, Complexity: 1
- **generate_ipc**(`0 args`) — Line 124, Complexity: 2
- **generate_bns**(`0 args`) — Line 146, Complexity: 2
- **generate_crpc**(`0 args`) — Line 170, Complexity: 2
- **generate_bnss**(`0 args`) — Line 191, Complexity: 2
- **generate_iea**(`0 args`) — Line 213, Complexity: 2
- **generate_bsa**(`0 args`) — Line 234, Complexity: 2
- **main**(`0 args`) — Line 256, Complexity: 2

### `backend\scripts\ingest_s3.py`
- **_disable_fts_trigger**(`0 args`) — Line 56, Complexity: 1
- **_enable_fts_trigger**(`0 args`) — Line 66, Complexity: 1
- **_rebuild_fts_vectors**(`0 args`) — Line 76, Complexity: 1
- **_build_key_pool**(`0 args`) — Line 111, Complexity: 3
- **_validate_api_keys**(`llm_pool`) — Line 128, Complexity: 3
- **_make_shutdown_handler**(`shutdown_event, loop`) — Line 156, Complexity: 2
- **_download_with_timeout**(`url, dest, timeout`) — Line 467, Complexity: 1
- **_s3_download**(`s3_path, local_path`) — Line 481, Complexity: 4
- **download_year_data**(`year, data_dir`) — Line 520, Complexity: 3
- **extract_tar**(`tar_path, extract_dir`) — Line 538, Complexity: 3
- **load_parquet_metadata**(`parquet_path`) — Line 553, Complexity: 3
- **_strip_language_suffix**(`stem`) — Line 575, Complexity: 1
- **_match_pdf_to_metadata**(`pdf_path, metadata_map, stem_index`) — Line 581, Complexity: 7
- **_reconcile_orphans**(`0 args`) — Line 685, Complexity: 3
- **ingest_year**(`year, data_dir, tracker`) — Line 707, Complexity: 38
- **parse_args**(`0 args`) — Line 1011, Complexity: 2
- **main**(`0 args`) — Line 1054, Complexity: 27
- **_handle_shutdown**(`sig, frame`) — Line 162, Complexity: 2
- **__init__**(`self, db_path`) — Line 183, Complexity: 1
- **_migrate_schema**(`self`) — Line 191, Complexity: 3
- **is_processed**(`self, doc_key`) — Line 240, Complexity: 2
- **is_permanently_failed**(`self, doc_key, max_retries`) — Line 258, Complexity: 4
- **add_warning**(`self, doc_key, warning`) — Line 273, Complexity: 3
- **init_doc**(`self, doc_key, year`) — Line 290, Complexity: 1
- **mark_stage**(`self, doc_key, stage, case_id`) — Line 299, Complexity: 7
- **mark_success**(`self, doc_key, case_id`) — Line 341, Complexity: 1
- **mark_failed**(`self, doc_key, error`) — Line 350, Complexity: 2
- **get_failed_at_stage**(`self, stage`) — Line 385, Complexity: 1
- **get_by_quality**(`self, tier`) — Line 395, Complexity: 1
- **stats**(`self`) — Line 405, Complexity: 1
- **detailed_stats**(`self, year`) — Line 413, Complexity: 3
- **close**(`self`) — Line 457, Complexity: 1
- **__init__**(`self, threshold, cooldown_secs`) — Line 628, Complexity: 1
- **is_tripped**(`self`) — Line 637, Complexity: 1
- **check**(`self`) — Line 640, Complexity: 4
- **record_success**(`self`) — Line 654, Complexity: 2
- **record_failure**(`self`) — Line 661, Complexity: 3
- **_process_one**(`pdf_path, llm, embedder, api_key`) — Line 835, Complexity: 11
- **_worker**(`worker_id`) — Line 933, Complexity: 8

### `backend\scripts\ingest_statutes.py`
- **load_progress**(`0 args`) — Line 92, Complexity: 2
- **save_progress**(`progress`) — Line 100, Complexity: 1
- **_handle_signal**(`signum, frame`) — Line 114, Complexity: 1
- **upsert_statute**(`db, statute`) — Line 134, Complexity: 3
- **compute_replacement_fields**(`act_short_name, section_number`) — Line 185, Complexity: 5
- **parse_statute_json**(`filepath`) — Line 213, Complexity: 6
- **_normalize_statute**(`raw`) — Line 236, Complexity: 5
- **ingest_statute_file**(`filepath, db, embedder, vector_store, graph_store, flash_llm, dry_run, breaker`) — Line 278, Complexity: 25
- **main**(`args`) — Line 420, Complexity: 20
- **__init__**(`self, threshold`) — Line 63, Complexity: 1
- **record_success**(`self`) — Line 68, Complexity: 1
- **record_failure**(`self`) — Line 71, Complexity: 2
- **is_open**(`self`) — Line 81, Complexity: 1

### `backend\scripts\monitor_ingestion.py`
- **check_all**(`0 args`) — Line 19, Complexity: 4
- **monitor_loop**(`0 args`) — Line 81, Complexity: 10

### `backend\scripts\normalize_acts_cited.py`
- **sync_pinecone_metadata**(`updated_cases`) — Line 50, Complexity: 10
- **normalize_all_cases**(`commit, sync_pinecone`) — Line 133, Complexity: 27
- **main**(`0 args`) — Line 283, Complexity: 1

### `backend\scripts\poll_batch_test.py`
- **main**(`0 args`) — Line 16, Complexity: 15

### `backend\scripts\populate_neo4j.py`
- **get_pg_dsn**(`0 args`) — Line 49, Complexity: 2
- **get_neo4j_driver**(`0 args`) — Line 59, Complexity: 1
- **_normalize_citation**(`s`) — Line 71, Complexity: 1
- **_extract_citation_patterns**(`cited_str`) — Line 86, Complexity: 4
- **_resolve_citation**(`cited_str, citation_map, title_map`) — Line 109, Complexity: 7
- **_extract_act_name**(`act_string`) — Line 139, Complexity: 3
- **fetch_cases**(`conn, offset, limit`) — Line 166, Complexity: 1
- **get_case_count**(`conn`) — Line 180, Complexity: 1
- **build_citation_index**(`conn`) — Line 185, Complexity: 10
- **clear_graph**(`driver, database`) — Line 244, Complexity: 1
- **create_constraints**(`driver, database`) — Line 251, Complexity: 7
- **batch_create_nodes**(`driver, database, cases, dry_run`) — Line 299, Complexity: 14
- **batch_create_edges**(`driver, database, cases, citation_map, title_map, dry_run`) — Line 340, Complexity: 11
- **batch_create_act_nodes**(`driver, database, cases, dry_run`) — Line 387, Complexity: 10
- **batch_create_judge_nodes**(`driver, database, cases, dry_run`) — Line 431, Complexity: 12
- **update_cited_by_counts**(`driver, database`) — Line 491, Complexity: 1
- **sync_cited_by_counts_to_pg**(`driver, database, conn`) — Line 501, Complexity: 4
- **get_neo4j_stats**(`driver, database`) — Line 544, Complexity: 1
- **_get_neo4j_case_ids**(`driver, database`) — Line 596, Complexity: 1
- **populate**(`batch_size, dry_run, incremental`) — Line 604, Complexity: 15
- **show_stats**(`0 args`) — Line 772, Complexity: 1
- **main**(`0 args`) — Line 795, Complexity: 2

### `backend\scripts\quality_eval.py`
- **run**(`0 args`) — Line 17, Complexity: 15

### `backend\scripts\reset_all_data.py`
- **reset_postgresql**(`0 args`) — Line 18, Complexity: 3
- **reset_pinecone**(`0 args`) — Line 46, Complexity: 5
- **reset_neo4j**(`0 args`) — Line 76, Complexity: 4
- **reset_sqlite_tracker**(`0 args`) — Line 113, Complexity: 2
- **reset_local_pdfs**(`0 args`) — Line 125, Complexity: 3
- **main**(`0 args`) — Line 139, Complexity: 1

### `backend\scripts\test_resume_flow.py`
- **test_resume_flow**(`0 args`) — Line 31, Complexity: 21

### `backend\scripts\verify_ingestion.py`
- **verify**(`sample_size`) — Line 28, Complexity: 15
- **main**(`0 args`) — Line 120, Complexity: 1

### `backend\tests\conftest.py`
- **_isolate_rate_limiter**(`0 args`) — Line 11, Complexity: 1
- **sample_judgment_text**(`0 args`) — Line 40, Complexity: 1
- **sample_parquet_metadata**(`0 args`) — Line 108, Complexity: 1

### `backend\tests\integration\test_ingestion.py`
- **_make_text_quality**(`text`) — Line 26, Complexity: 1
- **_make_db_mock**(`0 args`) — Line 35, Complexity: 3
- **_make_llm_mock**(`0 args`) — Line 77, Complexity: 1
- **_make_embedder_mock**(`dimension`) — Line 101, Complexity: 1
- **_make_vector_store_mock**(`0 args`) — Line 112, Complexity: 1
- **_make_graph_store_mock**(`0 args`) — Line 118, Complexity: 1
- **_make_storage_mock**(`case_id`) — Line 125, Complexity: 1
- **_execute_side_effect**(`stmt, params`) — Line 46, Complexity: 3
- **test_full_pipeline_success**(`self, sample_judgment_text, sample_parquet_metadata`) — Line 140, Complexity: 1
- **test_pipeline_with_ocr_fallback**(`self, sample_judgment_text, sample_parquet_metadata`) — Line 205, Complexity: 1
- **test_pipeline_records_failure_on_no_text**(`self, sample_parquet_metadata`) — Line 254, Complexity: 3
- **test_duplicate_citation_skips_insert**(`self, sample_judgment_text, sample_parquet_metadata`) — Line 314, Complexity: 3
- **test_pipeline_stores_pdf**(`self, sample_judgment_text, sample_parquet_metadata`) — Line 358, Complexity: 1
- **test_pipeline_creates_chunks_and_embeddings**(`self, sample_judgment_text, sample_parquet_metadata`) — Line 403, Complexity: 3
- **test_pipeline_builds_citation_graph**(`self, sample_judgment_text, sample_parquet_metadata`) — Line 466, Complexity: 3
- **test_safe_filename_from_title**(`self`) — Line 532, Complexity: 1
- **test_safe_filename_special_characters**(`self`) — Line 543, Complexity: 2
- **test_safe_filename_empty**(`self`) — Line 552, Complexity: 1
- **test_safe_filename_long_title_truncated**(`self`) — Line 567, Complexity: 1
- **test_embed_chunks_batching**(`self`) — Line 576, Complexity: 1
- **test_embed_chunks_single_batch**(`self`) — Line 610, Complexity: 1
- **test_embed_chunks_empty_list**(`self`) — Line 630, Complexity: 1
- **__aenter__**(`self`) — Line 68, Complexity: 1
- **__aexit__**(`self`) — Line 70, Complexity: 1

### `backend\tests\integration\test_search.py`
- **_make_case_row**(`case_id, title, citation, court, year, case_type, bench_type, judge, decision_date`) — Line 30, Complexity: 1
- **_fake_query_understanding**(`query`) — Line 55, Complexity: 1
- **_mock_db_session**(`0 args`) — Line 71, Complexity: 1
- **_configure_db_for_facets**(`db`) — Line 77, Complexity: 1
- **_configure_db_for_suggest**(`db, rows`) — Line 102, Complexity: 2
- **_mock_redis_none**(`0 args`) — Line 114, Complexity: 1
- **_mock_llm**(`0 args`) — Line 122, Complexity: 1
- **_mock_embedder**(`0 args`) — Line 144, Complexity: 1
- **_mock_vector_store**(`results`) — Line 152, Complexity: 2
- **_mock_reranker**(`top_ids_count`) — Line 164, Complexity: 1
- **anyio_backend**(`0 args`) — Line 182, Complexity: 1
- **mock_db**(`0 args`) — Line 187, Complexity: 1
- **mock_redis**(`0 args`) — Line 192, Complexity: 1
- **app_client**(`0 args`) — Line 197, Complexity: 1
- **test_basic_search_returns_results**(`self, app_client`) — Line 215, Complexity: 1
- **test_search_with_filters**(`self, app_client`) — Line 271, Complexity: 1
- **test_search_empty_query_returns_error**(`self, app_client`) — Line 325, Complexity: 1
- **test_search_missing_query_returns_error**(`self, app_client`) — Line 333, Complexity: 1
- **test_search_returns_facets_in_response**(`self, app_client`) — Line 341, Complexity: 2
- **test_suggest_returns_suggestions**(`self, app_client`) — Line 422, Complexity: 1
- **test_suggest_empty_query**(`self, app_client`) — Line 451, Complexity: 1
- **test_suggest_short_query**(`self, app_client`) — Line 459, Complexity: 1
- **test_suggest_no_results**(`self, app_client`) — Line 467, Complexity: 1
- **test_facets_returns_courts_and_years**(`self, app_client`) — Line 498, Complexity: 1
- **test_facets_response_shape**(`self, app_client`) — Line 526, Complexity: 1
- **test_rrf_merge_integrates_vector_and_fts**(`self`) — Line 576, Complexity: 1
- **test_rrf_scores_reflect_overlap**(`self`) — Line 608, Complexity: 1
- **test_search_falls_back_on_llm_failure**(`self`) — Line 620, Complexity: 1
- **test_search_falls_back_on_llm_connection_error**(`self`) — Line 640, Complexity: 1
- **test_hybrid_search_empty_results**(`self`) — Line 655, Complexity: 1
- **test_hybrid_search_reranker_failure_uses_rrf_order**(`self`) — Line 684, Complexity: 1
- **override_get_db**(`0 args`) — Line 241, Complexity: 1
- **override_get_db**(`0 args`) — Line 293, Complexity: 1
- **override_get_db**(`0 args`) — Line 363, Complexity: 1
- **override_get_db**(`0 args`) — Line 429, Complexity: 1
- **override_get_db**(`0 args`) — Line 474, Complexity: 1
- **override_get_db**(`0 args`) — Line 505, Complexity: 1
- **override_get_db**(`0 args`) — Line 533, Complexity: 1

### `backend\tests\integration\test_search_accuracy.py`
- **client**(`0 args`) — Line 34, Complexity: 1
- **_search**(`client, q`) — Line 39, Complexity: 1
- **test_exact_citation_2024_insc_878**(`self, client`) — Line 62, Complexity: 1
- **test_criminal_appeal_cases**(`self, client`) — Line 74, Complexity: 5
- **test_civil_appeal_cases**(`self, client`) — Line 92, Complexity: 4
- **test_slp_cases**(`self, client`) — Line 109, Complexity: 5
- **test_writ_petition_cases**(`self, client`) — Line 127, Complexity: 4
- **test_right_to_privacy**(`self, client`) — Line 155, Complexity: 5
- **test_murder_section_302**(`self, client`) — Line 173, Complexity: 5
- **test_land_acquisition_compensation**(`self, client`) — Line 195, Complexity: 4
- **test_bail_conditions**(`self, client`) — Line 216, Complexity: 5
- **test_constitutional_validity**(`self, client`) — Line 238, Complexity: 4
- **test_court_filter_supreme_court**(`self, client`) — Line 273, Complexity: 2
- **test_year_filter_2024**(`self, client`) — Line 286, Complexity: 2
- **test_case_type_filter_criminal_appeal**(`self, client`) — Line 299, Complexity: 2
- **test_combined_topic_and_case_type**(`self, client`) — Line 315, Complexity: 6
- **test_page_size_limit**(`self, client`) — Line 344, Complexity: 1

### `backend\tests\load\locustfile.py`
- **on_start**(`self`) — Line 53, Complexity: 4
- **_headers**(`self`) — Line 81, Complexity: 2
- **search**(`self`) — Line 87, Complexity: 1
- **search_with_filters**(`self`) — Line 98, Complexity: 1
- **suggest**(`self`) — Line 114, Complexity: 1
- **health_check**(`self`) — Line 125, Complexity: 1
- **view_judges**(`self`) — Line 130, Complexity: 1

### `backend\tests\quality\conftest.py`
- **db_session**(`0 args`) — Line 37, Complexity: 1
- **search_client**(`db_session`) — Line 92, Complexity: 1
- **agent_runner**(`0 args`) — Line 201, Complexity: 1
- **__init__**(`self, db`) — Line 51, Complexity: 1
- **search**(`self, query, page_size, language`) — Line 58, Complexity: 3
- **__init__**(`self`) — Line 105, Complexity: 1
- **run_research**(`self, query`) — Line 113, Complexity: 1
- **run_strategy**(`self, case_facts, desired_relief`) — Line 138, Complexity: 1
- **run_drafting**(`self, doc_type, case_facts`) — Line 169, Complexity: 1

### `backend\tests\quality\test_agent_quality.py`
- **test_research_memo_has_citations**(`self, scenario, agent_runner`) — Line 85, Complexity: 2
- **test_research_has_confidence**(`self, scenario, agent_runner`) — Line 100, Complexity: 1
- **test_strategy_memo_content**(`self, scenario, agent_runner`) — Line 114, Complexity: 2
- **test_strategy_has_strength_assessment**(`self, scenario, agent_runner`) — Line 132, Complexity: 1
- **test_draft_has_sections**(`self, scenario, agent_runner`) — Line 151, Complexity: 2
- **test_draft_has_no_placeholder**(`self, scenario, agent_runner`) — Line 169, Complexity: 2

### `backend\tests\quality\test_metadata_benchmark.py`
- **_load_gold_standard**(`0 args`) — Line 25, Complexity: 1
- **test_fixture_loads**(`self`) — Line 33, Complexity: 1
- **test_all_required_fields_present**(`self`) — Line 37, Complexity: 4
- **test_gold_case_confidence_above_threshold**(`self, case_data`) — Line 54, Complexity: 1
- **test_validation_preserves_gold_data**(`self, case_data`) — Line 73, Complexity: 2

### `backend\tests\quality\test_search_accuracy.py`
- **test_citation_in_top_5**(`self, query, keywords, fragment, search_client`) — Line 108, Complexity: 1
- **test_keywords_in_results**(`self, query, keywords, search_client`) — Line 129, Complexity: 2
- **test_hindi_returns_results**(`self, query, expected_keywords, search_client`) — Line 151, Complexity: 1

### `backend\tests\security\test_jwt_claims.py`
- **test_access_token_has_iss_claim**(`self`) — Line 22, Complexity: 1
- **test_access_token_has_aud_claim**(`self`) — Line 30, Complexity: 1
- **test_refresh_token_has_iss_claim**(`self`) — Line 38, Complexity: 1
- **test_refresh_token_has_aud_claim**(`self`) — Line 46, Complexity: 1
- **test_reject_token_wrong_audience**(`self`) — Line 55, Complexity: 1
- **test_reject_token_wrong_issuer**(`self`) — Line 72, Complexity: 1
- **test_reject_expired_token**(`self`) — Line 89, Complexity: 1

### `backend\tests\security\test_security.py`
- **test_script_tag_removed**(`self`) — Line 17, Complexity: 1
- **test_img_onerror_removed**(`self`) — Line 21, Complexity: 1
- **test_nested_tags_removed**(`self`) — Line 25, Complexity: 1
- **test_html_entities_in_tags**(`self`) — Line 29, Complexity: 1
- **test_single_quotes_preserved_in_legal_text**(`self`) — Line 37, Complexity: 1
- **test_semicolons_preserved**(`self`) — Line 42, Complexity: 1
- **test_injection_detected**(`self, attack`) — Line 64, Complexity: 1
- **test_safe_input_not_flagged**(`self, safe_input`) — Line 77, Complexity: 1
- **test_search_query_strips_injections**(`self`) — Line 80, Complexity: 1

### `backend\tests\unit\test_35k_hardening.py`
- **test_short_text_passes_through**(`self`) — Line 30, Complexity: 1
- **test_exact_boundary_passes_through**(`self`) — Line 34, Complexity: 1
- **test_long_text_truncated**(`self`) — Line 38, Complexity: 1
- **test_100k_text**(`self`) — Line 46, Complexity: 1
- **test_all_null_response_raises**(`self`) — Line 61, Complexity: 1
- **test_empty_dict_raises**(`self`) — Line 69, Complexity: 1
- **test_partial_null_passes**(`self`) — Line 77, Complexity: 1
- **test_invalid_judicial_tone_cleared**(`self`) — Line 91, Complexity: 1
- **test_valid_judicial_tone_kept**(`self`) — Line 96, Complexity: 1
- **test_judicial_tone_case_insensitive**(`self`) — Line 101, Complexity: 1
- **test_invalid_filing_date_cleared**(`self`) — Line 107, Complexity: 1
- **test_valid_filing_date_kept**(`self`) — Line 112, Complexity: 1
- **test_hearing_count_out_of_range**(`self`) — Line 117, Complexity: 1
- **test_hearing_count_negative**(`self`) — Line 122, Complexity: 1
- **test_hearing_count_valid**(`self`) — Line 127, Complexity: 1
- **test_operative_order_capped**(`self`) — Line 132, Complexity: 1
- **test_list_field_capped**(`self`) — Line 137, Complexity: 1
- **test_non_list_converted_to_list**(`self`) — Line 142, Complexity: 1
- **test_citation_treatments_invalid_filtered**(`self`) — Line 147, Complexity: 1
- **test_party_counsel_invalid_filtered**(`self`) — Line 157, Complexity: 1
- **test_null_bytes_removed**(`self`) — Line 172, Complexity: 1
- **test_bell_char_removed**(`self`) — Line 179, Complexity: 1
- **test_newlines_preserved**(`self`) — Line 184, Complexity: 1
- **test_mixed_control_chars**(`self`) — Line 189, Complexity: 1
- **test_reporter_patterns**(`self, line, should_match`) — Line 222, Complexity: 2

### `backend\tests\unit\test_acts_normalization.py`
- **test_normalize_full_name_to_short_code**(`self`) — Line 22, Complexity: 1
- **test_normalize_section_ref_to_act**(`self`) — Line 27, Complexity: 1
- **test_normalize_article_ref**(`self`) — Line 34, Complexity: 1
- **test_normalize_already_short**(`self`) — Line 41, Complexity: 1
- **test_normalize_newline_broken**(`self`) — Line 46, Complexity: 1
- **test_garbage_filtered**(`self`) — Line 51, Complexity: 1
- **test_year_only_filtered**(`self`) — Line 58, Complexity: 1
- **test_vague_refs_filtered**(`self`) — Line 63, Complexity: 1
- **test_dedup_variants**(`self`) — Line 70, Complexity: 1
- **test_unknown_act_passes_through**(`self`) — Line 77, Complexity: 1
- **test_new_acts_normalize**(`self`) — Line 82, Complexity: 1
- **test_empty_and_none**(`self`) — Line 91, Complexity: 1
- **test_read_with_format**(`self`) — Line 96, Complexity: 1
- **test_section_short_code_format**(`self`) — Line 103, Complexity: 1
- **test_multiple_acts_sorted**(`self`) — Line 108, Complexity: 1
- **test_article_without_of**(`self`) — Line 117, Complexity: 1
- **test_valid_act**(`self`) — Line 128, Complexity: 1
- **test_too_short**(`self`) — Line 132, Complexity: 1
- **test_blocklist**(`self`) — Line 136, Complexity: 1
- **test_year_only**(`self`) — Line 143, Complexity: 1
- **test_year_act_pattern**(`self`) — Line 147, Complexity: 1
- **test_newline_rejected**(`self`) — Line 151, Complexity: 1
- **test_valid_passes**(`self`) — Line 154, Complexity: 1
- **test_new_act_full_to_short**(`self, raw, expected`) — Line 178, Complexity: 1
- **test_enrich_adds_bns_for_ipc**(`self`) — Line 187, Complexity: 1
- **test_enrich_adds_ipc_for_bns**(`self`) — Line 191, Complexity: 1
- **test_enrich_bidirectional_crpc**(`self`) — Line 195, Complexity: 1
- **test_enrich_bidirectional_iea**(`self`) — Line 201, Complexity: 1
- **test_enrich_no_duplicates**(`self`) — Line 207, Complexity: 1
- **test_enrich_preserves_other_acts**(`self`) — Line 211, Complexity: 1
- **test_enrich_empty_list**(`self`) — Line 215, Complexity: 1
- **test_normalize_act_filter_full_name**(`self`) — Line 222, Complexity: 1
- **test_normalize_act_filter_already_short**(`self`) — Line 228, Complexity: 1
- **test_normalize_act_filter_with_year**(`self`) — Line 233, Complexity: 1
- **test_normalize_act_filter_case_insensitive**(`self`) — Line 238, Complexity: 1
- **test_normalize_act_filter_unknown_passthrough**(`self`) — Line 243, Complexity: 1
- **test_known_act_with_year**(`self`) — Line 251, Complexity: 1
- **test_known_act_without_year**(`self`) — Line 256, Complexity: 1
- **test_unknown_code_passthrough**(`self`) — Line 261, Complexity: 1
- **test_case_insensitive**(`self`) — Line 265, Complexity: 1
- **test_new_criminal_codes**(`self`) — Line 268, Complexity: 1
- **test_display_list**(`self`) — Line 273, Complexity: 1
- **test_display_list_empty**(`self`) — Line 280, Complexity: 1
- **test_display_list_none**(`self`) — Line 283, Complexity: 1
- **test_full_pipeline_normalization**(`self`) — Line 295, Complexity: 1
- **test_display_name_roundtrip**(`self`) — Line 330, Complexity: 2
- **test_section_refs_never_stored**(`self`) — Line 347, Complexity: 2
- **test_order_rule_filtered**(`self`) — Line 366, Complexity: 2
- **test_health_check_query_syntax**(`self`) — Line 380, Complexity: 1

### `backend\tests\unit\test_admin_routes.py`
- **_make_app**(`0 args`) — Line 37, Complexity: 2
- **_mock_db_for_mappings**(`rows`) — Line 47, Complexity: 1
- **_make_client**(`self, db`) — Line 68, Complexity: 1
- **test_list_review_queue_returns_items**(`self`) — Line 73, Complexity: 1
- **test_list_review_queue_empty**(`self`) — Line 95, Complexity: 1
- **test_approve_case**(`self`) — Line 107, Complexity: 1
- **test_approve_nonexistent_case**(`self`) — Line 118, Complexity: 1
- **test_reject_case**(`self`) — Line 128, Complexity: 1
- **_make_client**(`self, db`) — Line 146, Complexity: 1
- **test_correct_scalar_field**(`self`) — Line 151, Complexity: 1
- **test_correct_invalid_field_rejected**(`self`) — Line 184, Complexity: 1
- **test_correct_nonexistent_case**(`self`) — Line 198, Complexity: 1
- **test_correction_history**(`self`) — Line 217, Complexity: 1
- **test_array_field_requires_list**(`self`) — Line 243, Complexity: 1
- **test_sql_injection_in_field_name_rejected**(`self, malicious_field`) — Line 263, Complexity: 1
- **_make_client**(`self, db`) — Line 287, Complexity: 1
- **test_dashboard_with_data**(`self`) — Line 292, Complexity: 1
- **test_dashboard_empty_database**(`self`) — Line 347, Complexity: 1
- **test_compare_scalar_match**(`self`) — Line 371, Complexity: 1
- **test_compare_scalar_mismatch**(`self`) — Line 381, Complexity: 1
- **test_compare_scalar_none_gold**(`self`) — Line 388, Complexity: 1
- **test_compare_list_overlap**(`self`) — Line 394, Complexity: 1
- **test_evaluate_case_tracks_metrics**(`self`) — Line 405, Complexity: 1

### `backend\tests\unit\test_agent_execution_model.py`
- **test_enum_values**(`self`) — Line 9, Complexity: 1
- **test_enum_members**(`self`) — Line 13, Complexity: 1
- **test_enum_values**(`self`) — Line 23, Complexity: 1
- **test_enum_members**(`self`) — Line 30, Complexity: 1
- **test_table_name**(`self`) — Line 41, Complexity: 1
- **test_has_required_columns**(`self`) — Line 44, Complexity: 1
- **test_agent_type_check_constraint**(`self`) — Line 64, Complexity: 2
- **test_status_check_constraint**(`self`) — Line 74, Complexity: 3
- **test_repr**(`self`) — Line 84, Complexity: 1

### `backend\tests\unit\test_agent_graph_execution.py`
- **test_route_after_plan_no_feedback_goes_to_search**(`self`) — Line 31, Complexity: 1
- **test_route_after_plan_with_feedback_loops_back**(`self`) — Line 47, Complexity: 1
- **test_route_after_plan_max_iterations_goes_to_dispatch**(`self`) — Line 65, Complexity: 1
- **test_route_after_findings_no_feedback_goes_to_synthesize**(`self`) — Line 85, Complexity: 1
- **test_route_after_memo_no_feedback_goes_to_end**(`self`) — Line 101, Complexity: 1
- **test_route_after_memo_with_feedback_loops**(`self`) — Line 117, Complexity: 1
- **_base_state**(`self`) — Line 144, Complexity: 1
- **test_route_after_load_no_error_goes_to_prioritize**(`self`) — Line 158, Complexity: 1
- **test_route_after_load_with_error_goes_to_end**(`self`) — Line 162, Complexity: 1
- **test_route_after_issues_no_feedback_goes_to_deep_search**(`self`) — Line 166, Complexity: 1
- **test_route_after_issues_with_feedback_loops**(`self`) — Line 170, Complexity: 1
- **test_route_after_strategy_no_feedback**(`self`) — Line 179, Complexity: 1
- **test_cp_route_after_memo_no_feedback**(`self`) — Line 183, Complexity: 1
- **test_research_graph_compiles**(`self`) — Line 196, Complexity: 2
- **test_case_prep_graph_compiles**(`self`) — Line 213, Complexity: 2

### `backend\tests\unit\test_agent_nodes_common.py`
- **test_empty_results_returns_no_results_message**(`self`) — Line 21, Complexity: 1
- **test_single_result_formatted_correctly**(`self`) — Line 24, Complexity: 1
- **test_multiple_results_numbered**(`self`) — Line 42, Complexity: 1
- **test_snippet_truncated_to_max_len**(`self`) — Line 52, Complexity: 1
- **test_missing_fields_use_defaults**(`self`) — Line 60, Complexity: 1
- **test_none_snippet_handled**(`self`) — Line 67, Complexity: 1
- **test_includes_ratio_field**(`self`) — Line 79, Complexity: 1
- **test_includes_bench_type**(`self`) — Line 94, Complexity: 1
- **test_no_ratio_still_works**(`self`) — Line 109, Complexity: 1
- **test_enriches_results_with_ratio**(`self`) — Line 132, Complexity: 1
- **test_enriches_bench_type**(`self`) — Line 148, Complexity: 1
- **test_empty_results_returns_empty**(`self`) — Line 163, Complexity: 1
- **test_empty_list_returns_empty_set**(`self`) — Line 177, Complexity: 1
- **test_returns_existing_ids**(`self`) — Line 184, Complexity: 1
- **test_no_matches_returns_empty_set**(`self`) — Line 195, Complexity: 1
- **test_extracts_section_ipc**(`self`) — Line 211, Complexity: 1
- **test_extracts_section_bns**(`self`) — Line 217, Complexity: 1
- **test_extracts_article**(`self`) — Line 223, Complexity: 1
- **test_extracts_multiple**(`self`) — Line 229, Complexity: 1
- **test_no_refs_returns_empty**(`self`) — Line 239, Complexity: 1
- **test_case_insensitive**(`self`) — Line 245, Complexity: 1
- **test_expands_old_to_new**(`self`) — Line 258, Complexity: 1
- **test_expands_new_to_old**(`self`) — Line 266, Complexity: 1
- **test_no_mapping_returns_original**(`self`) — Line 274, Complexity: 1
- **test_crpc_to_bnss**(`self`) — Line 282, Complexity: 1
- **test_extracts_and_fetches_statutes**(`self`) — Line 299, Complexity: 1
- **test_empty_query_no_refs**(`self`) — Line 334, Complexity: 1
- **test_semantic_results_merged**(`self`) — Line 360, Complexity: 2
- **test_returns_elements_from_llm**(`self`) — Line 407, Complexity: 1
- **test_fallback_on_llm_error**(`self`) — Line 451, Complexity: 1
- **test_includes_statute_text_in_prompt**(`self`) — Line 470, Complexity: 1

### `backend\tests\unit\test_agent_prompts.py`
- **test_system_prompts_are_nonempty_strings**(`self, prompt`) — Line 52, Complexity: 1
- **test_user_prompts_are_nonempty_strings**(`self, prompt`) — Line 67, Complexity: 1
- **test_decompose_user_has_placeholders**(`self`) — Line 71, Complexity: 1
- **test_synthesize_user_has_placeholders**(`self`) — Line 75, Complexity: 1
- **test_system_prompts_are_nonempty_strings**(`self, prompt`) — Line 105, Complexity: 1
- **test_user_prompts_are_nonempty_strings**(`self, prompt`) — Line 120, Complexity: 1
- **test_prioritize_user_has_placeholders**(`self`) — Line 124, Complexity: 1
- **test_strategy_user_has_placeholders**(`self`) — Line 129, Complexity: 1
- **test_schema_is_valid_object_type**(`self, schema`) — Line 156, Complexity: 1
- **test_classify_schema_has_expected_fields**(`self`) — Line 164, Complexity: 1
- **test_classify_schema_topic_enum**(`self`) — Line 172, Complexity: 1
- **test_classify_schema_complexity_enum**(`self`) — Line 179, Complexity: 1
- **test_classify_schema_jurisdiction_nullable**(`self`) — Line 184, Complexity: 1
- **test_decompose_schema_has_sub_queries**(`self`) — Line 190, Complexity: 1
- **test_chat_system_has_anti_sycophancy**(`self`) — Line 207, Complexity: 3
- **test_chat_system_has_bench_strength**(`self`) — Line 213, Complexity: 1
- **test_chat_system_has_anti_supplementation_rule**(`self`) — Line 218, Complexity: 1
- **test_research_synthesize_has_precedent_strength**(`self`) — Line 223, Complexity: 2
- **test_case_prep_has_time_bar_check**(`self`) — Line 228, Complexity: 2
- **test_element_decomposition_prompt_exists**(`self`) — Line 237, Complexity: 2
- **test_element_decomposition_schema_valid**(`self`) — Line 243, Complexity: 1
- **test_adversarial_search_prompt_exists**(`self`) — Line 250, Complexity: 2
- **test_adversarial_search_schema_valid**(`self`) — Line 256, Complexity: 1
- **test_classify_schema_has_procedural_context**(`self`) — Line 267, Complexity: 1
- **test_evaluate_extract_has_bench_and_obiter**(`self`) — Line 272, Complexity: 1
- **test_merge_has_risk_assessment**(`self`) — Line 279, Complexity: 1
- **test_quality_check_has_temporal_and_bench**(`self`) — Line 284, Complexity: 1
- **test_plan_has_element_context**(`self`) — Line 291, Complexity: 2
- **test_has_ik_inline_filters**(`self`) — Line 301, Complexity: 2
- **test_has_aggregator_doctypes**(`self`) — Line 306, Complexity: 2
- **test_schema_has_new_filter_properties**(`self`) — Line 311, Complexity: 2

### `backend\tests\unit\test_agent_routes.py`
- **_make_token**(`user_id`) — Line 28, Complexity: 1
- **_make_execution**(`user_id, status, agent_type`) — Line 39, Complexity: 1
- **app**(`0 args`) — Line 64, Complexity: 1
- **authed_client**(`app`) — Line 71, Complexity: 1
- **unauthed_client**(`app`) — Line 83, Complexity: 1
- **_override_user**(`0 args`) — Line 74, Complexity: 1
- **test_routes_registered**(`self`) — Line 94, Complexity: 1
- **test_run_is_post**(`self`) — Line 101, Complexity: 4
- **test_list_executions_is_get**(`self`) — Line 106, Complexity: 5
- **test_resume_is_post**(`self`) — Line 117, Complexity: 4
- **test_cancel_is_delete**(`self`) — Line 125, Complexity: 5
- **test_invalid_agent_type_returns_422**(`self, authed_client`) — Line 144, Complexity: 1
- **test_missing_auth_returns_401**(`self, unauthed_client`) — Line 158, Complexity: 1
- **test_returns_empty_list_for_new_user**(`self, authed_client`) — Line 172, Complexity: 1
- **test_returns_404_for_nonexistent**(`self, authed_client`) — Line 208, Complexity: 1
- **test_returns_403_for_other_user**(`self, authed_client`) — Line 225, Complexity: 1
- **test_returns_execution_detail**(`self, authed_client`) — Line 244, Complexity: 1
- **test_cancel_updates_status**(`self, authed_client`) — Line 273, Complexity: 1
- **test_cancel_already_completed_returns_400**(`self, authed_client`) — Line 297, Complexity: 1
- **test_cancel_returns_404_for_nonexistent**(`self, authed_client`) — Line 320, Complexity: 1
- **test_resume_returns_400_when_not_waiting**(`self, authed_client`) — Line 346, Complexity: 1
- **test_get_checkpointer_returns_singleton**(`self`) — Line 370, Complexity: 1
- **test_resume_returns_404_for_nonexistent**(`self, authed_client`) — Line 379, Complexity: 1
- **_override_db**(`0 args`) — Line 147, Complexity: 1
- **_override_db**(`0 args`) — Line 187, Complexity: 1
- **_override_db**(`0 args`) — Line 214, Complexity: 1
- **_override_db**(`0 args`) — Line 232, Complexity: 1
- **_override_db**(`0 args`) — Line 251, Complexity: 1
- **_override_db**(`0 args`) — Line 283, Complexity: 1
- **_override_db**(`0 args`) — Line 308, Complexity: 1
- **_override_db**(`0 args`) — Line 328, Complexity: 1
- **_override_db**(`0 args`) — Line 357, Complexity: 1
- **_override_db**(`0 args`) — Line 387, Complexity: 1

### `backend\tests\unit\test_agent_session_routes.py`
- **_token**(`user_id, role`) — Line 31, Complexity: 1
- **_mock_db**(`0 args`) — Line 45, Complexity: 1
- **_mock_mapping_result**(`rows, single`) — Line 49, Complexity: 3
- **_scalar_one_result**(`value`) — Line 66, Complexity: 1
- **_one_or_none_result**(`row`) — Line 72, Complexity: 1
- **app**(`0 args`) — Line 85, Complexity: 1
- **mock_db**(`0 args`) — Line 92, Complexity: 1
- **client_a**(`app, mock_db`) — Line 97, Complexity: 1
- **client_b**(`app, mock_db`) — Line 109, Complexity: 1
- **_patch_rate_limiter**(`0 args`) — Line 140, Complexity: 1
- **_patch_providers**(`0 args`) — Line 153, Complexity: 8
- **_override_db**(`0 args`) — Line 99, Complexity: 1
- **_override_db**(`0 args`) — Line 111, Complexity: 1
- **_noop**(`0 args`) — Line 142, Complexity: 1
- **test_create_session_returns_sse_stream**(`self, mock_llm, mock_flash, mock_embedder, mock_vector, mock_reranker, mock_graph_store, mock_checkpointer, mock_ik, mock_web, mock_redis, mock_encrypt, mock_audit, client_a, mock_db`) — Line 201, Complexity: 1
- **test_create_session_invalid_agent_type**(`self, client_a`) — Line 238, Complexity: 1
- **test_create_session_no_body**(`self, client_a`) — Line 249, Complexity: 1
- **test_create_session_short_query**(`self, client_a`) — Line 257, Complexity: 1
- **test_create_session_prompt_injection_blocked**(`self, mock_detect, client_a`) — Line 269, Complexity: 1
- **test_follow_up_returns_sse**(`self, mock_sanitize, mock_detect, mock_checkpointer, mock_llm, mock_flash, mock_embedder, mock_vector, mock_reranker, mock_redis, mock_decrypt, mock_encrypt, mock_audit, client_a, mock_db`) — Line 303, Complexity: 1
- **test_follow_up_invalid_session_id**(`self, client_a`) — Line 359, Complexity: 1
- **test_follow_up_session_not_found**(`self, client_a, mock_db`) — Line 371, Complexity: 1
- **test_follow_up_concurrent_execution_409**(`self, mock_sanitize, mock_detect, client_a, mock_db`) — Line 387, Complexity: 1
- **test_follow_up_no_completed_execution_400**(`self, mock_sanitize, mock_detect, client_a, mock_db`) — Line 412, Complexity: 1
- **test_follow_up_short_message**(`self, client_a`) — Line 435, Complexity: 1
- **test_follow_up_prompt_injection_blocked**(`self, mock_detect, client_a, mock_db`) — Line 447, Complexity: 1
- **test_list_sessions_empty**(`self, client_a, mock_db`) — Line 476, Complexity: 1
- **test_list_sessions_with_results**(`self, client_a, mock_db`) — Line 494, Complexity: 1
- **test_list_sessions_filter_by_agent_type**(`self, client_a, mock_db`) — Line 527, Complexity: 1
- **test_list_sessions_pagination**(`self, client_a, mock_db`) — Line 541, Complexity: 1
- **test_get_session_detail**(`self, client_a, mock_db`) — Line 568, Complexity: 1
- **test_get_session_not_found**(`self, client_a, mock_db`) — Line 606, Complexity: 1
- **test_get_session_invalid_uuid**(`self, client_a`) — Line 617, Complexity: 1
- **test_get_messages**(`self, mock_decrypt, client_a, mock_db`) — Line 635, Complexity: 1
- **test_get_messages_not_found**(`self, client_a, mock_db`) — Line 678, Complexity: 1
- **test_delete_session**(`self, mock_audit, client_a, mock_db`) — Line 699, Complexity: 1
- **test_delete_session_not_found**(`self, client_a, mock_db`) — Line 722, Complexity: 1
- **test_delete_session_invalid_uuid**(`self, client_a`) — Line 733, Complexity: 1
- **test_get_session_idor_blocked**(`self, client_b, mock_db`) — Line 750, Complexity: 1
- **test_get_messages_idor_blocked**(`self, client_b, mock_db`) — Line 771, Complexity: 1
- **test_delete_session_idor_blocked**(`self, client_b, mock_db`) — Line 783, Complexity: 1
- **test_follow_up_idor_blocked**(`self, mock_sanitize, mock_detect, client_b, mock_db`) — Line 797, Complexity: 1
- **test_list_sessions_only_returns_own**(`self, client_a, mock_db`) — Line 815, Complexity: 1
- **test_session_routes_registered**(`self`) — Line 844, Complexity: 1
- **test_create_session_is_post**(`self`) — Line 852, Complexity: 4
- **test_follow_up_is_post**(`self`) — Line 857, Complexity: 4
- **test_list_sessions_is_get**(`self`) — Line 862, Complexity: 4
- **test_delete_session_is_delete**(`self`) — Line 867, Complexity: 5
- **_noop**(`0 args`) — Line 169, Complexity: 1

### `backend\tests\unit\test_agent_state.py`
- **test_can_create_state**(`self`) — Line 12, Complexity: 1
- **test_search_results_uses_replace_semantics**(`self`) — Line 27, Complexity: 1
- **test_has_required_fields**(`self`) — Line 37, Complexity: 1
- **test_has_required_fields**(`self`) — Line 53, Complexity: 1
- **test_has_required_fields**(`self`) — Line 66, Complexity: 1
- **test_research_state_has_v3_fields**(`self`) — Line 79, Complexity: 1
- **test_can_create_state**(`self`) — Line 91, Complexity: 1

### `backend\tests\unit\test_amendment_service.py`
- **test_empty_entries**(`self`) — Line 19, Complexity: 1
- **test_single_entry**(`self`) — Line 25, Complexity: 1
- **test_multiple_entries_same_act**(`self`) — Line 41, Complexity: 1
- **test_cross_act_mappings**(`self`) — Line 65, Complexity: 1
- **test_returns_non_empty_dicts**(`self`) — Line 94, Complexity: 1
- **test_ipc_302_to_bns_103**(`self`) — Line 100, Complexity: 1
- **test_bns_103_to_ipc_302**(`self`) — Line 105, Complexity: 1
- **test_crpc_438_to_bnss**(`self`) — Line 110, Complexity: 1
- **test_iea_to_bsa**(`self`) — Line 115, Complexity: 1
- **test_consistency_with_centralized_lookups**(`self`) — Line 121, Complexity: 1

### `backend\tests\unit\test_anonymizer.py`
- **test_masks_aadhaar_number**(`self`) — Line 12, Complexity: 1
- **test_masks_aadhaar_without_spaces**(`self`) — Line 19, Complexity: 1
- **test_masks_pan_number**(`self`) — Line 25, Complexity: 1
- **test_masks_mobile_number_with_prefix**(`self`) — Line 32, Complexity: 1
- **test_masks_mobile_number_bare**(`self`) — Line 39, Complexity: 1
- **test_no_modification_when_clean**(`self`) — Line 45, Complexity: 1
- **test_masks_multiple_pii_types**(`self`) — Line 51, Complexity: 1
- **test_preserves_section_numbers**(`self`) — Line 59, Complexity: 1
- **test_preserves_year_numbers**(`self`) — Line 66, Complexity: 1
- **test_phone_with_91_prefix_not_masked_as_aadhaar**(`self`) — Line 72, Complexity: 1
- **test_pan_false_positive_legal_strings**(`self`) — Line 80, Complexity: 1
- **test_bare_phone_in_continuous_digits_no_match**(`self`) — Line 88, Complexity: 2
- **test_detects_pocso_in_acts_cited**(`self`) — Line 99, Complexity: 1
- **test_detects_pocso_short_name**(`self`) — Line 105, Complexity: 1
- **test_detects_ipc_376_sexual_offence**(`self`) — Line 109, Complexity: 1
- **test_detects_bns_equivalent_sexual_offence**(`self`) — Line 116, Complexity: 1
- **test_detects_keyword_prosecutrix**(`self`) — Line 123, Complexity: 1
- **test_detects_keyword_minor_victim**(`self`) — Line 128, Complexity: 1
- **test_detects_identity_disclosure_phrase**(`self`) — Line 133, Complexity: 1
- **test_not_sensitive_civil_case**(`self`) — Line 138, Complexity: 1
- **test_not_sensitive_empty_metadata**(`self`) — Line 145, Complexity: 1

### `backend\tests\unit\test_audio_routes.py`
- **test_routes_registered**(`self`) — Line 14, Complexity: 1
- **test_generate_is_post**(`self`) — Line 20, Complexity: 4
- **test_status_is_get**(`self`) — Line 25, Complexity: 4
- **test_stream_is_get**(`self`) — Line 30, Complexity: 4
- **test_chunked_yields_multiple_chunks**(`self, tmp_path`) — Line 39, Complexity: 1
- **test_chunked_file_not_found**(`self, tmp_path`) — Line 64, Complexity: 1
- **test_chunked_small_file_single_chunk**(`self, tmp_path`) — Line 79, Complexity: 1
- **collect_chunks**(`0 args`) — Line 54, Complexity: 1
- **attempt_read**(`0 args`) — Line 72, Complexity: 1
- **collect_chunks**(`0 args`) — Line 93, Complexity: 1

### `backend\tests\unit\test_audio_tasks.py`
- **test_returns_mock_when_no_api_key**(`self, mock_settings`) — Line 11, Complexity: 1
- **test_returns_mock_when_sarvam_no_key**(`self, mock_settings`) — Line 18, Complexity: 1

### `backend\tests\unit\test_audit_logging.py`
- **test_inserts_log_entry**(`self`) — Line 17, Complexity: 1
- **test_handles_none_metadata**(`self`) — Line 36, Complexity: 1
- **test_handles_none_ip_address**(`self`) — Line 56, Complexity: 1
- **test_ip_address_is_hashed**(`self`) — Line 75, Complexity: 1
- **test_metadata_serialized_as_json**(`self`) — Line 99, Complexity: 1

### `backend\tests\unit\test_auth.py`
- **mock_settings**(`0 args`) — Line 35, Complexity: 2
- **mock_redis**(`0 args`) — Line 44, Complexity: 1
- **test_create_and_verify**(`self`) — Line 57, Complexity: 1
- **test_custom_expiry**(`self`) — Line 65, Complexity: 1
- **test_expired_token_raises**(`self`) — Line 71, Complexity: 1
- **test_invalid_token_raises**(`self`) — Line 77, Complexity: 1
- **test_refresh_token_rejected_as_access**(`self`) — Line 82, Complexity: 1
- **test_create_and_verify**(`self`) — Line 92, Complexity: 1
- **test_access_token_rejected_as_refresh**(`self`) — Line 98, Complexity: 1
- **test_revoke_token_blocks_verification**(`self, mock_redis`) — Line 108, Complexity: 1
- **test_revoke_refresh_token**(`self, mock_redis`) — Line 118, Complexity: 1
- **test_is_token_revoked**(`self, mock_redis`) — Line 127, Complexity: 1
- **test_unrevoked_token_still_works**(`self, mock_redis`) — Line 134, Complexity: 1
- **test_clear_revoked_tokens_is_noop**(`self`) — Line 140, Complexity: 1
- **test_hash_and_verify**(`self`) — Line 148, Complexity: 1
- **test_wrong_password_fails**(`self`) — Line 152, Complexity: 1
- **test_hash_is_not_plaintext**(`self`) — Line 156, Complexity: 1
- **test_different_hashes_for_same_password**(`self`) — Line 161, Complexity: 1

### `backend\tests\unit\test_auth_routes.py`
- **_mock_db_session**(`0 args`) — Line 32, Complexity: 1
- **_user_row**(`0 args`) — Line 37, Complexity: 1
- **app**(`0 args`) — Line 63, Complexity: 1
- **mock_db**(`0 args`) — Line 87, Complexity: 1
- **client**(`app, mock_db`) — Line 93, Complexity: 1
- **_auth_err**(`request, exc`) — Line 69, Complexity: 1
- **_rate_err**(`request, exc`) — Line 76, Complexity: 1
- **_override_db**(`0 args`) — Line 96, Complexity: 1
- **test_register_returns_201**(`self, mock_hash, mock_access, mock_refresh, client, mock_db`) — Line 115, Complexity: 1
- **test_register_duplicate_email_returns_409**(`self, client, mock_db`) — Line 155, Complexity: 1
- **test_register_invalid_email_returns_422**(`self, client`) — Line 178, Complexity: 1
- **test_register_short_password_returns_422**(`self, client`) — Line 194, Complexity: 1
- **test_register_without_consent_returns_400**(`self, client`) — Line 210, Complexity: 1
- **test_login_returns_tokens**(`self, mock_get_limiter, mock_verify, mock_access, mock_refresh, mock_audit, client, mock_db`) — Line 241, Complexity: 1
- **test_login_wrong_password_returns_401**(`self, mock_get_limiter, mock_verify, mock_audit, client, mock_db`) — Line 281, Complexity: 1
- **test_login_nonexistent_user_returns_401**(`self, mock_get_limiter, client, mock_db`) — Line 311, Complexity: 1
- **test_login_rate_limited**(`self, mock_get_limiter, app, mock_db`) — Line 338, Complexity: 1
- **test_refresh_returns_new_access_token**(`self, mock_verify_refresh, mock_access, mock_refresh, mock_audit, mock_revoke, client, mock_db`) — Line 379, Complexity: 1
- **test_refresh_invalid_token_returns_401**(`self, mock_verify_refresh, client`) — Line 419, Complexity: 1
- **test_logout_revokes_token**(`self, mock_revoke, app`) — Line 445, Complexity: 1
- **test_logout_without_token_returns_401**(`self, client`) — Line 470, Complexity: 1
- **test_auth_routes_registered**(`self`) — Line 489, Complexity: 1
- **test_register_is_post**(`self`) — Line 496, Complexity: 4
- **test_login_is_post**(`self`) — Line 501, Complexity: 4
- **test_failed_login_increments_count**(`self, mock_get_limiter, mock_verify, mock_audit, client, mock_db`) — Line 518, Complexity: 1
- **test_locked_account_returns_423**(`self, mock_get_limiter, client, mock_db`) — Line 551, Complexity: 1
- **test_inactive_user_login_returns_403**(`self, mock_get_limiter, mock_verify, client, mock_db`) — Line 592, Complexity: 1
- **test_inactive_user_refresh_returns_401**(`self, mock_verify_refresh, client, mock_db`) — Line 619, Complexity: 2
- **_override_db**(`0 args`) — Line 350, Complexity: 1

### `backend\tests\unit\test_batch_llm.py`
- **sample_result**(`self`) — Line 12, Complexity: 1
- **llm**(`self, sample_result`) — Line 24, Complexity: 1
- **test_generate_structured_from_pdf_returns_cached**(`self, llm, sample_result`) — Line 28, Complexity: 1
- **test_generate_structured_returns_cached**(`self, llm, sample_result`) — Line 38, Complexity: 1
- **test_generate_raises_not_implemented**(`self, llm`) — Line 47, Complexity: 1
- **test_stream_raises_not_implemented**(`self, llm`) — Line 52, Complexity: 1
- **test_has_generate_structured_from_pdf_attribute**(`self, llm`) — Line 57, Complexity: 1
- **test_empty_result_passes_through**(`self`) — Line 63, Complexity: 1

### `backend\tests\unit\test_batch_state.py`
- **db**(`self, tmp_path`) — Line 12, Complexity: 1
- **test_insert_doc**(`self, db`) — Line 15, Complexity: 1
- **test_insert_doc_idempotent**(`self, db`) — Line 31, Complexity: 1
- **test_update_status**(`self, db`) — Line 38, Complexity: 1
- **test_store_result**(`self, db`) — Line 45, Complexity: 1
- **test_mark_error**(`self, db`) — Line 53, Complexity: 1
- **test_get_docs_by_status**(`self, db`) — Line 60, Complexity: 1
- **test_insert_job**(`self, db`) — Line 68, Complexity: 1
- **test_update_job_status**(`self, db`) — Line 74, Complexity: 1
- **test_get_pending_jobs**(`self, db`) — Line 81, Complexity: 1
- **test_get_docs_for_year**(`self, db`) — Line 89, Complexity: 1

### `backend\tests\unit\test_bulk_upsert.py`
- **test_batch_executes_once_per_batch_not_per_row**(`self`) — Line 11, Complexity: 1
- **test_returns_pre_generated_ids**(`self`) — Line 29, Complexity: 1

### `backend\tests\unit\test_case_model_v2.py`
- **test_column_exists**(`self, col`) — Line 20, Complexity: 1

### `backend\tests\unit\test_case_prep_agent.py`
- **_base_state**(`0 args`) — Line 21, Complexity: 1
- **_build_graph**(`0 args`) — Line 36, Complexity: 1
- **test_build_case_prep_graph_returns_compiled**(`self`) — Line 66, Complexity: 1
- **test_graph_has_expected_nodes**(`self`) — Line 71, Complexity: 2
- **test_initial_state_structure**(`self`) — Line 77, Complexity: 1
- **test_continues_without_feedback**(`self`) — Line 91, Complexity: 1
- **test_continues_with_empty_feedback**(`self`) — Line 95, Complexity: 1
- **test_loops_with_feedback**(`self`) — Line 101, Complexity: 1
- **test_loops_with_feedback_iteration_2**(`self`) — Line 110, Complexity: 1
- **test_stops_at_max_iterations**(`self`) — Line 119, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 130, Complexity: 1
- **test_continues_without_feedback**(`self`) — Line 146, Complexity: 1
- **test_continues_with_empty_feedback**(`self`) — Line 150, Complexity: 1
- **test_loops_with_feedback**(`self`) — Line 158, Complexity: 1
- **test_stops_at_max_iterations**(`self`) — Line 171, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 182, Complexity: 1
- **test_continues_without_feedback**(`self`) — Line 198, Complexity: 1
- **test_continues_with_empty_feedback**(`self`) — Line 202, Complexity: 1
- **test_loops_with_feedback**(`self`) — Line 210, Complexity: 1
- **test_stops_at_max_iterations**(`self`) — Line 223, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 234, Complexity: 1

### `backend\tests\unit\test_case_prep_nodes.py`
- **_make_state**(`0 args`) — Line 26, Complexity: 1
- **_make_llm**(`0 args`) — Line 42, Complexity: 2
- **_make_db_with_analysis_row**(`row_dict`) — Line 52, Complexity: 1
- **_make_db_no_results**(`0 args`) — Line 65, Complexity: 1
- **test_loads_analysis_from_db**(`self`) — Line 85, Complexity: 1
- **test_returns_error_when_not_found**(`self`) — Line 108, Complexity: 1
- **test_no_error_key_when_analysis_exists**(`self`) — Line 128, Complexity: 1
- **test_handles_dict_fields_already_parsed**(`self`) — Line 147, Complexity: 1
- **test_returns_prioritized_issues_sorted**(`self`) — Line 171, Complexity: 1
- **test_empty_issues_returns_empty**(`self`) — Line 218, Complexity: 1
- **test_passes_prompt_with_issues**(`self`) — Line 227, Complexity: 1
- **test_searches_top_3_issues**(`self`) — Line 251, Complexity: 1
- **test_empty_prioritized_issues**(`self`) — Line 307, Complexity: 1
- **test_merges_graph_neighbors**(`self`) — Line 315, Complexity: 1
- **test_graph_neighbor_metadata_extracted_correctly**(`self`) — Line 376, Complexity: 1
- **test_returns_ordered_arguments**(`self`) — Line 457, Complexity: 1
- **test_fallback_when_llm_returns_unparseable**(`self`) — Line 492, Complexity: 1
- **test_empty_prioritized_issues_and_unparseable**(`self`) — Line 511, Complexity: 1
- **test_generates_memo**(`self`) — Line 528, Complexity: 1
- **test_handles_missing_analysis_fields**(`self`) — Line 549, Complexity: 1
- **test_passes_precedent_findings_to_prompt**(`self`) — Line 559, Complexity: 1
- **test_no_uuids_returns_unchanged_memo**(`self`) — Line 584, Complexity: 1
- **test_valid_uuids_no_warning**(`self`) — Line 591, Complexity: 1
- **test_invalid_uuids_appends_warning**(`self`) — Line 604, Complexity: 1
- **test_empty_memo_returns_empty**(`self`) — Line 618, Complexity: 1
- **test_human_citation_unverified_appends_warning**(`self`) — Line 625, Complexity: 1
- **test_human_citation_verified_no_warning**(`self`) — Line 641, Complexity: 1
- **test_ungrounded_citation_appends_warning**(`self`) — Line 661, Complexity: 1
- **test_grounded_citation_no_ungrounded_warning**(`self`) — Line 682, Complexity: 1
- **test_valid_json_array**(`self`) — Line 708, Complexity: 1
- **test_json_in_code_fence**(`self`) — Line 711, Complexity: 1
- **test_empty_array**(`self`) — Line 715, Complexity: 1
- **test_garbage_returns_empty**(`self`) — Line 718, Complexity: 1
- **test_routes_to_end_when_error_set**(`self`) — Line 728, Complexity: 1
- **test_routes_to_prioritize_when_no_error**(`self`) — Line 733, Complexity: 1
- **test_routes_to_prioritize_when_error_is_empty_string**(`self`) — Line 738, Complexity: 1
- **test_prioritize_adds_score_note**(`self`) — Line 753, Complexity: 2
- **test_deep_search_updates_score_note_no_results**(`self`) — Line 780, Complexity: 1
- **test_deep_search_boosts_legal_strength_with_binding**(`self`) — Line 799, Complexity: 1
- **test_deep_search_partial_validation**(`self`) — Line 854, Complexity: 1
- **test_deep_search_limited_validation**(`self`) — Line 908, Complexity: 1
- **test_deep_search_returns_prioritized_issues_in_result**(`self`) — Line 959, Complexity: 1

### `backend\tests\unit\test_case_routes.py`
- **_make_case_row**(`case_id`) — Line 27, Complexity: 1
- **_make_summary_row**(`case_id, title`) — Line 62, Complexity: 1
- **_mock_db_execute**(`rows`) — Line 74, Complexity: 2
- **_mock_db_multi_execute**(`results`) — Line 96, Complexity: 5
- **app**(`0 args`) — Line 126, Complexity: 1
- **client**(`app`) — Line 133, Complexity: 1
- **test_all_case_endpoints_present**(`self`) — Line 143, Complexity: 1
- **test_all_endpoints_are_get**(`self`) — Line 151, Complexity: 3
- **test_get_case_returns_full_detail**(`self, app, client`) — Line 163, Complexity: 1
- **test_get_case_not_found_returns_404**(`self, app, client`) — Line 198, Complexity: 1
- **test_get_case_empty_full_text_returns_empty_sections**(`self, app, client`) — Line 214, Complexity: 1
- **test_get_citations_returns_cited_cases**(`self, mock_get_graph, app, client`) — Line 241, Complexity: 1
- **test_get_citations_case_not_found**(`self, app, client`) — Line 283, Complexity: 1
- **test_get_cited_by_returns_citing_cases**(`self, mock_get_graph, app, client`) — Line 306, Complexity: 1
- **test_get_cited_by_case_not_found**(`self, app, client`) — Line 346, Complexity: 1
- **test_get_similar_cases**(`self, mock_get_embedder, mock_get_vector, app, client`) — Line 370, Complexity: 1
- **test_get_similar_case_not_found**(`self, app, client`) — Line 420, Complexity: 1
- **test_get_similar_no_ratio_returns_empty**(`self, mock_get_embedder, mock_get_vector, app, client`) — Line 437, Complexity: 1
- **test_get_pdf_returns_file**(`self, mock_get_storage, app, client`) — Line 474, Complexity: 1
- **test_get_pdf_case_not_found**(`self, app, client`) — Line 503, Complexity: 1
- **test_get_pdf_no_pdf_path_returns_404**(`self, app, client`) — Line 518, Complexity: 1
- **test_get_pdf_storage_error_returns_404**(`self, mock_get_storage, app, client`) — Line 537, Complexity: 1
- **_override_db**(`0 args`) — Line 168, Complexity: 1
- **_override_db**(`0 args`) — Line 202, Complexity: 1
- **_override_db**(`0 args`) — Line 222, Complexity: 1
- **_override_db**(`0 args`) — Line 251, Complexity: 1
- **_override_db**(`0 args`) — Line 287, Complexity: 1
- **_override_db**(`0 args`) — Line 315, Complexity: 1
- **_override_db**(`0 args`) — Line 350, Complexity: 1
- **_override_db**(`0 args`) — Line 386, Complexity: 1
- **_override_db**(`0 args`) — Line 424, Complexity: 1
- **_override_db**(`0 args`) — Line 449, Complexity: 1
- **_override_db**(`0 args`) — Line 483, Complexity: 1
- **_override_db**(`0 args`) — Line 507, Complexity: 1
- **_override_db**(`0 args`) — Line 525, Complexity: 1
- **_override_db**(`0 args`) — Line 546, Complexity: 1

### `backend\tests\unit\test_case_section_model.py`
- **test_model_has_required_fields**(`self`) — Line 7, Complexity: 1
- **test_table_name**(`self`) — Line 16, Complexity: 1
- **test_section_types**(`self`) — Line 19, Complexity: 2
- **test_summary_is_optional**(`self`) — Line 30, Complexity: 1

### `backend\tests\unit\test_celery_config.py`
- **test_celery_app_exists**(`self`) — Line 7, Complexity: 1
- **test_celery_serializer_config**(`self`) — Line 11, Complexity: 1
- **test_celery_broker_configured**(`self`) — Line 15, Complexity: 2
- **test_celery_task_acks_late**(`self`) — Line 19, Complexity: 1

### `backend\tests\unit\test_chat_routes.py`
- **_make_token**(`user_id`) — Line 30, Complexity: 1
- **_make_session_row**(`user_id, session_id, title`) — Line 41, Complexity: 1
- **_make_message_row**(`role, content, sources`) — Line 57, Complexity: 1
- **app**(`0 args`) — Line 77, Complexity: 1
- **mock_db**(`0 args`) — Line 84, Complexity: 1
- **mock_redis**(`0 args`) — Line 89, Complexity: 1
- **authed_client**(`app, mock_db, mock_redis`) — Line 94, Complexity: 1
- **_override_user**(`0 args`) — Line 97, Complexity: 1
- **_override_db**(`0 args`) — Line 100, Complexity: 1
- **_override_redis**(`0 args`) — Line 103, Complexity: 1
- **test_routes_registered**(`self`) — Line 119, Complexity: 1
- **test_create_chat_is_post**(`self`) — Line 127, Complexity: 4
- **test_sessions_is_get**(`self`) — Line 132, Complexity: 4
- **test_delete_is_delete**(`self`) — Line 137, Complexity: 5
- **test_create_session_returns_sse_stream**(`self, mock_rag, mock_get_llm, mock_get_embedder, mock_get_vs, mock_get_reranker, authed_client`) — Line 161, Complexity: 2
- **test_send_message_to_existing_session**(`self, mock_rag, mock_get_llm, mock_get_embedder, mock_get_vs, mock_get_reranker, authed_client, mock_db`) — Line 204, Complexity: 1
- **test_get_sessions_returns_user_sessions**(`self, authed_client, mock_db`) — Line 248, Complexity: 1
- **test_get_sessions_returns_empty_list**(`self, authed_client, mock_db`) — Line 271, Complexity: 1
- **test_get_history_returns_decrypted_messages**(`self, mock_decrypt, authed_client, mock_db`) — Line 294, Complexity: 1
- **test_get_history_returns_404_for_missing_session**(`self, authed_client, mock_db`) — Line 322, Complexity: 1
- **test_get_history_returns_empty_sources_when_null**(`self, authed_client, mock_db`) — Line 334, Complexity: 1
- **test_delete_session_returns_deleted_status**(`self, authed_client, mock_db`) — Line 362, Complexity: 1
- **test_delete_session_returns_404_for_missing**(`self, authed_client, mock_db`) — Line 378, Complexity: 1
- **test_history_access_denied_for_other_users_session**(`self, authed_client, mock_db`) — Line 397, Complexity: 1
- **test_delete_access_denied_for_other_users_session**(`self, authed_client, mock_db`) — Line 412, Complexity: 1
- **_fake_rag**(`0 args`) — Line 173, Complexity: 1
- **_fake_rag**(`0 args`) — Line 224, Complexity: 1

### `backend\tests\unit\test_checkpointer.py`
- **test_converts_asyncpg_prefix**(`self`) — Line 10, Complexity: 1
- **test_preserves_plain_postgresql_prefix**(`self`) — Line 16, Complexity: 1

### `backend\tests\unit\test_chunker.py`
- **test_dense_sections_get_smaller_chunks**(`0 args`) — Line 583, Complexity: 2
- **test_legal_signal_scoring**(`0 args`) — Line 595, Complexity: 1
- **test_detects_main_sections**(`self`) — Line 68, Complexity: 1
- **test_sections_cover_full_text**(`self`) — Line 76, Complexity: 1
- **test_sections_are_non_overlapping**(`self`) — Line 81, Complexity: 2
- **test_empty_text**(`self`) — Line 86, Complexity: 1
- **test_no_sections_found**(`self`) — Line 89, Complexity: 1
- **test_section_text_not_empty**(`self`) — Line 94, Complexity: 2
- **test_short_text_single_chunk**(`self`) — Line 103, Complexity: 1
- **test_chunk_size_limit**(`self`) — Line 110, Complexity: 2
- **test_chunks_have_section_type**(`self`) — Line 117, Complexity: 2
- **test_chunk_indexes_sequential**(`self`) — Line 127, Complexity: 2
- **test_empty_text_no_chunks**(`self`) — Line 132, Complexity: 1
- **test_custom_sections_respected**(`self`) — Line 135, Complexity: 1
- **test_chunk_size_is_2000**(`self`) — Line 151, Complexity: 1
- **test_chunk_overlap_is_200**(`self`) — Line 154, Complexity: 1
- **test_ipc_not_sentence_break**(`self`) — Line 166, Complexity: 2
- **test_crpc_not_sentence_break**(`self`) — Line 177, Complexity: 1
- **test_vs_not_sentence_break**(`self`) — Line 181, Complexity: 1
- **test_real_sentence_end_still_breaks**(`self`) — Line 185, Complexity: 1
- **test_dr_abbreviation**(`self`) — Line 189, Complexity: 1
- **test_single_letter_abbreviation**(`self`) — Line 193, Complexity: 1
- **test_scc_abbreviation**(`self`) — Line 197, Complexity: 1
- **test_find_break_skips_abbreviation**(`self`) — Line 201, Complexity: 2
- **test_dot_format**(`self`) — Line 218, Complexity: 1
- **test_paren_format**(`self`) — Line 225, Complexity: 1
- **test_bracket_format**(`self`) — Line 232, Complexity: 1
- **test_closing_paren_format**(`self`) — Line 239, Complexity: 1
- **test_para_keyword_format**(`self`) — Line 246, Complexity: 1
- **test_mixed_formats**(`self`) — Line 253, Complexity: 1
- **test_no_paragraphs**(`self`) — Line 260, Complexity: 1
- **test_evidence_section**(`self`) — Line 276, Complexity: 1
- **test_evidence_on_record**(`self`) — Line 282, Complexity: 1
- **test_appreciation_of_evidence**(`self`) — Line 288, Complexity: 1
- **test_statutory_framework**(`self`) — Line 294, Complexity: 1
- **test_relevant_provisions**(`self`) — Line 300, Complexity: 1
- **test_directions_section**(`self`) — Line 306, Complexity: 1
- **test_relief_granted**(`self`) — Line 312, Complexity: 1
- **test_per_curiam**(`self`) — Line 318, Complexity: 1
- **test_by_the_court**(`self`) — Line 324, Complexity: 1
- **test_preliminary_section**(`self`) — Line 330, Complexity: 1
- **test_the_law_section**(`self`) — Line 336, Complexity: 1
- **test_overlap_starts_at_sentence_boundary**(`self`) — Line 351, Complexity: 4
- **test_overlap_not_mid_word**(`self`) — Line 368, Complexity: 2
- **test_same_type_within_50_chars_deduped**(`self`) — Line 388, Complexity: 1
- **test_different_type_beyond_20_chars_kept**(`self`) — Line 396, Complexity: 1
- **test_different_type_within_20_chars_deduped**(`self`) — Line 404, Complexity: 1
- **test_same_type_beyond_50_chars_kept**(`self`) — Line 416, Complexity: 1
- **test_standard_judge_format**(`self`) — Line 432, Complexity: 1
- **test_cji_format**(`self`) — Line 439, Complexity: 1
- **test_per_prefix**(`self`) — Line 446, Complexity: 1
- **test_bracketed_per**(`self`) — Line 453, Complexity: 1
- **test_parenthesized_per**(`self`) — Line 460, Complexity: 1
- **test_multiple_authors**(`self`) — Line 467, Complexity: 1
- **test_no_authors**(`self`) — Line 481, Complexity: 1
- **test_short_name_filtered**(`self`) — Line 487, Complexity: 1
- **test_multi_opinion_chunks**(`self`) — Line 499, Complexity: 1
- **test_single_opinion_author**(`self`) — Line 518, Complexity: 2
- **test_no_opinion_header_gives_none**(`self`) — Line 526, Complexity: 2
- **test_chunk_dataclass_has_opinion_author_field**(`self`) — Line 533, Complexity: 1
- **test_chunk_opinion_author_defaults_to_none**(`self`) — Line 544, Complexity: 1
- **test_long_line_with_evidence_keyword_is_not_heading**(`self`) — Line 558, Complexity: 1
- **test_short_line_is_heading**(`self`) — Line 565, Complexity: 1
- **test_numbered_short_line_is_heading**(`self`) — Line 571, Complexity: 1

### `backend\tests\unit\test_circuit_breaker.py`
- **test_new_breaker_is_closed**(`self`) — Line 30, Complexity: 1
- **test_failures_below_threshold_stay_closed**(`self`) — Line 37, Complexity: 2
- **test_success_resets_failure_count**(`self`) — Line 47, Complexity: 3
- **test_trips_at_threshold**(`self`) — Line 63, Complexity: 2
- **test_open_rejects_requests**(`self`) — Line 72, Complexity: 1
- **test_record_failure_returns_true_on_trip**(`self`) — Line 81, Complexity: 1
- **test_transitions_to_half_open_after_cooldown**(`self`) — Line 93, Complexity: 1
- **test_half_open_success_closes_breaker**(`self`) — Line 109, Complexity: 1
- **test_half_open_failure_reopens_breaker**(`self`) — Line 123, Complexity: 1
- **test_multiple_successes_in_closed_state**(`self`) — Line 141, Complexity: 2
- **test_check_before_cooldown_stays_open**(`self`) — Line 150, Complexity: 1
- **test_custom_threshold_and_cooldown**(`self`) — Line 160, Complexity: 1
- **test_concurrent_checks_are_serialized**(`self`) — Line 171, Complexity: 1

### `backend\tests\unit\test_citation_equivalence.py`
- **test_returns_results_for_matching_citation**(`self`) — Line 10, Complexity: 1
- **test_returns_empty_for_no_match**(`self`) — Line 32, Complexity: 1
- **test_also_checks_equivalents_table**(`self`) — Line 43, Complexity: 1

### `backend\tests\unit\test_citation_equivalent_model.py`
- **test_model_has_required_fields**(`self`) — Line 7, Complexity: 1
- **test_table_name**(`self`) — Line 16, Complexity: 1
- **test_reporter_values**(`self`) — Line 19, Complexity: 1
- **test_citation_text_stored**(`self`) — Line 29, Complexity: 1

### `backend\tests\unit\test_citation_formats.py`
- **test_standard_scc**(`self`) — Line 21, Complexity: 1
- **test_scc_with_volume**(`self`) — Line 30, Complexity: 1
- **test_scc_online**(`self`) — Line 37, Complexity: 1
- **test_scc_sub_reporter**(`self`) — Line 43, Complexity: 1
- **test_air_supreme_court**(`self`) — Line 53, Complexity: 1
- **test_air_high_court**(`self`) — Line 63, Complexity: 1
- **test_air_delhi**(`self`) — Line 70, Complexity: 1
- **test_neutral_citation**(`self`) — Line 80, Complexity: 1
- **test_neutral_with_spaces_after_normalization**(`self`) — Line 87, Complexity: 2
- **test_manu_supreme_court**(`self`) — Line 99, Complexity: 1
- **test_manu_high_court**(`self`) — Line 107, Complexity: 1
- **test_manu_with_spaces**(`self`) — Line 115, Complexity: 1
- **test_livelaw_sc**(`self`) — Line 124, Complexity: 2
- **test_livelaw_hc**(`self`) — Line 130, Complexity: 2
- **test_normalize_scc_brackets**(`self`) — Line 140, Complexity: 1
- **test_normalize_neutral_separators**(`self`) — Line 145, Complexity: 1
- **test_normalize_manu_spaces**(`self`) — Line 150, Complexity: 1
- **test_normalize_versus**(`self`) — Line 155, Complexity: 1

### `backend\tests\unit\test_citation_verifier.py`
- **test_extracts_scc_citation**(`self`) — Line 21, Complexity: 1
- **test_extracts_air_citation**(`self`) — Line 26, Complexity: 1
- **test_extracts_scc_online**(`self`) — Line 31, Complexity: 1
- **test_extracts_insc_citation**(`self`) — Line 36, Complexity: 1
- **test_extracts_scr_citation**(`self`) — Line 41, Complexity: 1
- **test_extracts_crlj_citation**(`self`) — Line 46, Complexity: 1
- **test_extracts_scale_citation**(`self`) — Line 51, Complexity: 1
- **test_no_citations**(`self`) — Line 56, Complexity: 1
- **test_multiple_citations**(`self`) — Line 61, Complexity: 1
- **test_deduplicates_repeated_citations**(`self`) — Line 69, Complexity: 1
- **test_empty_list_returns_empty**(`self`) — Line 85, Complexity: 1
- **test_found_in_cases_table**(`self`) — Line 92, Complexity: 1
- **test_found_in_equivalents_table**(`self`) — Line 107, Complexity: 1
- **test_not_found_is_unverified**(`self`) — Line 125, Complexity: 1
- **test_db_error_treated_as_unverified**(`self`) — Line 139, Complexity: 1
- **test_flags_ungrounded_citation**(`self`) — Line 157, Complexity: 1
- **test_all_grounded**(`self`) — Line 166, Complexity: 1
- **test_empty_memo_citations**(`self`) — Line 174, Complexity: 1
- **test_empty_search_citations**(`self`) — Line 178, Complexity: 1
- **test_normalization_handles_whitespace_differences**(`self`) — Line 184, Complexity: 1

### `backend\tests\unit\test_cited_by_count.py`
- **test_get_cited_by_count**(`self`) — Line 11, Complexity: 1
- **test_get_cited_by_count_not_found**(`self`) — Line 21, Complexity: 1
- **test_get_cited_by_count_on_error**(`self`) — Line 31, Complexity: 1

### `backend\tests\unit\test_classify_treatment_llm.py`
- **mock_llm**(`0 args`) — Line 19, Complexity: 1
- **test_overruled_classification**(`self, mock_llm`) — Line 29, Complexity: 1
- **test_distinguished_classification**(`self, mock_llm`) — Line 44, Complexity: 1
- **test_followed_classification**(`self, mock_llm`) — Line 59, Complexity: 1
- **test_returns_none_on_invalid_treatment**(`self, mock_llm`) — Line 73, Complexity: 1
- **test_returns_none_on_llm_failure**(`self, mock_llm`) — Line 83, Complexity: 1
- **test_returns_none_on_malformed_json**(`self, mock_llm`) — Line 90, Complexity: 1
- **test_truncates_context_to_1000_chars**(`self, mock_llm`) — Line 97, Complexity: 1
- **test_handles_markdown_wrapped_json**(`self, mock_llm`) — Line 114, Complexity: 1
- **test_per_incuriam_classification**(`self, mock_llm`) — Line 122, Complexity: 1
- **test_cited_text_truncated_to_200**(`self, mock_llm`) — Line 136, Complexity: 1
- **test_default_confidence**(`self, mock_llm`) — Line 148, Complexity: 1

### `backend\tests\unit\test_common_nodes.py`
- **test_max_results_for_llm**(`self`) — Line 29, Complexity: 1
- **test_hindi_suffix_exists**(`self`) — Line 32, Complexity: 1
- **test_hindi_appends_suffix**(`self`) — Line 43, Complexity: 1
- **test_english_no_change**(`self`) — Line 48, Complexity: 1
- **test_unknown_language_no_change**(`self`) — Line 52, Complexity: 1
- **test_returns_none_for_empty_messages**(`self`) — Line 63, Complexity: 1
- **test_returns_none_when_no_matching_step**(`self`) — Line 66, Complexity: 1
- **test_returns_content_for_matching_step**(`self`) — Line 72, Complexity: 1
- **test_returns_latest_when_multiple**(`self`) — Line 78, Complexity: 1
- **test_ignores_non_feedback_messages**(`self`) — Line 85, Complexity: 1
- **test_returns_none_for_empty**(`self`) — Line 99, Complexity: 1
- **test_returns_data_for_matching_type**(`self`) — Line 102, Complexity: 1
- **test_returns_latest_match**(`self`) — Line 108, Complexity: 1
- **test_empty_list**(`self`) — Line 122, Complexity: 1
- **test_keeps_highest_score**(`self`) — Line 125, Complexity: 1
- **test_multiple_case_ids**(`self`) — Line 134, Complexity: 1
- **test_skips_empty_case_id**(`self`) — Line 143, Complexity: 1
- **test_empty_results**(`self`) — Line 154, Complexity: 1
- **test_detects_overruled**(`self, mock_check`) — Line 158, Complexity: 1
- **test_no_overruling**(`self, mock_check`) — Line 166, Complexity: 1
- **test_skips_empty_case_id**(`self`) — Line 172, Complexity: 1
- **test_empty_results**(`self`) — Line 183, Complexity: 1
- **test_collects_citations**(`self`) — Line 186, Complexity: 1
- **test_valid_json_object**(`self`) — Line 203, Complexity: 1
- **test_valid_json_array**(`self`) — Line 206, Complexity: 1
- **test_markdown_fenced_json**(`self`) — Line 209, Complexity: 1
- **test_embedded_json**(`self`) — Line 213, Complexity: 1
- **test_invalid_returns_default**(`self`) — Line 217, Complexity: 1
- **test_custom_default**(`self`) — Line 220, Complexity: 1
- **test_returns_list**(`self`) — Line 225, Complexity: 1
- **test_wraps_object_in_list**(`self`) — Line 228, Complexity: 1
- **test_returns_empty_list_on_failure**(`self`) — Line 231, Complexity: 1
- **test_empty_results**(`self`) — Line 241, Complexity: 1
- **test_basic_formatting**(`self`) — Line 244, Complexity: 1
- **test_bench_type_label**(`self`) — Line 259, Complexity: 1
- **test_empty_memo_returns_empty**(`self`) — Line 280, Complexity: 1
- **test_memo_without_citations_unchanged**(`self`) — Line 286, Complexity: 1

### `backend\tests\unit\test_concurrent_ingestion.py`
- **_make_chunk**(`text, index`) — Line 19, Complexity: 1
- **test_same_text_same_hash**(`self`) — Line 31, Complexity: 1
- **test_different_text_different_hash**(`self`) — Line 37, Complexity: 1
- **test_whitespace_normalization**(`self`) — Line 43, Complexity: 1
- **test_case_insensitive**(`self`) — Line 49, Complexity: 1
- **test_leading_trailing_whitespace_ignored**(`self`) — Line 55, Complexity: 1
- **test_hash_is_sha256**(`self`) — Line 61, Complexity: 1
- **test_successful_single_batch**(`self`) — Line 72, Complexity: 1
- **test_retry_does_not_duplicate_embeddings**(`self`) — Line 84, Complexity: 1
- **test_retry_exhaustion_raises**(`self`) — Line 100, Complexity: 1
- **test_empty_chunks_returns_empty**(`self`) — Line 112, Complexity: 1
- **test_concurrent_texts_produce_unique_hashes**(`self`) — Line 123, Complexity: 1
- **test_duplicate_texts_produce_same_hash**(`self`) — Line 133, Complexity: 1

### `backend\tests\unit\test_confidence_scoring.py`
- **test_zero_results_gives_zero**(`self`) — Line 7, Complexity: 1
- **test_strong_results_high_confidence**(`self`) — Line 14, Complexity: 1
- **test_contradictions_reduce_confidence**(`self`) — Line 26, Complexity: 1
- **test_confidence_capped_at_one**(`self`) — Line 44, Complexity: 1
- **test_only_persuasive_lower_than_binding**(`self`) — Line 55, Complexity: 1

### `backend\tests\unit\test_config_pool.py`
- **test_pool_size_lowered**(`self`) — Line 8, Complexity: 1
- **test_max_overflow_lowered**(`self`) — Line 16, Complexity: 1

### `backend\tests\unit\test_config_validation.py`
- **test_app_debug_defaults_to_false**(`0 args`) — Line 7, Complexity: 1
- **test_empty_jwt_secret_raises_in_production**(`0 args`) — Line 15, Complexity: 1
- **test_empty_refresh_secret_raises_in_production**(`0 args`) — Line 22, Complexity: 1
- **test_short_jwt_secret_raises**(`0 args`) — Line 28, Complexity: 1
- **test_empty_encryption_key_raises_in_production**(`0 args`) — Line 35, Complexity: 1
- **test_test_env_skips_validation**(`0 args`) — Line 46, Complexity: 1
- **test_development_env_warns_but_allows_empty**(`0 args`) — Line 53, Complexity: 1

### `backend\tests\unit\test_courts.py`
- **test_supreme_court_abbreviation**(`self`) — Line 16, Complexity: 1
- **test_supreme_court_full_name**(`self`) — Line 19, Complexity: 1
- **test_high_court_abbreviation**(`self`) — Line 22, Complexity: 1
- **test_air_code_delhi**(`self`) — Line 25, Complexity: 1
- **test_air_code_allahabad**(`self`) — Line 28, Complexity: 1
- **test_case_insensitive_lookup**(`self`) — Line 31, Complexity: 1
- **test_tribunal_nclt**(`self`) — Line 35, Complexity: 1
- **test_unknown_court_returns_input**(`self`) — Line 38, Complexity: 1
- **test_punjab_haryana_variants**(`self`) — Line 41, Complexity: 1
- **test_telangana**(`self`) — Line 45, Complexity: 1
- **test_jk_ladakh**(`self`) — Line 48, Complexity: 1
- **test_supreme_court**(`self`) — Line 55, Complexity: 1
- **test_high_court**(`self`) — Line 59, Complexity: 1
- **test_tribunal**(`self`) — Line 63, Complexity: 1
- **test_district_court_keyword**(`self`) — Line 67, Complexity: 1
- **test_unknown**(`self`) — Line 71, Complexity: 1
- **test_air_code_gives_correct_level**(`self`) — Line 74, Complexity: 1
- **test_all_air_codes_have_valid_courts**(`self`) — Line 82, Complexity: 2
- **test_court_name_map_no_empty_values**(`self`) — Line 87, Complexity: 2

### `backend\tests\unit\test_devanagari_preservation.py`
- **test_zwnj_preserved**(`self`) — Line 17, Complexity: 1
- **test_zwj_preserved**(`self`) — Line 24, Complexity: 1
- **test_zwsp_removed**(`self`) — Line 31, Complexity: 1
- **test_bom_removed**(`self`) — Line 37, Complexity: 1
- **test_basic_hindi_legal_text_preserved**(`self`) — Line 47, Complexity: 1
- **test_mixed_hindi_english_preserved**(`self`) — Line 58, Complexity: 1
- **test_devanagari_with_matras_preserved**(`self`) — Line 70, Complexity: 1
- **test_devanagari_numerals_preserved**(`self`) — Line 78, Complexity: 1
- **test_nfkc_does_not_mangle_devanagari**(`self`) — Line 84, Complexity: 1

### `backend\tests\unit\test_document_analyzer.py`
- **_make_mock_llm**(`0 args`) — Line 14, Complexity: 1
- **test_extracts_issues_from_document**(`self`) — Line 20, Complexity: 1
- **test_handles_empty_issues**(`self`) — Line 47, Complexity: 1
- **test_truncates_long_documents**(`self`) — Line 64, Complexity: 1
- **test_generates_memo**(`self`) — Line 87, Complexity: 1
- **test_parses_formatted_counter_arguments**(`self`) — Line 106, Complexity: 1
- **test_handles_empty_response**(`self`) — Line 124, Complexity: 1

### `backend\tests\unit\test_document_routes.py`
- **test_routes_registered**(`self`) — Line 9, Complexity: 1
- **test_upload_is_post**(`self`) — Line 16, Complexity: 4
- **test_delete_exists**(`self`) — Line 21, Complexity: 5
- **test_list_is_get**(`self`) — Line 33, Complexity: 5

### `backend\tests\unit\test_document_tasks.py`
- **test_formats_single_issue**(`self`) — Line 9, Complexity: 1
- **test_formats_multiple_issues**(`self`) — Line 24, Complexity: 1
- **test_handles_no_precedents**(`self`) — Line 37, Complexity: 1

### `backend\tests\unit\test_dpdp_routes.py`
- **_token_payload**(`user_id`) — Line 33, Complexity: 1
- **_mock_db_session**(`0 args`) — Line 55, Complexity: 1
- **app**(`0 args`) — Line 69, Complexity: 1
- **mock_db**(`0 args`) — Line 77, Complexity: 1
- **token**(`0 args`) — Line 82, Complexity: 1
- **client**(`app, mock_db, token`) — Line 87, Complexity: 1
- **unauth_client**(`app, mock_db`) — Line 100, Complexity: 1
- **__aenter__**(`self`) — Line 48, Complexity: 1
- **__aexit__**(`self`) — Line 51, Complexity: 1
- **_override_db**(`0 args`) — Line 90, Complexity: 1
- **_override_db**(`0 args`) — Line 103, Complexity: 1
- **test_data_summary_unauthenticated**(`self, unauth_client`) — Line 120, Complexity: 1
- **test_erasure_unauthenticated**(`self, unauth_client`) — Line 124, Complexity: 1
- **test_consent_withdraw_unauthenticated**(`self, unauth_client`) — Line 128, Complexity: 1
- **test_consent_status_unauthenticated**(`self, unauth_client`) — Line 132, Complexity: 1
- **test_data_summary_returns_counts**(`self, client, mock_db, token`) — Line 145, Complexity: 1
- **test_data_summary_zero_counts**(`self, client, mock_db, token`) — Line 173, Complexity: 2
- **test_data_summary_executes_query_with_user_id**(`self, client, mock_db, token`) — Line 197, Complexity: 1
- **test_data_summary_response_structure**(`self, client, mock_db`) — Line 221, Complexity: 1
- **test_erasure_returns_success**(`self, client, mock_db`) — Line 261, Complexity: 2
- **test_erasure_uses_nested_transaction**(`self, client, mock_db`) — Line 273, Complexity: 1
- **test_erasure_commits_after_nested**(`self, client, mock_db`) — Line 281, Complexity: 1
- **test_erasure_deletes_all_tables**(`self, client, mock_db, token`) — Line 289, Complexity: 2
- **test_erasure_logs_to_dpdp_audit**(`self, client, mock_db`) — Line 312, Complexity: 2
- **test_erasure_deactivates_user**(`self, client, mock_db`) — Line 328, Complexity: 2
- **test_erasure_passes_correct_user_id**(`self, client, mock_db, token`) — Line 343, Complexity: 3
- **test_erasure_deletes_chat_messages_via_session_join**(`self, client, mock_db`) — Line 356, Complexity: 3
- **test_consent_withdraw_returns_success**(`self, client, mock_db`) — Line 384, Complexity: 1
- **test_consent_withdraw_updates_only_active_consents**(`self, client, mock_db`) — Line 394, Complexity: 2
- **test_consent_withdraw_logs_audit**(`self, client, mock_db`) — Line 413, Complexity: 2
- **test_consent_withdraw_commits**(`self, client, mock_db`) — Line 429, Complexity: 1
- **test_consent_withdraw_uses_correct_user_id**(`self, client, mock_db, token`) — Line 437, Complexity: 3
- **test_consent_status_returns_consents**(`self, client, mock_db, token`) — Line 457, Complexity: 1
- **test_consent_status_empty_list**(`self, client, mock_db, token`) — Line 501, Complexity: 1
- **test_consent_status_response_structure**(`self, client, mock_db`) — Line 516, Complexity: 1
- **test_consent_status_uses_correct_user_id**(`self, client, mock_db, token`) — Line 541, Complexity: 1
- **test_consent_status_revoked_at_is_string_when_present**(`self, client, mock_db`) — Line 555, Complexity: 1
- **test_all_routes_registered**(`self`) — Line 588, Complexity: 1
- **test_data_summary_is_get**(`self`) — Line 595, Complexity: 4
- **test_erasure_is_post**(`self`) — Line 600, Complexity: 4
- **test_consent_withdraw_is_post**(`self`) — Line 605, Complexity: 4
- **test_consent_status_is_get**(`self`) — Line 610, Complexity: 4

### `backend\tests\unit\test_drafting_graph.py`
- **_make_state**(`0 args`) — Line 24, Complexity: 1
- **test_returns_end_when_error_is_set**(`self`) — Line 58, Complexity: 1
- **test_returns_gather_provisions_when_no_error**(`self`) — Line 63, Complexity: 1
- **test_returns_gather_provisions_when_error_is_none**(`self`) — Line 68, Complexity: 1
- **test_returns_end_for_missing_fields_error**(`self`) — Line 74, Complexity: 1
- **test_returns_draft_sections_when_no_feedback**(`self`) — Line 86, Complexity: 1
- **test_returns_gather_provisions_when_feedback_present_and_iteration_below_3**(`self`) — Line 91, Complexity: 1
- **test_returns_draft_sections_when_iteration_at_3**(`self`) — Line 105, Complexity: 1
- **test_returns_draft_sections_when_feedback_is_empty_string**(`self`) — Line 117, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 131, Complexity: 1
- **test_uses_last_sources_feedback_when_multiple_messages**(`self`) — Line 146, Complexity: 1
- **test_returns_verify_final_when_no_feedback**(`self`) — Line 167, Complexity: 1
- **test_returns_revise_section_when_feedback_present**(`self`) — Line 172, Complexity: 1
- **test_returns_verify_final_when_iteration_at_3**(`self`) — Line 186, Complexity: 1
- **test_returns_verify_final_when_draft_feedback_is_empty**(`self`) — Line 198, Complexity: 1
- **test_ignores_sources_feedback_for_draft_routing**(`self`) — Line 208, Complexity: 1
- **test_returns_end_when_no_feedback**(`self`) — Line 229, Complexity: 1
- **test_returns_revise_section_when_feedback_present**(`self`) — Line 234, Complexity: 1
- **test_returns_end_when_iteration_at_3**(`self`) — Line 248, Complexity: 1
- **test_returns_end_when_final_feedback_is_empty**(`self`) — Line 260, Complexity: 1
- **test_ignores_draft_feedback_for_final_routing**(`self`) — Line 270, Complexity: 1
- **test_compiles_without_checkpointer**(`self`) — Line 291, Complexity: 1
- **test_has_expected_nodes**(`self`) — Line 311, Complexity: 1
- **test_compiles_with_mock_checkpointer**(`self`) — Line 348, Complexity: 2

### `backend\tests\unit\test_drafting_nodes.py`
- **_make_state**(`0 args`) — Line 24, Complexity: 1
- **_make_llm**(`0 args`) — Line 52, Complexity: 2
- **test_returns_template_dict_for_valid_doc_type**(`self`) — Line 69, Complexity: 1
- **test_returns_error_for_missing_doc_type**(`self`) — Line 82, Complexity: 1
- **test_returns_error_for_unknown_doc_type**(`self`) — Line 91, Complexity: 1
- **test_returns_error_for_missing_required_fields**(`self`) — Line 100, Complexity: 1
- **test_returns_template_with_all_expected_keys**(`self`) — Line 115, Complexity: 1
- **test_returns_template_for_writ_petition_with_correct_fields**(`self`) — Line 124, Complexity: 1
- **test_returns_provisions_from_llm**(`self`) — Line 147, Complexity: 1
- **test_returns_empty_list_when_no_case_facts**(`self`) — Line 179, Complexity: 1
- **test_handles_db_exception_gracefully**(`self`) — Line 190, Complexity: 1
- **test_validates_provision_keys**(`self`) — Line 210, Complexity: 1
- **test_tags_precedents_as_verified_or_unverified**(`self`) — Line 248, Complexity: 1
- **test_returns_empty_list_when_no_precedents**(`self`) — Line 274, Complexity: 1
- **test_skips_precedents_without_citation**(`self`) — Line 282, Complexity: 1
- **test_handles_verify_exception_gracefully**(`self`) — Line 304, Complexity: 1
- **test_drafts_all_template_sections**(`self`) — Line 329, Complexity: 2
- **test_returns_empty_dict_when_no_sections**(`self`) — Line 352, Complexity: 1
- **test_handles_llm_exception_for_individual_section**(`self`) — Line 362, Complexity: 2
- **test_uses_fallback_system_prompt_for_unknown_prompt_key**(`self`) — Line 395, Complexity: 1
- **test_includes_case_facts_in_prompt**(`self`) — Line 413, Complexity: 1
- **test_assembles_sections_into_full_draft**(`self`) — Line 440, Complexity: 1
- **test_returns_empty_string_when_no_section_drafts**(`self`) — Line 464, Complexity: 1
- **test_includes_court_header_in_prompt**(`self`) — Line 474, Complexity: 1
- **test_falls_back_to_raw_text_on_llm_failure**(`self`) — Line 495, Complexity: 1
- **test_assembles_sections_in_template_order**(`self`) — Line 520, Complexity: 1
- **test_revises_target_section**(`self`) — Line 560, Complexity: 1
- **test_returns_unchanged_when_no_feedback**(`self`) — Line 591, Complexity: 1
- **test_detects_section_from_feedback_text**(`self`) — Line 606, Complexity: 1
- **test_defaults_to_first_section_when_section_unknown**(`self`) — Line 633, Complexity: 1
- **test_passes_through_clean_draft**(`self`) — Line 666, Complexity: 1
- **test_appends_warning_for_invalid_uuid**(`self`) — Line 688, Complexity: 1
- **test_appends_warning_for_unverified_human_readable_citation**(`self`) — Line 712, Complexity: 1
- **test_appends_ungrounded_warning_for_citations_not_in_precedents**(`self`) — Line 731, Complexity: 1
- **test_no_ungrounded_warning_when_citation_in_precedents**(`self`) — Line 754, Complexity: 1
- **test_returns_empty_full_draft_unchanged**(`self`) — Line 774, Complexity: 1
- **flaky_generate**(`0 args`) — Line 365, Complexity: 2
- **capture_generate**(`0 args`) — Line 524, Complexity: 1

### `backend\tests\unit\test_drafting_templates.py`
- **test_all_seven_templates_exist_in_templates_dict**(`self`) — Line 45, Complexity: 1
- **test_each_template_is_document_template_instance**(`self`) — Line 48, Complexity: 2
- **test_each_template_has_non_empty_sections**(`self`) — Line 54, Complexity: 2
- **test_each_template_has_non_empty_required_fields**(`self`) — Line 63, Complexity: 2
- **test_each_template_has_non_empty_display_name**(`self`) — Line 72, Complexity: 2
- **test_each_template_prompt_key_maps_to_valid_prompt**(`self`) — Line 81, Complexity: 3
- **test_section_names_are_non_empty_strings**(`self`) — Line 94, Complexity: 4
- **test_required_field_names_are_non_empty_strings**(`self`) — Line 102, Complexity: 4
- **test_bail_application_has_expected_sections**(`self`) — Line 110, Complexity: 1
- **test_bail_application_has_expected_required_fields**(`self`) — Line 124, Complexity: 1
- **test_writ_petition_226_uses_writ_petition_prompt**(`self`) — Line 131, Complexity: 1
- **test_writ_petition_32_uses_writ_petition_prompt**(`self`) — Line 135, Complexity: 1
- **test_writ_petition_32_targets_supreme_court**(`self`) — Line 139, Complexity: 1
- **test_templates_dict_is_frozen_and_not_mutated**(`self`) — Line 144, Complexity: 1
- **test_doc_type_matches_key**(`self`) — Line 152, Complexity: 2
- **test_returns_correct_template_for_bail_application**(`self`) — Line 167, Complexity: 1
- **test_returns_correct_template_for_writ_petition_226**(`self`) — Line 173, Complexity: 2
- **test_returns_correct_template_for_writ_petition_32**(`self`) — Line 178, Complexity: 2
- **test_returns_correct_template_for_written_statement**(`self`) — Line 183, Complexity: 1
- **test_returns_correct_template_for_legal_notice**(`self`) — Line 187, Complexity: 1
- **test_returns_correct_template_for_appeal**(`self`) — Line 191, Complexity: 1
- **test_returns_correct_template_for_interim_application**(`self`) — Line 195, Complexity: 1
- **test_raises_value_error_for_unknown_doc_type**(`self`) — Line 199, Complexity: 1
- **test_error_message_lists_valid_types**(`self`) — Line 203, Complexity: 2
- **test_error_message_mentions_invalid_type**(`self`) — Line 214, Complexity: 1
- **test_raises_for_empty_string**(`self`) — Line 220, Complexity: 1
- **test_raises_for_near_miss_type**(`self`) — Line 224, Complexity: 1
- **test_raises_for_wrong_case**(`self`) — Line 229, Complexity: 1
- **test_returned_template_is_frozen**(`self`) — Line 234, Complexity: 1
- **test_returns_same_object_on_repeated_calls**(`self`) — Line 240, Complexity: 1

### `backend\tests\unit\test_editorial_filters.py`
- **test_editorial_re_matches**(`self, line`) — Line 32, Complexity: 1
- **test_editorial_re_does_not_match_judgment_text**(`self, line`) — Line 41, Complexity: 1
- **test_reporter_page_marker_matches**(`self, line`) — Line 55, Complexity: 1
- **test_reporter_page_marker_no_false_positives**(`self, line`) — Line 63, Complexity: 1
- **test_strips_headnotes_byline**(`self`) — Line 70, Complexity: 1
- **test_strips_result_of_case**(`self`) — Line 77, Complexity: 1
- **test_strips_scr_page_markers**(`self`) — Line 83, Complexity: 1
- **test_preserves_normal_judgment_text**(`self`) — Line 90, Complexity: 1
- **test_headnotes_rule_excludes_editorial**(`self`) — Line 103, Complexity: 1
- **test_operative_order_excludes_editorial**(`self`) — Line 107, Complexity: 1
- **test_rule_30_editorial_content**(`self`) — Line 111, Complexity: 1

### `backend\tests\unit\test_encryption.py`
- **mock_settings**(`0 args`) — Line 15, Complexity: 1
- **test_round_trip**(`self`) — Line 25, Complexity: 1
- **test_encrypted_differs_from_plaintext**(`self`) — Line 31, Complexity: 1
- **test_different_encryptions_produce_different_output**(`self`) — Line 36, Complexity: 1
- **test_round_trip_unicode**(`self`) — Line 42, Complexity: 1
- **test_round_trip_empty_string**(`self`) — Line 48, Complexity: 1
- **test_tampered_ciphertext_fails**(`self`) — Line 53, Complexity: 1
- **test_invalid_base64_fails**(`self`) — Line 60, Complexity: 1
- **test_too_short_ciphertext_fails**(`self`) — Line 64, Complexity: 1
- **test_invalid_key_raises**(`self`) — Line 74, Complexity: 1
- **test_base64_key_works**(`self`) — Line 80, Complexity: 1

### `backend\tests\unit\test_extractor.py`
- **test_scc_citation**(`self`) — Line 17, Complexity: 1
- **test_air_citation**(`self`) — Line 27, Complexity: 1
- **test_insc_citation**(`self`) — Line 35, Complexity: 1
- **test_scc_online_citation**(`self`) — Line 43, Complexity: 1
- **test_scr_citation**(`self`) — Line 50, Complexity: 1
- **test_crlj_citation**(`self`) — Line 57, Complexity: 1
- **test_scale_citation**(`self`) — Line 63, Complexity: 1
- **test_multiple_citations_in_text**(`self`) — Line 69, Complexity: 1
- **test_no_citations**(`self`) — Line 77, Complexity: 1
- **test_citation_raw_text_preserved**(`self`) — Line 82, Complexity: 1
- **test_section_of_act**(`self`) — Line 91, Complexity: 1
- **test_article_of_constitution**(`self`) — Line 97, Complexity: 1
- **test_no_acts**(`self`) — Line 102, Complexity: 1
- **test_normalizes_spaces**(`self`) — Line 111, Complexity: 1
- **test_returns_input_unchanged_if_no_match**(`self`) — Line 115, Complexity: 1
- **test_air_known_court_code_matches**(`self`) — Line 128, Complexity: 1
- **test_air_unknown_court_code_does_not_match**(`self`) — Line 137, Complexity: 1
- **test_air_with_dots_known_code**(`self`) — Line 143, Complexity: 1
- **test_section_range_dash**(`self`) — Line 159, Complexity: 1
- **test_section_range_to**(`self`) — Line 168, Complexity: 2
- **test_read_with_full**(`self`) — Line 185, Complexity: 1
- **test_rw_shorthand**(`self`) — Line 193, Complexity: 1
- **test_read_with_no_second_section_prefix**(`self`) — Line 201, Complexity: 1
- **test_bare_article_21_defaults_to_constitution**(`self`) — Line 218, Complexity: 1
- **test_bare_article_500_defaults_to_unknown**(`self`) — Line 226, Complexity: 1
- **test_article_with_constitution_still_works**(`self`) — Line 233, Complexity: 1
- **test_article_19_1_a**(`self`) — Line 249, Complexity: 1
- **test_article_226_1**(`self`) — Line 256, Complexity: 1
- **test_article_368A**(`self`) — Line 263, Complexity: 1
- **test_article_21_read_with_14**(`self`) — Line 270, Complexity: 1
- **test_article_rw_shorthand**(`self`) — Line 280, Complexity: 2
- **test_regulation_sebi**(`self`) — Line 297, Complexity: 1
- **test_clause_pattern**(`self`) — Line 303, Complexity: 1
- **test_order_rule_cpc**(`self`) — Line 309, Complexity: 1
- **test_order_rule_without_cpc**(`self`) — Line 316, Complexity: 1
- **test_short_act_resolves**(`self, code, expected`) — Line 343, Complexity: 1
- **test_duplicate_act_section_deduped**(`self`) — Line 358, Complexity: 2
- **test_livelaw_citation**(`self`) — Line 373, Complexity: 1
- **test_itr_citation**(`self`) — Line 382, Complexity: 1
- **test_taxmann_citation**(`self`) — Line 391, Complexity: 1
- **test_compcas_citation**(`self`) — Line 400, Complexity: 1
- **test_llj_citation**(`self`) — Line 409, Complexity: 1
- **test_itr_with_parens**(`self`) — Line 417, Complexity: 1
- **test_lnind_citation**(`self`) — Line 428, Complexity: 2
- **test_cdj_citation**(`self`) — Line 433, Complexity: 2
- **test_bomlr_citation**(`self`) — Line 438, Complexity: 2
- **test_calwn_citation**(`self`) — Line 443, Complexity: 2
- **test_wlr_citation**(`self`) — Line 448, Complexity: 2
- **test_mplj_citation**(`self`) — Line 453, Complexity: 2
- **test_unknown_reporter_caught**(`self`) — Line 462, Complexity: 2
- **test_catch_all_does_not_duplicate_known**(`self`) — Line 467, Complexity: 1
- **test_catch_all_capped_at_10**(`self`) — Line 473, Complexity: 1
- **test_catch_all_skips_common_words**(`self`) — Line 481, Complexity: 1

### `backend\tests\unit\test_extractor_confidence.py`
- **test_name_citation_has_low_confidence**(`0 args`) — Line 6, Complexity: 1
- **test_neutral_citation_has_high_confidence**(`0 args`) — Line 15, Complexity: 1
- **test_neutral_hc_citation_has_high_confidence**(`0 args`) — Line 23, Complexity: 1
- **test_formal_reporter_has_medium_high_confidence**(`0 args`) — Line 31, Complexity: 2
- **test_air_citation_confidence**(`0 args`) — Line 40, Complexity: 1
- **test_manu_citation_confidence**(`0 args`) — Line 49, Complexity: 1
- **test_insc_space_delimited_confidence**(`0 args`) — Line 58, Complexity: 1
- **test_default_confidence_is_one**(`0 args`) — Line 67, Complexity: 1
- **test_confidence_tiers_ordering**(`0 args`) — Line 82, Complexity: 1

### `backend\tests\unit\test_follow_up_nodes.py`
- **_make_state**(`0 args`) — Line 49, Complexity: 1
- **_make_search_results**(`n`) — Line 74, Complexity: 1
- **test_basic_reformulation**(`self`) — Line 96, Complexity: 1
- **test_strips_quotes_from_llm_response**(`self`) — Line 110, Complexity: 1
- **test_single_quotes_stripped**(`self`) — Line 118, Complexity: 1
- **test_llm_called_with_correct_params**(`self`) — Line 126, Complexity: 1
- **test_long_memo_truncated_for_reformulation**(`self`) — Line 139, Complexity: 1
- **test_empty_conversation_history**(`self`) — Line 155, Complexity: 1
- **test_empty_prior_memo**(`self`) — Line 166, Complexity: 1
- **test_llm_failure_propagates**(`self`) — Line 175, Complexity: 1
- **test_detail_truncated_to_100_chars**(`self`) — Line 183, Complexity: 1
- **_make_deps**(`self, search_results`) — Line 201, Complexity: 2
- **test_basic_search_returns_results**(`self`) — Line 237, Complexity: 1
- **test_progress_event_emitted**(`self`) — Line 266, Complexity: 1
- **test_falls_back_to_follow_up_query_when_no_reformulated**(`self`) — Line 293, Complexity: 1
- **test_uses_reformulated_query_when_present**(`self`) — Line 316, Complexity: 1
- **test_passes_settings_max_results**(`self`) — Line 339, Complexity: 1
- **test_empty_search_results**(`self`) — Line 364, Complexity: 1
- **test_hybrid_search_failure_propagates**(`self`) — Line 387, Complexity: 1
- **test_redis_client_none_accepted**(`self`) — Line 408, Complexity: 1
- **test_basic_synthesis_without_streaming**(`self`) — Line 437, Complexity: 1
- **test_llm_called_with_correct_params**(`self`) — Line 468, Complexity: 1
- **test_streaming_with_callback**(`self`) — Line 482, Complexity: 2
- **test_progress_event_emitted**(`self`) — Line 504, Complexity: 1
- **test_footnotes_from_multiple_search_results**(`self`) — Line 518, Complexity: 2
- **test_long_snippet_truncated_in_footnote**(`self`) — Line 544, Complexity: 1
- **test_long_memo_truncated_per_settings**(`self`) — Line 567, Complexity: 1
- **test_empty_search_results_and_footnotes**(`self`) — Line 586, Complexity: 1
- **test_llm_failure_propagates**(`self`) — Line 602, Complexity: 1
- **test_streaming_error_propagates**(`self`) — Line 611, Complexity: 1
- **test_footnote_missing_fields_default_gracefully**(`self`) — Line 626, Complexity: 1
- **test_empty_history**(`self`) — Line 649, Complexity: 1
- **test_single_message**(`self`) — Line 652, Complexity: 1
- **test_role_title_cased**(`self`) — Line 657, Complexity: 1
- **test_max_messages_limits_output**(`self`) — Line 662, Complexity: 1
- **test_content_truncated_to_500_chars**(`self`) — Line 671, Complexity: 1
- **test_missing_role_defaults_to_user**(`self`) — Line 678, Complexity: 1
- **test_missing_content_defaults_to_empty**(`self`) — Line 683, Complexity: 1
- **test_empty_footnotes**(`self`) — Line 690, Complexity: 1
- **test_single_footnote**(`self`) — Line 693, Complexity: 1
- **test_max_footnotes_limit**(`self`) — Line 710, Complexity: 1
- **test_missing_fields_use_defaults**(`self`) — Line 719, Complexity: 1
- **test_empty_results**(`self`) — Line 727, Complexity: 1
- **test_single_result**(`self`) — Line 730, Complexity: 1
- **test_snippet_truncated_to_500**(`self`) — Line 748, Complexity: 1
- **test_missing_fields_use_defaults**(`self`) — Line 754, Complexity: 1
- **fake_stream**(`0 args`) — Line 485, Complexity: 2
- **failing_stream**(`0 args`) — Line 614, Complexity: 1

### `backend\tests\unit\test_fulltext.py`
- **test_no_filters**(`self`) — Line 12, Complexity: 1
- **test_empty_filters**(`self`) — Line 18, Complexity: 1
- **test_court_filter**(`self`) — Line 24, Complexity: 1
- **test_year_range_filter**(`self`) — Line 31, Complexity: 1
- **test_year_from_only**(`self`) — Line 38, Complexity: 1
- **test_case_type_filter**(`self`) — Line 44, Complexity: 1
- **test_bench_type_filter**(`self`) — Line 50, Complexity: 1
- **test_judge_filter**(`self`) — Line 56, Complexity: 1
- **test_act_filter**(`self`) — Line 62, Complexity: 1
- **test_all_filters_combined**(`self`) — Line 67, Complexity: 1

### `backend\tests\unit\test_gcs_storage.py`
- **mock_gcs_client**(`0 args`) — Line 13, Complexity: 1
- **test_store_uploads_file**(`self, mock_gcs_client`) — Line 34, Complexity: 1
- **test_store_rejects_oversized_file**(`self, mock_gcs_client`) — Line 47, Complexity: 1
- **test_retrieve_downloads_bytes**(`self, mock_gcs_client`) — Line 59, Complexity: 1
- **test_retrieve_chunked_yields_chunks**(`self, mock_gcs_client`) — Line 74, Complexity: 1
- **test_delete_removes_blob**(`self, mock_gcs_client`) — Line 91, Complexity: 1
- **test_delete_handles_not_found**(`self, mock_gcs_client`) — Line 101, Complexity: 1
- **test_exists_returns_true_when_blob_exists**(`self, mock_gcs_client`) — Line 115, Complexity: 1
- **test_exists_returns_false_when_blob_missing**(`self, mock_gcs_client`) — Line 124, Complexity: 1
- **test_parse_gs_path_extracts_blob_name**(`self, mock_gcs_client`) — Line 134, Complexity: 1
- **test_parse_gs_path_handles_plain_path**(`self, mock_gcs_client`) — Line 138, Complexity: 1
- **test_protocol_compliance**(`self, mock_gcs_client`) — Line 144, Complexity: 1

### `backend\tests\unit\test_gemini_pdf_multimodal.py`
- **test_reads_pdf_bytes_and_calls_gemini**(`self`) — Line 14, Complexity: 1
- **test_returns_empty_dict_on_json_error**(`self`) — Line 43, Complexity: 1
- **test_uses_pdf_when_path_provided**(`self`) — Line 71, Complexity: 1
- **test_falls_back_to_text_when_no_pdf_path**(`self`) — Line 89, Complexity: 1
- **test_falls_back_when_llm_lacks_pdf_method**(`self`) — Line 103, Complexity: 1
- **test_protocol_has_pdf_method**(`self`) — Line 121, Complexity: 1

### `backend\tests\unit\test_graceful_shutdown.py`
- **test_shutdown_event_stops_processing**(`self`) — Line 24, Complexity: 1
- **test_call_soon_threadsafe_sets_event**(`self`) — Line 34, Complexity: 1
- **test_workers_check_shutdown_event**(`self`) — Line 47, Complexity: 3
- **test_shutdown_event_with_multiple_workers**(`self`) — Line 74, Complexity: 2
- **mock_worker**(`items`) — Line 52, Complexity: 3
- **trigger_shutdown**(`0 args`) — Line 60, Complexity: 1
- **mock_worker**(`worker_id`) — Line 79, Complexity: 2
- **trigger_shutdown**(`0 args`) — Line 84, Complexity: 1

### `backend\tests\unit\test_graph_retry.py`
- **_make_db**(`0 args`) — Line 20, Complexity: 1
- **test_inserts_row_with_correct_params**(`self`) — Line 34, Complexity: 1
- **test_truncates_error_to_500_chars**(`self`) — Line 51, Complexity: 1
- **test_short_error_not_truncated**(`self`) — Line 62, Complexity: 1
- **test_returns_cases_under_max_retries**(`self`) — Line 79, Complexity: 1
- **test_returns_empty_list_when_no_pending**(`self`) — Line 99, Complexity: 1
- **test_default_max_retries_is_3**(`self`) — Line 110, Complexity: 1
- **test_deletes_row_for_case**(`self`) — Line 129, Complexity: 1
- **test_updates_retry_count**(`self`) — Line 149, Complexity: 1

### `backend\tests\unit\test_graph_routes.py`
- **app**(`0 args`) — Line 30, Complexity: 1
- **client**(`app`) — Line 37, Complexity: 1
- **_mock_graph_store**(`0 args`) — Line 46, Complexity: 1
- **test_neighborhood_returns_nodes_and_edges**(`self, mock_get_graph, client`) — Line 61, Complexity: 1
- **test_neighborhood_with_depth_param**(`self, mock_get_graph, client`) — Line 118, Complexity: 1
- **test_neighborhood_graph_error_returns_empty**(`self, mock_get_graph, client`) — Line 134, Complexity: 1
- **test_chain_returns_forward_citations**(`self, mock_get_graph, client`) — Line 156, Complexity: 1
- **test_chain_with_max_depth**(`self, mock_get_graph, client`) — Line 199, Complexity: 1
- **test_chain_graph_error_returns_empty**(`self, mock_get_graph, client`) — Line 214, Complexity: 1
- **test_authorities_returns_most_cited**(`self, mock_get_graph, client`) — Line 236, Complexity: 1
- **test_authorities_respects_limit**(`self, mock_get_graph, client`) — Line 268, Complexity: 1
- **test_authorities_graph_error_returns_empty**(`self, mock_get_graph, client`) — Line 283, Complexity: 1
- **test_stats_returns_global_stats**(`self, mock_get_graph, mock_get_redis, client`) — Line 306, Complexity: 1
- **test_stats_uses_cache**(`self, mock_get_graph, mock_get_redis, client`) — Line 345, Complexity: 1
- **test_stats_graph_error_returns_zeros**(`self, mock_get_graph, mock_get_redis, client`) — Line 376, Complexity: 1
- **test_depth_parameter_rejects_zero**(`self, client`) — Line 402, Complexity: 1
- **test_depth_parameter_rejects_above_max**(`self, client`) — Line 407, Complexity: 1
- **test_chain_max_depth_rejects_zero**(`self, client`) — Line 412, Complexity: 1
- **test_chain_max_depth_rejects_above_max**(`self, client`) — Line 417, Complexity: 1
- **test_authorities_limit_rejects_zero**(`self, client`) — Line 422, Complexity: 1
- **test_authorities_limit_rejects_above_max**(`self, client`) — Line 427, Complexity: 1
- **test_all_graph_endpoints_present**(`self`) — Line 439, Complexity: 1
- **test_all_endpoints_are_get**(`self`) — Line 447, Complexity: 3

### `backend\tests\unit\test_graph_traversal.py`
- **_make_graph_store**(`query_return, get_node_return, raise_on_query`) — Line 23, Complexity: 3
- **test_empty_graph**(`self`) — Line 50, Complexity: 1
- **test_with_neighbors**(`self`) — Line 60, Complexity: 1
- **test_depth_capped_at_3**(`self`) — Line 93, Complexity: 1
- **test_deduplicates_edges**(`self`) — Line 102, Complexity: 1
- **test_handles_connection_error**(`self`) — Line 126, Complexity: 1
- **test_empty_chain**(`self`) — Line 142, Complexity: 1
- **test_with_citations**(`self`) — Line 151, Complexity: 1
- **test_max_depth_capped_at_5**(`self`) — Line 173, Complexity: 1
- **test_handles_runtime_error**(`self`) — Line 181, Complexity: 1
- **test_returns_authorities**(`self`) — Line 197, Complexity: 1
- **test_empty_result**(`self`) — Line 226, Complexity: 1
- **test_handles_connection_error**(`self`) — Line 232, Complexity: 1
- **test_returns_stats**(`self`) — Line 247, Complexity: 1
- **test_connection_error_returns_zeros**(`self`) — Line 266, Complexity: 1
- **test_uses_redis_cache**(`self`) — Line 273, Complexity: 1
- **test_caches_result_in_redis**(`self`) — Line 287, Complexity: 1

### `backend\tests\unit\test_health_extended.py`
- **_build_app**(`user`) — Line 22, Complexity: 1
- **_healthy_dep**(`response_ms`) — Line 43, Complexity: 1
- **_unhealthy_dep**(`error`) — Line 47, Complexity: 1
- **_override_user**(`0 args`) — Line 27, Complexity: 1
- **test_all_healthy**(`self, mock_pg, mock_redis, mock_pinecone, mock_neo4j, mock_gemini`) — Line 64, Complexity: 1
- **test_postgres_down_returns_503**(`self, mock_pg, mock_redis, mock_pinecone, mock_neo4j, mock_gemini`) — Line 96, Complexity: 1
- **test_neo4j_down_returns_degraded**(`self, mock_pg, mock_redis, mock_pinecone, mock_neo4j, mock_gemini`) — Line 126, Complexity: 1
- **test_includes_response_ms**(`self, mock_pg, mock_redis, mock_pinecone, mock_neo4j, mock_gemini`) — Line 156, Complexity: 2
- **test_unauthenticated_minimal_response**(`self, mock_pg, mock_redis, mock_pinecone, mock_neo4j, mock_gemini`) — Line 188, Complexity: 1

### `backend\tests\unit\test_hindi_fts_skip.py`
- **test_hindi_fts_returns_empty**(`self`) — Line 12, Complexity: 1
- **test_english_fts_requires_db**(`self`) — Line 22, Complexity: 1
- **test_default_language_is_english**(`self`) — Line 32, Complexity: 1

### `backend\tests\unit\test_hindi_search.py`
- **translator**(`0 args`) — Line 8, Complexity: 1
- **test_hindi_query_detected**(`self, translator`) — Line 29, Complexity: 1
- **test_english_query_detected**(`self, translator`) — Line 39, Complexity: 1
- **test_mixed_script_detection**(`self, translator`) — Line 49, Complexity: 1
- **test_translate_hindi_to_english**(`self, translator`) — Line 61, Complexity: 1
- **test_translate_english_to_hindi**(`self, translator`) — Line 80, Complexity: 1
- **test_empty_query_defaults_to_english**(`self, translator`) — Line 99, Complexity: 1

### `backend\tests\unit\test_hybrid_search.py`
- **_make_qu**(`strategy, expanded, original, filters`) — Line 32, Complexity: 3
- **_vector_result**(`case_id, score, text`) — Line 48, Complexity: 1
- **_fts_result**(`case_id, rank, snippet`) — Line 56, Complexity: 1
- **_db_row**(`case_id`) — Line 60, Complexity: 1
- **_mock_db_execute**(`rows, equiv_rows`) — Line 77, Complexity: 3
- **mock_llm**(`0 args`) — Line 98, Complexity: 1
- **mock_embedder**(`0 args`) — Line 103, Complexity: 1
- **mock_vector_store**(`0 args`) — Line 110, Complexity: 1
- **mock_reranker**(`0 args`) — Line 115, Complexity: 1
- **mock_db**(`0 args`) — Line 120, Complexity: 1
- **test_hybrid_search_balanced_strategy**(`mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 132, Complexity: 1
- **test_hybrid_search_exact_match_strategy**(`mock_uq, mock_exact, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 185, Complexity: 1
- **test_hybrid_search_empty_results**(`mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 220, Complexity: 1
- **test_rrf_merge_deduplication**(`0 args`) — Line 247, Complexity: 1
- **test_reranker_timeout_fallback**(`mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 275, Complexity: 1
- **test_redis_cache_hit**(`mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 319, Complexity: 1
- **test_redis_cache_miss**(`mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 365, Complexity: 1
- **test_pagination**(`mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 414, Complexity: 1
- **test_filters_applied_to_vector**(`mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 460, Complexity: 2
- **test_filters_applied_to_fts**(`mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 506, Complexity: 2
- **test_rrf_merge_lower_k_steeper_separation**(`0 args`) — Line 558, Complexity: 1
- **test_strategy_config_maps_correctly**(`0 args`) — Line 584, Complexity: 1
- **test_per_strategy_k_settings_exist**(`0 args`) — Line 617, Complexity: 1
- **_execute**(`sql, params`) — Line 82, Complexity: 2
- **test_search_result_item_has_treatment_warning_field**(`self`) — Line 638, Complexity: 1
- **test_treatment_warning_set_when_present**(`self`) — Line 643, Complexity: 1
- **test_overruled_snippet_triggers_warning**(`self, mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 655, Complexity: 1
- **test_neutral_snippet_no_warning**(`self, mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db`) — Line 690, Complexity: 1

### `backend\tests\unit\test_ik_worker.py`
- **_make_task**(`0 args`) — Line 9, Complexity: 1
- **mock_ik_client**(`0 args`) — Line 26, Complexity: 1
- **_mock_redis**(`0 args`) — Line 36, Complexity: 1
- **test_passes_boolean_query**(`self, mock_ik_client`) — Line 50, Complexity: 1
- **test_passes_court_filter**(`self, mock_ik_client`) — Line 61, Complexity: 1
- **test_passes_date_range**(`self, mock_ik_client`) — Line 72, Complexity: 1
- **test_passes_sort_by**(`self, mock_ik_client`) — Line 84, Complexity: 1
- **test_passes_title_filter**(`self, mock_ik_client`) — Line 95, Complexity: 1
- **test_passes_author_filter**(`self, mock_ik_client`) — Line 105, Complexity: 1
- **test_passes_bench_filter**(`self, mock_ik_client`) — Line 115, Complexity: 1
- **test_passes_maxcites**(`self, mock_ik_client`) — Line 125, Complexity: 1
- **test_extracts_rich_fields**(`self, mock_ik_client`) — Line 135, Complexity: 1
- **test_no_filters_still_works**(`self, mock_ik_client`) — Line 156, Complexity: 1
- **test_includes_court_copy_url**(`self, mock_ik_client`) — Line 167, Complexity: 1
- **test_returns_source_urls**(`self, mock_ik_client`) — Line 178, Complexity: 1
- **test_limits_fragment_calls**(`self`) — Line 194, Complexity: 1
- **test_results_without_fragments_still_included**(`self`) — Line 211, Complexity: 1
- **test_uses_search_headline_skips_fragment**(`self`) — Line 230, Complexity: 1
- **test_falls_back_to_fragment_when_headline_short**(`self`) — Line 252, Complexity: 1

### `backend\tests\unit\test_indiankanoon_client.py`
- **_mock_response**(`json_data`) — Line 11, Complexity: 1
- **mock_settings**(`0 args`) — Line 21, Complexity: 1
- **ik_client**(`mock_settings`) — Line 30, Complexity: 1
- **test_has_asyncio_lock**(`self, ik_client`) — Line 39, Complexity: 1
- **test_no_deprecated_get_event_loop**(`self, ik_client`) — Line 44, Complexity: 1
- **test_uses_settings_timeout**(`self, mock_settings`) — Line 51, Complexity: 2
- **test_search_uses_boolean_query**(`self, ik_client`) — Line 64, Complexity: 1
- **test_search_maps_court_codes**(`self, ik_client`) — Line 78, Complexity: 1
- **test_search_passes_date_params**(`self, ik_client`) — Line 88, Complexity: 1
- **test_search_passes_sort_by**(`self, ik_client`) — Line 99, Complexity: 1
- **test_search_uses_maxpages_param**(`self, ik_client`) — Line 109, Complexity: 1
- **test_search_single_page_no_maxpages**(`self, ik_client`) — Line 120, Complexity: 1
- **test_search_appends_title_filter**(`self, ik_client`) — Line 129, Complexity: 1
- **test_search_appends_cite_filter**(`self, ik_client`) — Line 137, Complexity: 1
- **test_search_appends_author_filter**(`self, ik_client`) — Line 145, Complexity: 1
- **test_search_appends_bench_filter**(`self, ik_client`) — Line 153, Complexity: 1
- **test_search_passes_maxcites**(`self, ik_client`) — Line 161, Complexity: 1
- **test_get_court_copy_calls_origdoc**(`self, ik_client`) — Line 170, Complexity: 1
- **test_court_codes_mapping**(`self`) — Line 181, Complexity: 1
- **test_court_codes_includes_all_courts**(`self`) — Line 191, Complexity: 4

### `backend\tests\unit\test_ingestion_integration.py`
- **_make_metadata**(`0 args`) — Line 61, Complexity: 1
- **test_chunks_have_section_types**(`self`) — Line 83, Complexity: 2
- **test_chunks_respect_size_limits**(`self`) — Line 93, Complexity: 2
- **test_chunks_have_case_id**(`self`) — Line 101, Complexity: 2
- **test_upsert_includes_case_metadata**(`self`) — Line 112, Complexity: 2
- **test_upsert_includes_section_type**(`self`) — Line 154, Complexity: 2
- **test_chunk_then_embed_produces_matching_counts**(`self`) — Line 187, Complexity: 1

### `backend\tests\unit\test_ingestion_pipeline.py`
- **_make_case_metadata**(`0 args`) — Line 30, Complexity: 1
- **_make_chunks**(`n, case_id`) — Line 54, Complexity: 1
- **_make_sections**(`0 args`) — Line 66, Complexity: 1
- **_make_embeddings**(`n`) — Line 73, Complexity: 1
- **mock_db**(`0 args`) — Line 84, Complexity: 1
- **mock_llm**(`0 args`) — Line 102, Complexity: 1
- **mock_embedder**(`0 args`) — Line 107, Complexity: 1
- **mock_vector_store**(`0 args`) — Line 115, Complexity: 1
- **mock_graph_store**(`0 args`) — Line 120, Complexity: 1
- **mock_storage**(`0 args`) — Line 125, Complexity: 1
- **test_pipeline_processes_document**(`self, mock_extract_and_score, mock_extract_meta_llm, mock_merge_meta, mock_validate, mock_validate_cross, mock_cross_validate_props, mock_insert_case, mock_detect_sections, mock_chunk, mock_embed_chunks, mock_upsert, mock_build_graph, mock_db, mock_llm, mock_embedder, mock_vector_store, mock_graph_store, mock_storage`) — Line 151, Complexity: 1
- **test_pipeline_handles_pdf_parse_failure**(`self, mock_extract_and_score, mock_record_failure, mock_db, mock_llm, mock_embedder, mock_vector_store, mock_graph_store, mock_storage`) — Line 224, Complexity: 1
- **test_pipeline_handles_embedding_failure**(`self, mock_extract_and_score, mock_extract_meta_llm, mock_merge_meta, mock_validate, mock_validate_cross, mock_insert_case, mock_detect_sections, mock_chunk, mock_embed_chunks, mock_upsert, mock_build_graph, mock_db, mock_llm, mock_embedder, mock_vector_store, mock_graph_store, mock_storage`) — Line 274, Complexity: 1
- **test_pipeline_handles_empty_text**(`self, mock_extract_and_score, mock_record_failure, mock_db, mock_llm, mock_embedder, mock_vector_store, mock_graph_store, mock_storage`) — Line 328, Complexity: 1
- **test_chunking_is_called_with_correct_params**(`self, mock_extract_and_score, mock_extract_meta_llm, mock_merge_meta, mock_validate, mock_validate_cross, mock_insert_case, mock_detect_sections, mock_chunk, mock_embed_chunks, mock_upsert, mock_build_graph, mock_db, mock_llm, mock_embedder, mock_vector_store, mock_graph_store, mock_storage`) — Line 374, Complexity: 1
- **test_embed_chunks_batches_correctly**(`self`) — Line 439, Complexity: 1
- **test_embed_chunks_empty_list**(`self`) — Line 463, Complexity: 1
- **test_safe_filename_normal**(`self`) — Line 474, Complexity: 1
- **test_safe_filename_empty_title**(`self`) — Line 479, Complexity: 1
- **test_safe_filename_long_title_truncated**(`self`) — Line 483, Complexity: 1

### `backend\tests\unit\test_ingestion_rate_limiter.py`
- **test_acquire_under_limit**(`self`) — Line 26, Complexity: 2
- **test_acquire_blocks_at_limit**(`self`) — Line 37, Complexity: 2
- **test_context_manager**(`self`) — Line 54, Complexity: 1
- **test_concurrent_acquire**(`self`) — Line 61, Complexity: 1
- **test_invalid_max_per_minute**(`self`) — Line 86, Complexity: 1
- **test_release_is_noop**(`self`) — Line 94, Complexity: 1
- **test_max_per_minute_property**(`self`) — Line 100, Complexity: 1
- **test_get_creates_limiter**(`self`) — Line 114, Complexity: 1
- **test_get_returns_same_limiter**(`self`) — Line 121, Complexity: 1
- **test_different_keys_get_different_limiters**(`self`) — Line 128, Complexity: 1
- **test_per_key_isolation**(`self`) — Line 136, Complexity: 2
- **test_invalid_rpm**(`self`) — Line 154, Complexity: 1
- **test_rpm_per_key_property**(`self`) — Line 159, Complexity: 1
- **_acquire_one**(`0 args`) — Line 68, Complexity: 1

### `backend\tests\unit\test_ingestion_sections.py`
- **test_extracts_scc_citation**(`self`) — Line 7, Complexity: 1
- **test_extracts_air_citation**(`self`) — Line 13, Complexity: 1
- **test_extracts_multiple_formats**(`self`) — Line 19, Complexity: 1
- **test_empty_text_returns_empty**(`self`) — Line 24, Complexity: 1

### `backend\tests\unit\test_judge_analytics.py`
- **_make_mock_session**(`0 args`) — Line 22, Complexity: 1
- **_mock_execute_returns**(`session`) — Line 28, Complexity: 3
- **test_list_judges_returns_paginated_result**(`self`) — Line 52, Complexity: 1
- **test_list_judges_with_search**(`self`) — Line 78, Complexity: 1
- **test_list_judges_empty_result**(`self`) — Line 95, Complexity: 1
- **test_list_judges_pagination**(`self`) — Line 108, Complexity: 1
- **test_returns_none_when_no_cases**(`self`) — Line 129, Complexity: 1
- **test_returns_profile_with_stats**(`self`) — Line 141, Complexity: 1
- **test_profile_bench_combinations**(`self`) — Line 214, Complexity: 1
- **test_returns_paginated_cases**(`self`) — Line 251, Complexity: 1
- **test_is_author_false_when_different_author**(`self`) — Line 284, Complexity: 1
- **test_empty_cases**(`self`) — Line 308, Complexity: 1
- **test_with_year_and_case_type_filters**(`self`) — Line 320, Complexity: 1
- **test_raises_for_single_judge**(`self`) — Line 352, Complexity: 1
- **test_raises_for_empty_list**(`self`) — Line 360, Complexity: 1
- **test_raises_for_more_than_three**(`self`) — Line 368, Complexity: 1
- **test_compare_two_judges**(`self`) — Line 378, Complexity: 1
- **test_compare_three_judges**(`self`) — Line 397, Complexity: 1
- **test_compare_with_unknown_judge_returns_none**(`self`) — Line 418, Complexity: 1
- **test_returns_none_when_no_cases**(`self`) — Line 439, Complexity: 1
- **test_returns_court_stats**(`self`) — Line 450, Complexity: 1
- **test_court_stats_empty_subcategories**(`self`) — Line 493, Complexity: 1
- **test_judge_list_item**(`self`) — Line 520, Complexity: 1
- **test_judge_profile_defaults**(`self`) — Line 525, Complexity: 1
- **test_paginated_result**(`self`) — Line 534, Complexity: 1
- **test_court_stats_defaults**(`self`) — Line 541, Complexity: 1
- **test_judge_case_item**(`self`) — Line 546, Complexity: 1

### `backend\tests\unit\test_judge_routes.py`
- **test_judges_routes_registered**(`0 args`) — Line 6, Complexity: 1
- **test_judge_route_ordering**(`0 args`) — Line 15, Complexity: 5
- **test_all_judge_endpoints_present**(`0 args`) — Line 36, Complexity: 2

### `backend\tests\unit\test_logging_config.py`
- **_make_record**(`self, msg`) — Line 17, Complexity: 2
- **test_produces_valid_json**(`self`) — Line 31, Complexity: 1
- **test_includes_severity**(`self`) — Line 38, Complexity: 1
- **test_includes_message**(`self`) — Line 44, Complexity: 1
- **test_includes_module**(`self`) — Line 50, Complexity: 1
- **test_includes_timestamp**(`self`) — Line 56, Complexity: 1
- **test_includes_exception_info**(`self`) — Line 64, Complexity: 2
- **test_includes_request_id_when_set**(`self`) — Line 86, Complexity: 1
- **test_excludes_request_id_when_not_set**(`self`) — Line 92, Complexity: 1
- **test_sets_correct_level**(`self, mock_settings`) — Line 103, Complexity: 1
- **test_uses_json_formatter_in_production**(`self, mock_settings`) — Line 111, Complexity: 1
- **test_uses_text_formatter_in_development**(`self, mock_settings`) — Line 120, Complexity: 1
- **test_silences_noisy_loggers**(`self, mock_settings`) — Line 129, Complexity: 2

### `backend\tests\unit\test_metadata.py`
- **test_cross_validate_synthesizes_ratio_from_propositions**(`0 args`) — Line 310, Complexity: 1
- **test_cross_validate_creates_proposition_from_ratio**(`0 args`) — Line 324, Complexity: 1
- **test_valid_metadata_unchanged**(`self`) — Line 19, Complexity: 1
- **test_impossible_year_cleared**(`self`) — Line 33, Complexity: 1
- **test_future_year_cleared**(`self`) — Line 38, Complexity: 1
- **test_valid_year_preserved**(`self`) — Line 44, Complexity: 1
- **test_invalid_date_format_cleared**(`self`) — Line 49, Complexity: 1
- **test_future_date_cleared**(`self`) — Line 54, Complexity: 1
- **test_invalid_bench_type_cleared**(`self`) — Line 59, Complexity: 1
- **test_valid_bench_type_normalized**(`self`) — Line 64, Complexity: 1
- **test_invalid_jurisdiction_cleared**(`self`) — Line 69, Complexity: 1
- **test_invalid_disposal_cleared**(`self`) — Line 74, Complexity: 1
- **test_disposal_title_cased**(`self`) — Line 79, Complexity: 1
- **test_non_list_judge_cleared**(`self`) — Line 84, Complexity: 1
- **test_court_normalized**(`self`) — Line 89, Complexity: 1
- **test_parquet_wins_for_title**(`self`) — Line 98, Complexity: 1
- **test_llm_fallback_for_title**(`self`) — Line 104, Complexity: 1
- **test_llm_wins_for_ratio**(`self`) — Line 110, Complexity: 1
- **test_judge_from_comma_string**(`self`) — Line 116, Complexity: 1
- **test_nc_display_stored_as_case_number_not_case_type**(`self`) — Line 123, Complexity: 1
- **test_empty_parquet_and_llm**(`self`) — Line 131, Complexity: 1
- **test_curative_petition**(`self`) — Line 140, Complexity: 1
- **test_miscellaneous_application**(`self`) — Line 144, Complexity: 1
- **test_arbitration_petition**(`self`) — Line 148, Complexity: 1
- **test_suo_motu**(`self`) — Line 152, Complexity: 1
- **test_election_petition**(`self`) — Line 155, Complexity: 1
- **test_slp_civil_criminal**(`self`) — Line 158, Complexity: 1
- **test_appeal_abbreviations**(`self`) — Line 162, Complexity: 1
- **test_interlocutory_application**(`self`) — Line 166, Complexity: 1
- **test_letters_patent_appeal**(`self`) — Line 170, Complexity: 1
- **test_existing_types_still_work**(`self`) — Line 174, Complexity: 1
- **test_year_synced_from_decision_date**(`self`) — Line 183, Complexity: 1
- **test_bench_type_cleared_when_single_with_many_judges**(`self`) — Line 188, Complexity: 1
- **test_bench_type_single_with_one_judge_preserved**(`self`) — Line 196, Complexity: 1
- **test_author_judge_not_in_list_warns**(`self, caplog`) — Line 204, Complexity: 1
- **test_author_judge_in_list_no_warning**(`self, caplog`) — Line 215, Complexity: 1
- **test_same_petitioner_respondent_clears_respondent**(`self`) — Line 224, Complexity: 1
- **test_different_petitioner_respondent_preserved**(`self`) — Line 232, Complexity: 1
- **test_writ_petition_criminal_warns**(`self, caplog`) — Line 240, Complexity: 1
- **test_ip_commercial_accepted**(`self`) — Line 253, Complexity: 1
- **test_ip_alias_normalized**(`self`) — Line 258, Complexity: 1
- **test_ip_commercial_mixed_case**(`self`) — Line 263, Complexity: 1
- **test_dr_justice_prefix**(`self`) — Line 272, Complexity: 1
- **test_dr_prefix**(`self`) — Line 276, Complexity: 1
- **test_smt_prefix**(`self`) — Line 280, Complexity: 1
- **test_shri_prefix**(`self`) — Line 284, Complexity: 1
- **test_existing_prefixes_still_work**(`self`) — Line 288, Complexity: 1
- **test_trailing_j_stripped**(`self`) — Line 292, Complexity: 1
- **test_initial_j_preserved**(`self`) — Line 296, Complexity: 1
- **test_multiple_judges_mixed_prefixes**(`self`) — Line 300, Complexity: 1

### `backend\tests\unit\test_metadata_llm_retry.py`
- **mock_llm**(`0 args`) — Line 27, Complexity: 1
- **test_successful_extraction**(`self, mock_llm`) — Line 36, Complexity: 1
- **test_transient_error_propagates**(`self, mock_llm`) — Line 51, Complexity: 1
- **test_runtime_error_propagates**(`self, mock_llm`) — Line 61, Complexity: 1
- **test_all_null_response_raises**(`self, mock_llm`) — Line 69, Complexity: 1
- **test_no_retry_on_value_error**(`self, mock_llm`) — Line 77, Complexity: 1
- **test_no_retry_on_key_error**(`self, mock_llm`) — Line 87, Complexity: 1
- **test_headnotes_list_converted_to_json**(`self, mock_llm`) — Line 97, Complexity: 1
- **test_unknown_fields_filtered_out**(`self, mock_llm`) — Line 112, Complexity: 1

### `backend\tests\unit\test_metadata_v2.py`
- **test_new_fields_have_none_defaults**(`self`) — Line 9, Complexity: 1
- **test_enrichment_status_defaults_to_flash_only**(`self`) — Line 34, Complexity: 1
- **test_arguments_raised_can_store_structured_data**(`self`) — Line 38, Complexity: 1
- **test_citation_treatments_structure**(`self`) — Line 53, Complexity: 1

### `backend\tests\unit\test_metadata_v2_prompts.py`
- **test_field_in_schema**(`self, field`) — Line 23, Complexity: 1
- **test_field_in_required**(`self, field`) — Line 37, Complexity: 1
- **test_system_prompt_mentions_arguments**(`self`) — Line 40, Complexity: 1
- **test_system_prompt_mentions_operative_order**(`self`) — Line 43, Complexity: 1
- **test_system_prompt_mentions_judicial_tone**(`self`) — Line 46, Complexity: 1
- **test_system_prompt_mentions_citation_treatments**(`self`) — Line 49, Complexity: 1
- **test_user_prompt_mentions_v2_fields**(`self`) — Line 52, Complexity: 1
- **test_schema_arguments_raised_is_array**(`self`) — Line 58, Complexity: 1
- **test_schema_judicial_tone_has_enum**(`self`) — Line 62, Complexity: 1

### `backend\tests\unit\test_migration_011.py`
- **_columns**(`self`) — Line 14, Complexity: 1
- **test_case_number_column_exists**(`self`) — Line 18, Complexity: 1
- **test_is_reportable_column_exists**(`self`) — Line 21, Complexity: 1
- **test_headnotes_column_exists**(`self`) — Line 24, Complexity: 1
- **test_outcome_summary_column_exists**(`self`) — Line 27, Complexity: 1
- **test_ingestion_status_column_exists**(`self`) — Line 30, Complexity: 1
- **test_coram_size_column_exists**(`self`) — Line 34, Complexity: 1
- **test_coram_size_is_integer**(`self`) — Line 37, Complexity: 1
- **test_coram_size_nullable**(`self`) — Line 41, Complexity: 1
- **test_lower_court_column_exists**(`self`) — Line 46, Complexity: 1
- **test_lower_court_case_number_column_exists**(`self`) — Line 49, Complexity: 1
- **test_appeal_from_column_exists**(`self`) — Line 52, Complexity: 1
- **test_appellate_columns_nullable**(`self`) — Line 55, Complexity: 2
- **test_opinion_type_column_exists**(`self`) — Line 61, Complexity: 1
- **test_dissenting_judges_column_exists**(`self`) — Line 64, Complexity: 1
- **test_concurring_judges_column_exists**(`self`) — Line 67, Complexity: 1
- **test_split_ratio_column_exists**(`self`) — Line 70, Complexity: 1
- **test_dissenting_judges_is_array**(`self`) — Line 73, Complexity: 2
- **test_concurring_judges_is_array**(`self`) — Line 77, Complexity: 2
- **test_petitioner_type_column_exists**(`self`) — Line 82, Complexity: 1
- **test_respondent_type_column_exists**(`self`) — Line 85, Complexity: 1
- **test_is_pil_column_exists**(`self`) — Line 88, Complexity: 1
- **test_is_pil_is_boolean**(`self`) — Line 91, Complexity: 1
- **test_companion_cases_column_exists**(`self`) — Line 96, Complexity: 1
- **test_companion_cases_is_array**(`self`) — Line 99, Complexity: 2
- **test_set_coram_size**(`self`) — Line 107, Complexity: 1
- **test_set_opinion_type**(`self`) — Line 111, Complexity: 1
- **test_set_appellate_chain**(`self`) — Line 115, Complexity: 1
- **test_set_split_tracking**(`self`) — Line 127, Complexity: 1
- **test_set_party_types**(`self`) — Line 139, Complexity: 1
- **test_set_companion_cases**(`self`) — Line 151, Complexity: 1
- **test_set_migration_009_columns**(`self`) — Line 159, Complexity: 1
- **test_new_columns_default_to_none**(`self`) — Line 173, Complexity: 1
- **_load_migration**(`self`) — Line 188, Complexity: 1
- **test_revision_id**(`self`) — Line 193, Complexity: 1
- **test_down_revision**(`self`) — Line 196, Complexity: 1
- **test_has_upgrade_function**(`self`) — Line 199, Complexity: 1
- **test_has_downgrade_function**(`self`) — Line 202, Complexity: 1
- **test_upgrade_adds_all_columns**(`self`) — Line 205, Complexity: 2
- **test_upgrade_adds_check_constraints**(`self`) — Line 235, Complexity: 1
- **test_upgrade_expands_disposal_nature**(`self`) — Line 253, Complexity: 1
- **test_downgrade_drops_all_columns**(`self`) — Line 273, Complexity: 2
- **test_downgrade_restores_original_disposal_nature**(`self`) — Line 302, Complexity: 1

### `backend\tests\unit\test_multi_court_filter.py`
- **test_court_default_none**(`self`) — Line 22, Complexity: 1
- **test_court_single_item_list**(`self`) — Line 26, Complexity: 1
- **test_court_multiple_items**(`self`) — Line 30, Complexity: 1
- **_build_pinecone_filter**(`filters`) — Line 48, Complexity: 3
- **test_no_court_filter**(`self`) — Line 58, Complexity: 1
- **test_single_court_uses_eq**(`self`) — Line 62, Complexity: 1
- **test_multiple_courts_uses_in**(`self`) — Line 68, Complexity: 1
- **test_three_courts_uses_in**(`self`) — Line 73, Complexity: 1
- **test_single_court_ilike**(`self`) — Line 92, Complexity: 1
- **test_two_courts_or_clause**(`self`) — Line 99, Complexity: 1
- **test_three_courts_or_clause**(`self`) — Line 112, Complexity: 2
- **test_multi_court_with_other_filters**(`self`) — Line 121, Complexity: 1
- **test_no_court_filter_unchanged**(`self`) — Line 134, Complexity: 1
- **test_llm_court_string_wrapped_in_list**(`self`) — Line 150, Complexity: 1
- **test_llm_no_court_stays_none**(`self`) — Line 162, Complexity: 1
- **test_llm_empty_court_stays_none**(`self`) — Line 174, Complexity: 1
- **_parse_court_param**(`court`) — Line 196, Complexity: 1
- **test_none_returns_none**(`self`) — Line 204, Complexity: 1
- **test_single_court**(`self`) — Line 207, Complexity: 1
- **test_two_courts_comma_separated**(`self`) — Line 211, Complexity: 1
- **test_courts_with_spaces_around_commas**(`self`) — Line 217, Complexity: 1
- **test_trailing_comma_ignored**(`self`) — Line 223, Complexity: 1
- **test_empty_string_returns_none**(`self`) — Line 227, Complexity: 1

### `backend\tests\unit\test_neo4j_store.py`
- **test_validate_label_accepts_known**(`0 args`) — Line 6, Complexity: 1
- **test_validate_label_rejects_unknown**(`0 args`) — Line 11, Complexity: 1
- **test_validate_label_rejects_injection**(`0 args`) — Line 16, Complexity: 1
- **test_validate_relationship_accepts_known**(`0 args`) — Line 21, Complexity: 1
- **test_validate_relationship_rejects_injection**(`0 args`) — Line 27, Complexity: 1
- **test_validate_relationship_rejects_unknown**(`0 args`) — Line 32, Complexity: 1

### `backend\tests\unit\test_pdf_extraction.py`
- **test_clean_extracted_text_removes_ligatures**(`self`) — Line 25, Complexity: 2
- **test_clean_extracted_text_removes_zero_width_chars**(`self`) — Line 43, Complexity: 1
- **test_clean_extracted_text_removes_page_numbers**(`self`) — Line 63, Complexity: 1
- **test_clean_extracted_text_removes_repeated_headers**(`self`) — Line 87, Complexity: 2
- **test_clean_extracted_text_normalizes_whitespace**(`self`) — Line 112, Complexity: 1
- **test_clean_extracted_text_preserves_legal_content**(`self`) — Line 127, Complexity: 1
- **test_smart_page_join_continues_paragraph**(`self`) — Line 148, Complexity: 1
- **test_smart_page_join_respects_paragraph_break**(`self`) — Line 160, Complexity: 1
- **test_smart_page_join_single_page**(`self`) — Line 171, Complexity: 1
- **test_smart_page_join_empty_list**(`self`) — Line 177, Complexity: 1
- **test_assess_extraction_quality_good**(`self`) — Line 185, Complexity: 1
- **test_assess_extraction_quality_poor**(`self`) — Line 198, Complexity: 1
- **test_assess_extraction_quality_returns_char_count**(`self`) — Line 206, Complexity: 1
- **test_assess_extraction_quality_empty_text**(`self`) — Line 212, Complexity: 1
- **test_extract_pdf_text_is_async**(`self`) — Line 222, Complexity: 1
- **test_extract_pdf_text_returns_coroutine**(`self`) — Line 228, Complexity: 1
- **test_hyphenated_word_rejoining**(`self`) — Line 241, Complexity: 1
- **test_hyphenated_word_rejoining_mid_word**(`self`) — Line 251, Complexity: 1
- **test_hyphen_not_rejoined_when_next_starts_uppercase**(`self`) — Line 261, Complexity: 2
- **test_hyphen_not_rejoined_when_next_starts_digit**(`self`) — Line 272, Complexity: 1
- **test_removes_lines_on_3_plus_pages**(`self`) — Line 287, Complexity: 3
- **test_first_occurrence_preserved**(`self`) — Line 305, Complexity: 1
- **test_fewer_than_3_pages_unchanged**(`self`) — Line 319, Complexity: 1
- **test_unique_lines_not_removed**(`self`) — Line 328, Complexity: 1
- **test_boilerplate_patterns_removed**(`self`) — Line 338, Complexity: 1

### `backend\tests\unit\test_pdf_ocr_and_password.py`
- **test_ocr_triggered_when_page_text_short**(`self`) — Line 18, Complexity: 1
- **test_ocr_not_triggered_when_sufficient_text**(`self`) — Line 40, Complexity: 1
- **test_ocr_used_only_when_better_than_pdfplumber**(`self`) — Line 60, Complexity: 1
- **test_multi_page_selective_ocr**(`self`) — Line 82, Complexity: 1
- **test_password_protected_returns_empty**(`self`) — Line 111, Complexity: 1
- **test_password_protected_does_not_raise**(`self`) — Line 123, Complexity: 1
- **test_os_error_returns_empty**(`self`) — Line 134, Complexity: 1
- **test_max_pages_exceeded_returns_empty**(`self`) — Line 143, Complexity: 1

### `backend\tests\unit\test_pdf_page_map.py`
- **test_page_map_field_exists**(`self`) — Line 9, Complexity: 1
- **test_page_map_default_empty**(`self`) — Line 18, Complexity: 1
- **test_page_map_char_ranges_are_contiguous**(`self`) — Line 25, Complexity: 2
- **test_simple_two_pages**(`self`) — Line 38, Complexity: 1
- **test_empty_page_skipped**(`self`) — Line 51, Complexity: 1
- **test_single_page**(`self`) — Line 58, Complexity: 1

### `backend\tests\unit\test_pdf_quality_scoring.py`
- **test_high_tier_with_legal_text**(`self`) — Line 22, Complexity: 1
- **test_medium_tier_moderate_text**(`self`) — Line 36, Complexity: 1
- **test_low_tier_short_text**(`self`) — Line 48, Complexity: 1
- **test_low_tier_empty_text**(`self`) — Line 55, Complexity: 1
- **test_low_alpha_ratio_forces_low_tier**(`self`) — Line 62, Complexity: 1
- **test_low_chars_per_page_forces_low_tier**(`self`) — Line 71, Complexity: 1
- **test_chars_per_page_not_checked_when_zero_pages**(`self`) — Line 81, Complexity: 1
- **test_ocr_used_flag_recorded**(`self`) — Line 89, Complexity: 1
- **test_page_count_recorded**(`self`) — Line 96, Complexity: 1
- **test_returns_text_quality_dataclass**(`self`) — Line 101, Complexity: 1
- **test_keyword_counting**(`self`) — Line 110, Complexity: 1
- **test_extract_and_score_returns_text_quality**(`self`) — Line 122, Complexity: 1
- **test_extract_and_score_falls_back_to_ocr**(`self`) — Line 142, Complexity: 1
- **test_extract_and_score_empty_extraction**(`self`) — Line 164, Complexity: 1
- **test_extract_and_score_sufficient_pdfplumber_text**(`self`) — Line 182, Complexity: 1

### `backend\tests\unit\test_pg_graph_store.py`
- **test_validate_label_accepts_known**(`0 args`) — Line 21, Complexity: 1
- **test_validate_label_rejects_unknown**(`0 args`) — Line 26, Complexity: 1
- **test_validate_label_rejects_injection**(`0 args`) — Line 31, Complexity: 1
- **test_validate_relationship_accepts_known**(`0 args`) — Line 36, Complexity: 1
- **test_validate_relationship_rejects_injection**(`0 args`) — Line 42, Complexity: 1
- **test_validate_relationship_rejects_unknown**(`0 args`) — Line 47, Complexity: 1
- **test_create_case_node_existing**(`self, mock_factory`) — Line 62, Complexity: 1
- **test_create_node_rejects_invalid_label**(`self`) — Line 79, Complexity: 1
- **test_create_node_requires_id**(`self`) — Line 85, Complexity: 1
- **test_create_non_case_node_returns_id**(`self, mock_factory`) — Line 92, Complexity: 1
- **test_get_existing_node**(`self, mock_factory`) — Line 104, Complexity: 1
- **test_get_nonexistent_node**(`self, mock_factory`) — Line 127, Complexity: 1
- **test_batch_create_citation_edges**(`self, mock_factory`) — Line 146, Complexity: 1
- **test_batch_create_empty_edges**(`self, mock_factory`) — Line 168, Complexity: 1
- **test_delete_node_removes_edges**(`self, mock_factory`) — Line 180, Complexity: 1
- **test_delete_node_no_edges**(`self, mock_factory`) — Line 196, Complexity: 1
- **test_get_neighbors_clamps_depth**(`self, mock_factory`) — Line 216, Complexity: 1
- **test_get_neighbors_validates_relationship**(`self`) — Line 233, Complexity: 1
- **test_ensure_constraints_noop**(`self`) — Line 243, Complexity: 1

### `backend\tests\unit\test_pgvector_store.py`
- **test_eq_filter**(`self`) — Line 22, Complexity: 1
- **test_gte_lte_filter**(`self`) — Line 28, Complexity: 1
- **test_in_filter_single_element**(`self`) — Line 38, Complexity: 1
- **test_in_filter_multiple_elements**(`self`) — Line 46, Complexity: 1
- **test_bare_value_filter**(`self`) — Line 55, Complexity: 1
- **test_ne_filter**(`self`) — Line 61, Complexity: 1
- **test_empty_filters**(`self`) — Line 67, Complexity: 1
- **test_combined_filters**(`self`) — Line 72, Complexity: 1
- **mock_session**(`self`) — Line 90, Complexity: 1
- **test_search_returns_results**(`self, mock_settings, mock_factory`) — Line 99, Complexity: 1
- **test_search_with_user_scope**(`self, mock_settings, mock_factory`) — Line 128, Complexity: 2
- **test_search_returns_empty_on_error**(`self, mock_settings, mock_factory`) — Line 150, Complexity: 1
- **test_upsert_empty_vectors**(`self, mock_settings, mock_factory`) — Line 170, Complexity: 1
- **test_upsert_calls_execute**(`self, mock_settings, mock_factory`) — Line 179, Complexity: 1
- **test_delete_by_metadata_without_exclude**(`self, mock_settings, mock_factory`) — Line 207, Complexity: 1
- **test_delete_by_metadata_with_exclude**(`self, mock_settings, mock_factory`) — Line 228, Complexity: 1

### `backend\tests\unit\test_phase5_models.py`
- **test_status_values_include_new_states**(`self`) — Line 11, Complexity: 3
- **test_has_processing_fields**(`self`) — Line 21, Complexity: 1
- **test_table_name**(`self`) — Line 29, Complexity: 1
- **test_has_required_columns**(`self`) — Line 32, Complexity: 1
- **test_document_id_is_unique**(`self`) — Line 41, Complexity: 1
- **test_repr**(`self`) — Line 45, Complexity: 1
- **test_table_name**(`self`) — Line 52, Complexity: 1
- **test_has_required_columns**(`self`) — Line 55, Complexity: 1
- **test_unique_constraint_case_language**(`self`) — Line 64, Complexity: 2
- **test_status_check_constraint**(`self`) — Line 72, Complexity: 2

### `backend\tests\unit\test_phase5_prompts.py`
- **test_issue_extraction_system_not_empty**(`self`) — Line 17, Complexity: 1
- **test_issue_extraction_user_has_placeholder**(`self`) — Line 20, Complexity: 1
- **test_issue_extraction_schema_has_required_fields**(`self`) — Line 23, Complexity: 1
- **test_issue_extraction_schema_issues_structure**(`self`) — Line 29, Complexity: 1
- **test_counter_arguments_user_has_placeholders**(`self`) — Line 34, Complexity: 1
- **test_research_memo_user_has_all_placeholders**(`self`) — Line 38, Complexity: 2
- **test_audio_summary_system_mentions_word_count**(`self`) — Line 47, Complexity: 1
- **test_audio_summary_user_has_placeholders**(`self`) — Line 50, Complexity: 2
- **test_audio_summary_system_mentions_spoken_delivery**(`self`) — Line 54, Complexity: 1

### `backend\tests\unit\test_pinecone_store_tenant.py`
- **mock_index**(`self`) — Line 14, Complexity: 1
- **test_search_without_user_scope**(`self, mock_pc_cls, mock_settings, mock_index`) — Line 26, Complexity: 2
- **test_search_with_user_scope**(`self, mock_pc_cls, mock_settings, mock_index`) — Line 42, Complexity: 2
- **test_search_with_user_scope_merges_filters**(`self, mock_pc_cls, mock_settings, mock_index`) — Line 58, Complexity: 2

### `backend\tests\unit\test_pipeline_citation_equivalents.py`
- **test_extracts_scc_citation_from_header**(`self`) — Line 21, Complexity: 1
- **test_only_header_citations_extracted**(`self`) — Line 36, Complexity: 1
- **test_empty_text_returns_empty**(`self`) — Line 51, Complexity: 1
- **test_no_citations_returns_empty**(`self`) — Line 55, Complexity: 1
- **test_result_structure**(`self`) — Line 60, Complexity: 1
- **test_creates_equivalent_to_edges**(`self`) — Line 76, Complexity: 1
- **test_skips_when_no_primary_citation**(`self`) — Line 97, Complexity: 1
- **test_skips_when_no_equivalents**(`self`) — Line 104, Complexity: 1
- **test_skips_when_all_equivalents_match_primary**(`self`) — Line 111, Complexity: 1
- **test_handles_graph_store_error_gracefully**(`self`) — Line 121, Complexity: 1

### `backend\tests\unit\test_pipeline_dedup.py`
- **test_dedup_check_uses_for_update_skip_locked**(`self`) — Line 10, Complexity: 1

### `backend\tests\unit\test_pipeline_pinecone_metadata.py`
- **_make_chunk**(`text, chunk_index, case_id`) — Line 15, Complexity: 1
- **_make_metadata**(`0 args`) — Line 24, Complexity: 1
- **test_truncation_warning_logged_when_chunk_exceeds_2000**(`caplog`) — Line 34, Complexity: 1
- **test_upserted_text_capped_at_2000**(`0 args`) — Line 50, Complexity: 1
- **test_no_warning_when_chunk_within_limit**(`caplog`) — Line 66, Complexity: 1

### `backend\tests\unit\test_pipeline_transaction.py`
- **_fake_begin**(`0 args`) — Line 18, Complexity: 1
- **_make_db_mock**(`0 args`) — Line 23, Complexity: 1
- **_make_metadata_mock**(`0 args`) — Line 37, Complexity: 1
- **_make_quality_mock**(`0 args`) — Line 57, Complexity: 1
- **_common_patches**(`fake_case_id`) — Line 67, Complexity: 1
- **_run_pipeline**(`db`) — Line 127, Complexity: 1
- **test_begin_nested_called_for_status_update**(`self`) — Line 145, Complexity: 1
- **test_status_update_inside_begin_nested_block**(`self`) — Line 163, Complexity: 3
- **tracking_begin**(`0 args`) — Line 172, Complexity: 1
- **tracking_execute**(`0 args`) — Line 183, Complexity: 3

### `backend\tests\unit\test_pipeline_treatment.py`
- **_make_case_metadata**(`0 args`) — Line 25, Complexity: 1
- **_make_citation**(`raw_text, reporter`) — Line 49, Complexity: 1
- **test_treatment_detected_for_each_citation**(`mock_detect, mock_extract`) — Line 68, Complexity: 1
- **test_default_referred_to_when_no_treatment**(`mock_detect, mock_extract`) — Line 97, Complexity: 1
- **test_treatment_property_passed_to_graph_store**(`mock_detect, mock_extract`) — Line 123, Complexity: 1
- **test_highest_confidence_treatment_picked**(`mock_detect, mock_extract`) — Line 155, Complexity: 1
- **test_citation_not_found_in_text_defaults_referred_to**(`mock_detect, mock_extract`) — Line 183, Complexity: 1

### `backend\tests\unit\test_precedent_mapper.py`
- **_make_search_response**(`n`) — Line 11, Complexity: 1
- **test_maps_single_issue**(`self, mock_search`) — Line 41, Complexity: 1
- **test_maps_multiple_issues_in_parallel**(`self, mock_search`) — Line 61, Complexity: 1
- **test_includes_acts_in_query**(`self, mock_search`) — Line 84, Complexity: 1
- **test_handles_search_failure_gracefully**(`self, mock_search`) — Line 104, Complexity: 1
- **test_respects_max_per_issue**(`self, mock_search`) — Line 123, Complexity: 1

### `backend\tests\unit\test_precedent_strength.py`
- **test_sc_is_binding_everywhere**(`self`) — Line 12, Complexity: 1
- **test_same_hc_equal_bench_is_binding**(`self`) — Line 21, Complexity: 1
- **test_same_hc_smaller_bench_is_persuasive**(`self`) — Line 30, Complexity: 1
- **test_different_hc_is_persuasive**(`self`) — Line 40, Complexity: 1
- **test_tribunal_is_persuasive**(`self`) — Line 49, Complexity: 1
- **test_constitution_bench_binds_division_bench**(`self`) — Line 58, Complexity: 1
- **test_no_target_defaults_to_general**(`self`) — Line 68, Complexity: 1
- **test_unknown_court_returns_persuasive**(`self`) — Line 82, Complexity: 1
- **test_none_year_returns_one**(`self`) — Line 94, Complexity: 1
- **test_current_year_returns_one**(`self`) — Line 98, Complexity: 1
- **test_recent_year_high_weight**(`self`) — Line 102, Complexity: 1
- **test_old_year_low_weight**(`self`) — Line 107, Complexity: 1
- **test_future_year_returns_one**(`self`) — Line 112, Complexity: 1
- **test_binding_not_overruled_recent**(`self`) — Line 120, Complexity: 1
- **test_binding_overruled_heavy_penalty**(`self`) — Line 127, Complexity: 1
- **test_binding_overruled_full_confidence**(`self`) — Line 135, Complexity: 1
- **test_persuasive_not_overruled**(`self`) — Line 142, Complexity: 1
- **test_distinguishable_not_overruled_old**(`self`) — Line 149, Complexity: 1
- **test_overruled_enum_value**(`self`) — Line 157, Complexity: 1
- **test_none_year_no_recency_penalty**(`self`) — Line 164, Complexity: 1
- **test_result_clamped_to_zero_one**(`self`) — Line 171, Complexity: 1

### `backend\tests\unit\test_provider_contracts.py`
- **_get_protocol_methods**(`protocol_cls`) — Line 22, Complexity: 3
- **test_gemini_llm_has_required_methods**(`self`) — Line 34, Complexity: 2
- **test_gemini_llm_is_runtime_checkable**(`self`) — Line 43, Complexity: 2
- **test_pinecone_store_has_required_methods**(`self`) — Line 58, Complexity: 2
- **test_neo4j_graph_has_required_methods**(`self`) — Line 71, Complexity: 2
- **test_cohere_reranker_has_required_methods**(`self`) — Line 84, Complexity: 2
- **test_gemini_embedder_has_required_methods**(`self`) — Line 97, Complexity: 2
- **test_local_storage_has_required_methods**(`self`) — Line 110, Complexity: 2

### `backend\tests\unit\test_provider_switching.py`
- **test_pgvector_provider_selected**(`self, mock_settings`) — Line 21, Complexity: 1
- **test_pinecone_provider_selected**(`self, mock_settings`) — Line 34, Complexity: 1
- **test_unknown_vector_provider_raises**(`self, mock_settings`) — Line 48, Complexity: 1
- **test_postgresql_provider_selected**(`self, mock_settings`) — Line 63, Complexity: 1
- **test_neo4j_provider_selected**(`self, mock_settings`) — Line 74, Complexity: 2
- **test_unknown_graph_provider_raises**(`self, mock_settings`) — Line 96, Complexity: 1

### `backend\tests\unit\test_query_understanding.py`
- **test_basic_passthrough**(`self`) — Line 18, Complexity: 1
- **test_empty_query_passthrough**(`self`) — Line 27, Complexity: 1
- **test_full_result**(`self`) — Line 36, Complexity: 1
- **test_minimal_result**(`self`) — Line 70, Complexity: 1
- **test_citation_lookup_intent**(`self`) — Line 85, Complexity: 1
- **test_fallback_on_llm_failure**(`self`) — Line 110, Complexity: 1
- **test_successful_llm_call**(`self`) — Line 129, Complexity: 1
- **generate_structured**(`self`) — Line 114, Complexity: 1
- **generate**(`self`) — Line 117, Complexity: 1
- **stream**(`self`) — Line 120, Complexity: 1
- **generate_structured**(`self`) — Line 133, Complexity: 1
- **generate**(`self`) — Line 149, Complexity: 1
- **stream**(`self`) — Line 152, Complexity: 1

### `backend\tests\unit\test_rag.py`
- **test_short_question**(`self`) — Line 22, Complexity: 1
- **test_long_question_truncated**(`self`) — Line 25, Complexity: 1
- **test_exactly_80_chars**(`self`) — Line 31, Complexity: 1
- **test_whitespace_stripped**(`self`) — Line 35, Complexity: 1
- **test_empty_sources**(`self`) — Line 42, Complexity: 1
- **test_single_source**(`self`) — Line 46, Complexity: 1
- **test_multiple_sources_numbered**(`self`) — Line 63, Complexity: 1
- **test_missing_fields_have_defaults**(`self`) — Line 74, Complexity: 1
- **test_overruled_language_triggers_warning**(`self`) — Line 86, Complexity: 1
- **test_per_incuriam_triggers_warning**(`self`) — Line 103, Complexity: 1
- **test_no_warning_for_neutral_text**(`self`) — Line 119, Complexity: 1
- **test_no_warning_when_no_text**(`self`) — Line 136, Complexity: 1
- **test_empty_history**(`self`) — Line 148, Complexity: 1
- **test_single_user_message**(`self`) — Line 151, Complexity: 1
- **test_user_and_assistant**(`self`) — Line 157, Complexity: 1
- **test_multiple_turns_preserved_order**(`self`) — Line 166, Complexity: 1
- **test_creation**(`self`) — Line 181, Complexity: 1
- **test_session_event**(`self`) — Line 186, Complexity: 1
- **test_source_event**(`self`) — Line 191, Complexity: 1
- **test_defaults**(`self`) — Line 202, Complexity: 1
- **test_immutable**(`self`) — Line 211, Complexity: 1
- **test_encrypt_then_safe_decrypt_roundtrip**(`self`) — Line 220, Complexity: 1
- **test_safe_decrypt_handles_plaintext**(`self`) — Line 228, Complexity: 1
- **test_safe_decrypt_handles_empty_string**(`self`) — Line 234, Complexity: 1
- **test_encrypt_produces_different_ciphertext_each_time**(`self`) — Line 239, Complexity: 1
- **test_calls_llm_generate_with_correct_prompt**(`self`) — Line 253, Complexity: 2
- **test_uses_last_four_messages**(`self`) — Line 274, Complexity: 1
- **test_strips_quotes_from_result**(`self`) — Line 301, Complexity: 1
- **test_fallback_on_llm_exception**(`self`) — Line 312, Complexity: 1
- **test_fallback_on_empty_result**(`self`) — Line 323, Complexity: 1
- **test_truncates_long_messages**(`self`) — Line 334, Complexity: 1
- **_make_sources**(`self, n, chunk_size`) — Line 354, Complexity: 1
- **_build_prompt**(`self, sources, history, question`) — Line 370, Complexity: 1
- **test_small_prompt_unchanged**(`self`) — Line 382, Complexity: 1
- **test_large_prompt_triggers_truncation**(`self`) — Line 393, Complexity: 1
- **test_max_prompt_chars_constant**(`self`) — Line 421, Complexity: 1

### `backend\tests\unit\test_rag_context.py`
- **_make_source**(`0 args`) — Line 12, Complexity: 1
- **test_includes_ratio_decidendi**(`self`) — Line 33, Complexity: 1
- **test_includes_bench_info**(`self`) — Line 40, Complexity: 1
- **test_includes_chunk_text**(`self`) — Line 48, Complexity: 1
- **test_empty_sources_returns_no_results_message**(`self`) — Line 55, Complexity: 1
- **test_missing_ratio_still_formats**(`self`) — Line 60, Complexity: 1
- **test_truncates_long_ratio**(`self`) — Line 69, Complexity: 1
- **test_truncates_long_chunk_text**(`self`) — Line 79, Complexity: 1
- **test_bench_labels_all_types**(`self`) — Line 87, Complexity: 2
- **test_unknown_bench_type_omits_label**(`self`) — Line 94, Complexity: 1
- **test_no_judge_names_omits_bench_line**(`self`) — Line 103, Complexity: 1
- **test_multiple_sources_numbered**(`self`) — Line 109, Complexity: 1

### `backend\tests\unit\test_rag_treatment_graph.py`
- **test_returns_overruled_cases**(`self`) — Line 11, Complexity: 1
- **test_returns_empty_when_no_overruled**(`self`) — Line 24, Complexity: 1
- **test_returns_empty_on_graph_error**(`self`) — Line 34, Complexity: 1
- **test_returns_empty_for_empty_input**(`self`) — Line 44, Complexity: 1

### `backend\tests\unit\test_rate_limiter.py`
- **test_valid_per_minute**(`self`) — Line 15, Complexity: 1
- **test_valid_per_second**(`self`) — Line 20, Complexity: 1
- **test_valid_per_hour**(`self`) — Line 25, Complexity: 1
- **test_valid_per_day**(`self`) — Line 30, Complexity: 1
- **test_valid_plural_units**(`self`) — Line 35, Complexity: 1
- **test_strips_whitespace**(`self`) — Line 40, Complexity: 1
- **test_invalid_format_no_slash**(`self`) — Line 45, Complexity: 1
- **test_invalid_format_too_many_slashes**(`self`) — Line 49, Complexity: 1
- **test_invalid_count_non_numeric**(`self`) — Line 53, Complexity: 1
- **test_invalid_unit**(`self`) — Line 57, Complexity: 1
- **test_redis_down_uses_in_memory_fallback**(`self`) — Line 66, Complexity: 1

### `backend\tests\unit\test_rbac.py`
- **_make_payload**(`role, sub, jti`) — Line 14, Complexity: 1
- **admin_payload**(`0 args`) — Line 25, Complexity: 1
- **researcher_payload**(`0 args`) — Line 30, Complexity: 1
- **test_allows_matching_role**(`self, admin_payload`) — Line 38, Complexity: 1
- **test_denies_non_matching_role**(`self, researcher_payload`) — Line 44, Complexity: 1
- **test_allows_any_of_multiple_roles**(`self, researcher_payload`) — Line 52, Complexity: 1
- **test_denies_viewer_for_admin_researcher**(`self`) — Line 60, Complexity: 1
- **test_error_message_is_generic**(`self`) — Line 67, Complexity: 1
- **test_single_role_allows_exact_match**(`self`) — Line 74, Complexity: 1

### `backend\tests\unit\test_research_agent.py`
- **_base_state**(`0 args`) — Line 22, Complexity: 1
- **_build_graph**(`0 args`) — Line 39, Complexity: 1
- **test_build_research_graph_returns_compiled**(`self`) — Line 83, Complexity: 1
- **test_graph_has_expected_nodes**(`self`) — Line 89, Complexity: 2
- **test_initial_state_structure**(`self`) — Line 97, Complexity: 1
- **test_continues_without_feedback**(`self`) — Line 111, Complexity: 1
- **test_continues_with_empty_feedback**(`self`) — Line 115, Complexity: 1
- **test_loops_with_feedback**(`self`) — Line 121, Complexity: 1
- **test_loops_with_feedback_iteration_2**(`self`) — Line 130, Complexity: 1
- **test_stops_at_max_iterations**(`self`) — Line 139, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 150, Complexity: 1
- **test_continues_without_feedback**(`self`) — Line 166, Complexity: 1
- **test_continues_with_empty_feedback**(`self`) — Line 170, Complexity: 1
- **test_loops_with_feedback**(`self`) — Line 178, Complexity: 1
- **test_stops_at_max_iterations**(`self`) — Line 191, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 202, Complexity: 1
- **test_continues_without_feedback**(`self`) — Line 218, Complexity: 1
- **test_continues_with_empty_feedback**(`self`) — Line 222, Complexity: 1
- **test_loops_with_feedback**(`self`) — Line 230, Complexity: 1
- **test_stops_at_max_iterations**(`self`) — Line 243, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 254, Complexity: 1
- **test_skips_when_disabled**(`self`) — Line 271, Complexity: 1
- **test_generates_counter_queries**(`self`) — Line 286, Complexity: 1
- **test_returns_empty_on_llm_failure**(`self`) — Line 335, Complexity: 1
- **test_flags_changed_sections**(`self`) — Line 362, Complexity: 1
- **test_no_warning_for_identical_text**(`self`) — Line 383, Complexity: 1
- **test_skips_non_repealed**(`self`) — Line 402, Complexity: 1
- **test_extracts_procedural_context**(`self`) — Line 427, Complexity: 1
- **test_defaults_to_empty_string**(`self`) — Line 452, Complexity: 1
- **test_element_context_enriches_query**(`self`) — Line 478, Complexity: 1
- **test_bench_filter_passed_to_search**(`self`) — Line 517, Complexity: 1
- **test_includes_statute_context_in_prompt**(`self`) — Line 558, Complexity: 1
- **test_plan_receives_statute_and_elements**(`self`) — Line 588, Complexity: 3
- **test_detects_refusal_loop**(`self`) — Line 647, Complexity: 1
- **test_accepts_valid_memo**(`self`) — Line 655, Complexity: 1
- **test_detects_too_short**(`self`) — Line 667, Complexity: 1
- **test_detects_extreme_repetition**(`self`) — Line 673, Complexity: 1

### `backend\tests\unit\test_research_nodes.py`
- **_make_state**(`0 args`) — Line 28, Complexity: 1
- **_make_llm**(`0 args`) — Line 47, Complexity: 2
- **test_returns_classification_in_messages**(`self`) — Line 64, Complexity: 1
- **test_passes_query_as_prompt**(`self`) — Line 84, Complexity: 1
- **test_returns_sub_queries**(`self`) — Line 102, Complexity: 1
- **test_empty_sub_queries_returns_empty_list**(`self`) — Line 121, Complexity: 1
- **test_includes_user_feedback_in_prompt**(`self`) — Line 130, Complexity: 1
- **test_no_user_feedback_prompt_unchanged**(`self`) — Line 151, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 168, Complexity: 1
- **test_handles_missing_classification_gracefully**(`self`) — Line 188, Complexity: 1
- **test_runs_search_for_each_sub_query**(`self`) — Line 206, Complexity: 1
- **test_empty_sub_queries_returns_empty**(`self`) — Line 248, Complexity: 1
- **test_handles_search_failure_gracefully**(`self`) — Line 254, Complexity: 1
- **test_identifies_cross_references**(`self`) — Line 270, Complexity: 1
- **test_no_cross_references_when_unique**(`self`) — Line 285, Complexity: 1
- **test_empty_results**(`self`) — Line 295, Complexity: 1
- **test_cross_refs_sorted_by_match_count**(`self`) — Line 301, Complexity: 1
- **test_parses_contradictions_from_llm**(`self`) — Line 322, Complexity: 1
- **test_empty_results_returns_empty**(`self`) — Line 344, Complexity: 1
- **test_handles_llm_returning_no_contradictions**(`self`) — Line 350, Complexity: 1
- **test_returns_memo_and_confidence**(`self`) — Line 366, Complexity: 1
- **test_zero_results_gives_zero_confidence**(`self`) — Line 383, Complexity: 1
- **test_many_results_high_confidence**(`self`) — Line 392, Complexity: 1
- **test_precedent_strengths_populated_from_results**(`self`) — Line 409, Complexity: 4
- **test_sc_constitutional_bench_yields_binding**(`self`) — Line 459, Complexity: 4
- **test_overruled_language_passes_warning_to_llm**(`self`) — Line 490, Complexity: 1
- **test_overruled_case_gets_overruled_strength**(`self`) — Line 528, Complexity: 1
- **test_no_treatment_warnings_for_neutral_results**(`self`) — Line 559, Complexity: 1
- **test_confidence_higher_with_binding_precedents**(`self`) — Line 585, Complexity: 1
- **test_no_uuids_returns_unchanged_memo**(`self`) — Line 626, Complexity: 1
- **test_valid_uuids_no_warning**(`self`) — Line 633, Complexity: 1
- **test_invalid_uuids_appends_warning**(`self`) — Line 646, Complexity: 1
- **test_empty_memo_returns_empty**(`self`) — Line 660, Complexity: 1
- **test_human_citation_unverified_appends_warning**(`self`) — Line 667, Complexity: 1
- **test_human_citation_verified_no_warning**(`self`) — Line 684, Complexity: 1
- **test_ungrounded_citation_appends_warning**(`self`) — Line 701, Complexity: 1
- **test_grounded_citation_no_ungrounded_warning**(`self`) — Line 721, Complexity: 1
- **test_valid_json_array**(`self`) — Line 745, Complexity: 1
- **test_json_in_code_fence**(`self`) — Line 748, Complexity: 1
- **test_empty_array**(`self`) — Line 752, Complexity: 1
- **test_garbage_returns_empty**(`self`) — Line 755, Complexity: 1
- **test_json_with_surrounding_text**(`self`) — Line 758, Complexity: 1
- **test_valid_json_dict**(`self`) — Line 769, Complexity: 1
- **test_valid_json_list**(`self`) — Line 772, Complexity: 1
- **test_json_in_code_fence**(`self`) — Line 775, Complexity: 1
- **test_json_in_code_fence_no_lang**(`self`) — Line 779, Complexity: 1
- **test_json_with_surrounding_prose**(`self`) — Line 783, Complexity: 1
- **test_garbage_returns_default_dict**(`self`) — Line 787, Complexity: 1
- **test_garbage_returns_custom_default**(`self`) — Line 790, Complexity: 1
- **test_whitespace_around_json**(`self`) — Line 793, Complexity: 1
- **test_nested_braces**(`self`) — Line 796, Complexity: 1
- **test_array_in_code_fence**(`self`) — Line 800, Complexity: 1
- **test_valid_json_array**(`self`) — Line 811, Complexity: 1
- **test_empty_array**(`self`) — Line 814, Complexity: 1
- **test_garbage_returns_empty_list**(`self`) — Line 817, Complexity: 1
- **test_dict_returned_as_single_element_list**(`self`) — Line 820, Complexity: 1
- **test_json_in_code_fence**(`self`) — Line 824, Complexity: 1
- **test_json_with_surrounding_text**(`self`) — Line 828, Complexity: 1

### `backend\tests\unit\test_research_v2_nodes.py`
- **_make_v2_state**(`0 args`) — Line 43, Complexity: 1
- **_make_llm**(`0 args`) — Line 84, Complexity: 2
- **_make_worker_result**(`task_id, task_type, query, results, error`) — Line 94, Complexity: 2
- **_make_search_result**(`case_id, title, citation, score`) — Line 114, Complexity: 1
- **test_returns_rewritten_query**(`self`) — Line 144, Complexity: 1
- **test_passes_original_query_to_llm**(`self`) — Line 155, Complexity: 1
- **test_fallback_on_failure**(`self`) — Line 167, Complexity: 1
- **test_generates_dual_queries**(`self`) — Line 187, Complexity: 2
- **test_generates_task_ids**(`self`) — Line 227, Complexity: 1
- **test_populates_sub_queries_for_backward_compat**(`self`) — Line 244, Complexity: 1
- **test_includes_user_feedback_in_prompt**(`self`) — Line 262, Complexity: 1
- **test_error_handling**(`self`) — Line 279, Complexity: 1
- **test_extracts_passages_from_correct_results**(`self`) — Line 299, Complexity: 1
- **test_crag_scoring_correct_ambiguous_incorrect**(`self`) — Line 336, Complexity: 5
- **test_crag_filtering_removes_incorrect**(`self`) — Line 377, Complexity: 1
- **test_no_passages_for_incorrect**(`self`) — Line 407, Complexity: 1
- **test_empty_worker_results**(`self`) — Line 426, Complexity: 1
- **test_parallel_batches**(`self`) — Line 436, Complexity: 1
- **test_finds_by_citation**(`self`) — Line 468, Complexity: 1
- **test_fallback_to_title_search**(`self`) — Line 521, Complexity: 1
- **test_error_handling**(`self`) — Line 569, Complexity: 1
- **test_dual_query_search**(`self`) — Line 604, Complexity: 1
- **test_single_query_when_no_boolean**(`self`) — Line 649, Complexity: 1
- **test_error_handling**(`self`) — Line 676, Complexity: 1
- **test_deduplicates_with_diversity**(`self`) — Line 710, Complexity: 1
- **test_cross_references_from_multiple_workers**(`self`) — Line 722, Complexity: 1
- **test_empty_worker_results**(`self`) — Line 741, Complexity: 1
- **test_returns_non_empty_reasoning**(`self`) — Line 757, Complexity: 1
- **test_cot_quality_mentions_findings**(`self`) — Line 785, Complexity: 1
- **test_reflection_returns_strategy_adjustment**(`self`) — Line 809, Complexity: 1
- **test_no_pivot_returns_none_strategy**(`self`) — Line 833, Complexity: 1
- **test_empty_worker_results**(`self`) — Line 847, Complexity: 1
- **test_identifies_evidence_gaps**(`self`) — Line 864, Complexity: 1
- **test_generates_new_tasks_for_gaps**(`self`) — Line 893, Complexity: 1
- **test_max_2_rounds_enforced**(`self`) — Line 916, Complexity: 2
- **test_mc_rag_conditioning**(`self`) — Line 938, Complexity: 1
- **test_strategy_adjustment_adds_gaps**(`self`) — Line 960, Complexity: 1
- **test_empty_worker_results**(`self`) — Line 986, Complexity: 1
- **test_simple_query_returns_results**(`self`) — Line 1002, Complexity: 1
- **test_fallback_when_few_results**(`self`) — Line 1030, Complexity: 1
- **test_fallback_on_search_error**(`self`) — Line 1047, Complexity: 1
- **test_produces_memo_and_confidence**(`self`) — Line 1063, Complexity: 1
- **test_empty_results_returns_no_results_memo**(`self`) — Line 1079, Complexity: 1
- **test_appends_legal_disclaimer**(`self`) — Line 1087, Complexity: 2
- **test_error_handling**(`self`) — Line 1098, Complexity: 1
- **test_dispatch_creates_sends_for_each_task**(`self`) — Line 1115, Complexity: 3
- **test_fallback_send_when_no_plan**(`self`) — Line 1168, Complexity: 3
- **test_web_fallback_reflected_in_gap_analysis_prompt**(`self`) — Line 1206, Complexity: 3
- **test_worker_reasonings_available_in_state**(`self`) — Line 1244, Complexity: 2
- **mock_generate_structured**(`0 args`) — Line 441, Complexity: 1

### `backend\tests\unit\test_research_v2_phase2.py`
- **_make_flash_llm**(`0 args`) — Line 32, Complexity: 2
- **test_returns_prefix_plus_original**(`self`) — Line 49, Complexity: 1
- **test_statute_prefix**(`self`) — Line 67, Complexity: 2
- **test_passes_metadata_to_llm**(`self`) — Line 91, Complexity: 1
- **test_fallback_on_failure**(`self`) — Line 103, Complexity: 1
- **test_adds_contextualized_text_key**(`self`) — Line 115, Complexity: 2
- **test_preserves_original_text**(`self`) — Line 134, Complexity: 1
- **test_handles_failure_gracefully**(`self`) — Line 144, Complexity: 1
- **test_produces_summaries_for_each_section**(`self`) — Line 163, Complexity: 2
- **test_skips_short_sections**(`self`) — Line 195, Complexity: 1
- **test_handles_llm_failure**(`self`) — Line 207, Complexity: 1
- **test_empty_sections_returns_empty**(`self`) — Line 216, Complexity: 1
- **test_builds_correct_vector_records**(`self`) — Line 225, Complexity: 1
- **test_ipc_to_bns_expansion**(`self`) — Line 253, Complexity: 1
- **test_bns_to_ipc_reverse**(`self`) — Line 260, Complexity: 1
- **test_crpc_to_bnss**(`self`) — Line 267, Complexity: 1
- **test_evidence_to_bsa**(`self`) — Line 273, Complexity: 2
- **test_no_expansion_for_unrelated_query**(`self`) — Line 283, Complexity: 1
- **test_ipc_has_substantial_mappings**(`self`) — Line 292, Complexity: 1
- **test_crpc_has_substantial_mappings**(`self`) — Line 296, Complexity: 1
- **test_evidence_has_substantial_mappings**(`self`) — Line 300, Complexity: 1
- **test_ipc_302_maps_to_bns_103**(`self`) — Line 304, Complexity: 1
- **test_ipc_420_maps_to_bns**(`self`) — Line 308, Complexity: 1
- **test_ipc_498a_maps_to_bns**(`self`) — Line 312, Complexity: 1
- **test_synthesis_prompt_mentions_dual_codes**(`self`) — Line 320, Complexity: 2
- **test_statute_model_exists**(`self`) — Line 334, Complexity: 1
- **test_statute_has_required_columns**(`self`) — Line 337, Complexity: 1
- **test_statute_unique_constraint**(`self`) — Line 348, Complexity: 2
- **test_statute_has_fts_index**(`self`) — Line 352, Complexity: 1
- **test_statute_has_act_index**(`self`) — Line 356, Complexity: 1
- **test_compute_replacement_fields_ipc**(`self`) — Line 369, Complexity: 1
- **test_compute_replacement_fields_bns**(`self`) — Line 377, Complexity: 1
- **test_compute_replacement_fields_unknown**(`self`) — Line 385, Complexity: 1
- **test_normalize_statute**(`self`) — Line 392, Complexity: 1
- **test_summaries_have_correct_metadata**(`self`) — Line 420, Complexity: 2
- **test_level1_and_level2_distinction**(`self`) — Line 450, Complexity: 1
- **test_summary_vector_ids_unique_per_section**(`self`) — Line 466, Complexity: 1
- **test_contextualized_text_longer_than_original**(`self`) — Line 495, Complexity: 1
- **test_batch_contextual_preserves_count**(`self`) — Line 507, Complexity: 1
- **test_pipeline_flow_order**(`self`) — Line 517, Complexity: 1
- **mock_generate**(`0 args`) — Line 168, Complexity: 1

### `backend\tests\unit\test_research_v2_phase3.py`
- **_make_mock_llm**(`0 args`) — Line 23, Complexity: 2
- **_make_mock_embedder**(`0 args`) — Line 36, Complexity: 1
- **_make_mock_vector_store**(`0 args`) — Line 44, Complexity: 1
- **_make_mock_reranker**(`0 args`) — Line 51, Complexity: 1
- **_make_mock_graph_store**(`0 args`) — Line 57, Complexity: 1
- **_make_task**(`task_type`) — Line 64, Complexity: 1
- **test_search_returns_docs**(`self`) — Line 88, Complexity: 1
- **test_get_fragment**(`self`) — Line 113, Complexity: 1
- **test_get_metadata**(`self`) — Line 134, Complexity: 1
- **test_get_document**(`self`) — Line 155, Complexity: 1
- **test_search_with_court_filter**(`self`) — Line 175, Complexity: 1
- **test_missing_token_raises**(`self`) — Line 197, Complexity: 1
- **test_search_returns_results**(`self`) — Line 215, Complexity: 1
- **test_search_with_custom_domains**(`self`) — Line 239, Complexity: 2
- **test_missing_api_key_raises**(`self`) — Line 260, Complexity: 1
- **test_returns_statute_results**(`self`) — Line 278, Complexity: 1
- **test_code_mapping_expansion**(`self`) — Line 311, Complexity: 1
- **test_returns_ik_results**(`self`) — Line 345, Complexity: 1
- **test_handles_ik_error_gracefully**(`self`) — Line 367, Complexity: 1
- **test_returns_web_results**(`self`) — Line 391, Complexity: 1
- **test_handles_web_error_gracefully**(`self`) — Line 411, Complexity: 1
- **test_returns_graph_results**(`self`) — Line 435, Complexity: 1
- **test_handles_graph_error**(`self`) — Line 454, Complexity: 1
- **test_leiden_produces_communities**(`self`) — Line 476, Complexity: 5
- **test_semantic_retrieval**(`self`) — Line 506, Complexity: 1
- **test_graph_overlap_retrieval**(`self`) — Line 541, Complexity: 1
- **test_deduplicates_across_strategies**(`self`) — Line 575, Complexity: 1
- **test_export_citation_graph**(`self`) — Line 618, Complexity: 1
- **test_summarize_community**(`self`) — Line 633, Complexity: 1
- **test_dispatch_routes_all_task_types**(`self`) — Line 663, Complexity: 1
- **test_all_worker_types_are_registered**(`self`) — Line 681, Complexity: 1
- **capture_post**(`url, data`) — Line 182, Complexity: 1
- **capture_post**(`url, json`) — Line 246, Complexity: 2

### `backend\tests\unit\test_research_v2_phase4.py`
- **_make_mock_llm**(`0 args`) — Line 47, Complexity: 2
- **_make_mock_flash_llm**(`0 args`) — Line 57, Complexity: 1
- **_make_worker_results**(`n`) — Line 82, Complexity: 3
- **_make_relevance_scores**(`0 args`) — Line 130, Complexity: 1
- **_make_extracted_passages**(`0 args`) — Line 137, Complexity: 1
- **_make_base_state**(`0 args`) — Line 151, Complexity: 2
- **test_three_drafts_generated_with_different_strategies**(`self`) — Line 182, Complexity: 1
- **test_each_draft_is_structurally_valid**(`self`) — Line 205, Complexity: 2
- **test_pro_merge_produces_final_memo**(`self`) — Line 235, Complexity: 1
- **test_empty_results_returns_gracefully**(`self`) — Line 266, Complexity: 1
- **test_source_attribution_built**(`self`) — Line 292, Complexity: 1
- **test_stream_callback_invoked_during_synthesis**(`self`) — Line 320, Complexity: 2
- **test_non_streaming_fallback**(`self`) — Line 353, Complexity: 1
- **test_footnotes_extracted_from_memo**(`self`) — Line 382, Complexity: 1
- **test_unused_sources_included**(`self`) — Line 405, Complexity: 1
- **test_empty_memo_returns_empty_footnotes**(`self`) — Line 419, Complexity: 1
- **test_deterministic_verify_missing_footnote**(`self`) — Line 437, Complexity: 1
- **test_deterministic_verify_sql_injection_safe**(`self`) — Line 458, Complexity: 3
- **test_verify_citations_uses_gather**(`self`) — Line 485, Complexity: 1
- **test_citation_verification_uses_title_search**(`self`) — Line 495, Complexity: 1
- **test_t4_guardrail_removes_unverifiable_citations**(`self`) — Line 524, Complexity: 1
- **test_verify_citations_v2_node_produces_banner**(`self`) — Line 560, Complexity: 1
- **test_citation_format_validation**(`self`) — Line 591, Complexity: 1
- **test_quality_check_returns_score_and_data_points**(`self`) — Line 612, Complexity: 1
- **test_quality_check_below_threshold**(`self`) — Line 641, Complexity: 1
- **test_quality_check_with_empty_memo**(`self`) — Line 672, Complexity: 1
- **test_contradictions_section_always_present**(`self`) — Line 695, Complexity: 1
- **test_merge_prompt_instructs_contradiction_detection**(`self`) — Line 722, Complexity: 1
- **test_graph_has_phase4_nodes**(`self`) — Line 739, Complexity: 1
- **test_synthesize_system_has_required_sections**(`self`) — Line 774, Complexity: 2
- **test_synthesize_system_has_irac**(`self`) — Line 791, Complexity: 2
- **test_synthesize_system_has_footnote_format**(`self`) — Line 801, Complexity: 2
- **test_synthesize_system_has_dual_code_refs**(`self`) — Line 808, Complexity: 1
- **test_synthesize_user_template_valid**(`self`) — Line 815, Complexity: 1
- **test_scc_citation**(`self`) — Line 839, Complexity: 1
- **test_air_citation**(`self`) — Line 844, Complexity: 1
- **test_neutral_citation**(`self`) — Line 848, Complexity: 1
- **test_invalid_citation**(`self`) — Line 852, Complexity: 1
- **test_exact_substring**(`self`) — Line 861, Complexity: 1
- **test_no_match**(`self`) — Line 865, Complexity: 1
- **test_empty_strings**(`self`) — Line 869, Complexity: 1
- **test_emit_status_creates_valid_event**(`self`) — Line 883, Complexity: 1
- **test_emit_status_all_event_types**(`self`) — Line 890, Complexity: 2
- **test_plan_research_emits_plan_event**(`self`) — Line 907, Complexity: 1
- **test_gather_results_emits_found_events**(`self`) — Line 940, Complexity: 1
- **test_batch_cot_emits_reflection_event**(`self`) — Line 955, Complexity: 1
- **test_gap_analysis_emits_gap_event**(`self`) — Line 977, Complexity: 1
- **test_speculative_synthesis_emits_drafting_events**(`self`) — Line 1010, Complexity: 2
- **test_verify_v2_emits_verification_event**(`self`) — Line 1045, Complexity: 1
- **test_legal_quality_emits_quality_event**(`self`) — Line 1082, Complexity: 1
- **test_state_process_events_is_annotated_reducer**(`self`) — Line 1103, Complexity: 1
- **test_sse_layer_forwards_process_events**(`self`) — Line 1111, Complexity: 2
- **test_exact_substring**(`self`) — Line 1141, Complexity: 1
- **test_rejects_unrelated_strings**(`self`) — Line 1146, Complexity: 1
- **test_rejects_anagram_like**(`self`) — Line 1153, Complexity: 1
- **test_same_words_reordered**(`self`) — Line 1158, Complexity: 1
- **test_near_exact_with_typo**(`self`) — Line 1163, Complexity: 1
- **test_empty_strings**(`self`) — Line 1171, Complexity: 1
- **test_infer_source_label**(`self`) — Line 1187, Complexity: 1
- **test_footnote_accepts_all_enriched_fields**(`self`) — Line 1210, Complexity: 1
- **test_footnote_web_source**(`self`) — Line 1237, Complexity: 1
- **test_footnote_ik_source_no_pdf**(`self`) — Line 1263, Complexity: 1
- **test_worker_results_deduped_by_task_id**(`self`) — Line 1293, Complexity: 1
- **test_different_task_ids_both_kept**(`self`) — Line 1319, Complexity: 1
- **mock_stream_callback**(`chunk`) — Line 328, Complexity: 1
- **mock_stream**(`0 args`) — Line 333, Complexity: 2
- **_fake_execute**(`0 args`) — Line 546, Complexity: 1
- **_fake_execute**(`0 args`) — Line 580, Complexity: 1
- **_fake_execute**(`0 args`) — Line 1051, Complexity: 1

### `backend\tests\unit\test_research_v2_phase5.py`
- **_make_mock_redis**(`0 args`) — Line 47, Complexity: 1
- **_get**(`key`) — Line 52, Complexity: 1
- **_setex**(`key, ttl, value`) — Line 55, Complexity: 1
- **test_lowercase_strip**(`self`) — Line 71, Complexity: 1
- **test_sorted_filters**(`self`) — Line 77, Complexity: 1
- **test_different_queries_different_keys**(`self`) — Line 83, Complexity: 1
- **test_key_length**(`self`) — Line 89, Complexity: 1
- **test_memo_cache_roundtrip**(`self`) — Line 105, Complexity: 1
- **test_memo_cache_miss**(`self`) — Line 120, Complexity: 1
- **test_memo_cache_none_redis**(`self`) — Line 127, Complexity: 1
- **test_search_cache_roundtrip**(`self`) — Line 133, Complexity: 1
- **test_ik_cache_roundtrip**(`self`) — Line 147, Complexity: 1
- **test_ik_fragment_cache_roundtrip**(`self`) — Line 160, Complexity: 1
- **test_embedding_cache_roundtrip**(`self`) — Line 172, Complexity: 1
- **test_community_cache_roundtrip**(`self`) — Line 185, Complexity: 1
- **test_cached_at_timestamp_present**(`self`) — Line 203, Complexity: 1
- **test_memo_ttl_24h**(`self`) — Line 223, Complexity: 1
- **test_search_ttl_1h**(`self`) — Line 226, Complexity: 1
- **test_ik_ttl_24h**(`self`) — Line 229, Complexity: 1
- **test_embedding_ttl_7d**(`self`) — Line 232, Complexity: 1
- **test_community_ttl_7d**(`self`) — Line 235, Complexity: 1
- **test_setex_called_with_correct_ttl**(`self`) — Line 239, Complexity: 1
- **test_redis_failure_falls_through**(`self`) — Line 249, Complexity: 1
- **test_cache_miss_calls_embedder**(`self`) — Line 272, Complexity: 1
- **test_cache_hit_skips_embedder**(`self`) — Line 289, Complexity: 1
- **test_ik_worker_caches_results**(`self`) — Line 318, Complexity: 1
- **test_ik_worker_uses_cache_on_hit**(`self`) — Line 347, Complexity: 1
- **test_creates_cache_on_first_call**(`self`) — Line 383, Complexity: 1
- **test_reuses_cache_on_subsequent_calls**(`self`) — Line 408, Complexity: 1
- **test_disabled_returns_none**(`self`) — Line 432, Complexity: 1
- **test_creation_failure_falls_back**(`self`) — Line 448, Complexity: 1
- **test_context_cache_enabled_default**(`self`) — Line 476, Complexity: 1
- **test_context_cache_ttl_default**(`self`) — Line 481, Complexity: 1
- **test_semantic_cache_get_miss_no_index**(`self`) — Line 496, Complexity: 1
- **test_semantic_cache_put_stores_embedding**(`self`) — Line 509, Complexity: 1
- **test_semantic_cache_threshold**(`self`) — Line 531, Complexity: 1
- **test_semantic_cache_get_below_threshold**(`self`) — Line 537, Complexity: 1
- **test_semantic_cache_get_above_threshold**(`self`) — Line 555, Complexity: 1
- **test_semantic_hit_but_memo_expired**(`self`) — Line 588, Complexity: 1
- **test_put_failure_is_silent**(`self`) — Line 606, Complexity: 1
- **test_creates_index_on_first_use**(`self`) — Line 628, Complexity: 1
- **test_pre_warm_computes_embeddings**(`self`) — Line 664, Complexity: 1
- **test_pre_warm_empty_plan**(`self`) — Line 688, Complexity: 1
- **test_pre_warm_failure_returns_empty**(`self`) — Line 700, Complexity: 1
- **test_pre_warm_wired_in_graph**(`self`) — Line 716, Complexity: 4
- **test_timeout_values_match_spec**(`self`) — Line 746, Complexity: 1
- **test_timeout_returns_error_result**(`self`) — Line 758, Complexity: 1
- **test_all_workers_have_timeouts**(`self`) — Line 773, Complexity: 1
- **test_source_diversity_single_tier**(`self`) — Line 793, Complexity: 1
- **test_source_diversity_multi_tier**(`self`) — Line 799, Complexity: 1
- **test_source_diversity_empty**(`self`) — Line 805, Complexity: 1
- **test_gap_coverage_all_filled**(`self`) — Line 810, Complexity: 1
- **test_gap_coverage_none_filled**(`self`) — Line 815, Complexity: 1
- **test_gap_coverage_no_initial_gaps**(`self`) — Line 820, Complexity: 1
- **test_confidence_with_diversity_boost**(`self`) — Line 825, Complexity: 1
- **test_confidence_backward_compatible**(`self`) — Line 839, Complexity: 1
- **test_weights_sum_to_one**(`self`) — Line 846, Complexity: 1
- **test_circuit_breaker_constants**(`self`) — Line 864, Complexity: 1
- **test_circuit_breaker_trips_on_429s**(`self`) — Line 873, Complexity: 1
- **test_circuit_breaker_resets_after_cooldown**(`self`) — Line 888, Complexity: 1
- **test_circuit_breaker_class_exists**(`self`) — Line 903, Complexity: 1
- **test_script_exists**(`self`) — Line 917, Complexity: 1
- **test_script_has_main**(`self`) — Line 922, Complexity: 1
- **_get_redis**(`0 args`) — Line 280, Complexity: 1
- **_get_redis**(`0 args`) — Line 300, Complexity: 1
- **_get_redis**(`0 args`) — Line 335, Complexity: 1
- **_get_redis**(`0 args`) — Line 364, Complexity: 1

### `backend\tests\unit\test_routing_utils.py`
- **test_proceed_phrases**(`self`) — Line 20, Complexity: 1
- **test_frontend_chip_phrases**(`self`) — Line 31, Complexity: 1
- **test_dict_structured_response**(`self`) — Line 37, Complexity: 1
- **test_json_string_from_frontend**(`self`) — Line 44, Complexity: 1
- **test_non_proceed_phrases**(`self`) — Line 57, Complexity: 1
- **test_no_feedback_proceeds**(`self`) — Line 70, Complexity: 1
- **test_proceed_feedback_proceeds**(`self`) — Line 75, Complexity: 1
- **test_substantive_feedback_loops**(`self`) — Line 85, Complexity: 1
- **test_max_iterations_stops_loop**(`self`) — Line 95, Complexity: 1
- **test_proceed_none_returns_end**(`self`) — Line 107, Complexity: 1
- **test_check_error_routes_to_end**(`self`) — Line 112, Complexity: 1
- **test_check_error_no_error_proceeds**(`self`) — Line 117, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 122, Complexity: 1
- **test_json_string_approval_proceeds**(`self`) — Line 132, Complexity: 1
- **test_router_function_name**(`self`) — Line 148, Complexity: 1

### `backend\tests\unit\test_rrf.py`
- **test_two_lists_with_overlap**(`self`) — Line 11, Complexity: 1
- **test_rrf_scores_are_correct**(`self`) — Line 26, Complexity: 1
- **test_single_list_passthrough**(`self`) — Line 41, Complexity: 1
- **test_empty_lists**(`self`) — Line 49, Complexity: 1
- **test_disjoint_lists**(`self`) — Line 55, Complexity: 1
- **test_custom_k_value**(`self`) — Line 64, Complexity: 1
- **test_three_lists**(`self`) — Line 78, Complexity: 1
- **test_sorted_by_descending_score**(`self`) — Line 91, Complexity: 1

### `backend\tests\unit\test_sanitizer.py`
- **test_strips_html_tags**(`self`) — Line 15, Complexity: 1
- **test_removes_null_bytes**(`self`) — Line 18, Complexity: 1
- **test_removes_control_characters**(`self`) — Line 21, Complexity: 1
- **test_preserves_normal_whitespace**(`self`) — Line 24, Complexity: 1
- **test_collapses_excessive_newlines**(`self`) — Line 29, Complexity: 1
- **test_strips_leading_trailing_whitespace**(`self`) — Line 33, Complexity: 1
- **test_normal_text_unchanged**(`self`) — Line 36, Complexity: 1
- **test_removes_injection_markers**(`self`) — Line 44, Complexity: 1
- **test_removes_role_switching**(`self`) — Line 48, Complexity: 1
- **test_normal_query_preserved**(`self`) — Line 52, Complexity: 1
- **test_collapses_excess_whitespace**(`self`) — Line 58, Complexity: 1
- **test_detects_ignore_instructions**(`self`) — Line 66, Complexity: 1
- **test_detects_system_prompt_marker**(`self`) — Line 69, Complexity: 1
- **test_detects_dan_mode**(`self`) — Line 72, Complexity: 1
- **test_detects_role_switching**(`self`) — Line 75, Complexity: 1
- **test_detects_chatml_tokens**(`self`) — Line 78, Complexity: 1
- **test_normal_legal_text_safe**(`self`) — Line 81, Complexity: 1
- **test_normal_query_safe**(`self`) — Line 86, Complexity: 1
- **test_detects_excessive_special_chars**(`self`) — Line 91, Complexity: 1

### `backend\tests\unit\test_search_history_routes.py`
- **_history_row**(`0 args`) — Line 44, Complexity: 1
- **app**(`0 args`) — Line 72, Complexity: 1
- **mock_db**(`0 args`) — Line 80, Complexity: 1
- **client_a**(`app, mock_db`) — Line 85, Complexity: 1
- **client_b**(`app, mock_db`) — Line 98, Complexity: 1
- **client_unauth**(`app, mock_db`) — Line 111, Complexity: 1
- **_override_db**(`0 args`) — Line 88, Complexity: 1
- **_override_db**(`0 args`) — Line 101, Complexity: 1
- **_override_db**(`0 args`) — Line 114, Complexity: 1
- **test_list_history_returns_entries**(`self, client_a, mock_db`) — Line 131, Complexity: 1
- **test_list_history_empty**(`self, client_a, mock_db`) — Line 159, Complexity: 1
- **test_list_history_pagination_params**(`self, client_a, mock_db`) — Line 180, Complexity: 1
- **test_list_history_unauthenticated_returns_401**(`self, client_unauth`) — Line 203, Complexity: 1
- **test_bookmark_toggle_on**(`self, client_a, mock_db`) — Line 222, Complexity: 1
- **test_bookmark_toggle_off**(`self, client_a, mock_db`) — Line 247, Complexity: 1
- **test_bookmark_not_found_returns_404**(`self, client_a, mock_db`) — Line 270, Complexity: 1
- **test_bookmark_idor_returns_403**(`self, client_b, mock_db`) — Line 287, Complexity: 1
- **test_bookmark_invalid_uuid_returns_422**(`self, client_a`) — Line 306, Complexity: 1
- **test_bookmark_unauthenticated_returns_401**(`self, client_unauth`) — Line 316, Complexity: 1
- **test_delete_success**(`self, client_a, mock_db`) — Line 334, Complexity: 1
- **test_delete_not_found_returns_404**(`self, client_a, mock_db`) — Line 358, Complexity: 1
- **test_delete_idor_returns_403**(`self, client_b, mock_db`) — Line 375, Complexity: 1
- **test_delete_invalid_uuid_returns_422**(`self, client_a`) — Line 393, Complexity: 1
- **test_delete_unauthenticated_returns_401**(`self, client_unauth`) — Line 403, Complexity: 1
- **test_authenticated_search_creates_history_task**(`self, mock_llm, mock_embedder, mock_vector, mock_reranker, mock_sanitize, mock_injection, mock_session_factory, mock_hybrid, mock_serialize, mock_get_redis, app, mock_db`) — Line 431, Complexity: 1
- **test_unauthenticated_search_skips_history**(`self, mock_llm, mock_embedder, mock_vector, mock_reranker, mock_sanitize, mock_injection, mock_hybrid, mock_serialize, mock_get_redis, app, mock_db`) — Line 500, Complexity: 1
- **_override_db**(`0 args`) — Line 473, Complexity: 1
- **_override_db**(`0 args`) — Line 535, Complexity: 1

### `backend\tests\unit\test_search_pipeline_integration.py`
- **_make_vector_result**(`case_id, score`) — Line 34, Complexity: 1
- **_make_fts_result**(`case_id, rank`) — Line 45, Complexity: 1
- **_make_db_row**(`case_id, citation, year`) — Line 54, Complexity: 1
- **_mock_db_execute**(`rows`) — Line 68, Complexity: 8
- **_execute**(`sql, params`) — Line 73, Complexity: 8
- **test_section_302_ipc_bail_returns_results**(`self`) — Line 106, Complexity: 3
- **test_statute_expansion_triggers_for_ipc**(`self`) — Line 175, Complexity: 1
- **test_response_pagination**(`self`) — Line 212, Complexity: 1
- **test_air_citation_format**(`self`) — Line 255, Complexity: 2

### `backend\tests\unit\test_search_routes.py`
- **_make_search_response**(`0 args`) — Line 22, Complexity: 1
- **_mock_db_session**(`0 args`) — Line 61, Complexity: 1
- **app**(`0 args`) — Line 72, Complexity: 1
- **client**(`app`) — Line 79, Complexity: 1
- **_override_db**(`0 args`) — Line 83, Complexity: 1
- **test_search_returns_200_with_results**(`self, mock_hybrid_search, mock_get_llm, mock_get_embedder, mock_get_vector_store, mock_get_reranker, mock_get_redis, client`) — Line 105, Complexity: 1
- **test_search_empty_query_returns_422**(`self, client`) — Line 132, Complexity: 1
- **test_search_missing_query_returns_422**(`self, client`) — Line 137, Complexity: 1
- **test_search_with_filters**(`self, mock_hybrid_search, mock_get_llm, mock_get_embedder, mock_get_vector_store, mock_get_reranker, mock_get_redis, client`) — Line 148, Complexity: 2
- **test_search_pagination_params**(`self, mock_hybrid_search, mock_get_llm, mock_get_embedder, mock_get_vector_store, mock_get_reranker, mock_get_redis, client`) — Line 189, Complexity: 3
- **test_suggest_returns_suggestions**(`self, mock_get_redis, app`) — Line 224, Complexity: 1
- **test_suggest_short_query_returns_422**(`self, client`) — Line 261, Complexity: 1
- **test_facets_returns_facets**(`self, mock_get_redis, client`) — Line 271, Complexity: 1
- **test_search_routes_registered**(`self`) — Line 313, Complexity: 2
- **test_search_is_get**(`self`) — Line 319, Complexity: 4
- **test_suggest_is_get**(`self`) — Line 324, Complexity: 4
- **test_facets_is_get**(`self`) — Line 329, Complexity: 4
- **_override_db**(`0 args`) — Line 242, Complexity: 1
- **_override_db**(`0 args`) — Line 294, Complexity: 1

### `backend\tests\unit\test_section_search.py`
- **test_section_filter_field_exists**(`self`) — Line 7, Complexity: 1
- **test_section_filter_default_none**(`self`) — Line 12, Complexity: 1

### `backend\tests\unit\test_statute_bidirectional.py`
- **test_ipc_302_maps_to_bns_103**(`self`) — Line 21, Complexity: 1
- **test_bns_103_maps_to_ipc_302**(`self`) — Line 26, Complexity: 1
- **test_crpc_438_maps_to_bnss**(`self`) — Line 31, Complexity: 1
- **test_bnss_maps_back_to_crpc_438**(`self`) — Line 38, Complexity: 1
- **test_iea_maps_to_bsa**(`self`) — Line 44, Complexity: 1
- **test_bsa_maps_back_to_iea**(`self`) — Line 50, Complexity: 1
- **test_ipc_302_expands_to_include_bns_103**(`self`) — Line 60, Complexity: 1
- **test_bns_103_expands_to_include_ipc_302**(`self`) — Line 66, Complexity: 1
- **test_crpc_expands_to_bnss**(`self`) — Line 72, Complexity: 2
- **test_iea_expands_to_bsa**(`self`) — Line 78, Complexity: 2
- **test_unknown_act_passes_through**(`self`) — Line 84, Complexity: 1
- **test_ipc_to_bns_expansion**(`self`) — Line 94, Complexity: 1
- **test_bns_to_ipc_expansion**(`self`) — Line 99, Complexity: 1
- **test_crpc_to_bnss_expansion**(`self`) — Line 104, Complexity: 1
- **test_bnss_to_crpc_expansion**(`self`) — Line 109, Complexity: 1
- **test_iea_to_bsa_expansion**(`self`) — Line 116, Complexity: 1
- **test_no_expansion_for_unrecognized**(`self`) — Line 121, Complexity: 1

### `backend\tests\unit\test_statute_enrichment.py`
- **test_enrich_adds_bns_for_ipc**(`self`) — Line 14, Complexity: 1
- **test_enrich_adds_ipc_for_bns**(`self`) — Line 19, Complexity: 1
- **test_enrich_bidirectional_crpc**(`self`) — Line 24, Complexity: 1
- **test_enrich_bidirectional_crpc_reverse**(`self`) — Line 29, Complexity: 1
- **test_enrich_bidirectional_iea**(`self`) — Line 34, Complexity: 1
- **test_enrich_bidirectional_iea_reverse**(`self`) — Line 39, Complexity: 1
- **test_enrich_no_duplicates**(`self`) — Line 44, Complexity: 1
- **test_enrich_preserves_other_acts**(`self`) — Line 49, Complexity: 1
- **test_enrich_empty_list**(`self`) — Line 53, Complexity: 1
- **test_enrich_multiple_old_codes**(`self`) — Line 56, Complexity: 1
- **test_enrich_multiple_new_codes**(`self`) — Line 63, Complexity: 1
- **test_non_criminal_acts_unchanged**(`self`) — Line 68, Complexity: 1
- **test_enrich_uppercase_crpc**(`self`) — Line 73, Complexity: 1
- **test_result_is_sorted**(`self`) — Line 78, Complexity: 1

### `backend\tests\unit\test_statute_expansion.py`
- **_expanded_str**(`query`) — Line 14, Complexity: 2
- **test_section_302_ipc_expands_to_bns_103**(`self`) — Line 31, Complexity: 1
- **test_section_420_ipc_expands_to_bns_318_4**(`self`) — Line 36, Complexity: 1
- **test_section_with_indian_penal_code_full_name**(`self`) — Line 40, Complexity: 1
- **test_section_498a_ipc**(`self`) — Line 44, Complexity: 1
- **test_case_insensitive_ipc**(`self`) — Line 48, Complexity: 1
- **test_section_34_ipc**(`self`) — Line 52, Complexity: 1
- **test_section_with_of_the_prefix**(`self`) — Line 56, Complexity: 1
- **test_multiple_ipc_sections**(`self`) — Line 60, Complexity: 1
- **test_section_103_bns_expands_to_ipc_302**(`self`) — Line 74, Complexity: 1
- **test_section_318_bns_expands_to_ipc_415**(`self`) — Line 79, Complexity: 1
- **test_bharatiya_nyaya_sanhita_full_name**(`self`) — Line 84, Complexity: 1
- **test_case_insensitive_bns**(`self`) — Line 88, Complexity: 1
- **test_section_438_crpc**(`self`) — Line 101, Complexity: 1
- **test_section_482_crpc**(`self`) — Line 105, Complexity: 1
- **test_section_154_code_of_criminal_procedure**(`self`) — Line 109, Complexity: 1
- **test_section_125_crpc**(`self`) — Line 113, Complexity: 1
- **test_section_482_bnss**(`self`) — Line 126, Complexity: 1
- **test_section_528_bnss**(`self`) — Line 130, Complexity: 1
- **test_bharatiya_nagarik_suraksha_sanhita_full_name**(`self`) — Line 134, Complexity: 1
- **test_section_65b_evidence_act**(`self`) — Line 149, Complexity: 1
- **test_section_45_evidence_act**(`self`) — Line 153, Complexity: 1
- **test_section_27_iea**(`self`) — Line 157, Complexity: 1
- **test_section_63_bsa**(`self`) — Line 170, Complexity: 1
- **test_bharatiya_sakshya_adhiniyam_full_name**(`self`) — Line 174, Complexity: 1
- **test_no_expansion_for_plain_query**(`self`) — Line 187, Complexity: 1
- **test_no_expansion_for_unknown_section**(`self`) — Line 193, Complexity: 1
- **test_preserves_original_query**(`self`) — Line 199, Complexity: 1
- **test_returns_tuple**(`self`) — Line 205, Complexity: 1
- **test_empty_query**(`self`) — Line 211, Complexity: 1
- **test_section_with_sub_section_parens**(`self`) — Line 216, Complexity: 1
- **test_section_number_not_matched_without_act_name**(`self`) — Line 221, Complexity: 1
- **test_ipc_378_theft_to_bns_303**(`self`) — Line 237, Complexity: 1
- **test_ipc_463_forgery_to_bns_336**(`self`) — Line 241, Complexity: 1
- **test_ipc_299_culpable_homicide_to_bns_100**(`self`) — Line 245, Complexity: 1
- **test_ipc_141_unlawful_assembly_to_bns_189**(`self`) — Line 249, Complexity: 1
- **test_ipc_489a_counterfeiting_to_bns_179**(`self`) — Line 253, Complexity: 1
- **test_ipc_96_private_defence_to_bns_34**(`self`) — Line 257, Complexity: 1
- **test_ipc_354d_stalking_to_bns_78**(`self`) — Line 261, Complexity: 1
- **test_ipc_405_cbt_to_bns_316**(`self`) — Line 265, Complexity: 1
- **test_ipc_441_trespass_to_bns_329**(`self`) — Line 269, Complexity: 1
- **test_ipc_107_abetment_to_bns_45**(`self`) — Line 273, Complexity: 1
- **test_crpc_41a_notice_of_appearance_to_bnss_35_3**(`self`) — Line 281, Complexity: 1
- **test_crpc_436_bail_to_bnss_478**(`self`) — Line 285, Complexity: 1
- **test_crpc_173_chargesheet_to_bnss_193**(`self`) — Line 289, Complexity: 1
- **test_crpc_227_discharge_to_bnss_260**(`self`) — Line 293, Complexity: 1
- **test_crpc_397_revision_to_bnss_436**(`self`) — Line 297, Complexity: 1
- **test_iea_6_res_gestae_to_bsa_5**(`self`) — Line 305, Complexity: 1
- **test_iea_101_burden_of_proof_to_bsa_95**(`self`) — Line 309, Complexity: 1
- **test_iea_154_hostile_witness_to_bsa_146**(`self`) — Line 313, Complexity: 1
- **test_iea_74_public_documents_to_bsa_68**(`self`) — Line 317, Complexity: 1
- **test_iea_106_burden_of_knowledge_to_bsa_100**(`self`) — Line 321, Complexity: 1

### `backend\tests\unit\test_strategy_graph.py`
- **_make_state**(`0 args`) — Line 21, Complexity: 1
- **test_returns_search_precedents_when_no_feedback**(`self`) — Line 54, Complexity: 1
- **test_returns_analyze_facts_when_feedback_present_and_iteration_under_3**(`self`) — Line 58, Complexity: 1
- **test_returns_search_precedents_when_iteration_equals_3**(`self`) — Line 71, Complexity: 1
- **test_returns_search_precedents_when_iteration_exceeds_3**(`self`) — Line 82, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 95, Complexity: 1
- **test_empty_feedback_content_does_not_loop**(`self`) — Line 109, Complexity: 1
- **test_returns_end_when_error_is_set**(`self`) — Line 122, Complexity: 1
- **test_uses_most_recent_feedback**(`self`) — Line 126, Complexity: 1
- **test_returns_counter_and_judge_when_no_feedback**(`self`) — Line 144, Complexity: 1
- **test_returns_generate_arguments_when_feedback_present_and_iteration_under_3**(`self`) — Line 148, Complexity: 1
- **test_returns_counter_and_judge_when_iteration_equals_3**(`self`) — Line 161, Complexity: 1
- **test_returns_counter_and_judge_when_iteration_exceeds_3**(`self`) — Line 172, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 184, Complexity: 1
- **test_empty_feedback_content_does_not_loop**(`self`) — Line 197, Complexity: 1
- **test_returns_end_when_error_is_set**(`self`) — Line 210, Complexity: 1
- **test_returns_end_when_no_feedback**(`self`) — Line 221, Complexity: 1
- **test_returns_synthesize_strategy_when_feedback_present_and_iteration_under_3**(`self`) — Line 225, Complexity: 1
- **test_returns_end_when_iteration_equals_3**(`self`) — Line 238, Complexity: 1
- **test_returns_end_when_iteration_exceeds_3**(`self`) — Line 249, Complexity: 1
- **test_ignores_feedback_for_other_steps**(`self`) — Line 261, Complexity: 1
- **test_empty_feedback_content_does_not_loop**(`self`) — Line 274, Complexity: 1
- **test_returns_end_when_error_is_set**(`self`) — Line 287, Complexity: 1
- **test_end_constant_value**(`self`) — Line 291, Complexity: 1
- **_build**(`self, checkpointer`) — Line 310, Complexity: 1
- **test_graph_compiles_without_checkpointer**(`self`) — Line 321, Complexity: 2
- **test_graph_has_expected_node_count**(`self`) — Line 325, Complexity: 1
- **test_graph_has_expected_nodes**(`self`) — Line 337, Complexity: 1
- **test_graph_starts_at_analyze_facts**(`self`) — Line 359, Complexity: 1
- **test_graph_returns_compiled_object_with_ainvoke**(`self`) — Line 366, Complexity: 1
- **test_graph_compiles_with_none_checkpointer_does_not_raise**(`self`) — Line 371, Complexity: 2

### `backend\tests\unit\test_strategy_nodes.py`
- **_make_state**(`0 args`) — Line 26, Complexity: 1
- **_make_llm**(`0 args`) — Line 53, Complexity: 2
- **test_returns_fact_analysis_from_llm**(`self`) — Line 70, Complexity: 1
- **test_passes_case_facts_as_prompt**(`self`) — Line 88, Complexity: 1
- **test_empty_facts_returns_empty_analysis**(`self`) — Line 100, Complexity: 1
- **test_error_handling_returns_error_dict**(`self`) — Line 110, Complexity: 1
- **test_returns_empty_profile_when_no_target_judge**(`self`) — Line 128, Complexity: 1
- **test_returns_profile_with_disposal_and_acts_when_judge_set**(`self`) — Line 137, Complexity: 1
- **test_handles_db_exception_gracefully**(`self`) — Line 174, Complexity: 1
- **test_returns_empty_profile_when_counts_row_is_none**(`self`) — Line 185, Complexity: 1
- **test_returns_search_results_and_precedent_map**(`self`) — Line 212, Complexity: 1
- **test_handles_empty_causes_of_action**(`self`) — Line 288, Complexity: 1
- **test_no_queries_returns_empty**(`self`) — Line 342, Complexity: 1
- **test_graph_neighbors_added_to_results**(`self`) — Line 364, Complexity: 1
- **test_returns_strength_assessment_from_llm**(`self`) — Line 444, Complexity: 1
- **test_includes_judge_profile_in_prompt_when_present**(`self`) — Line 464, Complexity: 1
- **test_empty_state_returns_empty_assessment**(`self`) — Line 480, Complexity: 1
- **test_error_handling_returns_error_dict**(`self`) — Line 490, Complexity: 1
- **test_returns_legal_arguments_from_structured_llm**(`self`) — Line 508, Complexity: 1
- **test_includes_desired_relief_in_prompt**(`self`) — Line 531, Complexity: 1
- **test_returns_empty_list_when_llm_returns_no_arguments**(`self`) — Line 543, Complexity: 1
- **test_error_handling_returns_error_dict**(`self`) — Line 553, Complexity: 1
- **test_returns_counter_arguments_from_structured_llm**(`self`) — Line 571, Complexity: 1
- **test_returns_empty_list_when_no_counter_arguments_key**(`self`) — Line 596, Complexity: 1
- **test_returns_empty_list_when_counter_arguments_is_empty**(`self`) — Line 606, Complexity: 1
- **test_returns_empty_list_when_counter_arguments_not_a_list**(`self`) — Line 616, Complexity: 1
- **test_error_handling_returns_error_dict**(`self`) — Line 626, Complexity: 1
- **test_returns_generic_considerations_when_no_judge_profile**(`self`) — Line 644, Complexity: 1
- **test_generic_considerations_include_bench_type**(`self`) — Line 660, Complexity: 1
- **test_calls_llm_when_judge_profile_is_set**(`self`) — Line 669, Complexity: 1
- **test_returns_empty_lists_when_llm_returns_non_dict**(`self`) — Line 699, Complexity: 1
- **test_error_handling_returns_error_dict**(`self`) — Line 712, Complexity: 1
- **test_generic_procedural_suggestions_are_non_empty**(`self`) — Line 725, Complexity: 1
- **test_returns_strategy_memo_and_confidence**(`self`) — Line 742, Complexity: 1
- **test_zero_search_results_gives_zero_confidence**(`self`) — Line 759, Complexity: 1
- **test_many_binding_precedents_raises_confidence**(`self`) — Line 769, Complexity: 1
- **test_includes_all_state_components_in_prompt**(`self`) — Line 789, Complexity: 1
- **test_confidence_is_float_between_0_and_1**(`self`) — Line 807, Complexity: 1
- **test_error_handling_returns_error_dict**(`self`) — Line 821, Complexity: 1
- **test_appends_warning_for_invalid_uuids**(`self`) — Line 839, Complexity: 1
- **test_passes_through_clean_memo_unchanged**(`self`) — Line 861, Complexity: 1
- **test_empty_memo_returns_empty**(`self`) — Line 874, Complexity: 1
- **test_valid_uuid_no_warning**(`self`) — Line 883, Complexity: 1
- **test_unverified_human_citation_appends_warning**(`self`) — Line 904, Complexity: 1
- **test_ungrounded_citation_appends_warning**(`self`) — Line 928, Complexity: 1
- **test_grounded_verified_citation_no_warning**(`self`) — Line 953, Complexity: 1

### `backend\tests\unit\test_tavily_client.py`
- **_mock_response**(`json_data`) — Line 9, Complexity: 1
- **mock_settings**(`0 args`) — Line 18, Complexity: 1
- **tavily_client**(`mock_settings`) — Line 26, Complexity: 1
- **test_search_sends_country**(`self, tavily_client`) — Line 36, Complexity: 1
- **test_search_sends_time_range**(`self, tavily_client`) — Line 46, Complexity: 1
- **test_search_requests_raw_content**(`self, tavily_client`) — Line 56, Complexity: 1
- **test_search_omits_raw_content_when_not_requested**(`self, tavily_client`) — Line 69, Complexity: 1
- **test_search_no_optional_params_when_none**(`self, tavily_client`) — Line 80, Complexity: 1
- **test_default_domains_expanded**(`self`) — Line 91, Complexity: 1
- **test_uses_settings_timeout**(`self, mock_settings`) — Line 101, Complexity: 2

### `backend\tests\unit\test_translation.py`
- **translator**(`0 args`) — Line 8, Complexity: 1
- **test_translate_returns_translated_text**(`self, translator`) — Line 30, Complexity: 1
- **test_translate_empty_text**(`self, translator`) — Line 42, Complexity: 1
- **test_translate_whitespace_only**(`self, translator`) — Line 52, Complexity: 1
- **test_translate_preserves_source_target_in_prompt**(`self, translator`) — Line 62, Complexity: 1
- **test_detect_language_hindi_text**(`self, translator`) — Line 76, Complexity: 1
- **test_detect_language_english_text**(`self, translator`) — Line 88, Complexity: 1
- **test_detect_language_empty_text**(`self, translator`) — Line 99, Complexity: 1
- **test_detect_language_ambiguous_uses_llm**(`self, translator`) — Line 109, Complexity: 1
- **test_translate_returns_original_on_api_failure**(`self, translator`) — Line 123, Complexity: 1
- **test_translate_handles_none_response**(`self, translator`) — Line 134, Complexity: 1
- **test_detect_language_returns_en_on_api_failure**(`self, translator`) — Line 145, Complexity: 1

### `backend\tests\unit\test_treatment.py`
- **test_detects_overruled_language**(`self`) — Line 17, Complexity: 1
- **test_detects_per_incuriam**(`self`) — Line 24, Complexity: 1
- **test_detects_no_longer_good_law**(`self`) — Line 31, Complexity: 1
- **test_detects_distinguished_language**(`self`) — Line 38, Complexity: 1
- **test_detects_affirmed_language**(`self`) — Line 45, Complexity: 1
- **test_detects_followed_language**(`self`) — Line 52, Complexity: 1
- **test_detects_relied_upon**(`self`) — Line 59, Complexity: 1
- **test_detects_explained_language**(`self`) — Line 66, Complexity: 1
- **test_detects_doubted_language**(`self`) — Line 73, Complexity: 1
- **test_returns_empty_for_neutral_text**(`self`) — Line 80, Complexity: 1
- **test_returns_context_around_match**(`self`) — Line 86, Complexity: 1
- **test_overruled_has_high_confidence**(`self`) — Line 95, Complexity: 1
- **test_followed_has_lower_confidence**(`self`) — Line 103, Complexity: 1
- **test_multiple_treatments_in_same_text**(`self`) — Line 111, Complexity: 1
- **test_detects_not_followed**(`self`) — Line 122, Complexity: 1
- **test_detects_declined_to_follow**(`self`) — Line 129, Complexity: 1
- **test_detects_refused_to_follow**(`self`) — Line 136, Complexity: 1
- **test_detects_never_followed**(`self`) — Line 143, Complexity: 1
- **test_not_followed_excludes_false_positive_followed**(`self`) — Line 150, Complexity: 1
- **test_not_followed_has_high_confidence**(`self`) — Line 158, Complexity: 1
- **test_returns_true_for_overruled**(`self`) — Line 168, Complexity: 1
- **test_returns_true_for_per_incuriam**(`self`) — Line 172, Complexity: 1
- **test_returns_true_for_no_longer_good_law**(`self`) — Line 176, Complexity: 1
- **test_returns_false_for_neutral_text**(`self`) — Line 180, Complexity: 1
- **test_returns_false_for_other_treatments**(`self`) — Line 184, Complexity: 1
- **test_overruled_true_returns_overruled**(`self`) — Line 190, Complexity: 1
- **test_overruled_true_overrides_binding**(`self`) — Line 201, Complexity: 1
- **test_overruled_false_follows_normal_logic**(`self`) — Line 223, Complexity: 1
- **test_overruled_default_is_false**(`self`) — Line 231, Complexity: 1

### `backend\tests\unit\test_treatment_citation_association.py`
- **test_overruled_detected_near_citation**(`self`) — Line 20, Complexity: 1
- **test_followed_detected_near_citation**(`self`) — Line 30, Complexity: 1
- **test_distinguished_detected_near_citation**(`self`) — Line 40, Complexity: 1
- **test_build_citation_graph_includes_treatment**(`self`) — Line 51, Complexity: 2
- **test_build_citation_graph_default_treatment_is_referred_to**(`self`) — Line 82, Complexity: 2
- **test_build_citation_graph_no_citations_skips_edges**(`self`) — Line 105, Complexity: 1

### `backend\tests\unit\test_tts_provider.py`
- **tts**(`self`) — Line 11, Complexity: 1
- **test_implements_protocol**(`self, tts`) — Line 14, Complexity: 1
- **test_synthesize_returns_bytes**(`self, tts`) — Line 17, Complexity: 1
- **test_synthesize_hindi**(`self, tts`) — Line 22, Complexity: 1
- **test_unsupported_language_raises**(`self, tts`) — Line 27, Complexity: 1
- **test_get_supported_languages**(`self, tts`) — Line 31, Complexity: 1
- **test_synthesize_starts_with_mp3_sync_bytes**(`self, tts`) — Line 36, Complexity: 1

### `backend\tests\unit\test_vector_chunk_text.py`
- **test_chunk_text_defaults_to_none**(`self`) — Line 26, Complexity: 1
- **test_chunk_text_can_be_set**(`self`) — Line 30, Complexity: 1
- **test_chunk_text_immutable**(`self`) — Line 38, Complexity: 1
- **test_chunk_text_in_serialization**(`self`) — Line 43, Complexity: 1
- **test_chunk_text_absent_in_old_data**(`self`) — Line 51, Complexity: 1
- **test_fts_snippet_takes_priority**(`self`) — Line 67, Complexity: 1
- **test_vector_chunk_text_used_when_no_fts**(`self`) — Line 74, Complexity: 1
- **test_mixed_fts_and_vector_only**(`self`) — Line 81, Complexity: 1
- **test_empty_vector_chunk_text_not_used**(`self`) — Line 92, Complexity: 1
- **test_fts_title_fallback_still_works**(`self`) — Line 99, Complexity: 1
- **test_both_empty_returns_empty**(`self`) — Line 106, Complexity: 1
- **test_multiple_vector_results_all_used**(`self`) — Line 110, Complexity: 1
- **test_chunk_text_preferred_over_snippet**(`self`) — Line 130, Complexity: 2
- **test_snippet_used_when_no_chunk_text**(`self`) — Line 149, Complexity: 2
- **test_description_used_when_both_none**(`self`) — Line 164, Complexity: 2
- **embed_text**(`self, text`) — Line 190, Complexity: 1
- **__init__**(`self, results`) — Line 195, Complexity: 1
- **search**(`self, vector, top_k, filters`) — Line 198, Complexity: 1
- **test_returns_three_tuples**(`self`) — Line 206, Complexity: 1
- **test_deduplicates_keeping_best_chunk**(`self`) — Line 220, Complexity: 1
- **test_chunk_text_from_text_field**(`self`) — Line 235, Complexity: 1
- **test_chunk_text_from_chunk_text_field**(`self`) — Line 246, Complexity: 1
- **test_empty_chunk_text_when_no_metadata_text**(`self`) — Line 257, Complexity: 1
- **test_sorted_by_descending_score**(`self`) — Line 268, Complexity: 1

### `backend\tests\unit\test_web_search_worker.py`
- **_make_task**(`0 args`) — Line 9, Complexity: 1
- **mock_web_search**(`0 args`) — Line 25, Complexity: 1
- **test_passes_country_in**(`self, mock_web_search`) — Line 37, Complexity: 1
- **test_passes_include_raw_content**(`self, mock_web_search`) — Line 48, Complexity: 1
- **test_passes_time_range_from_filters**(`self, mock_web_search`) — Line 59, Complexity: 1
- **test_passes_custom_domains**(`self, mock_web_search`) — Line 70, Complexity: 1
- **test_prefers_raw_content_for_snippet**(`self, mock_web_search`) — Line 81, Complexity: 1
- **test_failure_returns_empty_not_error**(`self, mock_web_search`) — Line 95, Complexity: 1

### `backend\tests\unit\test_weighted_rrf.py`
- **_make_list**(`self, ids`) — Line 24, Complexity: 1
- **test_equal_weights_matches_unweighted**(`self`) — Line 28, Complexity: 1
- **test_double_weight_boosts_list**(`self`) — Line 38, Complexity: 1
- **test_zero_weight_excludes_list**(`self`) — Line 52, Complexity: 1
- **test_weights_length_mismatch_raises**(`self`) — Line 67, Complexity: 1
- **test_empty_lists**(`self`) — Line 78, Complexity: 1
- **test_single_list_with_weight**(`self`) — Line 83, Complexity: 2
- **test_search_strategy_exact_match**(`self`) — Line 106, Complexity: 1
- **test_exact_match_no_results**(`self`) — Line 139, Complexity: 1

### `frontend\next.config.ts`
- **rewrites**(`0 args`) — Line 16, Complexity: ?
- **headers**(`0 args`) — Line 26, Complexity: ?

### `frontend\src\__tests__\agent-components.test.tsx`
- **if**(`0 args`) — Line 188, Complexity: ?
- **if**(`0 args`) — Line 195, Complexity: ?

### `frontend\src\__tests__\agent-history-page.test.tsx`
- **makeExecution**(`0 args`) — Line 63, Complexity: ?
- **setupDefaultMocks**(`0 args`) — Line 81, Complexity: ?

### `frontend\src\__tests__\api-client.test.ts`
- **localStorageMock**(`0 args`) — Line 10, Complexity: ?

### `frontend\src\__tests__\case-detail-page.test.tsx`
- **makeCaseDetail**(`0 args`) — Line 44, Complexity: ?

### `frontend\src\__tests__\case-prep-workspace.test.tsx`
- **backLink**(`0 args`) — Line 71, Complexity: ?

### `frontend\src\__tests__\courts-page.test.tsx`
- **makeStats**(`0 args`) — Line 45, Complexity: ?

### `frontend\src\__tests__\document-detail-page.test.tsx`
- **makeCompletedDoc**(`0 args`) — Line 37, Complexity: ?

### `frontend\src\__tests__\error-boundary.test.tsx`
- **Thrower**(`0 args`) — Line 10, Complexity: ?
- **if**(`0 args`) — Line 11, Complexity: ?
- **ConditionalThrower**(`0 args`) — Line 55, Complexity: ?

### `frontend\src\__tests__\graph-page.test.tsx`
- **makeStats**(`0 args`) — Line 50, Complexity: ?

### `frontend\src\__tests__\judge-compare-page.test.tsx`
- **makeCompareResponse**(`0 args`) — Line 69, Complexity: ?

### `frontend\src\__tests__\judge-profile-page.test.tsx`
- **makeProfile**(`0 args`) — Line 48, Complexity: ?
- **makeCases**(`0 args`) — Line 90, Complexity: ?

### `frontend\src\__tests__\research-workspace.test.tsx`
- **backLink**(`0 args`) — Line 60, Complexity: ?

### `frontend\src\__tests__\search-page.test.tsx`
- **makeFacets**(`0 args`) — Line 43, Complexity: ?
- **makeSearchResponse**(`0 args`) — Line 52, Complexity: ?

### `frontend\src\__tests__\setup.tsx`
- **t**(`0 args`) — Line 47, Complexity: ?

### `frontend\src\__tests__\test-utils.tsx`
- **AllProviders**(`0 args`) — Line 9, Complexity: ?

### `frontend\src\app\about\page.tsx`
- **AboutPage**(`0 args`) — Line 10, Complexity: ?

### `frontend\src\app\agents\case-prep\page.tsx`
- **CasePrepAgentPage**(`0 args`) — Line 47, Complexity: ?
- **filteredDocuments**(`0 args`) — Line 58, Complexity: ?
- **catch**(`0 args`) — Line 89, Complexity: ?
- **handleEvent**(`0 args`) — Line 105, Complexity: ?
- **if**(`0 args`) — Line 108, Complexity: ?
- **switch**(`0 args`) — Line 112, Complexity: ?
- **handleStart**(`0 args`) — Line 171, Complexity: ?
- **handleReset**(`0 args`) — Line 223, Complexity: ?
- **if**(`0 args`) — Line 235, Complexity: ?
- **selectedDoc**(`0 args`) — Line 246, Complexity: ?

### `frontend\src\app\agents\drafting\page.tsx`
- **DraftingAgentPage**(`0 args`) — Line 54, Complexity: ?
- **selectedTemplate**(`0 args`) — Line 62, Complexity: ?
- **if**(`0 args`) — Line 97, Complexity: ?
- **catch**(`0 args`) — Line 100, Complexity: ?
- **if**(`0 args`) — Line 101, Complexity: ?
- **if**(`0 args`) — Line 124, Complexity: ?
- **for**(`0 args`) — Line 126, Complexity: ?
- **handleEvent**(`0 args`) — Line 135, Complexity: ?
- **if**(`0 args`) — Line 138, Complexity: ?
- **switch**(`0 args`) — Line 142, Complexity: ?
- **handleSubmit**(`0 args`) — Line 222, Complexity: ?
- **handleRevise**(`0 args`) — Line 290, Complexity: ?
- **handleExport**(`0 args`) — Line 296, Complexity: ?
- **catch**(`0 args`) — Line 308, Complexity: ?
- **handleReset**(`0 args`) — Line 313, Complexity: ?
- **if**(`0 args`) — Line 329, Complexity: ?
- **formatFieldName**(`0 args`) — Line 620, Complexity: ?

### `frontend\src\app\agents\history\page.tsx`
- **statusColor**(`0 args`) — Line 35, Complexity: ?
- **switch**(`0 args`) — Line 36, Complexity: ?
- **switch**(`0 args`) — Line 55, Complexity: ?
- **agentTypeLabel**(`0 args`) — Line 68, Complexity: ?
- **switch**(`0 args`) — Line 69, Complexity: ?
- **getInputSummary**(`0 args`) — Line 83, Complexity: ?
- **if**(`0 args`) — Line 85, Complexity: ?
- **if**(`0 args`) — Line 90, Complexity: ?
- **timeAgo**(`0 args`) — Line 96, Complexity: ?
- **AgentHistoryPage**(`0 args`) — Line 117, Complexity: ?
- **fetchExecutions**(`0 args`) — Line 145, Complexity: ?
- **catch**(`0 args`) — Line 155, Complexity: ?
- **fetchSessions**(`0 args`) — Line 167, Complexity: ?
- **catch**(`0 args`) — Line 175, Complexity: ?
- **if**(`0 args`) — Line 187, Complexity: ?
- **handleCancel**(`0 args`) — Line 193, Complexity: ?
- **catch**(`0 args`) — Line 198, Complexity: ?
- **handleExport**(`0 args`) — Line 206, Complexity: ?
- **catch**(`0 args`) — Line 218, Complexity: ?
- **handleDeleteSession**(`0 args`) — Line 226, Complexity: ?
- **catch**(`0 args`) — Line 231, Complexity: ?
- **handleKeyDown**(`0 args`) — Line 242, Complexity: ?

### `frontend\src\app\agents\page.tsx`
- **AgentsPage**(`0 args`) — Line 14, Complexity: ?
- **if**(`0 args`) — Line 23, Complexity: ?

### `frontend\src\app\agents\research\page.tsx`
- **ResearchAgentPage**(`0 args`) — Line 99, Complexity: ?
- **goOffline**(`0 args`) — Line 154, Complexity: ?
- **goOnline**(`0 args`) — Line 155, Complexity: ?
- **tick**(`0 args`) — Line 179, Complexity: ?
- **if**(`0 args`) — Line 180, Complexity: ?
- **fetchSessions**(`0 args`) — Line 197, Complexity: ?
- **if**(`0 args`) — Line 217, Complexity: ?
- **loadSession**(`0 args`) — Line 223, Complexity: ?
- **if**(`0 args`) — Line 235, Complexity: ?
- **if**(`0 args`) — Line 237, Complexity: ?
- **catch**(`0 args`) — Line 247, Complexity: ?
- **handleDeleteSession**(`0 args`) — Line 253, Complexity: ?
- **if**(`0 args`) — Line 257, Complexity: ?
- **catch**(`0 args`) — Line 260, Complexity: ?
- **handleNewSession**(`0 args`) — Line 266, Complexity: ?
- **handleEvent**(`0 args`) — Line 301, Complexity: ?
- **if**(`0 args`) — Line 302, Complexity: ?
- **if**(`0 args`) — Line 307, Complexity: ?
- **if**(`0 args`) — Line 320, Complexity: ?
- **switch**(`0 args`) — Line 325, Complexity: ?
- **if**(`0 args`) — Line 328, Complexity: ?
- **if**(`0 args`) — Line 331, Complexity: ?
- **if**(`0 args`) — Line 341, Complexity: ?
- **stepIdx**(`0 args`) — Line 353, Complexity: ?
- **if**(`0 args`) — Line 377, Complexity: ?
- **if**(`0 args`) — Line 382, Complexity: ?
- **if**(`0 args`) — Line 389, Complexity: ?
- **if**(`0 args`) — Line 392, Complexity: ?
- **if**(`0 args`) — Line 406, Complexity: ?
- **if**(`0 args`) — Line 409, Complexity: ?
- **if**(`0 args`) — Line 415, Complexity: ?
- **if**(`0 args`) — Line 418, Complexity: ?
- **if**(`0 args`) — Line 430, Complexity: ?
- **if**(`0 args`) — Line 456, Complexity: ?
- **handleSubmit**(`0 args`) — Line 468, Complexity: ?
- **if**(`0 args`) — Line 536, Complexity: ?
- **if**(`0 args`) — Line 550, Complexity: ?
- **if**(`0 args`) — Line 557, Complexity: ?
- **while**(`0 args`) — Line 564, Complexity: ?
- **for**(`0 args`) — Line 570, Complexity: ?
- **if**(`0 args`) — Line 574, Complexity: ?
- **if**(`0 args`) — Line 582, Complexity: ?
- **for**(`0 args`) — Line 587, Complexity: ?
- **if**(`0 args`) — Line 593, Complexity: ?
- **catch**(`0 args`) — Line 606, Complexity: ?
- **handleFollowUp**(`0 args`) — Line 617, Complexity: ?
- **if**(`0 args`) — Line 639, Complexity: ?
- **if**(`0 args`) — Line 642, Complexity: ?
- **if**(`0 args`) — Line 653, Complexity: ?
- **handleCancel**(`0 args`) — Line 667, Complexity: ?
- **if**(`0 args`) — Line 673, Complexity: ?

### `frontend\src\app\agents\strategy\page.tsx`
- **StrategyAgentPage**(`0 args`) — Line 51, Complexity: ?
- **handleEvent**(`0 args`) — Line 83, Complexity: ?
- **if**(`0 args`) — Line 86, Complexity: ?
- **switch**(`0 args`) — Line 90, Complexity: ?
- **handleSubmit**(`0 args`) — Line 149, Complexity: ?
- **handleReset**(`0 args`) — Line 204, Complexity: ?
- **if**(`0 args`) — Line 219, Complexity: ?

### `frontend\src\app\case\[id]\loading.tsx`
- **Loading**(`0 args`) — Line 3, Complexity: ?

### `frontend\src\app\case\[id]\page.tsx`
- **ForceGraph2D**(`0 args`) — Line 19, Complexity: ?
- **CaseDetailPage**(`0 args`) — Line 26, Complexity: ?
- **load**(`0 args`) — Line 50, Complexity: ?
- **catch**(`0 args`) — Line 66, Complexity: ?
- **toggleSummaryLanguage**(`0 args`) — Line 75, Complexity: ?
- **if**(`0 args`) — Line 77, Complexity: ?

### `frontend\src\app\chat\page.tsx`
- **ChatPage**(`0 args`) — Line 66, Complexity: ?
- **ChatPageInner**(`0 args`) — Line 83, Complexity: ?
- **stopFlushTimer**(`0 args`) — Line 105, Complexity: ?
- **if**(`0 args`) — Line 106, Complexity: ?
- **if**(`0 args`) — Line 130, Complexity: ?
- **if**(`0 args`) — Line 137, Complexity: ?
- **if**(`0 args`) — Line 149, Complexity: ?
- **if**(`0 args`) — Line 158, Complexity: ?
- **loadSessions**(`0 args`) — Line 167, Complexity: ?
- **catch**(`0 args`) — Line 172, Complexity: ?
- **loadHistory**(`0 args`) — Line 180, Complexity: ?
- **catch**(`0 args`) — Line 193, Complexity: ?
- **selectSession**(`0 args`) — Line 202, Complexity: ?
- **startNewChat**(`0 args`) — Line 211, Complexity: ?
- **handleDeleteSession**(`0 args`) — Line 220, Complexity: ?
- **if**(`0 args`) — Line 226, Complexity: ?
- **catch**(`0 args`) — Line 229, Complexity: ?
- **onEvent**(`0 args`) — Line 270, Complexity: ?
- **switch**(`0 args`) — Line 271, Complexity: ?
- **if**(`0 args`) — Line 273, Complexity: ?
- **if**(`0 args`) — Line 291, Complexity: ?
- **if**(`0 args`) — Line 294, Complexity: ?
- **if**(`0 args`) — Line 300, Complexity: ?
- **if**(`0 args`) — Line 314, Complexity: ?
- **if**(`0 args`) — Line 328, Complexity: ?
- **if**(`0 args`) — Line 332, Complexity: ?
- **if**(`0 args`) — Line 349, Complexity: ?
- **onError**(`0 args`) — Line 367, Complexity: ?
- **if**(`0 args`) — Line 373, Complexity: ?
- **if**(`0 args`) — Line 386, Complexity: ?
- **exportSession**(`0 args`) — Line 395, Complexity: ?
- **if**(`0 args`) — Line 402, Complexity: ?
- **handleKeyDown**(`0 args`) — Line 421, Complexity: ?
- **if**(`0 args`) — Line 422, Complexity: ?
- **if**(`0 args`) — Line 429, Complexity: ?
- **MessageBubble**(`0 args`) — Line 664, Complexity: ?
- **handleCopy**(`0 args`) — Line 668, Complexity: ?
- **if**(`0 args`) — Line 677, Complexity: ?
- **if**(`0 args`) — Line 791, Complexity: ?
- **if**(`0 args`) — Line 820, Complexity: ?

### `frontend\src\app\courts\page.tsx`
- **CourtsPage**(`0 args`) — Line 40, Complexity: ?
- **loadCourts**(`0 args`) — Line 49, Complexity: ?
- **if**(`0 args`) — Line 52, Complexity: ?
- **load**(`0 args`) — Line 64, Complexity: ?
- **catch**(`0 args`) — Line 70, Complexity: ?

### `frontend\src\app\documents\[id]\page.tsx`
- **IssueCard**(`0 args`) — Line 24, Complexity: ?
- **CounterArgumentsSection**(`0 args`) — Line 92, Complexity: ?
- **ResearchMemoSection**(`0 args`) — Line 123, Complexity: ?
- **handleCopy**(`0 args`) — Line 126, Complexity: ?
- **DocumentDetailPage**(`0 args`) — Line 153, Complexity: ?
- **fetchDoc**(`0 args`) — Line 164, Complexity: ?
- **if**(`0 args`) — Line 171, Complexity: ?
- **if**(`0 args`) — Line 172, Complexity: ?
- **catch**(`0 args`) — Line 177, Complexity: ?
- **if**(`0 args`) — Line 182, Complexity: ?
- **if**(`0 args`) — Line 191, Complexity: ?
- **if**(`0 args`) — Line 197, Complexity: ?
- **if**(`0 args`) — Line 203, Complexity: ?
- **if**(`0 args`) — Line 221, Complexity: ?
- **handleDelete**(`0 args`) — Line 228, Complexity: ?
- **catch**(`0 args`) — Line 234, Complexity: ?
- **if**(`0 args`) — Line 243, Complexity: ?
- **if**(`0 args`) — Line 254, Complexity: ?
- **if**(`0 args`) — Line 266, Complexity: ?

### `frontend\src\app\documents\page.tsx`
- **switch**(`0 args`) — Line 18, Complexity: ?
- **statusColor**(`0 args`) — Line 30, Complexity: ?
- **switch**(`0 args`) — Line 31, Complexity: ?
- **DocumentsPage**(`0 args`) — Line 43, Complexity: ?
- **fetchDocuments**(`0 args`) — Line 52, Complexity: ?
- **catch**(`0 args`) — Line 60, Complexity: ?
- **if**(`0 args`) — Line 71, Complexity: ?
- **if**(`0 args`) — Line 77, Complexity: ?
- **if**(`0 args`) — Line 84, Complexity: ?

### `frontend\src\app\graph\page.tsx`
- **ForceGraph2D**(`0 args`) — Line 30, Complexity: ?
- **GraphPage**(`0 args`) — Line 56, Complexity: ?
- **handleSearchInput**(`0 args`) — Line 88, Complexity: ?
- **if**(`0 args`) — Line 128, Complexity: ?
- **if**(`0 args`) — Line 134, Complexity: ?
- **catch**(`0 args`) — Line 139, Complexity: ?
- **handleSelectCase**(`0 args`) — Line 149, Complexity: ?
- **handleDepthChange**(`0 args`) — Line 155, Complexity: ?
- **handleModeChange**(`0 args`) — Line 160, Complexity: ?

### `frontend\src\app\judge\[name]\loading.tsx`
- **Loading**(`0 args`) — Line 3, Complexity: ?

### `frontend\src\app\judge\[name]\page.tsx`
- **JudgeProfilePage**(`0 args`) — Line 32, Complexity: ?
- **load**(`0 args`) — Line 43, Complexity: ?
- **catch**(`0 args`) — Line 53, Complexity: ?

### `frontend\src\app\judges\compare\page.tsx`
- **JudgeComparePage**(`0 args`) — Line 27, Complexity: ?
- **handleClick**(`0 args`) — Line 41, Complexity: ?
- **searchJudges**(`0 args`) — Line 53, Complexity: ?
- **handleSearchChange**(`0 args`) — Line 71, Complexity: ?
- **addJudge**(`0 args`) — Line 79, Complexity: ?
- **removeJudge**(`0 args`) — Line 87, Complexity: ?
- **handleCompare**(`0 args`) — Line 91, Complexity: ?
- **if**(`0 args`) — Line 101, Complexity: ?
- **disposalCompare**(`0 args`) — Line 116, Complexity: ?

### `frontend\src\app\judges\page.tsx`
- **JudgesPage**(`0 args`) — Line 12, Complexity: ?
- **fetchJudges**(`0 args`) — Line 21, Complexity: ?
- **catch**(`0 args`) — Line 31, Complexity: ?
- **handleSearchChange**(`0 args`) — Line 43, Complexity: ?
- **if**(`0 args`) — Line 45, Complexity: ?

### `frontend\src\app\login\page.tsx`
- **LoginPage**(`0 args`) — Line 14, Complexity: ?
- **if**(`0 args`) — Line 19, Complexity: ?
- **validate**(`0 args`) — Line 30, Complexity: ?
- **if**(`0 args`) — Line 35, Complexity: ?
- **handleSubmit**(`0 args`) — Line 44, Complexity: ?
- **catch**(`0 args`) — Line 52, Complexity: ?

### `frontend\src\app\page.tsx`
- **HomePage**(`0 args`) — Line 39, Complexity: ?
- **handleSearch**(`0 args`) — Line 43, Complexity: ?
- **handleExampleClick**(`0 args`) — Line 50, Complexity: ?

### `frontend\src\app\privacy\page.tsx`
- **PrivacyPage**(`0 args`) — Line 4, Complexity: ?

### `frontend\src\app\providers.tsx`
- **Providers**(`0 args`) — Line 6, Complexity: ?

### `frontend\src\app\register\page.tsx`
- **RegisterPage**(`0 args`) — Line 14, Complexity: ?
- **validate**(`0 args`) — Line 25, Complexity: ?
- **if**(`0 args`) — Line 30, Complexity: ?
- **handleSubmit**(`0 args`) — Line 39, Complexity: ?
- **catch**(`0 args`) — Line 47, Complexity: ?

### `frontend\src\app\robots.ts`
- **robots**(`0 args`) — Line 3, Complexity: ?

### `frontend\src\app\search\loading.tsx`
- **Loading**(`0 args`) — Line 3, Complexity: ?

### `frontend\src\app\search\page.tsx`
- **SearchContent**(`0 args`) — Line 33, Complexity: ?
- **executeSearch**(`0 args`) — Line 67, Complexity: ?
- **catch**(`0 args`) — Line 90, Complexity: ?
- **if**(`0 args`) — Line 100, Complexity: ?
- **fetchSuggestions**(`0 args`) — Line 113, Complexity: ?
- **catch**(`0 args`) — Line 131, Complexity: ?
- **handleSuggestionSelect**(`0 args`) — Line 139, Complexity: ?
- **handleHistorySelect**(`0 args`) — Line 146, Complexity: ?
- **if**(`0 args`) — Line 149, Complexity: ?
- **handleInputKeyDown**(`0 args`) — Line 159, Complexity: ?
- **if**(`0 args`) — Line 162, Complexity: ?
- **if**(`0 args`) — Line 167, Complexity: ?
- **if**(`0 args`) — Line 172, Complexity: ?
- **if**(`0 args`) — Line 175, Complexity: ?
- **if**(`0 args`) — Line 183, Complexity: ?
- **handleSearch**(`0 args`) — Line 202, Complexity: ?
- **handlePageChange**(`0 args`) — Line 211, Complexity: ?
- **exportResults**(`0 args`) — Line 217, Complexity: ?
- **if**(`0 args`) — Line 272, Complexity: ?
- **SearchPage**(`0 args`) — Line 628, Complexity: ?

### `frontend\src\app\sitemap.ts`
- **sitemap**(`0 args`) — Line 3, Complexity: ?

### `frontend\src\app\terms\page.tsx`
- **TermsPage**(`0 args`) — Line 9, Complexity: ?

### `frontend\src\app\upload\page.tsx`
- **UploadPage**(`0 args`) — Line 13, Complexity: ?
- **if**(`0 args`) — Line 21, Complexity: ?
- **catch**(`0 args`) — Line 34, Complexity: ?
- **if**(`0 args`) — Line 46, Complexity: ?

### `frontend\src\components\__tests__\footnote-list-item.test.tsx`
- **makeMockFootnote**(`0 args`) — Line 6, Complexity: ?

### `frontend\src\components\__tests__\footnotes-panel.test.tsx`
- **makeMockFootnote**(`0 args`) — Line 14, Complexity: ?

### `frontend\src\components\agent-checkpoint-prompt.tsx`
- **inferSuggestions**(`0 args`) — Line 23, Complexity: ?
- **if**(`0 args`) — Line 26, Complexity: ?
- **if**(`0 args`) — Line 38, Complexity: ?
- **renderValue**(`0 args`) — Line 54, Complexity: ?
- **if**(`0 args`) — Line 67, Complexity: ?
- **AgentCheckpointPrompt**(`0 args`) — Line 82, Complexity: ?
- **handleSubmit**(`0 args`) — Line 92, Complexity: ?
- **handleChipClick**(`0 args`) — Line 113, Complexity: ?
- **handleRetry**(`0 args`) — Line 131, Complexity: ?

### `frontend\src\components\agent-hub-card.tsx`
- **AgentHubCard**(`0 args`) — Line 16, Complexity: ?

### `frontend\src\components\agent-memo-viewer.tsx`
- **if**(`0 args`) — Line 80, Complexity: ?
- **if**(`0 args`) — Line 86, Complexity: ?
- **if**(`0 args`) — Line 110, Complexity: ?
- **if**(`0 args`) — Line 164, Complexity: ?
- **stripFootnoteDefinitions**(`0 args`) — Line 174, Complexity: ?
- **extractHeadings**(`0 args`) — Line 179, Complexity: ?
- **slugify**(`0 args`) — Line 189, Complexity: ?
- **extractSectionContent**(`0 args`) — Line 194, Complexity: ?
- **for**(`0 args`) — Line 198, Complexity: ?
- **if**(`0 args`) — Line 200, Complexity: ?
- **if**(`0 args`) — Line 203, Complexity: ?
- **MemoTOC**(`0 args`) — Line 212, Complexity: ?
- **for**(`0 args`) — Line 219, Complexity: ?
- **if**(`0 args`) — Line 220, Complexity: ?
- **AgentMemoViewer**(`0 args`) — Line 257, Complexity: ?
- **headings**(`0 args`) — Line 264, Complexity: ?
- **footnotesMap**(`0 args`) — Line 266, Complexity: ?
- **handleCopy**(`0 args`) — Line 272, Complexity: ?
- **handleCopySection**(`0 args`) — Line 292, Complexity: ?
- **if**(`0 args`) — Line 294, Complexity: ?
- **handleDownload**(`0 args`) — Line 305, Complexity: ?
- **cleanContent**(`0 args`) — Line 317, Complexity: ?
- **components**(`0 args`) — Line 320, Complexity: ?
- **if**(`0 args`) — Line 549, Complexity: ?
- **if**(`0 args`) — Line 554, Complexity: ?
- **if**(`0 args`) — Line 560, Complexity: ?
- **if**(`0 args`) — Line 574, Complexity: ?

### `frontend\src\components\agent-step-timeline.tsx`
- **getStepLabel**(`0 args`) — Line 49, Complexity: ?
- **AgentStepTimeline**(`0 args`) — Line 59, Complexity: ?
- **derivedCompleted**(`0 args`) — Line 60, Complexity: ?

### `frontend\src\components\agents\AgentFollowUpInput.tsx`
- **handleSend**(`0 args`) — Line 28, Complexity: ?
- **if**(`0 args`) — Line 34, Complexity: ?
- **if**(`0 args`) — Line 41, Complexity: ?
- **handleChange**(`0 args`) — Line 49, Complexity: ?

### `frontend\src\components\agents\AgentFollowUpThread.tsx`
- **StreamingDots**(`0 args`) — Line 18, Complexity: ?
- **SourceBadges**(`0 args`) — Line 28, Complexity: ?
- **MemoMessage**(`0 args`) — Line 45, Complexity: ?
- **if**(`0 args`) — Line 82, Complexity: ?

### `frontend\src\components\agents\AgentSessionSidebar.tsx`
- **timeAgo**(`0 args`) — Line 12, Complexity: ?

### `frontend\src\components\audio-player.tsx`
- **formatTime**(`0 args`) — Line 34, Complexity: ?
- **AudioPlayer**(`0 args`) — Line 40, Complexity: ?
- **fetchStatus**(`0 args`) — Line 53, Complexity: ?
- **load**(`0 args`) — Line 68, Complexity: ?
- **if**(`0 args`) — Line 73, Complexity: ?
- **startPolling**(`0 args`) — Line 87, Complexity: ?
- **if**(`0 args`) — Line 91, Complexity: ?
- **stopPolling**(`0 args`) — Line 98, Complexity: ?
- **if**(`0 args`) — Line 99, Complexity: ?
- **handleTimeUpdate**(`0 args`) — Line 113, Complexity: ?
- **if**(`0 args`) — Line 114, Complexity: ?
- **handleLoadedMetadata**(`0 args`) — Line 119, Complexity: ?
- **if**(`0 args`) — Line 120, Complexity: ?
- **handleEnded**(`0 args`) — Line 125, Complexity: ?
- **togglePlay**(`0 args`) — Line 129, Complexity: ?
- **if**(`0 args`) — Line 131, Complexity: ?
- **handleSeek**(`0 args`) — Line 140, Complexity: ?
- **if**(`0 args`) — Line 142, Complexity: ?
- **handlePlaybackRateChange**(`0 args`) — Line 148, Complexity: ?
- **if**(`0 args`) — Line 150, Complexity: ?
- **handleGenerate**(`0 args`) — Line 155, Complexity: ?
- **handleLanguageChange**(`0 args`) — Line 165, Complexity: ?
- **if**(`0 args`) — Line 172, Complexity: ?
- **if**(`0 args`) — Line 189, Complexity: ?
- **if**(`0 args`) — Line 207, Complexity: ?

### `frontend\src\components\bench-strength.tsx`
- **BenchStrength**(`0 args`) — Line 16, Complexity: ?
- **if**(`0 args`) — Line 22, Complexity: ?

### `frontend\src\components\confidence-meter.tsx`
- **ConfidenceMeter**(`0 args`) — Line 10, Complexity: ?

### `frontend\src\components\cookie-consent.tsx`
- **CookieConsent**(`0 args`) — Line 9, Complexity: ?
- **if**(`0 args`) — Line 15, Complexity: ?
- **accept**(`0 args`) — Line 20, Complexity: ?

### `frontend\src\components\draft-section-viewer.tsx`
- **formatSectionName**(`0 args`) — Line 16, Complexity: ?
- **DraftSectionViewer**(`0 args`) — Line 22, Complexity: ?
- **toggleSection**(`0 args`) — Line 29, Complexity: ?
- **handleStartRevision**(`0 args`) — Line 41, Complexity: ?
- **handleCancelRevision**(`0 args`) — Line 46, Complexity: ?
- **handleSubmitRevision**(`0 args`) — Line 51, Complexity: ?
- **if**(`0 args`) — Line 96, Complexity: ?

### `frontend\src\components\equivalent-citations.tsx`
- **EquivalentCitations**(`0 args`) — Line 12, Complexity: ?
- **handleCopy**(`0 args`) — Line 21, Complexity: ?
- **onSuccess**(`0 args`) — Line 23, Complexity: ?
- **if**(`0 args`) — Line 28, Complexity: ?
- **fallbackCopyText**(`0 args`) — Line 38, Complexity: ?

### `frontend\src\components\error-boundary.tsx`
- **getDerivedStateFromError**(`0 args`) — Line 10, Complexity: ?
- **componentDidCatch**(`0 args`) — Line 14, Complexity: ?
- **render**(`0 args`) — Line 18, Complexity: ?
- **if**(`0 args`) — Line 19, Complexity: ?

### `frontend\src\components\file-upload.tsx`
- **FileUpload**(`0 args`) — Line 13, Complexity: ?
- **if**(`0 args`) — Line 22, Complexity: ?
- **if**(`0 args`) — Line 27, Complexity: ?
- **handleDragLeave**(`0 args`) — Line 45, Complexity: ?
- **handleClick**(`0 args`) — Line 72, Complexity: ?

### `frontend\src\components\footer.tsx`
- **Footer**(`0 args`) — Line 7, Complexity: ?

### `frontend\src\components\footnote-list-item.tsx`
- **if**(`0 args`) — Line 49, Complexity: ?
- **if**(`0 args`) — Line 52, Complexity: ?
- **if**(`0 args`) — Line 55, Complexity: ?

### `frontend\src\components\footnote-preview.tsx`
- **PdfViewer**(`0 args`) — Line 23, Complexity: ?
- **FootnotePreview**(`0 args`) — Line 88, Complexity: ?
- **if**(`0 args`) — Line 106, Complexity: ?
- **if**(`0 args`) — Line 110, Complexity: ?

### `frontend\src\components\footnotes-panel.tsx`
- **filteredFootnotes**(`0 args`) — Line 33, Complexity: ?
- **if**(`0 args`) — Line 35, Complexity: ?
- **usedFootnotes**(`0 args`) — Line 50, Complexity: ?
- **unusedFootnotes**(`0 args`) — Line 51, Complexity: ?
- **handleFootnoteClick**(`0 args`) — Line 57, Complexity: ?

### `frontend\src\components\header.tsx`
- **LanguageToggle**(`0 args`) — Line 12, Complexity: ?
- **if**(`0 args`) — Line 14, Complexity: ?
- **toggleLocale**(`0 args`) — Line 21, Complexity: ?
- **Header**(`0 args`) — Line 42, Complexity: ?
- **handleSearch**(`0 args`) — Line 50, Complexity: ?

### `frontend\src\components\legal-disclaimer.tsx`
- **LegalDisclaimer**(`0 args`) — Line 8, Complexity: ?

### `frontend\src\components\pdf-viewer.tsx`
- **PdfViewer**(`0 args`) — Line 15, Complexity: ?

### `frontend\src\components\plan-review.tsx`
- **if**(`0 args`) — Line 209, Complexity: ?
- **moveTask**(`0 args`) — Line 214, Complexity: ?
- **removeTask**(`0 args`) — Line 221, Complexity: ?
- **handleApprove**(`0 args`) — Line 225, Complexity: ?
- **handleRequestChanges**(`0 args`) — Line 242, Complexity: ?

### `frontend\src\components\precedent-badge.tsx`
- **PrecedentBadge**(`0 args`) — Line 34, Complexity: ?

### `frontend\src\components\processing-status.tsx`
- **getStepIndex**(`0 args`) — Line 19, Complexity: ?
- **ProcessingStatus**(`0 args`) — Line 23, Complexity: ?
- **if**(`0 args`) — Line 24, Complexity: ?
- **if**(`0 args`) — Line 50, Complexity: ?
- **if**(`0 args`) — Line 53, Complexity: ?

### `frontend\src\components\research-audit-trail.tsx`
- **ResearchAuditTrail**(`0 args`) — Line 11, Complexity: ?

### `frontend\src\components\research-process-panel.tsx`
- **formatEventData**(`0 args`) — Line 24, Complexity: ?
- **switch**(`0 args`) — Line 26, Complexity: ?
- **ResearchProcessPanel**(`0 args`) — Line 50, Complexity: ?

### `frontend\src\components\research-progress-bar.tsx`
- **for**(`0 args`) — Line 22, Complexity: ?
- **computeProgress**(`0 args`) — Line 33, Complexity: ?
- **for**(`0 args`) — Line 35, Complexity: ?
- **if**(`0 args`) — Line 37, Complexity: ?
- **types**(`0 args`) — Line 47, Complexity: ?
- **has**(`0 args`) — Line 49, Complexity: ?
- **if**(`0 args`) — Line 73, Complexity: ?
- **ResearchProgressBar**(`0 args`) — Line 80, Complexity: ?

### `frontend\src\components\search\SearchHistoryDropdown.tsx`
- **if**(`0 args`) — Line 37, Complexity: ?
- **sorted**(`0 args`) — Line 39, Complexity: ?
- **if**(`0 args`) — Line 40, Complexity: ?

### `frontend\src\components\section-filter.tsx`
- **SectionFilter**(`0 args`) — Line 40, Complexity: ?

### `frontend\src\components\skeleton.tsx`
- **Skeleton**(`0 args`) — Line 3, Complexity: ?
- **SearchResultSkeleton**(`0 args`) — Line 9, Complexity: ?
- **CaseDetailSkeleton**(`0 args`) — Line 24, Complexity: ?

### `frontend\src\components\ui\card.tsx`
- **Card**(`0 args`) — Line 5, Complexity: ?
- **CardHeader**(`0 args`) — Line 18, Complexity: ?
- **CardTitle**(`0 args`) — Line 31, Complexity: ?
- **CardDescription**(`0 args`) — Line 41, Complexity: ?
- **CardContent**(`0 args`) — Line 51, Complexity: ?

### `frontend\src\components\ui\dropdown-menu.tsx`
- **DropdownMenu**(`0 args`) — Line 7, Complexity: ?
- **DropdownMenuTrigger**(`0 args`) — Line 11, Complexity: ?

### `frontend\src\components\ui\input.tsx`
- **Input**(`0 args`) — Line 5, Complexity: ?

### `frontend\src\components\ui\textarea.tsx`
- **Textarea**(`0 args`) — Line 5, Complexity: ?

### `frontend\src\components\verification-banner.tsx`
- **VerificationBanner**(`0 args`) — Line 11, Complexity: ?

### `frontend\src\lib\api.ts`
- **setTokens**(`0 args`) — Line 48, Complexity: ?
- **if**(`0 args`) — Line 51, Complexity: ?
- **clearTokens**(`0 args`) — Line 57, Complexity: ?
- **if**(`0 args`) — Line 60, Complexity: ?
- **loadTokens**(`0 args`) — Line 66, Complexity: ?
- **if**(`0 args`) — Line 67, Complexity: ?
- **getAccessToken**(`0 args`) — Line 73, Complexity: ?
- **getRefreshToken**(`0 args`) — Line 77, Complexity: ?
- **onSessionExpired**(`0 args`) — Line 85, Complexity: ?
- **emitSessionExpired**(`0 args`) — Line 90, Complexity: ?
- **for**(`0 args`) — Line 91, Complexity: ?
- **tryRefreshToken**(`0 args`) — Line 97, Complexity: ?
- **isTokenExpired**(`0 args`) — Line 102, Complexity: ?
- **ensureFreshToken**(`0 args`) — Line 113, Complexity: ?
- **extractErrorMessage**(`0 args`) — Line 139, Complexity: ?
- **extractErrorCode**(`0 args`) — Line 156, Complexity: ?
- **if**(`0 args`) — Line 172, Complexity: ?
- **timeoutId**(`0 args`) — Line 179, Complexity: ?
- **if**(`0 args`) — Line 182, Complexity: ?
- **if**(`0 args`) — Line 196, Complexity: ?
- **catch**(`0 args`) — Line 200, Complexity: ?
- **if**(`0 args`) — Line 203, Complexity: ?
- **if**(`0 args`) — Line 208, Complexity: ?
- **if**(`0 args`) — Line 211, Complexity: ?
- **if**(`0 args`) — Line 224, Complexity: ?
- **tryRefresh**(`0 args`) — Line 239, Complexity: ?
- **_doRefresh**(`0 args`) — Line 251, Complexity: ?
- **login**(`0 args`) — Line 270, Complexity: ?
- **register**(`0 args`) — Line 279, Complexity: ?
- **logout**(`0 args`) — Line 288, Complexity: ?
- **searchFacets**(`0 args`) — Line 335, Complexity: ?
- **getCase**(`0 args`) — Line 362, Complexity: ?
- **getCaseCitations**(`0 args`) — Line 366, Complexity: ?
- **getCaseCitedBy**(`0 args`) — Line 374, Complexity: ?
- **getCaseSimilar**(`0 args`) — Line 382, Complexity: ?
- **getCasePdfUrl**(`0 args`) — Line 390, Complexity: ?
- **getChatSessions**(`0 args`) — Line 437, Complexity: ?
- **getChatHistory**(`0 args`) — Line 442, Complexity: ?
- **deleteChatSession**(`0 args`) — Line 447, Complexity: ?
- **if**(`0 args`) — Line 475, Complexity: ?
- **if**(`0 args`) — Line 487, Complexity: ?
- **catch**(`0 args`) — Line 491, Complexity: ?
- **if**(`0 args`) — Line 492, Complexity: ?
- **if**(`0 args`) — Line 497, Complexity: ?
- **if**(`0 args`) — Line 512, Complexity: ?
- **while**(`0 args`) — Line 525, Complexity: ?
- **for**(`0 args`) — Line 533, Complexity: ?
- **if**(`0 args`) — Line 540, Complexity: ?
- **if**(`0 args`) — Line 552, Complexity: ?
- **catch**(`0 args`) — Line 555, Complexity: ?
- **if**(`0 args`) — Line 561, Complexity: ?
- **getGraphStats**(`0 args`) — Line 616, Complexity: ?
- **getJudgeProfile**(`0 args`) — Line 637, Complexity: ?
- **compareJudges**(`0 args`) — Line 656, Complexity: ?
- **namesParam**(`0 args`) — Line 657, Complexity: ?
- **getCourtStats**(`0 args`) — Line 661, Complexity: ?
- **uploadDocument**(`0 args`) — Line 669, Complexity: ?
- **if**(`0 args`) — Line 674, Complexity: ?
- **timeoutId**(`0 args`) — Line 680, Complexity: ?
- **if**(`0 args`) — Line 690, Complexity: ?
- **catch**(`0 args`) — Line 694, Complexity: ?
- **if**(`0 args`) — Line 695, Complexity: ?
- **if**(`0 args`) — Line 700, Complexity: ?
- **if**(`0 args`) — Line 714, Complexity: ?
- **getDocument**(`0 args`) — Line 734, Complexity: ?
- **deleteDocument**(`0 args`) — Line 738, Complexity: ?
- **getAudioStatus**(`0 args`) — Line 751, Complexity: ?
- **getAudioUrl**(`0 args`) — Line 755, Complexity: ?
- **getAgentExecution**(`0 args`) — Line 811, Complexity: ?
- **if**(`0 args`) — Line 826, Complexity: ?
- **if**(`0 args`) — Line 835, Complexity: ?
- **catch**(`0 args`) — Line 839, Complexity: ?
- **if**(`0 args`) — Line 840, Complexity: ?
- **if**(`0 args`) — Line 845, Complexity: ?
- **if**(`0 args`) — Line 857, Complexity: ?
- **getDraftingTemplates**(`0 args`) — Line 913, Complexity: ?
- **if**(`0 args`) — Line 922, Complexity: ?
- **if**(`0 args`) — Line 931, Complexity: ?
- **catch**(`0 args`) — Line 935, Complexity: ?
- **if**(`0 args`) — Line 936, Complexity: ?
- **if**(`0 args`) — Line 941, Complexity: ?
- **if**(`0 args`) — Line 953, Complexity: ?
- **deleteAgentSession**(`0 args`) — Line 1020, Complexity: ?
- **deleteSearchHistoryEntry**(`0 args`) — Line 1046, Complexity: ?

### `frontend\src\lib\auth-context.tsx`
- **isTokenExpired**(`0 args`) — Line 30, Complexity: ?
- **AuthProvider**(`0 args`) — Line 40, Complexity: ?
- **init**(`0 args`) — Line 48, Complexity: ?
- **if**(`0 args`) — Line 54, Complexity: ?
- **if**(`0 args`) — Line 66, Complexity: ?
- **if**(`0 args`) — Line 73, Complexity: ?
- **if**(`0 args`) — Line 80, Complexity: ?
- **unsubscribe**(`0 args`) — Line 92, Complexity: ?
- **login**(`0 args`) — Line 99, Complexity: ?
- **catch**(`0 args`) — Line 104, Complexity: ?
- **register**(`0 args`) — Line 112, Complexity: ?
- **catch**(`0 args`) — Line 117, Complexity: ?
- **logout**(`0 args`) — Line 125, Complexity: ?
- **clearAuthError**(`0 args`) — Line 131, Complexity: ?
- **useAuth**(`0 args`) — Line 141, Complexity: ?

### `frontend\src\lib\utils.ts`
- **cn**(`0 args`) — Line 4, Complexity: ?

### `frontend\src\middleware.ts`
- **middleware**(`0 args`) — Line 3, Complexity: ?

### `ralph_loop_scanner.py`
- **load_config**(`config_path`) — Line 29, Complexity: 1
- **__init__**(`self, config`) — Line 40, Complexity: 1
- **discover_files**(`self`) — Line 46, Complexity: 5
- **read_file_safe**(`self, filepath`) — Line 61, Complexity: 3
- **get_file_hash**(`self, content`) — Line 70, Complexity: 1
- **analyze**(`self, filepath, content`) — Line 81, Complexity: 4
- **_analyze_node**(`self, tree, content, findings, filepath`) — Line 107, Complexity: 9
- **_analyze_function**(`self, node, content, lines`) — Line 143, Complexity: 22
- **_analyze_class**(`self, node, content, lines`) — Line 241, Complexity: 4
- **_analyze_import**(`self, node`) — Line 261, Complexity: 3
- **_check_security_patterns**(`self, content, lines, findings`) — Line 276, Complexity: 4
- **_check_error_handling**(`self, tree, content, findings`) — Line 306, Complexity: 10
- **_check_hardcoded_values**(`self, content, lines, findings`) — Line 333, Complexity: 5
- **_get_snippet**(`self, content, lineno, context`) — Line 357, Complexity: 1
- **_get_call_name**(`self, node`) — Line 364, Complexity: 3
- **_get_decorator_name**(`self, node`) — Line 371, Complexity: 4
- **_get_node_name**(`self, node`) — Line 380, Complexity: 3
- **_is_module_level**(`self, node, tree`) — Line 387, Complexity: 1
- **analyze**(`self, filepath, content`) — Line 398, Complexity: 1
- **_extract_functions**(`self, content, lines, findings`) — Line 417, Complexity: 7
- **_extract_imports**(`self, content, lines, findings`) — Line 455, Complexity: 4
- **_extract_classes**(`self, content, lines, findings`) — Line 462, Complexity: 3
- **_check_patterns**(`self, content, lines, findings`) — Line 472, Complexity: 4
- **_check_react_patterns**(`self, content, lines, findings, filepath`) — Line 502, Complexity: 5
- **analyze**(`self, filepath, content`) — Line 532, Complexity: 5
- **_check_env_file**(`self, lines, findings`) — Line 557, Complexity: 8
- **_check_json**(`self, content, filepath, findings`) — Line 574, Complexity: 3
- **_check_json_keys**(`self, data, filepath, findings, depth`) — Line 588, Complexity: 9
- **_check_sql**(`self, lines, findings`) — Line 607, Complexity: 3
- **_check_yaml**(`self, lines, findings`) — Line 618, Complexity: 3
- **__init__**(`self`) — Line 637, Complexity: 1
- **build_graph**(`self, all_findings`) — Line 641, Complexity: 6
- **find_circular_deps**(`self`) — Line 649, Complexity: 5
- **__init__**(`self, config`) — Line 702, Complexity: 1
- **get_focus_for_iteration**(`self, iteration`) — Line 717, Complexity: 3
- **hash_issue**(`self, issue`) — Line 723, Complexity: 1
- **run_single_iteration**(`self, iteration`) — Line 727, Complexity: 10
- **generate_markdown_report**(`self`) — Line 805, Complexity: 27
- **run**(`self`) — Line 996, Complexity: 4
- **dfs**(`node, path`) — Line 654, Complexity: 4

---

## 7. RECOMMENDATIONS

1. **IMMEDIATE:** Fix all CRITICAL security and syntax issues before next deployment
2. **THIS SPRINT:** Address HIGH severity issues, especially error handling gaps
3. **SECRETS:** Move all hardcoded secrets to environment variables / vault
4. **TYPE SAFETY:** Add type hints / TypeScript strict mode progressively
5. **CLEANUP:** Remove dead code and resolve all TODO/FIXME comments
6. **LOGGING:** Replace print/console.log with structured logging

---
*Report generated by Ralph Loop v1.0 — 100 iterations*
*Smriti Legal AI — NeetiQ / Nyaya / Ritam*