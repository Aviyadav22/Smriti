# Research UI/UX Premium Overhaul — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the research agent UI from "functional prototype" to "premium legal AI" — true slide-out source panel, memo streaming, connected timeline, scroll-spy TOC, and polish.

**Architecture:** The footnotes panel becomes a fixed-positioned slide-out (transform-based) instead of a grid column. Memo streaming is wired through the existing `stream_callback` infrastructure (backend) and `streamingMemo` state (frontend). All polish items are incremental CSS/component fixes.

**Tech Stack:** Next.js 15, React, Tailwind CSS, shadcn/ui, FastAPI, LangGraph, SSE

**Design doc:** `docs/plans/2026-03-22-research-ui-premium-overhaul.md`

---

## Task 1: Backend — Wire memo streaming through SSE

The synthesis node already accepts `stream_callback` but it's hardcoded to `None`. Wire the SSE queue through to it.

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py:1421` (stream_callback type)
- Modify: `backend/app/core/agents/research.py:106-117` (build_research_graph signature)
- Modify: `backend/app/core/agents/research.py:327-338` (synthesis closures)
- Modify: `backend/app/api/routes/agents.py:196,547-557` (queue + graph builder call)

**Step 1: Make stream_callback async-compatible**

In `research_nodes.py:1421`, change the type:
```python
# OLD
stream_callback: Callable[[str], None] | None = None,
# NEW
stream_callback: Callable[[str], Any] | None = None,
```

At line 1700, await if it's a coroutine:
```python
# OLD
stream_callback(chunk)
# NEW
import asyncio
result = stream_callback(chunk)
if asyncio.iscoroutine(result):
    await result
```

Add `from typing import Any` to imports if not present. Add `import asyncio` if not present.

**Step 2: Add memo_stream_callback param to build_research_graph**

In `research.py:106-117`, add a parameter:
```python
def build_research_graph(
    *,
    llm: Any,
    flash_llm: Any,
    embedder: Any,
    vector_store: Any,
    reranker: Any,
    graph_store: Any = None,
    web_search: Any = None,
    ik_client: Any = None,
    checkpointer: Any | None = None,
    memo_stream_callback: Any | None = None,  # NEW — async callable for SSE memo streaming
) -> Any:
```

**Step 3: Wire callback into synthesis closures**

In `research.py:327-338`, replace:
```python
async def speculative_synthesis(state: ResearchState) -> dict:
    return await speculative_synthesis_with_contradictions_node(
        state, llm, flash_llm,
        stream_callback=memo_stream_callback,
    )

async def moderate_synthesis(state: ResearchState) -> dict:
    return await speculative_synthesis_with_contradictions_node(
        state, flash_llm, flash_llm,
        stream_callback=memo_stream_callback,
    )
```

**Step 4: Create the callback in the SSE route and pass to graph builder**

In `agents.py`, inside `_stream_agent_events` (around line 196), after the queue is created, define:
```python
async def _memo_stream_cb(chunk: str) -> None:
    await queue.put(
        f'data: {json.dumps({"type": "memo_stream", "execution_id": str(exec_id), "chunk": chunk})}\n\n'
    )
