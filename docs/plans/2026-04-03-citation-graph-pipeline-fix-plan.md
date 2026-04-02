# Citation Graph Pipeline Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface treatment data (overruled, affirmed, distinguished, etc.) through the full stack — from Neo4j edges to colored graph edges in the frontend — and fix placeholder resolution, `cited_by_count` persistence, and `is_overruled` flag.

**Architecture:** Treatment data is already stored on CITES edges in Neo4j during ingestion. The fix is plumbing: modify traversal Cypher to extract `rel.treatment`, normalize to frontend display types in Python, pass through API, and map to edge colors in React. Ingestion gets three enhancements: placeholder node promotion (in-place SET), `cited_by_count` persistence, and `is_overruled` flag setting.

**Tech Stack:** Python/FastAPI (backend), Neo4j Cypher (graph queries), React/Next.js + react-force-graph-2d (frontend), pytest + vitest (tests)

**Design doc:** `docs/plans/2026-04-03-citation-graph-pipeline-fix-design.md`

---

## Task 1: Traversal — Extract Treatment and Normalize Edge Types

**Files:**
- Modify: `backend/app/core/graph/traversal.py:32-101` (get_neighborhood) and `:114-170` (get_citation_chain)

### Step 1: Write failing tests for treatment normalization

Add to `backend/tests/unit/test_graph_traversal.py`:

```python
class TestTreatmentNormalization:
    """Test that treatment properties on CITES edges are normalized to display types."""

    @pytest.mark.asyncio
    async def test_overruled_treatment_becomes_overrules(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2",
                    "title": "Overruled Case",
                    "citation": "(2020) 1 SCC 2",
                    "court": "Supreme Court of India",
                    "year": 2020,
                    "cited_by_count": 5,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": "overruled", "context": None},
                    ],
                },
            ],
            get_node_return={
                "id": "case_1", "title": "Center", "citation": "(2019) 1 SCC 1",
                "court": "SC", "year": 2019, "cited_by_count": 10,
            },
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "overrules"

    @pytest.mark.asyncio
    async def test_affirmed_treatment_becomes_affirms(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2", "title": "Affirmed Case", "citation": None,
                    "court": "SC", "year": 2020, "cited_by_count": 0,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": "affirmed", "context": None},
                    ],
                },
            ],
            get_node_return={"id": "case_1"},
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "affirms"

    @pytest.mark.asyncio
    async def test_distinguished_treatment_becomes_distinguishes(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2", "title": "X", "citation": None,
                    "court": "SC", "year": 2020, "cited_by_count": 0,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": "distinguished", "context": None},
                    ],
                },
            ],
            get_node_return={"id": "case_1"},
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "distinguishes"

    @pytest.mark.asyncio
    async def test_null_treatment_becomes_cites(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2", "title": "X", "citation": None,
                    "court": "SC", "year": 2020, "cited_by_count": 0,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": None, "context": None},
                    ],
                },
            ],
            get_node_return={"id": "case_1"},
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "cites"

    @pytest.mark.asyncio
    async def test_referred_to_treatment_becomes_cites(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2", "title": "X", "citation": None,
                    "court": "SC", "year": 2020, "cited_by_count": 0,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": "referred_to", "context": None},
                    ],
                },
            ],
            get_node_return={"id": "case_1"},
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "cites"

    @pytest.mark.asyncio
    async def test_all_treatment_types_mapped(self) -> None:
        """Every known treatment value produces a valid display type."""
        treatments = {
            "overruled": "overrules",
            "affirmed": "affirms",
            "distinguished": "distinguishes",
            "followed": "followed",
            "not_followed": "not_followed",
            "doubted": "doubted",
            "explained": "explained",
            "per_incuriam": "per_incuriam",
            "referred_to": "cites",
            None: "cites",
        }
        for treatment_val, expected_type in treatments.items():
            store = _make_graph_store(
                query_return=[
                    {
                        "id": "case_2", "title": "X", "citation": None,
                        "court": "SC", "year": 2020, "cited_by_count": 0,
                        "edges": [
                            {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": treatment_val, "context": None},
                        ],
                    },
                ],
                get_node_return={"id": "case_1"},
            )
            result = await get_neighborhood("case_1", graph_store=store, depth=1)
            assert result["edges"][0]["type"] == expected_type, f"treatment={treatment_val!r} should map to {expected_type!r}"

    @pytest.mark.asyncio
    async def test_citation_chain_also_normalizes_treatment(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "cited_1", "title": "X", "citation": None,
                    "court": "SC", "year": 2018, "cited_by_count": 3,
                    "edges": [
                        {"from": "case_1", "to": "cited_1", "treatment": "overruled"},
                    ],
                },
            ],
        )
        result = await get_citation_chain("case_1", graph_store=store, max_depth=2)
        assert result["edges"][0]["type"] == "overrules"
```

