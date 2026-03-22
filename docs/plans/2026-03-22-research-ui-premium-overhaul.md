# Research Agent UI/UX Premium Overhaul

**Date:** 2026-03-22
**Status:** Design approved, pending implementation plan

## Problem

The research agent UI has multiple UX issues that make it feel unprofessional compared to competitors (Harvey AI, Westlaw, Perplexity):

1. **Footnotes panel never truly closes** — 380px grid column stays even when "closed"
2. **No memo streaming** — users wait with no feedback, then see the entire memo at once
3. **Broken heading hierarchy** — H2 same size as body text, poor scannability
4. **Container width jumps** when footnotes load (max-w-6xl → max-w-[1400px])
5. **No prose-width constraint** — memo text stretches full width on wide screens
6. **No connecting line in step timeline** — looks like a plain list
7. **Inconsistent sticky offsets** — TOC at top-4, footnotes at top-20
8. **Tight border radius** (6px) — feels boxy vs modern 8-12px
9. **No scroll-spy on TOC** — no active heading highlighting
10. **Hacky inline `<style>`, bare `<input>`, raw dropdown div**

## Competitive Research Summary

| Feature | Harvey AI | Perplexity | Jhana AI | Current Smriti |
|---------|-----------|------------|----------|----------------|
| Panel behavior | Sliding right panel | Sidecar slide-in | N/A | Fixed grid column |
| Streaming | Yes (SSE, progressive) | Yes (true SSE) | No | No (all-at-once) |
| Background | Warm ivory | Paper White #F3F3EE | Pure white | Parchment #F5F0E8 |
| Typography | Custom serif + sans | FK Grotesk (custom) | Work Sans + Lora | Inter + Lora |
| Heading hierarchy | Clear, editorial | Clear | Clear | Broken (H2 = body) |
| Border radius | 8-12px | 8px | 10px | 6px |
| Trust signals | Source chips, paper trail | Sources-first | DPDPA badges | Verification icons |

## Design Decisions