```

At the `build_research_graph` call site (line 547), add the parameter:
```python
graph = build_research_graph(
    llm=llm,
    flash_llm=get_flash_llm(),
    embedder=embedder,
    vector_store=vector_store,
    reranker=reranker,
    graph_store=get_graph_store(),
    web_search=_web_search,
    ik_client=_ik_client,
    checkpointer=checkpointer,
    memo_stream_callback=_memo_stream_cb,
)
```

**Important:** The `_memo_stream_cb` closure must be created inside `_stream_agent_events` where `queue` and `exec_id` are in scope. The `build_research_graph` call is inside the `_run_graph` producer which is nested inside `_stream_agent_events` — so the closure has access. However, `build_research_graph` is called OUTSIDE `_stream_agent_events` at lines 547-557. We need to restructure: define the callback in the route handler, pass it to `_stream_agent_events`, and from there to the graph.

**Revised approach:** The graph is built at line 547 (in the route handler), and `_stream_agent_events` receives the already-built graph. So the callback can't directly reference the queue (which is created inside `_stream_agent_events`).

**Solution:** Use an `asyncio.Queue` created at the route handler level, passed into both the graph builder (for the callback) and `_stream_agent_events` (as an additional source of events):

Actually, the simplest approach: create the callback inside `_run_graph` (the producer inside `_stream_agent_events`), but we can't because the graph is already built.

**Simplest approach:** Don't pass it through build_research_graph. Instead, add `memo_stream_callback` as an attribute on the graph object or pass it through the LangGraph config's `configurable` dict:

```python
# In _run_graph (line 200), before graph.astream():
config["configurable"]["memo_stream_callback"] = _memo_stream_cb
```

But the graph nodes don't receive config — they receive state.

**Final approach (cleanest):** Build the graph lazily inside `_run_graph` where the queue is available. Move the `build_research_graph` call from line 547 into the `_run_graph` function. This means `_stream_agent_events` receives the graph builder args instead of a built graph. But this is a bigger refactor.

**Simplest working approach:** Store callback on an object that's already in scope. The `graph` object is passed to `_stream_agent_events`. We can attach the callback to it after creation:

In the route handler (after line 557):
```python
graph._smriti_memo_stream_callback = None  # Will be set in producer
```

In `_run_graph` producer (around line 200):
```python
async def _memo_stream_cb(chunk: str) -> None:
    await queue.put(
        f'data: {json.dumps({"type": "memo_stream", "execution_id": str(exec_id), "chunk": chunk})}\n\n'
    )
```

But the graph nodes don't see the graph object — they see state.

**Actually simplest:** Just create a module-level dict keyed by exec_id, and have the callback look it up. Or: pass the callback via state.

**WINNER — Pass via ResearchState:**

Add `memo_stream_callback` to the initial input dict:
```python
# In agents.py route handler, when building initial_input:
initial_input["_memo_stream_callback"] = None  # placeholder
```

In `_run_graph` (line 200), before `graph.astream`, set it:
```python
# Create callback that writes to queue
async def _memo_stream_cb(chunk: str) -> None:
    await queue.put(
        f'data: {json.dumps({"type": "memo_stream", "execution_id": str(exec_id), "chunk": chunk})}\n\n'
    )
initial_input["_memo_stream_callback"] = _memo_stream_cb
```

But `initial_input` goes through Pydantic-validated state — it won't accept a callable.

**ACTUAL SIMPLEST — Inject into closure scope via build_research_graph at _run_graph time:**

Restructure so the graph is built INSIDE `_run_graph`:

In `agents.py` route handler (line ~540-560):
- Instead of calling `build_research_graph(...)` and passing `graph` to `_stream_agent_events`
- Pass the graph builder kwargs as a dict to `_stream_agent_events`
- Build the graph inside `_run_graph` where `queue` is in scope

This is the cleanest approach. Here's the plan:

In the route handler, replace:
```python
graph = build_research_graph(...)
response = StreamingResponse(
    _stream_agent_events(graph, initial_input, config, exec_id),
    ...
)
```

With:
```python
graph_kwargs = dict(
    llm=llm,
    flash_llm=get_flash_llm(),
    embedder=embedder,
    vector_store=vector_store,
    reranker=reranker,
    graph_store=get_graph_store(),
    web_search=_web_search,
    ik_client=_ik_client,
    checkpointer=checkpointer,
)
response = StreamingResponse(
    _stream_agent_events(None, initial_input, config, exec_id, graph_kwargs=graph_kwargs),
    ...
)
```

In `_stream_agent_events`, add `graph_kwargs` param. Inside `_run_graph`, when `graph_kwargs` is provided:
```python
async def _memo_stream_cb(chunk: str) -> None:
    await queue.put(
        f'data: {json.dumps({"type": "memo_stream", "execution_id": str(exec_id), "chunk": chunk})}\n\n'
    )