### Step 2: Run tests to verify they fail

Run: `cd backend && python -m pytest tests/unit/test_graph_traversal.py::TestTreatmentNormalization -v`
Expected: FAIL — edges currently pass through `type` as-is ("CITES"), no treatment normalization exists.

### Step 3: Implement treatment normalization in traversal.py

Add the treatment-to-display-type mapping at the top of the file (after `MAX_NODES`):

```python
# Map Neo4j treatment property values to frontend display types.
# Past-tense values from ingestion → present-tense/noun form for display.
_TREATMENT_TO_DISPLAY: dict[str | None, str] = {
    "overruled": "overrules",
    "affirmed": "affirms",
    "distinguished": "distinguishes",
    "followed": "followed",
    "not_followed": "not_followed",
    "doubted": "doubted",
    "explained": "explained",
    "per_incuriam": "per_incuriam",
    "referred_to": "cites",
    None: "cites",
}
```

Modify the Cypher edge projection in `get_neighborhood()` (line 43) to include `treatment`:

```python
"  [rel IN rels | {from: startNode(rel).id, to: endNode(rel).id, "
"   type: type(rel), treatment: rel.treatment, context: rel.context}] AS edges "
```

Modify the edge-building loop in `get_neighborhood()` (lines 87-96) to normalize the type:

```python
for edge in record.get("edges", []):
    edge_key = (edge["from"], edge["to"], edge.get("type", "CITES"))
    if edge_key not in edges_set:
        edges_set.add(edge_key)
        treatment = edge.get("treatment")
        edges_list.append({
            "from": edge["from"],
            "to": edge["to"],
            "type": _TREATMENT_TO_DISPLAY.get(treatment, "cites"),
            "context": edge.get("context"),
        })
```

Apply the same changes to `get_citation_chain()`:

Modify the Cypher (line 130) to include `treatment`:
```python
"  [rel IN rels | {from: startNode(rel).id, to: endNode(rel).id, "
"   type: type(rel), treatment: rel.treatment}] AS edges "
```

Modify the edge-building loop (lines 158-166):
```python
for edge in record.get("edges", []):
    edge_key = (edge["from"], edge["to"])
    if edge_key not in edges_set:
        edges_set.add(edge_key)
        treatment = edge.get("treatment")
        edges_list.append({
            "from": edge["from"],
            "to": edge["to"],
            "type": _TREATMENT_TO_DISPLAY.get(treatment, "cites"),
        })
```

### Step 4: Run tests to verify they pass

Run: `cd backend && python -m pytest tests/unit/test_graph_traversal.py -v`
Expected: ALL PASS (both new treatment tests and existing tests).

### Step 5: Commit

```bash
git add backend/app/core/graph/traversal.py backend/tests/unit/test_graph_traversal.py
git commit -m "feat(graph): surface treatment data in traversal queries

Extract rel.treatment from Neo4j CITES edges and normalize
to display types (overrules, affirms, distinguishes, etc.)
for frontend edge coloring."
```

---

## Task 2: Frontend — Expand Edge Colors and Add Placeholder Styling

**Files:**
- Modify: `frontend/src/app/graph/page.tsx:43-48` (EDGE_COLORS), `:295-304` (nodeColor/linkColor), `:320-334` (legend)
- Modify: `frontend/src/app/case/[id]/page.tsx:330-338` (nodeColor/linkColor in mini graph)

### Step 1: Write failing vitest tests

Create or add to `frontend/src/app/graph/__tests__/graph-helpers.test.ts`:

```typescript
import { describe, it, expect } from "vitest";

// These will be extracted as helpers during implementation
const EDGE_COLORS: Record<string, string> = {
    cites: "#9CA3AF",
    overrules: "#EF4444",
    affirms: "#22C55E",
    distinguishes: "#F97316",
    followed: "#60A5FA",
    not_followed: "#F87171",
    doubted: "#FBBF24",
    explained: "#A78BFA",
    per_incuriam: "#EF4444",
};

function isPlaceholderNode(node: { id: string; year?: number | null; court?: string | null }): boolean {
    if (node.id.startsWith("ref_")) return true;
    if (node.year == null && node.court == null) return true;
    return false;
}

describe("EDGE_COLORS", () => {
    it("has colors for all treatment types", () => {
        const required = ["cites", "overrules", "affirms", "distinguishes", "followed", "not_followed", "doubted", "explained", "per_incuriam"];
        for (const type of required) {
            expect(EDGE_COLORS[type]).toBeDefined();
        }
    });

    it("returns gray for unknown types via fallback", () => {
        expect(EDGE_COLORS["unknown_type"] ?? "#9CA3AF").toBe("#9CA3AF");
    });
});

describe("isPlaceholderNode", () => {
    it("detects ref_ prefixed IDs as placeholder", () => {
        expect(isPlaceholderNode({ id: "ref_a1b2c3d4e5f6", year: null, court: null })).toBe(true);
    });

    it("detects nodes with no year and no court as placeholder", () => {
        expect(isPlaceholderNode({ id: "some-uuid", year: null, court: null })).toBe(true);
    });

    it("does not flag real nodes with year and court", () => {
        expect(isPlaceholderNode({ id: "some-uuid", year: 2020, court: "SC" })).toBe(false);
    });

    it("does not flag nodes with only year set", () => {
        expect(isPlaceholderNode({ id: "some-uuid", year: 2020, court: null })).toBe(false);
    });
});
```

### Step 2: Run tests to verify they fail

Run: `cd frontend && npx vitest run src/app/graph/__tests__/graph-helpers.test.ts`
Expected: FAIL — file doesn't exist yet.

### Step 3: Implement edge colors and placeholder detection

**3a.** Update `frontend/src/app/graph/page.tsx` — expand EDGE_COLORS (lines 43-48):

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
    per_incuriam:   "#EF4444", // red (equally severe as overruled)
};
```

**3b.** Add placeholder detection helper (above the component function):

```typescript
function isPlaceholderNode(node: Record<string, unknown>): boolean {
    if (typeof node.id === "string" && node.id.startsWith("ref_")) return true;
    if (node.year == null && node.court == null) return true;
    return false;
}
```

**3c.** Update `nodeColor` callback in full graph page (lines 295-301):

```typescript
nodeColor={(node: Record<string, unknown>) => {
    if (node.id === activeCaseId) return "#B89B6A";
    if (node.id === selectedNode?.id) return "#60A5FA";
    if (isPlaceholderNode(node)) return "#D1D5DB"; // lighter gray for placeholders
    return "#6B7280";
}}
```

**3d.** Update `nodeVal` callback (or add one) to make placeholders smaller. In the `fgData` computation (around line 168-170), adjust val for placeholders:

```typescript
nodes: graphData.nodes.map((n) => ({
    ...n,
    val: isPlaceholderNode(n as Record<string, unknown>)
        ? 1.5
        : Math.max(2, Math.log2((n.cited_by_count || 0) + 1) * 3),
})),
```

**3e.** Update legend (lines 320-334) to show the 6 most important types:

```typescript
{/* Legend */}
<div className="absolute bottom-4 left-4 bg-card/90 border rounded-md px-3 py-2 text-[10px] space-y-1">
    {(["cites", "overrules", "affirms", "distinguishes", "followed", "doubted"] as const).map((type) => (
        <div key={type} className="flex items-center gap-2">
            <span
                className="w-4 h-0.5 inline-block rounded"
                style={{ backgroundColor: EDGE_COLORS[type] }}
            />
            <span className="capitalize text-muted-foreground">{type.replace(/_/g, " ")}</span>
        </div>
    ))}
    <div className="text-muted-foreground/50 mt-1 pt-1 border-t">
        Right-click node to view case
    </div>
