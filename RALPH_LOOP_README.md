# RALPH LOOP — Setup & Usage Guide
## Recursive Audit Loop for Programmatic Health

### What This Does

Runs **100 iterations** of deep code analysis over **8+ hours** on the Smriti codebase.
Each iteration scans **every single file**, traces **every function**, and checks for:

- Security vulnerabilities (eval, injection, XSS, hardcoded secrets)
- Error handling gaps (bare excepts, missing try/catch in async)
- Logic flow issues (high complexity, long functions, loose equality)
- Type safety problems (missing type hints, `any` types, @ts-ignore)
- Dead code (TODO/FIXME/HACK comments, unreachable code)
- Performance bottlenecks (N+1 patterns, SELECT *, array index keys)
- State management bugs (race conditions, side effects)
- Dependency chain risks (circular imports)
- API contract mismatches
- Configuration drift and hardcoded values
- Logging gaps (print/console.log in production)
- And 20+ other audit categories

### Output

- `ralph_loop_reports/ralph_loop_100.md` — The full 100-iteration report
- `ralph_loop_reports/ralph_loop_raw.json` — Machine-readable raw findings
- `ralph_loop_reports/checkpoint_iter_*.json` — Progress checkpoints every 10 iterations

---

## Quick Setup (3 Steps)

### Step 1: Copy files to your Smriti project root

```bash
# Copy these 3 files to your Smriti project root directory:
cp ralph_loop_config.json /path/to/smriti/
cp ralph_loop_scanner.py /path/to/smriti/
cp ralph_loop_runner.sh /path/to/smriti/

# Make the runner executable
cd /path/to/smriti
chmod +x ralph_loop_runner.sh
```

### Step 2: Edit config (optional)

Open `ralph_loop_config.json` and adjust:
- `codebase_root` — set to `"."` if files are in project root
- `exclude_dirs` — add any folders you want to skip
- `file_extensions_to_audit` — add/remove file types

### Step 3: Run it

```bash
# Option A: Run in foreground (watch it work)
./ralph_loop_runner.sh

# Option B: Run in background (overnight — RECOMMENDED)
./ralph_loop_runner.sh --background

# Monitor progress
tail -f ralph_loop_reports/ralph_loop.log

# Check status
./ralph_loop_runner.sh --status

# Stop early if needed
./ralph_loop_runner.sh --stop
```

---

## Claude Code Prompt

If you want to run this through **Claude Code** for enhanced AI-powered analysis, use this prompt:

---

### PROMPT TO GIVE CLAUDE CODE:

```
I have a Ralph Loop audit system set up in this project. Here's what I need you to do:

1. First, read ralph_loop_config.json, ralph_loop_scanner.py, and ralph_loop_runner.sh to understand the system.

2. Then run the Ralph Loop:
   - Execute: python3 ralph_loop_scanner.py ralph_loop_config.json
   - This will run 100 iterations scanning every file in the codebase
   - Each iteration analyzes every function, traces logic flow, checks security, error handling, types, dead code, and 20+ categories
   - It will run for 8+ hours with checkpoints every 10 iterations

3. While it runs, I want you to ALSO do your own parallel deep audit:
   - Read every single .py, .js, .jsx, .ts, .tsx file in this project
   - For each file, trace every function call chain end-to-end
   - Map the complete data flow from API input to database to response
   - Identify any logic that doesn't match its docstring/comments
   - Find any function that is defined but never called
   - Check every API endpoint for input validation
   - Verify every database query has proper error handling
   - Check auth middleware is applied consistently
   - Look for any state mutations without proper synchronization

4. After the automated loop completes, read ralph_loop_reports/ralph_loop_100.md and ralph_loop_reports/ralph_loop_raw.json

5. Combine YOUR manual findings with the automated report into a MASTER AUDIT DOCUMENT that covers:
   - Executive summary with health score
   - Every critical and high severity issue with fix recommendations
   - Complete function registry (every function in the codebase)
   - Call graph showing which functions call which
   - Data flow diagram for each API endpoint
   - Security audit summary
   - Performance hotspots
   - Test coverage gaps
   - Architecture improvement recommendations

Save the final combined report as ralph_loop_reports/MASTER_AUDIT_REPORT.md
```

---

### SHORTER PROMPT (if you want just the automated scan):

```
Run `python3 ralph_loop_scanner.py` in this project directory. It will do 100 iterations of deep code analysis over 8 hours. Monitor the output and let me know when it completes. Then read ralph_loop_reports/ralph_loop_100.md and give me a summary of the top findings.
```

---

## How the Iterations Work

| Iterations | Focus Area | What It Does |
|-----------|-----------|-------------|
| 1-10 | Surface Scan | Function signatures, imports, basic structure |
| 11-20 | Logic Trace | Control flow, branches, return paths |
| 21-30 | Error Audit | Exception handling, edge cases, failure modes |
| 31-40 | Security Sweep | Injection points, auth gaps, data exposure |
| 41-50 | Performance Scan | Complexity hotspots, N+1 queries, memory |
| 51-60 | State Analysis | State mutations, race conditions, side effects |
| 61-70 | Dependency Audit | Import chains, circular deps, version risks |
| 71-80 | Dead Code Hunt | Unreachable code, unused exports, stale configs |
| 81-90 | API Contract Check | Input/output validation, schema drift |
| 91-100 | Final Synthesis | Cross-cutting concerns, architecture review |

Each iteration scans ALL files but applies extra scrutiny to its focus area.
Issues are deduplicated — the same issue won't be reported twice.
Dynamic sleep between iterations ensures the loop runs for the full 8 hours.

---

## Reading the Report

The `ralph_loop_100.md` report contains:

1. **Executive Summary** — Health score (0-100), total files/lines/functions/issues
2. **Issues by Category** — All 20 audit categories with severity breakdown
3. **Hotspot Files** — Top 30 files with most issues
4. **Iteration Timeline** — What each iteration found and how long it took
5. **Critical Issues Detail** — Full code snippets for every CRITICAL issue
6. **Complete Function Registry** — Every function in the codebase listed with complexity
7. **Recommendations** — Prioritized action items

---

*Built for Smriti — NeetiQ / Nyaya / Ritam Legal AI*