if graph_kwargs:
    graph = build_research_graph(**graph_kwargs, memo_stream_callback=_memo_stream_cb)
```

**Step 5: Run backend tests**

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30`
Expected: All 2039 tests pass (the stream_callback changes are backward compatible — None still works).

**Step 6: Commit**
```
git add backend/app/core/agents/nodes/research_nodes.py backend/app/core/agents/research.py backend/app/api/routes/agents.py
git commit -m "feat: wire memo streaming through SSE pipeline"
```

---

## Task 2: Frontend — Handle memo_stream events

**Files:**
- Modify: `frontend/src/lib/types.ts` (add memo_stream to event type)
- Modify: `frontend/src/app/agents/research/page.tsx:152-166,499` (handle streaming, display logic)

**Step 1: Add memo_stream to event type**

In `types.ts`, in the `AgentStreamEvent` type union, add `"memo_stream"` to the type field if not already there (check line where type is defined).

**Step 2: Update SSE handler in page.tsx**

At line 163-166 where `memo_stream` is already handled:
```typescript
// This already exists — verify it works:
if (event.type === "memo_stream") {
    setStreamingMemo((prev) => prev + event.chunk);
    return;
}
```

Verify `event.chunk` is the right field (matches the backend `{"type": "memo_stream", "chunk": "..."}` payload).

**Step 3: Add blinking cursor to streaming memo display**

At line 499, where `displayMemo` is set:
```typescript
const displayMemo = memo || streamingMemo;
const isStreaming = !memo && !!streamingMemo;
```

Where the `AgentMemoViewer` is rendered (find it in the JSX), wrap it:
```tsx
{displayMemo && (
    <div className="relative">
        <AgentMemoViewer
            content={displayMemo}
            confidence={isStreaming ? 0 : confidence}
            onFootnoteClick={handleFootnoteClick}
            maxFootnote={footnotes.length}
            footnoteVerification={footnoteVerification}
            confidenceBreakdown={confidenceBreakdown}
            executionId={executionId}
            onReviseSection={isStreaming ? undefined : handleReviseSection}
            footnotes={footnotes}
        />
        {isStreaming && (
            <span className="inline-block w-1.5 h-5 bg-[var(--gold)] animate-pulse ml-0.5 align-text-bottom" />
        )}
    </div>
)}
```

**Step 4: Add skeleton shimmer before first chunk**

Before the memo area, when research is running but no memo/streaming yet:
```tsx
{isRunning && !displayMemo && (
    <div className="space-y-4 animate-pulse">
        <div className="h-6 w-3/4 bg-muted rounded" />
        <div className="h-4 w-full bg-muted rounded" />
        <div className="h-4 w-full bg-muted rounded" />
        <div className="h-4 w-5/6 bg-muted rounded" />
        <div className="h-6 w-2/3 bg-muted rounded mt-6" />
        <div className="h-4 w-full bg-muted rounded" />
        <div className="h-4 w-4/5 bg-muted rounded" />
    </div>
)}
```

**Step 5: Build and test**

Run: `cd frontend && npm run build && npx vitest run`
Expected: Build passes, 311 tests pass.

**Step 6: Commit**
```
git add frontend/src/lib/types.ts frontend/src/app/agents/research/page.tsx
git commit -m "feat: handle memo_stream SSE events with blinking cursor"
```

---

