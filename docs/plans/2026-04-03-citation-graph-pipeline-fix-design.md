# Citation Graph Pipeline Fix — Design Document

**Date:** 2026-04-03
**Status:** Approved
**Approach:** B (Full Pipeline Fix)

## Problem Statement

The citation graph feature has treatment detection and storage working in the ingestion pipeline, but the data never reaches the frontend. All edges render as gray "cites" regardless of actual treatment (overruled, affirmed, distinguished, etc.). Additionally, placeholder nodes for unresolved citations are never merged when real cases are ingested, `cited_by_count` is not persisted on nodes, and the `is_overruled` flag is never set.

### Specific Issues

1. **Traversal queries extract `type(rel)` (returns "CITES") but not `rel.treatment`** — treatment data stored on edges is invisible to the frontend.
2. **Frontend legend is decorative** — colors defined for overrules/affirms/distinguishes but never triggered since all edges arrive as type "cites".
3. **Placeholder nodes never merge** — cited cases not yet ingested get `ref_*` placeholder IDs; when the real case is later ingested, it creates a separate node. CITES edges stay on the orphaned placeholder.
4. **`cited_by_count` not persisted** — computed on-demand but never stored on Neo4j nodes, so graph node sizing is broken.
5. **`is_overruled` is dead code** — authorities query filters on it but ingestion never sets it.

## Design

### Layer 1: Traversal — Surface Treatment Data

**File:** `backend/app/core/graph/traversal.py`

Modify `get_neighborhood()` and `get_citation_chain()` Cypher edge projections to include `rel.treatment`:

```cypher
[rel IN rels | {from: startNode(rel).id, to: endNode(rel).id,
 type: type(rel), treatment: rel.treatment, context: rel.context}]
```

After query, normalize edge `type` for frontend consumption:

| `rel.treatment` value | Edge `type` sent to frontend |
|----------------------|------------------------------|
| `overruled` | `overrules` |
| `affirmed` | `affirms` |
| `distinguished` | `distinguishes` |
| `followed` | `followed` |
| `not_followed` | `not_followed` |
| `doubted` | `doubted` |
| `explained` | `explained` |
| `per_incuriam` | `per_incuriam` |
| `referred_to` / null | `cites` |

This mapping converts past-tense treatment values (stored during ingestion) to display-ready type strings matching the frontend color map.

### Layer 2: Frontend — Edge Colors and Placeholder Styling

**Files:** `frontend/src/lib/types.ts`, `frontend/src/app/case/[id]/page.tsx`, `frontend/src/app/graph/page.tsx`

#### Edge Color Map (expanded)

```typescript
const EDGE_COLORS: Record<string, string> = {
    cites:          "#9CA3AF", // gray
    overrules:      "#EF4444", // red
    affirms:        "#22C55E", // green
    distinguishes:  "#F97316", // orange
    followed:       "#60A5FA", // blue
    not_followed:   "#F87171", // light red
    doubted:        "#FBBF24", // amber
    explained:      "#A78BFA", // purple
    per_incuriam:   "#EF4444", // red (same as overrules — equally severe)
};
```

#### Placeholder Node Styling

Detection heuristic: a node is a placeholder if its `id` starts with `ref_` OR (`year` is null AND `court` is null AND `title` matches a citation pattern).

Visual treatment:
- **Regular nodes:** Solid fill, gold (active) / gray (others)
- **Placeholder nodes:** Reduced opacity (0.4), slightly smaller size, lighter fill

#### Legend Update

Expand the full graph page legend to show the 6 most important types: Cites, Overrules, Affirms, Distinguishes, Followed, Doubted.

### Layer 3: Ingestion — Placeholder Resolution

**File:** `backend/app/core/ingestion/pipeline.py` — `_build_citation_graph()`

Before `create_node`, attempt in-place promotion of an existing placeholder:

```cypher
MATCH (p:Case {citation: $citation})
WHERE p.id STARTS WITH 'ref_'
SET p.id = $real_id, p.title = $title, p.court = $court,
    p.year = $year, p.bench_type = $bench_type,
    p.case_type = $case_type, p.disposal_nature = $disposal_nature,
    p.judge = $judge, p.keywords = $keywords,
    p.acts_cited = $acts_cited, p.ratio = $ratio
RETURN p.id
```

In-place `SET` preserves all existing incoming/outgoing CITES edges — no edge migration needed.

If no placeholder found, fall through to normal `create_node`.

For equivalent citations, merge additional placeholder nodes into the real node by transferring their edges then deleting the duplicate.

### Layer 4: Ingestion — Persist `cited_by_count` and `is_overruled`

**File:** `backend/app/core/ingestion/pipeline.py` — `_build_citation_graph()`

#### `is_overruled` — set atomically during edge creation

Modify the CITES edge creation query to also set the flag:

```cypher
UNWIND $edges AS e
MATCH (a:Case {id: $from_id}), (b:Case {citation: e.citation})
MERGE (a)-[r:CITES]->(b)
SET r.reporter = e.reporter, r.treatment = e.treatment
WITH b, e WHERE e.treatment = 'overruled'
SET b.is_overruled = true
```

#### `cited_by_count` — compute after edge creation

```cypher
// Update counts for all cases this case cites
MATCH (target:Case)<-[:CITES]-(citing:Case {id: $case_id})
WITH target, count { (target)<-[:CITES]-() } AS cnt
SET target.cited_by_count = cnt
```

```cypher
// Update this case's own count
MATCH (self:Case {id: $case_id})
SET self.cited_by_count = count { (self)<-[:CITES]-() }
```

### Layer 5: Migration Script

**File:** `backend/scripts/migrate_graph_properties.py`

One-time idempotent script to backfill existing data:

1. **Persist `cited_by_count` for all nodes:**
   ```cypher
   MATCH (c:Case)
   SET c.cited_by_count = count { (c)<-[:CITES]-() }
   ```

2. **Set `is_overruled` from existing treatment data:**
   ```cypher
   MATCH (target:Case)<-[r:CITES]-(source)
   WHERE r.treatment = 'overruled'
   SET target.is_overruled = true
   ```

3. **Resolve placeholders matching already-ingested cases:**
   ```cypher
   MATCH (real:Case), (placeholder:Case)
   WHERE NOT real.id STARTS WITH 'ref_'
     AND placeholder.id STARTS WITH 'ref_'
     AND placeholder.citation = real.citation
   // Transfer edges, delete placeholder
   ```

Features: dry-run mode, progress logging, idempotent (safe to re-run).

### Layer 6: Tests

- **Traversal unit tests:** Verify treatment → display type normalization for all 8 treatments
- **Placeholder resolution test:** Mock graph store, verify in-place promotion preserves edges
- **`is_overruled` test:** Verify flag set when treatment is "overruled"
- **`cited_by_count` test:** Verify count persisted after graph build
- **Frontend tests (vitest):** Edge color mapping for all treatment types, placeholder node detection and styling

## Files Changed

| File | Changes |
|------|---------|
| `backend/app/core/graph/traversal.py` | Extract `rel.treatment`, normalize edge types |
| `backend/app/core/ingestion/pipeline.py` | Placeholder resolution, `cited_by_count`, `is_overruled` |
| `frontend/src/lib/types.ts` | (No change needed — `type: string` already flexible) |
| `frontend/src/app/case/[id]/page.tsx` | Placeholder node styling, edge colors |
| `frontend/src/app/graph/page.tsx` | Expanded color map, legend update, placeholder styling |
| `backend/scripts/migrate_graph_properties.py` | New — one-time migration |
| `backend/tests/unit/test_graph_traversal.py` | New/expanded — traversal + treatment tests |

## Non-Goals

- Separate Neo4j relationship types (OVERRULES, AFFIRMS, etc.) — deferred; property-based approach is sufficient and doesn't require re-ingestion.
- Re-ingestion of existing cases — migration script handles backfill.
- Bench strength / precedent scoring — future feature, not part of this fix.
