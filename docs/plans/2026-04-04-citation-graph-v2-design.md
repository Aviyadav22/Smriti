# Citation Graph Explorer v2 — "Indian Citator"

**Date:** 2026-04-04
**Status:** Approved
**Goal:** Transform the empty graph page into a case validation and discovery tool for litigating advocates.

## Core Concept

Three modes: **Dashboard** (landing state), **Timeline View** (date × authority), **Network View** (enhanced force-directed). Powered by topic-sensitive PageRank, treatment signals, and structural importance metrics precomputed via Neo4j GDS.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Graph Page                      │
│  ┌───────────┬──────────────┬──────────────────┐ │
│  │ Dashboard │ Timeline View│ Network View     │ │
│  │ (landing) │ (date x rank)│ (force-directed) │ │
│  └───────────┴──────────────┴──────────────────┘ │
│  ┌──────────────────────────────────────────────┐ │
│  │          Case Detail Side Panel              │ │
│  └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│              API Endpoints                       │
│  GET /graph/dashboard                            │
│  GET /graph/communities                          │
│  GET /graph/{id}/treatment-summary               │
│  GET /graph/path?from={id}&to={id}               │
│  (existing: neighborhood, chain, authorities,    │
│   stats, evolution — enhanced with new props)    │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│     Neo4j Community + GDS (self-hosted VM)       │
│  - Precomputed PageRank (global + per-topic)     │
│  - Louvain community detection                   │
│  - Stored as node properties                     │
└─────────────────────────────────────────────────┘
```

## Section 1: Dashboard (Landing State)

When an advocate lands on `/graph`, they see three columns:

- **Most Cited Authorities** — Top 10 by topic-sensitive PageRank, filtered by selected topic (defaults to "All"). Shows authority score badge.
- **Rising Authorities** — Cases most cited by judgments from the last 3 years (by judgment date, not ingestion date). Cases where `recent_citation_ratio > 0.4` AND `cited_by_count > 5`.
- **Recently Overruled/Distinguished** — Cases with negative treatment, sorted by the overruling judgment's date.

**Topic filter pills** at the bottom: Constitutional, Criminal, Civil, Tax, Labour, Property, Family, Commercial, All. Derived from Louvain clusters auto-labeled by most common `acts_cited`/`keywords`.

Each case card shows: title, citation, authority score, treatment badge (green/yellow/red). Clickable to enter graph view centered on that case.

Graph stats displayed at bottom: "X judgments · Y citations"

## Section 2: Timeline View (Date × Authority)

New default visualization when exploring a case.

- **X-axis** = judgment date
- **Y-axis** = topic-sensitive authority score (0-100)
- **Node size** = `cited_by_count` (log scale)
- **Node color** = treatment status relative to query case: green (followed/affirmed), red (overruled), yellow (distinguished), gray (neutral/cites)
- **Edge color** = treatment type (existing `EDGE_COLORS` map)
- **Edge style** = solid for positive treatment, dashed for negative
- **Hover** = tooltip with case name, citation, year, authority score
- **Click** = opens side panel

**Filters:** topic dropdown (switches PageRank scores), treatment type multi-select, date range slider, bench size.

**Why better than force-directed for advocates:** Spatial position encodes recency + authority. Upper-right quadrant = recent + authoritative = best cases to cite.

**Implementation:** D3 scatterplot with zoom/pan + edge rendering, or `react-force-graph-2d` with fixed X/Y positioning (force simulation disabled).

## Section 3: Network View (Enhanced Force-Directed)

Existing `react-force-graph-2d` view, enhanced:

- **Node color by treatment** — green/yellow/red/gray relative to query case
- **Authority score badge** — small number label on each node
- **Community cluster shading** — light background color per Louvain community
- **Edge labels on hover** — treatment type + citing paragraph snippet (from existing `context` on CITES edges)
- **Filter panel** — same as Timeline: topic, treatment, date range, bench size

**New mode: Citation Path Finder**
- Third toggle alongside "Neighborhood" / "Chain": **"Path"**
- Two search boxes: "From case" and "To case"
- Shows all shortest paths via Neo4j `shortestPath()`
- Answers "how does Case A connect to Case B through precedent?"

## Section 4: Case Detail Side Panel

Slides in from right on node click. Contains:

- **Case header** — title, citation
- **Treatment summary bar** — percentage positive vs negative, single-word verdict (Followed / Cautionary / Overruled). Answers "can I cite this?" at a glance.
- **Topic-sensitive authority scores** — top 2-3 relevant topics for this case
- **Case metadata** — bench type, year, case type
- **Ratio excerpt** — truncated ratio decidendi from Neo4j node property (max 2000 chars)
- **Treatment breakdown** — count by type (followed, applied, distinguished, overruled, etc.)
- **Top citing cases** — 3-5 most authoritative cases that cite this one
- **Action buttons** — "View Full Case" navigates to `/cases/{id}`, "Explore from here" recenters graph on this case

## Section 5: Backend — Precomputed Analytics

### Analytics Job (post-ingestion)

Run as a Python CLI command after each ingestion batch:

1. **Louvain Community Detection** → store `community_id`, `community_label` on nodes. Auto-label by most frequent `acts_cited`/`keywords`. Typically 15-30 communities.
2. **Topic-Sensitive PageRank** → run PageRank on subgraphs filtered by community. Also run global PageRank. Store `pagerank_global`, `pagerank_community`. Normalize to 0-100.
3. **Rising Authority** → count citations from judgments dated within last 3 years vs total. Store `recent_citation_ratio`.
4. **Treatment Aggregation** → count incoming CITES edges grouped by treatment type. Compute `treatment_positive_pct`. Store `treatment_positive_pct`, `treatment_summary` (JSON).
5. **Invalidate Redis caches** — `graph:stats`, `graph:dashboard`, `graph:communities`.

### New API Endpoints

| Endpoint | Purpose | Cache |
|----------|---------|-------|
| `GET /graph/dashboard` | Dashboard data (most-cited, rising, overruled by topic) | 1 hour Redis |
| `GET /graph/communities` | List of communities with labels and top cases | 1 hour Redis |
| `GET /graph/{id}/treatment-summary` | Treatment breakdown for one case | 15 min Redis |
| `GET /graph/path?from={id}&to={id}` | Shortest paths between two cases | No cache |

### Enhanced Existing Endpoints

`neighborhood`, `chain`, `authorities` responses include new node properties: `pagerank_global`, `pagerank_community`, `community_id`, `community_label`, `treatment_positive_pct`, `treatment_summary`, `recent_citation_ratio`.

### New Node Properties

```
pagerank_global: float         # 0-100, global authority score
pagerank_community: float      # 0-100, authority within own topic
community_id: int              # Louvain community ID
community_label: str           # Auto-generated topic label
recent_citation_ratio: float   # 0-1, fraction of citations from recent (3yr) judgments
treatment_positive_pct: float  # 0-1, fraction of positive treatment
treatment_summary: str         # JSON: {"followed": 43, "distinguished": 7, ...}
```

## Section 6: Infrastructure

- **Current:** Neo4j AuraDB Free — fully supported by this implementation
- **Implementation:** Analytics computed via Python `networkx` library, results written back to Neo4j as node properties. No GDS dependency.
- **Future (optional):** At 30K+ nodes, consider self-hosted Neo4j + GDS Community Edition for native in-database computation (faster, no data transfer). Not required for current scale.

## Data Flow

```
Ingestion Batch Completes
         │
         ▼
  Analytics Job (CLI: python -m scripts.compute_graph_analytics)
         │
         ├─→ Louvain communities → node properties
         ├─→ PageRank (global + per community) → node properties
         ├─→ Rising authority calc → node properties
         ├─→ Treatment aggregation → node properties
         └─→ Invalidate Redis caches
         
Frontend Load
         │
         ├─→ GET /graph/dashboard (cached 1hr) → 3-column dashboard
         │
         User searches/clicks case
         │
         ├─→ GET /graph/{id}/neighborhood → Timeline or Network view
         │
         User clicks node
         │
         └─→ Side panel (data from graph response, no extra call)
```

## Key Decisions

- **networkx vs Neo4j GDS:** Using networkx for now (works with AuraDB Free). At 30K+ nodes, consider migrating to self-hosted Neo4j + GDS for native in-database computation. Current implementation has no GDS dependency.
- **Real-time vs precomputed:** All analytics precomputed. Dashboard loads <200ms. Zero extra latency on graph views.
- **Timeline implementation:** D3 scatterplot preferred over hacking `react-force-graph-2d` with fixed positions. Cleaner separation of concerns.
- **Ingestion-agnostic trending:** "Rising authority" uses judgment date (not ingestion date) to avoid batch ingestion noise.
- **Treatment summary:** Stored as JSON string on node, parsed client-side. Avoids extra API call on node click.