## Task 3: True slide-out footnotes panel

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx:506-508,613-615,809-816` (layout, panel positioning)
- Modify: `frontend/src/components/footnotes-panel.tsx:62-84` (remove collapsed button, add floating tab)

**Step 1: Fix the container width — always use max-w-[1400px]**

At line 506-508, replace:
```tsx
// OLD
<div className={`mx-auto px-4 py-8 ${
    footnotes.length > 0 ? "max-w-[1400px]" : "max-w-6xl"
}`}>
// NEW
<div className="mx-auto px-4 py-8 max-w-[1400px]">
```

**Step 2: Fix the grid — always 2-column, no 3rd footnotes column**

At line 613-615, replace:
```tsx
// OLD
<div className={`grid gap-6 md:grid-cols-[240px_1fr] ${
    footnotes.length > 0 ? "lg:grid-cols-[240px_1fr_380px]" : ""
}`}>
// NEW
<div className="grid gap-6 md:grid-cols-[240px_1fr]">
```

**Step 3: Move footnotes panel to fixed slide-out position**

Replace the desktop footnotes panel section (around line 808-817). Remove the old grid column div and replace with:
```tsx
{/* Desktop slide-out footnotes panel */}
<div
    className={cn(
        "hidden lg:block fixed right-0 top-20 h-[calc(100vh-5rem)] w-[400px] z-40",
        "border-l bg-background shadow-xl",
        "transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
        footnotesPanelOpen ? "translate-x-0" : "translate-x-full",
    )}
>
    <FootnotesPanel
        footnotes={footnotes}
        selectedFootnoteNumber={selectedFootnoteNum}
        onFootnoteSelect={setSelectedFootnoteNum}
        isOpen={true}  // Always "open" internally when panel is visible
        onToggle={() => setFootnotesPanelOpen(false)}
    />
