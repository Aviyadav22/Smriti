# Product Evolution Design — April 2026

**Date:** 2026-04-01
**Status:** Approved
**Scope:** 7 features that take Smriti from polished engine to user-ready product

---

## Table of Contents

1. [Feature 1: Fix Session Restore](#feature-1-fix-session-restore)
2. [Feature 2: Share Research Memo via Link](#feature-2-share-research-memo-via-link)
3. [Feature 3: Judge Prediction Model](#feature-3-judge-prediction-model)
4. [Feature 4: Argument Builder (Strategy Agent Upgrade)](#feature-4-argument-builder-strategy-agent-upgrade)
5. [Feature 5: Opposing Counsel Analysis](#feature-5-opposing-counsel-analysis)
6. [Feature 6: Case Timeline Visualization](#feature-6-case-timeline-visualization)
7. [Feature 7: Smriti Learning Over Time](#feature-7-smriti-learning-over-time)

---

## Feature 1: Fix Session Restore

### Problem

When a user clicks a previous research agent session in the sidebar or history page, only the session title appears — the memo content does not render.

### Root Cause

Two issues working together:

**A. Memo message may never get saved to `agent_messages`.**
The `AgentMessage` with `message_type="memo"` is created in the `_session_stream()` generator AFTER the SSE stream finishes (`agents.py:1516-1542`). If the client disconnects or the generator isn't fully consumed, this post-stream code never runs. The `except Exception` at line 1541 silently swallows failures.

**B. `loadSession()` only looks at messages, ignores execution `result_data`.**
The execution's `result_data` (saved reliably at `agents.py:346-353` inside `_stream_agent_events`) always contains the memo when the agent completes. But `loadSession()` (`research/page.tsx:223-251`) only calls `getAgentSessionMessages()` — it never fetches execution data. If the memo message wasn't saved (issue A), there's nothing to display.

### Fix

**Change 1 — Backend: Include `result_data` in session detail response.**
`GET /sessions/{session_id}` (`agents.py:1906-1931`) currently queries executions without `result_data`. Add `result_data` to the SELECT so the frontend can access memo content from the execution.

**Change 2 — Frontend: Update `loadSession()` with execution fallback.**
1. Call `getAgentSessionMessages(sid)` AND `getAgentSessionDetail(sid)` in parallel.
2. Try to extract memo from messages first (existing behavior).
3. Fallback: if no memo message found, get it from the latest completed execution's `result_data`.
4. Also restore from `result_data`: `confidence`, `confidenceBreakdown`, `researchAudit`, `executionId`, `footnotes`.

**Change 3 — Backend: Move memo-as-message save to reliable location.**
Move the memo message creation from the `_session_stream()` generator (unreliable, depends on generator being fully consumed) to inside `_stream_agent_events`'s completion block (where `result_data` is already saved at line 346). This ensures the memo message is saved whenever the agent completes, regardless of client connection state.

### Files Changed

- `backend/app/api/routes/agents.py` — Add `result_data` to session detail query; move memo message save
- `frontend/src/app/agents/research/page.tsx` — Update `loadSession()` with execution fallback
- `frontend/src/lib/api.ts` — Update `getAgentSessionDetail` return type if needed

---

## Feature 2: Share Research Memo via Link

### Overview

Allow users to share a completed research memo via a public URL. The recipient can view the memo and footnotes without authentication.

### Database Schema

```sql
CREATE TABLE shared_memos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES agent_executions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    share_token VARCHAR(32) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_shared_memos_token ON shared_memos (share_token) WHERE is_active = true;
CREATE INDEX idx_shared_memos_user ON shared_memos (user_id);
CREATE UNIQUE INDEX idx_shared_memos_execution ON shared_memos (execution_id) WHERE is_active = true;
```

### Backend Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/agents/research/{execution_id}/share` | POST | Required | Create/return share token |
| `/agents/research/{execution_id}/share` | GET | Required | Check if active share exists |
| `/agents/research/{execution_id}/share` | DELETE | Required | Revoke share (set `is_active=false`) |
| `/shared/{token}` | GET | **None** | Public read-only memo viewer |

**POST /agents/research/{execution_id}/share:**
- Validates user owns the execution
- Generates 22-char URL-safe token via `secrets.token_urlsafe(16)`
- If active share already exists for this execution, returns existing token (upsert)
- Optional body: `{expires_in_days: int}` — sets `expires_at`
- Returns: `{share_url: "https://neetiq.in/shared/{token}", token, expires_at, share_id}`

**GET /shared/{token}:**
- Public endpoint — no authentication
- Queries `shared_memos` by token WHERE `is_active=true` AND (`expires_at IS NULL OR expires_at > NOW()`)
- Increments `view_count`
- Returns: `{title, memo, footnotes, created_at, agent_type}`
- Returns 404 if token invalid, expired, or revoked

### Privacy

Only the memo text and footnotes are exposed. No user identity, original query, session context, or search history is shared.

### Frontend

- **Share button** in `AgentMemoViewer` component — calls POST, copies URL to clipboard, shows success toast
- **Share indicator** — if memo has active share, show link icon with "Shared" badge and copy/revoke actions
- **Public viewer page** at `/shared/[token]` — read-only rendered memo with footnotes. NeetiQ branding. No auth required. "Powered by NeetiQ — AI Legal Research" footer with CTA.

---

## Feature 3: Judge Prediction Model

### Overview

Statistical prediction of likely case outcome based on judge's historical disposal patterns. Not ML — a heuristic model using existing metadata.

### Algorithm

**Input:** `judge_name(s)`, `case_type`, `jurisdiction` (optional), `acts_cited[]` (optional), `bench_type` (optional)

**Steps:**

1. **Base rate:** Query `disposal_nature` distribution for this judge WHERE `case_type` matches. E.g., Judge X dismissed 62% of Criminal Appeals (47 cases).

2. **Act-specific adjustment:** If `acts_cited` provided, check if judge has skewed patterns on those specific acts. E.g., Judge X dismisses 71% of NDPS cases (14 cases). Weight: blend base rate and act-specific rate based on act-specific sample size.

3. **Bench composition effect:** If multiple judges specified, query historical outcomes for exact bench combinations or pairwise co-judge patterns. Some bench combinations have materially different outcomes.

4. **Temporal weighting:** Apply exponential decay — cases from last 3 years weighted 2x compared to older cases. Captures evolving judicial disposition.

5. **Sample size guard:** If total matching cases < 10, set confidence to "low" and add prominent caveat.

**Output:**
```python
JudgePrediction(
    predicted_outcome="Dismissed",
    outcome_probabilities={"Dismissed": 0.62, "Allowed": 0.28, "Partly Allowed": 0.10},
    confidence=0.72,  # based on sample size and data consistency
    sample_size=47,
    factors=[
        Factor(name="Disposal pattern for Criminal Appeals", impact="strong", detail="62% dismissal rate (47 cases)"),
        Factor(name="NDPS Act cases", impact="moderate", detail="71% dismissal (14 cases)"),
        Factor(name="Temporal trend", impact="weak", detail="Slight increase in dismissals over last 2 years"),
    ],
    caveats=[
        "Based on 47 historical cases from Supreme Court records.",
        "Past judicial patterns do not predict future outcomes.",
        "This is a statistical summary, not legal advice.",
    ],
)
```

### API

`GET /judges/predict?judges=Judge+A,Judge+B&case_type=Criminal+Appeal&acts=NDPS+Act&bench_type=division`

Rate limited: 30/minute. Cached: 1 hour (keyed on params).

### Frontend

- **Prediction card** on judge profile page (`/judge/[name]`) — shows predicted outcome, probability bars, contributing factors, caveats
- **Optional integration** in research agent — during Understand stage, if judge is known, fetch prediction as context for the research plan

### Data Dependencies

All fields already exist in PostgreSQL case model:
- `judge` (ARRAY), `disposal_nature` (String), `case_type` (String)
- `jurisdiction` (String), `acts_cited` (ARRAY), `bench_type` (String)
- `decision_date` (Date) for temporal weighting

---

## Feature 4: Argument Builder (Strategy Agent Upgrade)

### Overview

Evolve the existing strategy agent into a full argument builder with IRAC-structured output, evidence-backed counter-arguments, and optimal argument ordering.

### Current Graph Flow

```
START → analyze_facts → fetch_judge → [checkpoint_analysis] →
search_precedents → assess_strength → generate_arguments →
[checkpoint_arguments] → counter_and_judge →
synthesize_strategy → verify → [checkpoint_memo] → END
```

### New Graph Flow

```
START → analyze_facts → element_decomposition → fetch_judge → [checkpoint_analysis] →
search_precedents → assess_strength → generate_arguments_irac → [checkpoint_arguments] →
adversarial_search → counter_and_judge → argument_ordering →
synthesize_argument_memo → verify → [checkpoint_memo] → END
```

### New/Modified Nodes

**1. `element_decomposition` (new, reused from research agent)**
- Imported from `app.core.agents.nodes.common.element_decomposition_node`
- After fact analysis, decomposes the legal question into elements: mens rea, actus reus, defenses, exceptions, statutory requirements
- Feeds into search_precedents (more targeted queries) and generate_arguments (structured issue identification)

**2. `adversarial_search` (new, adapted from research agent)**
- After arguments are generated, actively searches for cases that OPPOSE the client's position
- Uses LLM to generate counter-argument queries, dispatches searches, validates via mini-CRAG relevance check
- Currently `counter_arguments_node` generates counters via LLM reasoning alone — this adds evidence-backed counter-arguments with real case citations

**3. `generate_arguments_irac` (modified from `generate_arguments_node`)**
- Output structured IRAC format per argument:
  - **Issue:** The specific legal question addressed
  - **Rule:** Statute text + binding precedents (with strength classification)
  - **Application:** How the client's facts map to the legal rule
  - **Conclusion:** The argued outcome
- Authorities ranked: BINDING > PERSUASIVE > DISTINGUISHABLE

**4. `argument_ordering` (new, logic from case_prep's `build_argument_order_node`)**
- Orders arguments by:
  - Strength of supporting authority (binding SC precedent > HC persuasive)
  - Judge's historical receptiveness (from judge profile)
  - Procedural priority (jurisdictional arguments first, merits second)
- Output: reordered `irac_arguments` list

**5. `synthesize_argument_memo` (modified from `synthesize_strategy_node`)**
- Generates a structured argument document:
  - Executive summary (2-3 paragraphs)
  - Ordered arguments (IRAC format, numbered)
  - Counter-arguments with rebuttals (evidence-backed from adversarial search)
  - Distinguishing adverse precedents
  - Recommended submission strategy
  - Authorities cited with precedent strength badges
- Exportable to Word/PDF via existing export infrastructure

### State Additions to `StrategyState`

```python
legal_elements: list[dict]        # from element_decomposition
adversarial_results: list[dict]   # opposing case law from adversarial_search
argument_order: list[int]         # optimal ordering indices
irac_arguments: list[dict]        # structured IRAC format
```

### Files Changed

- `backend/app/core/agents/strategy.py` — Updated graph with new nodes and edges
- `backend/app/core/agents/state.py` — `StrategyState` additions
- `backend/app/core/agents/nodes/strategy_nodes.py` — New/modified node functions
- `backend/app/core/legal/prompts.py` — IRAC prompt templates, adversarial prompts
- `backend/app/core/drafting/export.py` — Argument memo export templates

---

## Feature 5: Opposing Counsel Analysis

### Overview

Analytics on advocates who have appeared before the Supreme Court — win rates, specializations, head-to-head records.

### Data Source

`party_counsel` JSONB field on cases. Structure:
```json
[{"party": "petitioner", "counsel_name": "R.K. Sharma", "designation": "senior_advocate"}]
```

### Name Normalization

Same lawyer may appear as "Mr. R.K. Sharma", "Shri R.K. Sharma", "R.K. Sharma, Sr. Adv."

**Approach:**
1. Strip honorifics: Mr., Smt., Shri, Dr., Ms., Mrs., Hon'ble
2. Normalize designations: "Senior Advocate"/"Sr. Adv."/"Sr. Advocate" → `senior_advocate`
3. Strip trailing whitespace, commas, periods
4. Store canonical form in a `counsel_names` lookup/materialized view
5. Fuzzy matching (trigram similarity via `pg_trgm`) for near-duplicates during aggregation

### New Service

`backend/app/core/analytics/counsel_analytics.py`

**Computed metrics per counsel:**
- Total appearances (petitioner side vs respondent side)
- Win rate: % of cases where their party got favorable disposal (Allowed for petitioner, Dismissed for respondent)
- Case type distribution (Criminal Appeal, SLP, Writ, etc.)
- Acts most frequently argued
- Courts appeared in
- Active year range (first appearance → last)
- Senior Advocate vs AOR distinction
- Bench compositions appeared before
- Frequent opposing counsels + head-to-head win/loss

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /counsel` | Search counsels by name (paginated, `pg_trgm` search) |
| `GET /counsel/{name}` | Full profile with all stats (cached 1hr) |
| `GET /counsel/{name}/cases` | Paginated case list with year/type filters |
| `GET /counsel/{name}/matchups` | Head-to-head records vs frequent opponents |

### Frontend

New `/counsel/[name]` page:
- Stats cards: total cases, win rate, specialization
- Case type pie chart
- Year-over-year activity bar chart
- Matchup table: top 10 opposing counsels with win/loss record
- Case list with filters

### Data Quality Caveat

Not all cases have clean `party_counsel` data. Extraction confidence varies. Display a data quality indicator on the profile page based on what percentage of the counsel's cases have confident extraction.

---

## Feature 6: Case Timeline Visualization

### Overview

Two timeline views: (A) procedural journey of a single case through courts, (B) precedent evolution showing how a legal principle developed through citations over time.

### A. Procedural Timeline

**Data sources** (all in PostgreSQL case model):
- `procedural_history` (JSONB) — court chain with dates and outcomes
- `filing_date`, `decision_date` — temporal anchors
- `interim_orders` (ARRAY) — stay orders, directions during pendency
- `lower_court`, `appeal_from` — appellate chain
- `hearing_count` — number of hearings

**API:** `GET /cases/{case_id}/timeline`

**Response:**
```json
{
    "case_title": "State of UP v. Ram Kumar",
    "events": [
        {"date": "2018-03-15", "type": "filing", "court": "Sessions Court, Lucknow", "detail": "FIR No. 123/2018 under S.302 IPC"},
        {"date": "2019-06-22", "type": "judgment", "court": "Sessions Court, Lucknow", "detail": "Convicted, sentenced to life imprisonment"},
        {"date": "2020-01-10", "type": "appeal_filed", "court": "Allahabad High Court", "detail": "Criminal Appeal No. 123/2020"},
        {"date": "2020-08-15", "type": "interim_order", "court": "Allahabad High Court", "detail": "Sentence suspended during appeal"},
        {"date": "2021-11-30", "type": "judgment", "court": "Allahabad High Court", "detail": "Appeal dismissed, conviction upheld"},
        {"date": "2022-03-01", "type": "appeal_filed", "court": "Supreme Court", "detail": "SLP (Crl.) No. 456/2022"},
        {"date": "2023-07-18", "type": "judgment", "court": "Supreme Court", "detail": "Allowed — conviction set aside, retrial ordered"}
    ]
}
```

**Logic:** Combine `procedural_history` entries, `filing_date` → "Filed" event, `decision_date` → judgment event, each `interim_order` → interim event. Sort chronologically.

### B. Citation Evolution Timeline

**Data source:** Neo4j citation graph

**API:** `GET /graph/{case_id}/evolution?direction=forward&max_depth=3`

**Logic:**
1. Start from the given case (landmark)
2. Follow outgoing CITES relationships forward in time (cases that cite this one)
3. For each citing case, include: citation treatment (followed/distinguished/overruled), date, court, one-line ratio
4. Sort chronologically
5. Cap at `max_depth` hops

**Response:**
```json
{
    "root_case": {"id": "...", "title": "Kharak Singh v. State of UP", "year": 1963},
    "evolution": [
        {"case_id": "...", "title": "Govind v. State of MP", "year": 1975, "treatment": "followed", "ratio_snippet": "Right to privacy implicit in Art. 21"},
        {"case_id": "...", "title": "PUCL v. Union of India", "year": 1997, "treatment": "followed", "ratio_snippet": "Telephone tapping violates Art. 21"},
        {"case_id": "...", "title": "K.S. Puttaswamy v. Union of India", "year": 2017, "treatment": "partly_overruled", "ratio_snippet": "Right to privacy is a fundamental right under Art. 21"}
    ]
}
```

### Frontend

New "Timeline" tab on case detail page (`/cases/[id]`).

**Procedural timeline:** Vertical timeline with event cards. Color-coded by type (filing=blue, judgment=green/red, interim=yellow). Click court name to navigate if that judgment is in our database.

**Citation evolution:** Horizontal or vertical chain with treatment badges (FOLLOWED=green, DISTINGUISHED=amber, OVERRULED=red). Click any case to navigate.

Implementation: Custom React component using CSS — no heavy charting library needed. Simple vertical list with connecting lines and date markers.

---

## Feature 7: Smriti Learning Over Time

### Overview

Three incremental layers that make Smriti increasingly personalized for individual lawyers and firms.

### Layer 1: User Preferences (build first)

**Schema change:** Add `preferences JSONB DEFAULT '{}'` column to `users` table.

**Structure:**
```json
{
    "frequent_acts": ["NDPS Act", "IPC", "CrPC"],
    "preferred_jurisdictions": ["criminal"],
    "common_case_types": ["Criminal Appeal", "Bail Application"],
    "preferred_courts": ["Supreme Court"],
    "output_preference": "detailed",
    "updated_at": "2026-04-15T10:00:00Z"
}
```

**Auto-population:** Background task (weekly cron or on-demand) analyzes last 30 days of:
- Search history queries and filters
- Research agent queries and result interactions
- Acts/sections that appear in bookmarked searches

**Usage points:**
- Search page: pre-fill jurisdiction/court/case_type filters from preferences
- Research agent: include preferences in system prompt context ("This user frequently researches NDPS cases")
- RRF scoring: apply small boost (+0.05) to results matching user's preferred acts/jurisdictions

**API:**
- `GET /users/me/preferences` — current preferences
- `PUT /users/me/preferences` — manual override
- `POST /users/me/preferences/refresh` — trigger re-analysis from history

### Layer 2: Firm/Organization Model (build second)

**New tables:**
```sql
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE org_memberships (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, org_id)
);
```

**Shared within org:**
- Bookmarked searches visible to all members
- Research memo library (completed memos browsable by org members)
- Firm-level preferences (aggregated from all members)
- Admin can set firm defaults: preferred courts, key acts, default output format

**API:**
- `POST /organizations` — create org (creator becomes admin)
- `POST /organizations/{org_id}/invite` — invite user by email
- `GET /organizations/{org_id}/memos` — shared memo library
- `GET /organizations/{org_id}/preferences` — firm-level aggregated preferences

### Layer 3: Implicit Feedback Loop (build third)

**Signals tracked:**
- Search result click-through (which results users actually open)
- Citation usage (which cases appear in final research memos)
- Session follow-up patterns (what users ask after initial research)
- Bookmark frequency (what users save for later)

**New table:**
```sql
CREATE TABLE usage_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    signal_type VARCHAR(30) NOT NULL, -- 'click', 'cite', 'bookmark', 'follow_up'
    case_id UUID REFERENCES cases(id),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_usage_signals_user ON usage_signals (user_id, signal_type, created_at DESC);
```

**Relevance boost:** Simple frequency-based weighting, not ML.
- Cases this user/firm has cited before: +0.1 RRF boost
- Acts this user/firm researches frequently: +0.05 boost in statute worker
- Judges this user views often: surface in research agent context

**Privacy:** All signals stay per-user (Layer 1) or per-org (Layer 2). No cross-user aggregation. DPDP-compliant — signals deleted on account deletion.

---

## Implementation Order

1. **Feature 1: Session restore fix** — Quick win, unblocks daily usage
2. **Feature 2: Share memo** — Enables distribution/virality
3. **Feature 6: Case timeline** — Uses existing data, visual differentiator
4. **Feature 5: Opposing counsel** — Uses existing data, new analytics surface
5. **Feature 3: Judge prediction** — Statistical model on existing data
6. **Feature 4: Argument builder** — Largest scope, builds on strategy agent
7. **Feature 7: Learning system** — Layer 1 first, Layers 2-3 later

Features 1-2 are pre-requisites for user testing. Features 3-6 can be parallelized. Feature 7 is ongoing.