### Decision 1: Keep & Refine Parchment/Gold Palette
Keep current warm palette (#F5F0E8 bg, #B89B6A gold). Fix inconsistencies (mixed HSL/hex), remove unused `--warm` variable, improve dark mode contrast.

### Decision 2: True Slide-Out Footnotes Panel
Panel slides off-screen when closed. A small floating tab on the right edge to reopen. Grid is always 2-column; panel is positioned independently.

### Decision 3: Memo Streaming via SSE
Backend streams memo chunks via `memo_stream` events. Frontend shows text appearing in real-time with a blinking cursor. Infrastructure already exists (`stream_callback` in synthesis node, queue in SSE layer).

---

## Architecture: Layout & Panel

### Current Layout
```
[240px timeline] [1fr memo] [380px footnotes (ALWAYS present)]
```

### New Layout
```
[240px timeline] [1fr memo (max-w-prose centered)]
                                            [400px footnotes panel — absolute positioned, slides in/out]
```

**Implementation:**
- Main grid is always `grid-cols-[240px_1fr]`
- Container is always `max-w-[1400px]`
- Memo content wrapper gets `max-w-[65ch] mx-auto` (prose width)
- Footnotes panel:
  - `fixed right-0 top-20 h-[calc(100vh-5rem)] w-[400px]`
  - `transform transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]`
  - Open: `translate-x-0`, Closed: `translate-x-full`
  - When open, main content area gets `mr-[400px] transition-[margin] duration-300`
- Floating reopen tab:
  - `fixed right-0 top-1/2 -translate-y-1/2`
  - Shows "Sources (N)" vertically or as a small pill
  - Only visible when panel is closed
  - `z-40` to stay above content

### Mobile Behavior (unchanged)
- Bottom Sheet drawer via shadcn Sheet component
- Full-width trigger button below memo

---

## Architecture: Memo Streaming

### Backend Change (agents.py)

The synthesis node already accepts `stream_callback`. Wire it to the SSE queue:

```python
# In _stream_sse_events producer function:
# Create a stream_callback that pushes memo_stream events
async def memo_stream_cb(chunk: str):
    await queue.put(
        f'data: {json.dumps({"type": "memo_stream", "execution_id": str(exec_id), "chunk": chunk})}\n\n'
    )

# Pass to graph config or node closure
```

The challenge: `stream_callback` is called inside a graph node, but the `queue` is in the SSE route. Solution: capture `queue` in the node closure via `research.py`'s `build_research_graph()`.

**Approach:** Add `memo_stream_queue: asyncio.Queue | None` parameter to `build_research_graph()`. The SSE route passes its queue. The `speculative_synthesis` closure captures it and creates the callback:

```python
# research.py
def build_research_graph(llm, flash_llm, ..., memo_stream_queue=None):
    ...
    async def speculative_synthesis(state):
        cb = None
        if memo_stream_queue:
            async def cb(chunk):
                await memo_stream_queue.put(
                    f'data: {json.dumps({"type": "memo_stream", "execution_id": str(exec_id), "chunk": chunk})}\n\n'
                )
        return await speculative_synthesis_with_contradictions_node(
            state, llm, flash_llm, stream_callback=cb,
        )
```

**Note:** The `stream_callback` in `speculative_synthesis_with_contradictions_node` is currently sync (`Callable[[str], None]`). Need to change to `Callable[[str], Awaitable[None]] | Callable[[str], None] | None` and `await` it if it's a coroutine.

### Frontend Change (page.tsx)

```typescript
// Handle memo_stream events
case "memo_stream":
    setStreamingMemo(prev => (prev || "") + event.data.chunk);
    break;

// Handle done event — replace streaming with final
case "done":
    // streamingMemo is replaced by the final memo from "memo" event
    setStreamingMemo(null);
    break;
```

The `streamingMemo` state already exists in page.tsx. The AgentMemoViewer already conditionally renders it.

Add a blinking cursor at the end of streaming text:
```tsx
{streamingMemo && (
    <AgentMemoViewer
        content={streamingMemo}
        confidence={0}
    />
    <span className="inline-block w-2 h-5 bg-foreground animate-pulse ml-0.5" />
)}
```

### Loading Sequence

1. User submits query → progress bar + step timeline start
2. Steps progress (classify, plan, workers, etc.)
3. Synthesis node starts → first `memo_stream` chunk arrives
4. Skeleton fades out → memo text starts streaming in real-time
5. Text streams with blinking cursor at end
6. `memo` event → final polished memo replaces streaming text, cursor disappears
7. `done` event → footnotes panel auto-slides in

---

## Architecture: Step Timeline Redesign

### Connecting Line
Add a vertical line connecting step circles:

```tsx
{/* Connecting line segment */}
{index < steps.length - 1 && (
    <div className="absolute left-[7px] top-6 bottom-0 w-0.5 bg-border" />
)}
```

Each step item becomes `relative` so the line is positioned within it.

### Active Step Glow
```css
.step-active-ring {
    @apply ring-2 ring-[var(--gold)]/30 ring-offset-2 ring-offset-background;
    animation: pulse-ring 2s ease-in-out infinite;
}
```

---

## Architecture: Polish & Consistency

### Typography Fixes
- H2 in memo: `text-base` → `text-lg` (17px vs 16px — creates visible hierarchy)
- Border radius: `--radius: 0.375rem` → `--radius: 0.5rem` (8px)
- Consistent sticky offset: both TOC and footnotes use `top-20`

### Scroll-Spy TOC
Use `IntersectionObserver` on all `h2[id]` elements in the memo:
```tsx
const [activeHeading, setActiveHeading] = useState<string>("");

useEffect(() => {
    const observer = new IntersectionObserver(
        (entries) => {
            for (const entry of entries) {
                if (entry.isIntersecting) {
                    setActiveHeading(entry.target.id);
                }
            }
        },
        { rootMargin: "-80px 0px -60% 0px", threshold: 0.1 }
    );
    document.querySelectorAll(".memo-body h2[id]").forEach(el => observer.observe(el));
    return () => observer.disconnect();
}, [cleanContent]);
```

Active TOC link: `text-[var(--gold)] font-medium` (vs default `text-muted-foreground`).

### Cleanup Items
1. Replace inline `<style>` with class in globals.css (`@media print { .memo-body ... }`)
2. Replace bare `<input>` in revision with shadcn `Input`
3. Replace raw export dropdown `div` with shadcn `DropdownMenu`
4. Remove `GripVertical` from plan-review (no drag-drop implemented)
5. Remove unused `--warm` CSS variable
6. Normalize all CSS variable values to hex (remove lone HSL)

### Micro-Animations
- Step completion: quick scale bounce `animate-[bounce-check_200ms_ease-out]`
- Memo sections: `opacity-0 → opacity-100` fade on viewport entry (IntersectionObserver)
- Progress bar: tick marks at stage boundaries (small circles on the track)

---

## Files Affected

### Backend (2 files)
- `backend/app/core/agents/research.py` — add `memo_stream_queue` param, wire callback
- `backend/app/api/routes/agents.py` — pass queue to graph builder
- `backend/app/core/agents/nodes/research_nodes.py` — make stream_callback async-compatible

### Frontend (8+ files)
- `frontend/src/app/agents/research/page.tsx` — layout grid, streaming, panel slide
- `frontend/src/components/agent-memo-viewer.tsx` — prose width, scroll-spy, cleanup
- `frontend/src/components/agent-step-timeline.tsx` — connecting line, glow ring
- `frontend/src/components/footnotes-panel.tsx` — slide-out mechanics, floating tab
- `frontend/src/components/research-progress-bar.tsx` — tick marks
- `frontend/src/components/plan-review.tsx` — remove GripVertical
- `frontend/src/app/globals.css` — radius, print CSS, animations, cleanup
- `frontend/src/lib/types.ts` — add memo_stream event type

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Streaming callback sync/async mismatch | Build error | Check if `llm.stream()` yields in async context, ensure callback is awaited |
| Panel slide breaks on mobile | Layout regression | Mobile path already uses Sheet (unchanged) |
| Prose-width constraint clips wide tables | Tables truncated | Add `overflow-x-auto` on table wrappers |
| IntersectionObserver SSR | Hydration error | Guard with `typeof window !== 'undefined'` |
| Streaming memo + footnote pills | Pills reference footnotes not yet loaded | Only process footnote pills after `done` event (streaming shows raw `[^N]` text) |

---

## Success Criteria

1. Footnotes panel fully closes (0px width, slide animation visible)
2. Memo text streams in real-time during synthesis
3. H2 headings visually larger than body text
4. TOC highlights current section on scroll
5. Timeline has connecting vertical line
6. Border radius 8px across all cards
7. No inline `<style>`, no bare `<input>`, no raw dropdown
8. All 311 frontend tests + 2039 backend tests pass
9. Build succeeds with no TypeScript errors