</div>
```

This div is placed OUTSIDE the grid, as a sibling of the main content div.

**Step 4: Add floating reopen tab**

When the panel is closed and footnotes exist, show a tab on the right edge:
```tsx
{/* Floating tab to reopen sources panel */}
{footnotes.length > 0 && !footnotesPanelOpen && (
    <button
        onClick={() => setFootnotesPanelOpen(true)}
        className="hidden lg:flex fixed right-0 top-1/2 -translate-y-1/2 z-30 items-center gap-1.5 bg-background/95 border border-r-0 rounded-l-lg shadow-md px-2 py-3 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors backdrop-blur-sm"
        style={{ writingMode: "vertical-rl" }}
    >
        <PanelRightOpen className="h-3.5 w-3.5 rotate-0" />
        Sources ({footnotes.filter(f => f.is_used).length})
    </button>
)}
```

**Step 5: Add margin transition on main content when panel opens**

The main grid wrapper needs right margin when panel is open:
```tsx
<div className={cn(
    "grid gap-6 md:grid-cols-[240px_1fr]",
    "transition-[margin] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
    footnotesPanelOpen ? "lg:mr-[400px]" : "",
)}>
```

**Step 6: Remove the collapsed button from FootnotesPanel**

In `footnotes-panel.tsx`, the `if (!isOpen)` block (lines 62-84) that renders the sticky button is no longer needed — the parent controls visibility via transform. Remove or simplify: since we now always pass `isOpen={true}` to the panel when it's in the slide-out, the collapsed state is handled by the parent transform. Remove the `if (!isOpen)` early return entirely.

**Step 7: Import cn in page.tsx if not already imported**

Check if `cn` from `@/lib/utils` is imported. If not, add it.

**Step 8: Import PanelRightOpen in page.tsx**

Add `PanelRightOpen` to the lucide-react imports in page.tsx.

**Step 9: Build and test**

Run: `cd frontend && npm run build && npx vitest run`

**Step 10: Commit**
```
git add frontend/src/app/agents/research/page.tsx frontend/src/components/footnotes-panel.tsx
git commit -m "feat: true slide-out footnotes panel with floating reopen tab"
```

---

## Task 4: Connected step timeline with glow ring

**Files:**
- Modify: `frontend/src/components/agent-step-timeline.tsx:58-89`
- Modify: `frontend/src/app/globals.css` (add keyframe)

**Step 1: Add connecting line and glow ring**

Replace the component body (lines 58-89):
```tsx
export function AgentStepTimeline({ steps, completedCount, totalCount }: AgentStepTimelineProps) {
    const derivedCompleted = completedCount ?? steps.filter((s) => s.status === "completed").length;
    const derivedTotal = totalCount ?? steps.length;

    return (
        <div>
            <div role="list" className="relative">
                {steps.map((step, i) => (
                    <div key={i} role="listitem" className="relative flex items-start gap-3 pb-3 last:pb-0">
                        {/* Connecting line */}
                        {i < steps.length - 1 && (
                            <div
                                className={cn(
                                    "absolute left-[7px] top-5 bottom-0 w-0.5",
                                    step.status === "completed" ? "bg-green-500/30" : "bg-border",
                                )}
                            />
                        )}
                        {/* Icon */}
                        <div className={cn(
                            "relative z-10 shrink-0 mt-0.5",
                            step.status === "active" && "ring-2 ring-[var(--gold)]/30 ring-offset-2 ring-offset-background rounded-full",
                        )}>
                            {step.status === "completed" && <CheckCircle2 aria-label="Completed" className="h-4 w-4 text-green-500" />}
                            {step.status === "active" && <Loader2 aria-label="In progress" className="h-4 w-4 text-[var(--gold)] animate-spin" />}
                            {step.status === "pending" && <Circle aria-label="Pending" className="h-4 w-4 text-muted-foreground/40" />}
                            {step.status === "error" && <AlertCircle aria-label="Error" className="h-4 w-4 text-red-500" />}
                        </div>
                        {/* Text */}
                        <div className="min-w-0">
                            <p className={cn(
                                "text-sm font-medium truncate",
                                step.status === "active" ? "text-foreground" : step.status === "completed" ? "text-muted-foreground" : "text-muted-foreground/50",
                            )}>
                                {getStepLabel(step.name)}
                            </p>
                            {step.message && (
                                <p className="text-xs text-muted-foreground mt-0.5 truncate">{step.message}</p>
                            )}
                        </div>
                    </div>
                ))}
            </div>
            {derivedTotal > 0 && (
                <p className="text-xs text-muted-foreground mt-2">
                    Step {derivedCompleted} of {derivedTotal}
                </p>
            )}
        </div>
    );
}
```

Import `cn` from `@/lib/utils` at the top of the file.

**Step 2: Build and test**

Run: `cd frontend && npm run build && npx vitest run`

**Step 3: Commit**
```
git add frontend/src/components/agent-step-timeline.tsx
git commit -m "feat: connected step timeline with vertical line and active glow ring"
```

---

## Task 5: Prose-width memo + scroll-spy TOC

**Files:**
- Modify: `frontend/src/components/agent-memo-viewer.tsx:493-511,513` (TOC scroll-spy, prose width)

**Step 1: Add prose-width constraint to memo body**

At line 513, change:
```tsx
// OLD
<div className="memo-body max-w-none text-foreground flex-1 min-w-0">
// NEW
<div className="memo-body max-w-[65ch] text-foreground flex-1 min-w-0">
```

**Step 2: Add scroll-spy to TOC**

Replace the TOC section (lines 493-511) with:
```tsx
{headings.length > 2 && (
    <MemoTOC headings={headings} />
)}
```

Add a new component above `AgentMemoViewer`:
```tsx
function MemoTOC({ headings }: { headings: string[] }) {
    const [activeId, setActiveId] = useState("");

    useEffect(() => {
        if (typeof window === "undefined") return;
        const observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        setActiveId(entry.target.id);
                    }
                }
            },
            { rootMargin: "-80px 0px -60% 0px", threshold: 0.1 },
        );
        const els = document.querySelectorAll(".memo-body h2[id], .memo-body div[id]");
        els.forEach((el) => observer.observe(el));
        return () => observer.disconnect();
    }, [headings]);

    return (
        <nav className="memo-toc hidden lg:block w-44 shrink-0 sticky top-20 self-start max-h-[calc(100vh-8rem)] overflow-y-auto">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Contents</p>
            <ul className="space-y-1">
                {headings.map((h) => (
                    <li key={h}>
                        <a
                            href={`#${slugify(h)}`}
                            className={cn(
                                "text-[11px] block truncate transition-colors",
                                activeId === slugify(h)
                                    ? "text-[var(--gold)] font-medium"
                                    : "text-muted-foreground hover:text-foreground",
                            )}
                            title={h}
                        >
                            {h}
                        </a>
                    </li>
                ))}
            </ul>
        </nav>
    );
}
```

Import `useEffect` if not in the existing imports. Import `cn` if not imported. Note: `slugify` is already defined in the file.

**Step 3: Fix TOC sticky offset**

The old TOC had `sticky top-4`. The new version uses `sticky top-20` — matching the footnotes panel offset.

**Step 4: Build and test**

Run: `cd frontend && npm run build && npx vitest run`

**Step 5: Commit**
```
git add frontend/src/components/agent-memo-viewer.tsx
git commit -m "feat: prose-width memo with scroll-spy TOC"
```

---

## Task 6: Typography & radius polish

**Files:**
- Modify: `frontend/src/app/globals.css:57,77,92,136` (radius, cleanup)
- Modify: `frontend/src/components/agent-memo-viewer.tsx:291` (H2 size)

**Step 1: Bump border radius**

In `globals.css:57`:
```css
/* OLD */
--radius: 0.375rem;
/* NEW */
--radius: 0.5rem;
```

**Step 2: Fix HSL/hex inconsistency**

In `globals.css:77`:
```css
/* OLD */
--muted-foreground: hsl(55 8% 30%);
/* NEW — convert to hex for consistency */
--muted-foreground: #4D4839;
```

**Step 3: Remove unused --warm variable**

Remove from both light mode (line 92) and dark mode (line 136):
```css
/* DELETE these lines */
--warm: #C4A97D;
```

**Step 4: Add print CSS to globals.css**

Add at the end of `globals.css`:
```css
@media print {
    .memo-toc, .memo-actions, .group button { display: none !important; }
    .memo-body { max-width: 100% !important; }
}
```

**Step 5: Remove inline `<style>` from agent-memo-viewer.tsx**

Delete line 490:
```tsx
<style>{`@media print { .memo-toc, .memo-actions, .group button { display: none !important; } .memo-body { max-width: 100% !important; } }`}</style>
```

**Step 6: Bump H2 heading size**

In agent-memo-viewer.tsx, the h2 component (around line 296):
```tsx
// OLD
<h2 className="text-base font-semibold text-foreground" {...props}>{children}</h2>
// NEW
<h2 className="text-lg font-semibold text-foreground" {...props}>{children}</h2>
```

**Step 7: Build and test**

Run: `cd frontend && npm run build && npx vitest run`

**Step 8: Commit**
```
git add frontend/src/app/globals.css frontend/src/components/agent-memo-viewer.tsx
git commit -m "fix: typography hierarchy, border radius, and CSS cleanup"
```

---

## Task 7: Replace hacky UI elements with shadcn components

**Files:**
- Modify: `frontend/src/components/agent-memo-viewer.tsx:321-337,466-484` (input, dropdown)
- Modify: `frontend/src/components/plan-review.tsx` (remove GripVertical)

**Step 1: Replace bare `<input>` with shadcn Input**

In agent-memo-viewer.tsx, import `Input` from `@/components/ui/input`.

Replace the bare input at lines 321-337:
```tsx
// OLD
<input
    className="flex-1 text-xs border rounded px-2 py-1 bg-background"
    placeholder="What should change in this section?"
    ...