</div>
```

**3f.** Update mini graph in `frontend/src/app/case/[id]/page.tsx` — add placeholder styling to nodeColor (around line 335):

```typescript
nodeColor={(node: Record<string, unknown>) => {
    if (node.id === caseId) return "#B89B6A";
    if (isPlaceholderNode(node)) return "#D1D5DB";
    return "#6B7280";
}}
```

Add `isPlaceholderNode` helper above the component (same definition).

Update `linkColor` (around line 338) to use edge type colors:

```typescript
linkColor={(link: Record<string, unknown>) =>
    EDGE_COLORS[(link.type as string) || "cites"] || "#9CA3AF"
}
```

Add the full `EDGE_COLORS` map to this file too (or extract to a shared constant in `lib/graph-utils.ts`).

**3g.** Add the `nodeCanvasObject` or `nodeCanvasObjectMode` for placeholder ring styling (optional enhancement — can use opacity via nodeColor alone for simplicity).

### Step 4: Run tests to verify they pass

Run: `cd frontend && npx vitest run src/app/graph/__tests__/graph-helpers.test.ts`
Expected: PASS

### Step 5: Run full frontend test suite

Run: `cd frontend && npx vitest run`
Expected: All ~311 tests pass.

### Step 6: Commit

```bash
git add frontend/src/app/graph/page.tsx frontend/src/app/case/\[id\]/page.tsx frontend/src/app/graph/__tests__/graph-helpers.test.ts
git commit -m "feat(graph): color edges by treatment type, style placeholder nodes

Expand EDGE_COLORS to 9 treatment types. Placeholder nodes
render lighter and smaller. Legend shows top 6 edge types."
```

---

## Task 3: Ingestion — Placeholder Resolution

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:1291-1366` (_build_citation_graph)
- Test: `backend/tests/unit/test_ingestion_pipeline.py`

### Step 1: Write failing test for placeholder promotion

Add to `backend/tests/unit/test_ingestion_pipeline.py`:

```python
class TestPlaceholderResolution:
    """Test that ingesting a real case promotes matching placeholder nodes."""

    @pytest.mark.asyncio
    async def test_placeholder_promoted_in_place(self) -> None:
        """When a placeholder exists with matching citation, promote it in-place."""
        graph_store = AsyncMock()
        # First query: placeholder resolution — returns a match (placeholder found)
        # Second query: would be create_node (should NOT be called)
        # Third+ queries: citation edge creation, cited_by_count, etc.
        graph_store.query = AsyncMock(side_effect=[
            [{"id": "ref_abc123"}],  # placeholder found and promoted
            [],  # placeholder MERGE for edges
            [],  # CITES edge creation
            [],  # cited_by_count update for targets
            [],  # cited_by_count update for self
        ])
        graph_store.create_node = AsyncMock()

        metadata = _make_metadata(citation="(2020) 1 SCC 100", title="Test Case")
        await _build_citation_graph("real-uuid", metadata, "some full text", graph_store)

        # create_node should NOT be called — placeholder was promoted
        graph_store.create_node.assert_not_called()
        # First query should be the placeholder resolution query
        first_call = graph_store.query.call_args_list[0]
        assert "ref_" in first_call.kwargs.get("cypher", first_call.args[0] if first_call.args else "")

    @pytest.mark.asyncio
    async def test_no_placeholder_falls_through_to_create_node(self) -> None:
        """When no placeholder exists, create node normally."""
        graph_store = AsyncMock()
        graph_store.query = AsyncMock(side_effect=[
            [],  # no placeholder found
            [],  # placeholder MERGE for edges
            [],  # CITES edge creation
            [],  # cited_by_count update for targets
            [],  # cited_by_count update for self
        ])
        graph_store.create_node = AsyncMock()

        metadata = _make_metadata(citation="(2020) 1 SCC 100", title="Test Case")
        await _build_citation_graph("real-uuid", metadata, "some full text", graph_store)

        # create_node SHOULD be called since no placeholder
        graph_store.create_node.assert_called_once()
```

Note: `_make_metadata` is a test helper — check if it already exists in the test file; if not, create a minimal one that returns a `CaseMetadata` with the required fields.

### Step 2: Run test to verify it fails

Run: `cd backend && python -m pytest tests/unit/test_ingestion_pipeline.py::TestPlaceholderResolution -v`
Expected: FAIL — `_build_citation_graph` doesn't attempt placeholder resolution.

### Step 3: Implement placeholder resolution

In `_build_citation_graph()` (pipeline.py, lines 1297-1320), replace the direct `create_node` call with placeholder-aware logic:

```python
async def _build_citation_graph(
    case_id: str,
    metadata: CaseMetadata,
    full_text: str,
    graph_store: GraphStore,
) -> None:
    """Create the case node and citation edges in Neo4j."""
    node_props = {
        "id": case_id,
        "title": metadata.title or "",
        "citation": metadata.citation or "",
        "court": metadata.court or "",
        "year": metadata.year or 0,
        "bench_type": metadata.bench_type or "",
        "case_type": metadata.case_type or "",
        "disposal_nature": metadata.disposal_nature or "",
        "judge": ", ".join(metadata.judge) if metadata.judge else "",
        "keywords": ", ".join(metadata.keywords[:30]) if metadata.keywords else "",
        "acts_cited": ", ".join(metadata.acts_cited[:25]) if metadata.acts_cited else "",
        "ratio": (metadata.ratio_decidendi or "")[:2000],
    }

    # --- Placeholder resolution: promote existing placeholder if citation matches ---
    promoted = False
    if metadata.citation:
        try:
            result = await graph_store.query(
                "MATCH (p:Case {citation: $citation}) "
                "WHERE p.id STARTS WITH 'ref_' "
                "SET p.id = $id, p.title = $title, p.court = $court, "
                "    p.year = $year, p.bench_type = $bench_type, "
                "    p.case_type = $case_type, p.disposal_nature = $disposal_nature, "
                "    p.judge = $judge, p.keywords = $keywords, "
                "    p.acts_cited = $acts_cited, p.ratio = $ratio "
                "RETURN p.id",
                params=node_props,
            )
            promoted = bool(result)
        except (OSError, ConnectionError, RuntimeError) as exc:
            logger.warning("Placeholder resolution failed for %s: %s", case_id, exc)

    if not promoted:
        try:
            await graph_store.create_node("Case", node_props)
        except (OSError, ConnectionError, RuntimeError) as exc:
            logger.error("Failed to create case node %s: %s", case_id, exc)
            return

    # ... rest of function (citation extraction + edge creation) unchanged ...
```

### Step 4: Run tests

Run: `cd backend && python -m pytest tests/unit/test_ingestion_pipeline.py::TestPlaceholderResolution -v`
Expected: PASS

Run: `cd backend && python -m pytest tests/unit/test_ingestion_pipeline.py -v`
Expected: All existing tests still pass.

### Step 5: Commit

```bash
git add backend/app/core/ingestion/pipeline.py backend/tests/unit/test_ingestion_pipeline.py
git commit -m "feat(ingestion): resolve placeholder nodes when real case is ingested

Before creating a new Case node, check if a placeholder (ref_*)
exists with matching citation and promote it in-place. This
preserves all existing CITES edges pointing at the placeholder."
```

---

## Task 4: Ingestion — Persist `cited_by_count` and `is_overruled`

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:1352-1366` (CITES edge creation)
- Test: `backend/tests/unit/test_ingestion_pipeline.py`

### Step 1: Write failing tests

Add to `backend/tests/unit/test_ingestion_pipeline.py`:

```python
class TestGraphPropertyPersistence:
    """Test that cited_by_count and is_overruled are persisted during ingestion."""

    @pytest.mark.asyncio
    async def test_is_overruled_set_on_overruled_citation(self) -> None:
        """When a CITES edge has treatment=overruled, target node gets is_overruled=true."""
        graph_store = AsyncMock()
        graph_store.query = AsyncMock(return_value=[])
        graph_store.create_node = AsyncMock()

        metadata = _make_metadata(citation="(2022) 1 SCC 1", title="Overruling Case")
        # Text containing an overruling reference
        full_text = "The decision in AIR 2010 SC 100 is hereby overruled by this bench."

        await _build_citation_graph("case-uuid", metadata, full_text, graph_store)

        # Find the CITES edge creation query that includes treatment
        cites_calls = [
            c for c in graph_store.query.call_args_list
            if "MERGE (a)-[r:CITES]->(b)" in (c.kwargs.get("cypher", "") or (c.args[0] if c.args else ""))
        ]
        assert len(cites_calls) >= 1
        # Check that the edge creation query includes is_overruled logic
        cites_cypher = cites_calls[0].kwargs.get("cypher", cites_calls[0].args[0] if cites_calls[0].args else "")
        assert "is_overruled" in cites_cypher

    @pytest.mark.asyncio
    async def test_cited_by_count_updated_after_edge_creation(self) -> None:
        """After creating CITES edges, cited_by_count is computed and persisted."""
        graph_store = AsyncMock()
        graph_store.query = AsyncMock(return_value=[])
        graph_store.create_node = AsyncMock()

        metadata = _make_metadata(citation="(2022) 1 SCC 1", title="Citing Case")
        full_text = "As held in AIR 2010 SC 100, the principle applies."

        await _build_citation_graph("case-uuid", metadata, full_text, graph_store)

        # Find queries that set cited_by_count
        count_calls = [
            c for c in graph_store.query.call_args_list
            if "cited_by_count" in (c.kwargs.get("cypher", "") or (c.args[0] if c.args else ""))
        ]
        assert len(count_calls) >= 1, "cited_by_count should be persisted after edge creation"