/>
// NEW
<Input
    className="flex-1 text-xs h-8"
    placeholder="What should change in this section?"
    value={revisionFeedback}
    onChange={(e) => setRevisionFeedback(e.target.value)}
    onKeyDown={(e) => { ... }}
    disabled={revisionLoading}
/>
```

**Step 2: Replace raw export dropdown with DropdownMenu**

Import from shadcn:
```tsx
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
```

Check if `dropdown-menu` component exists:
```bash
ls frontend/src/components/ui/dropdown-menu.tsx
```

If it doesn't exist, install it:
```bash
cd frontend && npx shadcn@latest add dropdown-menu --yes
```
(May need to use npm manually if shadcn CLI has pnpm issues — check the existing hover-card.tsx as a pattern and create dropdown-menu.tsx manually from Radix primitives if needed.)

Replace the export button + raw dropdown (lines 440-484) with:
```tsx
<DropdownMenu>
    <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1">
            <Download className="h-3.5 w-3.5" />
            Export
            <ChevronDown className="h-3 w-3" />
        </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end">
        {(["docx", "pdf"] as const).map((fmt) => (
            <DropdownMenuItem
                key={fmt}
                onClick={() => window.open(`/api/agents/research/export/${executionId}?format=${fmt}`, "_blank")}
            >
                Download {fmt.toUpperCase()}
            </DropdownMenuItem>
        ))}
    </DropdownMenuContent>
</DropdownMenu>
```

Remove the `exportOpen` state and related code since DropdownMenu manages its own open state.

**Step 3: Remove GripVertical from plan-review.tsx**

Find and remove the `GripVertical` icon and its import from `plan-review.tsx`. It suggests drag-and-drop which isn't implemented.

**Step 4: Build and test**

Run: `cd frontend && npm run build && npx vitest run`

**Step 5: Commit**
```
git add frontend/src/components/agent-memo-viewer.tsx frontend/src/components/plan-review.tsx frontend/src/components/ui/dropdown-menu.tsx
git commit -m "fix: replace hacky UI elements with shadcn components"
```

---

## Task 8: Progress bar tick marks

**Files:**
- Modify: `frontend/src/components/research-progress-bar.tsx`

**Step 1: Add tick marks at stage boundaries**

In the progress bar track (the `div.h-2.5.bg-muted.rounded-full`), add small circles at each stage boundary:
```tsx
<div className="relative h-2.5 bg-muted rounded-full overflow-hidden">
    {/* Fill bar */}
    <div
        className="h-full bg-[var(--gold)] rounded-full transition-all duration-500 ease-out"
        style={{ width: `${Math.min(progress * 100, 100)}%` }}
        role="progressbar"
        aria-valuenow={Math.round(progress * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
    />
    {/* Stage tick marks */}
    {[0.15, 0.35, 0.55, 0.70, 0.90].map((pos, i) => (
        <div
            key={i}
            className="absolute top-1/2 -translate-y-1/2 w-1 h-1 rounded-full bg-background/60"
            style={{ left: `${pos * 100}%` }}
        />
    ))}
</div>
```

**Step 2: Build and test**

Run: `cd frontend && npm run build && npx vitest run`

**Step 3: Commit**
```
git add frontend/src/components/research-progress-bar.tsx
git commit -m "feat: add stage tick marks to progress bar"
```

---

## Task 9: Final verification

**Step 1: Run full backend tests**

Run: `cd backend && python -m pytest tests/ -x -q --timeout=30`
Expected: All 2039+ tests pass.

**Step 2: Run full frontend tests**

Run: `cd frontend && npx vitest run`
Expected: All 311+ tests pass.

**Step 3: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors.

**Step 4: Visual checklist (manual)**

- [ ] Footnotes panel slides out completely when closed (0px visible)
- [ ] Floating "Sources (N)" tab appears on right edge when panel closed
- [ ] Clicking tab slides panel back in with animation
- [ ] Memo has `max-w-[65ch]` prose width
- [ ] TOC highlights current heading on scroll
- [ ] Step timeline has vertical connecting line
- [ ] Active step has gold glow ring
- [ ] H2 headings are visually larger than body text
- [ ] Border radius is 8px (rounder cards)
- [ ] No inline `<style>` tag in memo viewer
- [ ] Export uses DropdownMenu (not raw div)
- [ ] Revision uses shadcn Input (not bare `<input>`)
- [ ] No GripVertical in plan review

**Step 5: Commit any final fixes and tag**
```
git commit -m "chore: research UI premium overhaul complete"
```