```

### Step 2: Run tests to verify they fail

Run: `cd backend && python -m pytest tests/unit/test_ingestion_pipeline.py::TestGraphPropertyPersistence -v`
Expected: FAIL — current code doesn't set `is_overruled` or persist `cited_by_count`.

### Step 3: Implement is_overruled and cited_by_count

**3a.** Modify the CITES edge creation query (pipeline.py, lines 1360-1365) to set `is_overruled`:

```python
await graph_store.query(
    "UNWIND $edges AS e "
    "MATCH (a:Case {id: $from_id}), (b:Case {citation: e.citation}) "
    "MERGE (a)-[r:CITES]->(b) "
    "SET r.reporter = e.reporter, r.treatment = e.treatment "
    "WITH b, e "
    "WHERE e.treatment = 'overruled' "
    "SET b.is_overruled = true",
    params={"from_id": case_id, "edges": edge_data},
)
```

**3b.** After the CITES edge creation block (after line 1368), add `cited_by_count` persistence:

```python
# Persist cited_by_count for all cases this case cites (they gained an incoming edge)
try:
    await graph_store.query(
        "MATCH (target:Case)<-[:CITES]-(citing:Case {id: $case_id}) "
        "WITH target, count { (target)<-[:CITES]-() } AS cnt "
        "SET target.cited_by_count = cnt",
        params={"case_id": case_id},
    )
    # Update this case's own count (others may already cite it)
    await graph_store.query(
        "MATCH (self:Case {id: $case_id}) "
        "SET self.cited_by_count = count { (self)<-[:CITES]-() }",
        params={"case_id": case_id},
    )
except (OSError, ConnectionError, RuntimeError) as exc:
    logger.debug("Could not update cited_by_count for %s: %s", case_id, exc)
```

### Step 4: Run tests

Run: `cd backend && python -m pytest tests/unit/test_ingestion_pipeline.py -v`
Expected: ALL PASS

### Step 5: Commit

```bash
git add backend/app/core/ingestion/pipeline.py backend/tests/unit/test_ingestion_pipeline.py
git commit -m "feat(ingestion): persist cited_by_count and is_overruled on graph nodes

Set is_overruled=true on target node when CITES edge treatment is
'overruled'. Compute and persist cited_by_count for affected nodes
after edge creation."
```

---

## Task 5: Migration Script — Backfill Existing Data

**Files:**
- Create: `backend/scripts/migrate_graph_properties.py`

### Step 1: Write the migration script

```python
"""One-time migration: backfill cited_by_count and is_overruled on Neo4j Case nodes.

Also resolves placeholder nodes that match already-ingested cases.

Usage:
    python -m scripts.migrate_graph_properties [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.core.config import settings
from app.core.providers.graph.neo4j_store import Neo4jGraphStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def migrate(dry_run: bool = False) -> None:
    graph = Neo4jGraphStore(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
    )
    try:
        await graph.connect()
        logger.info("Connected to Neo4j at %s", settings.neo4j_uri)

        # 1. Backfill cited_by_count for all Case nodes
        logger.info("Step 1: Backfilling cited_by_count...")
        if not dry_run:
            result = await graph.query(
                "MATCH (c:Case) "
                "SET c.cited_by_count = count { (c)<-[:CITES]-() } "
                "RETURN count(c) AS updated"
            )
            count = result[0]["updated"] if result else 0
            logger.info("  Updated cited_by_count on %d nodes", count)
        else:
            result = await graph.query("MATCH (c:Case) RETURN count(c) AS total")
            logger.info("  [DRY RUN] Would update %d nodes", result[0]["total"] if result else 0)

        # 2. Set is_overruled from existing treatment data
        logger.info("Step 2: Setting is_overruled flags...")
        if not dry_run:
            result = await graph.query(
                "MATCH (target:Case)<-[r:CITES]-(source) "
                "WHERE r.treatment = 'overruled' "
                "SET target.is_overruled = true "
                "RETURN count(DISTINCT target) AS flagged"
            )
            count = result[0]["flagged"] if result else 0
            logger.info("  Flagged %d cases as overruled", count)
        else:
            result = await graph.query(
                "MATCH (target:Case)<-[r:CITES]-(source) "
                "WHERE r.treatment = 'overruled' "
                "RETURN count(DISTINCT target) AS flagged"
            )
            logger.info("  [DRY RUN] Would flag %d cases", result[0]["flagged"] if result else 0)

        # 3. Resolve placeholders matching real cases
        logger.info("Step 3: Resolving placeholder nodes...")
        if not dry_run:
            # Find placeholders that have a matching real case by citation
            result = await graph.query(
                "MATCH (real:Case), (placeholder:Case) "
                "WHERE NOT real.id STARTS WITH 'ref_' "
                "  AND placeholder.id STARTS WITH 'ref_' "
                "  AND placeholder.citation = real.citation "
                "  AND real.id <> placeholder.id "
                "WITH real, placeholder "
                "CALL { "
                "  WITH real, placeholder "
                "  MATCH (placeholder)<-[r_in]-(src) WHERE src <> real "
                "  CREATE (real)<-[r2:CITES]-(src) SET r2 = properties(r_in) "
                "  DELETE r_in "
                "} "
                "CALL { "
                "  WITH real, placeholder "
                "  MATCH (placeholder)-[r_out]->(tgt) WHERE tgt <> real "
                "  CREATE (real)-[r2:CITES]->(tgt) SET r2 = properties(r_out) "
                "  DELETE r_out "
                "} "
                "DETACH DELETE placeholder "
                "RETURN count(placeholder) AS resolved"
            )
            count = result[0]["resolved"] if result else 0
            logger.info("  Resolved %d placeholder nodes", count)
        else:
            result = await graph.query(
                "MATCH (real:Case), (placeholder:Case) "
                "WHERE NOT real.id STARTS WITH 'ref_' "
                "  AND placeholder.id STARTS WITH 'ref_' "
                "  AND placeholder.citation = real.citation "
                "RETURN count(placeholder) AS resolvable"
            )
            logger.info("  [DRY RUN] Would resolve %d placeholders", result[0]["resolvable"] if result else 0)

        # 4. Summary stats
        logger.info("Step 4: Summary...")
        stats = await graph.query(
            "MATCH (c:Case) "
            "RETURN count(c) AS total_nodes, "
            "       count(CASE WHEN c.id STARTS WITH 'ref_' THEN 1 END) AS placeholders, "
            "       count(CASE WHEN c.is_overruled = true THEN 1 END) AS overruled, "
            "       count(CASE WHEN c.cited_by_count > 0 THEN 1 END) AS has_citations"
        )
        if stats:
            s = stats[0]
            logger.info("  Total nodes: %d | Placeholders remaining: %d | Overruled: %d | With citations: %d",
                        s["total_nodes"], s["placeholders"], s["overruled"], s["has_citations"])

        logger.info("Migration complete!")

    finally:
        await graph.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill graph node properties")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()
    asyncio.run(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
```

### Step 2: Test with dry-run

Run: `cd backend && python -m scripts.migrate_graph_properties --dry-run`
Expected: Prints counts of nodes that would be updated without making changes.

### Step 3: Commit

```bash
git add backend/scripts/migrate_graph_properties.py
git commit -m "feat(scripts): add one-time migration for graph node properties

Backfills cited_by_count, is_overruled, and resolves placeholder
nodes matching already-ingested cases. Supports --dry-run mode."
```

---

## Task 6: Extract Shared Frontend Constants

**Files:**
- Create: `frontend/src/lib/graph-utils.ts`
- Modify: `frontend/src/app/graph/page.tsx`
- Modify: `frontend/src/app/case/[id]/page.tsx`

### Step 1: Create shared constants file

```typescript
/** Shared constants and helpers for citation graph rendering. */

export const EDGE_COLORS: Record<string, string> = {
    cites:          "#9CA3AF", // gray
    overrules:      "#EF4444", // red
    affirms:        "#22C55E", // green
    distinguishes:  "#F97316", // orange
    followed:       "#60A5FA", // blue
    not_followed:   "#F87171", // light red
    doubted:        "#FBBF24", // amber
    explained:      "#A78BFA", // purple
    per_incuriam:   "#EF4444", // red (equally severe)
};

/** Top-level legend entries (subset of EDGE_COLORS for compact display). */
export const LEGEND_TYPES = ["cites", "overrules", "affirms", "distinguishes", "followed", "doubted"] as const;

/** Detect whether a graph node is a placeholder (unresolved citation). */
export function isPlaceholderNode(node: Record<string, unknown>): boolean {
    if (typeof node.id === "string" && node.id.startsWith("ref_")) return true;
    if (node.year == null && node.court == null) return true;
    return false;
}

/** Get edge color by type, with fallback to gray. */
export function getEdgeColor(type: string | undefined | null): string {
    return EDGE_COLORS[type || "cites"] || "#9CA3AF";
}
```

### Step 2: Update graph/page.tsx to import from shared file

Replace inline `EDGE_COLORS` with:
```typescript
import { EDGE_COLORS, LEGEND_TYPES, isPlaceholderNode, getEdgeColor } from "@/lib/graph-utils";
```

Remove the inline `EDGE_COLORS` definition. Update legend to use `LEGEND_TYPES`. Update callbacks to use imported helpers.

### Step 3: Update case/[id]/page.tsx similarly

Import shared helpers instead of defining inline.

### Step 4: Move test to use shared module

Update `frontend/src/app/graph/__tests__/graph-helpers.test.ts` to import from `@/lib/graph-utils` instead of inlining.

### Step 5: Run full frontend test suite

Run: `cd frontend && npx vitest run`
Expected: All tests pass.

### Step 6: Commit

```bash
git add frontend/src/lib/graph-utils.ts frontend/src/app/graph/page.tsx frontend/src/app/case/\[id\]/page.tsx frontend/src/app/graph/__tests__/graph-helpers.test.ts
git commit -m "refactor(graph): extract shared edge colors and placeholder helpers

DRY: both graph pages now import from lib/graph-utils.ts."
```

---

## Task 7: Full Integration Verification

### Step 1: Run all backend tests

Run: `cd backend && python -m pytest tests/ -x -q`
Expected: ~2185 tests pass (the 1 pre-existing ingestion failure is unrelated).

### Step 2: Run all frontend tests

Run: `cd frontend && npx vitest run`
Expected: ~311+ tests pass.

### Step 3: Manual smoke test

1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open a case with citations → click GRAPH tab
4. Verify: edges show different colors based on treatment
5. Verify: placeholder nodes appear lighter/smaller
6. Verify: node hover shows title or citation string, not raw UUID
7. Verify: legend shows 6 edge types
8. Open Full Graph page → verify same behavior

### Step 4: Final commit

```bash
git commit --allow-empty -m "chore: citation graph pipeline fix complete

Treatment data now flows from Neo4j edges through traversal
to colored frontend edges. Placeholder nodes styled distinctly.
Ingestion resolves placeholders, persists cited_by_count and
is_overruled. Migration script for existing data."
```

---

## Task Summary

| # | Task | Files | Tests |
|---|------|-------|-------|
| 1 | Traversal: extract treatment, normalize types | traversal.py | test_graph_traversal.py |
| 2 | Frontend: edge colors, placeholder styling | graph/page.tsx, case/[id]/page.tsx | graph-helpers.test.ts |
| 3 | Ingestion: placeholder resolution | pipeline.py | test_ingestion_pipeline.py |
| 4 | Ingestion: cited_by_count + is_overruled | pipeline.py | test_ingestion_pipeline.py |
| 5 | Migration script | migrate_graph_properties.py | manual (--dry-run) |
| 6 | Extract shared frontend constants | graph-utils.ts | graph-helpers.test.ts |
| 7 | Integration verification | — | full suites + smoke test |
