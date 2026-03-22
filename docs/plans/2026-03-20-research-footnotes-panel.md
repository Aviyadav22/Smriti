# Research Footnotes Panel — Jhana-Style Source Preview

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the research agent results page with a Jhana/Harvey-style right-side footnotes panel featuring inline clickable citations, source list with Case/Web badges, detailed case preview with metadata+summaries, embedded PDF viewer jumping to relevant pages, and web source previews with "View Full Document" links.

**Architecture:** Split-panel layout on desktop (memo left, footnotes panel right). Footnotes panel has two tabs: "Footnotes" (scrollable list of all sources) and "Preview" (detailed view of selected source). Clicking a footnote number `[N]` in the memo or footnote list opens the Preview tab with full case metadata, summaries, PDF viewer, or web content preview. Mobile: footnotes panel slides up as a drawer.

**Tech Stack:** Next.js 15, React, Tailwind CSS, shadcn/ui (Sheet, ScrollArea, Tabs), `react-pdf` (pdfjs-dist), existing ResearchFootnote type

---

### Task 1: Install Dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install react-pdf for embedded PDF viewing**

```bash
cd frontend
npm install react-pdf
```

**Step 2: Install missing shadcn/ui components**

```bash
npx shadcn@latest add scroll-area tabs tooltip sheet
```

**Step 3: Verify installs**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/ui/
git commit -m "chore: add react-pdf, shadcn scroll-area/tabs/tooltip/sheet"
```

---

### Task 2: Enrich Backend Footnote Data

The current `Footnote` TypedDict is missing fields needed for the preview panel (court, year, author, bench, ik_doc_id, pdf_url). We need to add them.

**Files:**
- Modify: `backend/app/core/agents/state.py:85-95`
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (format_footnotes_node)
- Modify: `frontend/src/lib/types.ts:429-439`
- Test: `backend/tests/unit/test_research_v2_phase4.py`

**Step 1: Write failing test**

In `backend/tests/unit/test_research_v2_phase4.py`, add:

```python
class TestFootnoteEnrichment:
    """Footnotes should include enriched case metadata for the preview panel."""

    def test_footnote_has_enriched_fields(self):
        """Footnote TypedDict should include court, year, author, ik_doc_id, pdf_available."""
        from app.core.agents.state import Footnote
        # Verify the TypedDict accepts enriched fields
        fn: Footnote = {
            "number": 1,
            "citation": "(2023) 5 SCC 1",
            "source_type": "case_law",
            "source_url": "/case/abc-123",
            "case_id": "abc-123",
            "excerpt": "The court held that...",
            "is_used": True,
            "verification_status": "verified_pg",
            "verified_against": "pg",
            # New enriched fields
            "court": "Supreme Court of India",
            "year": 2023,
            "author": "D Y Chandrachud",
            "bench": "Constitution Bench",
            "ik_doc_id": "12345678",
            "pdf_available": True,
            "title": "State of Kerala v. People's Union",
            "source_label": "Case",
        }
        assert fn["court"] == "Supreme Court of India"
        assert fn["ik_doc_id"] == "12345678"
        assert fn["pdf_available"] is True
        assert fn["source_label"] == "Case"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_research_v2_phase4.py::TestFootnoteEnrichment -v`
Expected: FAIL (TypedDict doesn't have new keys)

**Step 3: Add enriched fields to Footnote TypedDict**

In `backend/app/core/agents/state.py`, update the `Footnote` class (line 85-95):

```python
class Footnote(TypedDict):
    """A structured footnote linking to a source document."""
    number: int
    citation: str         # Full case citation or statute reference
    source_type: str      # "case_law"|"statute"|"constitution"|"web"|"ik_search"|"llm_knowledge"
    source_url: str       # Link to case viewer, IK page, or web URL
    case_id: str | None   # Our internal case_id if available
    excerpt: str          # Relevant passage
    is_used: bool         # True if cited in memo, False if searched but not cited
    verification_status: str  # [T4] "verified_pg"|"verified_ik"|"verified_neo4j"|"unverified"|"removed"
    verified_against: str     # [T4] Which source confirmed
    # Enriched fields for preview panel
    title: str                # Case title or web page title
    court: str                # Court name (e.g., "Supreme Court of India")
    year: int | None          # Decision year
    author: str               # Author judge
    bench: str                # Bench composition
    ik_doc_id: str            # Indian Kanoon doc ID (for IK link)
    pdf_available: bool       # True if pdf_storage_path exists
    source_label: str         # Display label: "Case" | "Statute" | "Web" | "Constitution"
```

**Step 4: Update format_footnotes_node to populate enriched fields**

In `backend/app/core/agents/nodes/research_nodes.py`, find the `format_footnotes_node` function. When building each Footnote entry, populate the new fields from worker_results metadata:

For case_law and ik_search sources:
```python
"title": result.get("title", ""),
"court": result.get("court", result.get("docsource", "")),
"year": result.get("year"),
"author": result.get("author", result.get("judge", "")),
"bench": result.get("bench_type", ""),
"ik_doc_id": str(result.get("ik_doc_id", "")),
"pdf_available": bool(result.get("case_id") and not str(result.get("case_id", "")).startswith("ik:")),
"source_label": "Case",
```

For statute sources:
```python
"title": result.get("title", ""),
"court": "",
"year": None,
"author": "",
"bench": "",
"ik_doc_id": "",
"pdf_available": False,
"source_label": "Statute" if result.get("document_type") != "constitution" else "Constitution",
```

For web sources:
```python
"title": result.get("title", ""),
"court": "",
"year": None,
"author": "",
"bench": "",
"ik_doc_id": "",
"pdf_available": False,
"source_label": "Web",
```

Default fallback (for any footnote missing metadata):
```python
"title": fn_def.get("title", ""),
"court": "",
"year": None,
"author": "",
"bench": "",
"ik_doc_id": "",
"pdf_available": False,
"source_label": _infer_source_label(source_type),
```

Add helper:
```python
def _infer_source_label(source_type: str) -> str:
    return {
        "case_law": "Case", "ik_search": "Case", "named_case": "Case",
        "statute": "Statute", "constitution": "Constitution",
        "web": "Web", "graph": "Case", "graph_community": "Case",
    }.get(source_type, "Source")
```

**Step 5: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_research_v2_phase4.py::TestFootnoteEnrichment -v`
Expected: PASS

**Step 6: Update frontend TypeScript types**

In `frontend/src/lib/types.ts`, update `ResearchFootnote` (line 429-439):

```typescript
export interface ResearchFootnote {
    number: number;
    citation: string;
    source_type: string;
    source_url: string;
    case_id: string | null;
    excerpt: string;
    is_used: boolean;
    verification_status: string;
    verified_against: string;
    // Enriched fields for preview panel
    title: string;
    court: string;
    year: number | null;
    author: string;
    bench: string;
    ik_doc_id: string;
    pdf_available: boolean;
    source_label: string;  // "Case" | "Statute" | "Web" | "Constitution"
}
```

**Step 7: Run all tests**

Run: `cd backend && python -m pytest tests/unit/ -x -q`
Expected: All pass

**Step 8: Commit**

```bash
git add backend/app/core/agents/state.py backend/app/core/agents/nodes/research_nodes.py frontend/src/lib/types.ts backend/tests/unit/test_research_v2_phase4.py
git commit -m "feat: enrich Footnote with court/year/author/ik_doc_id for preview panel"
```

---

### Task 3: Create FootnoteListItem Component

The individual footnote row in the right panel list. Shows number, title, citation details, and Case/Web badge.

**Files:**
- Create: `frontend/src/components/footnote-list-item.tsx`

**Step 1: Create the component**

```tsx
"use client";

import { Scale, Globe, BookOpen, FileText } from "lucide-react";
import type { ResearchFootnote } from "@/lib/types";

const LABEL_CONFIG: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
    Case: { icon: Scale, color: "text-green-700 dark:text-green-400", bg: "bg-green-100 dark:bg-green-900/30" },
    Web: { icon: Globe, color: "text-blue-700 dark:text-blue-400", bg: "bg-blue-100 dark:bg-blue-900/30" },
    Statute: { icon: BookOpen, color: "text-purple-700 dark:text-purple-400", bg: "bg-purple-100 dark:bg-purple-900/30" },
    Constitution: { icon: BookOpen, color: "text-amber-700 dark:text-amber-400", bg: "bg-amber-100 dark:bg-amber-900/30" },
    Source: { icon: FileText, color: "text-muted-foreground", bg: "bg-muted" },
};

interface FootnoteListItemProps {
    footnote: ResearchFootnote;
    isSelected: boolean;
    onClick: () => void;
}

export function FootnoteListItem({ footnote, isSelected, onClick }: FootnoteListItemProps) {
    const label = LABEL_CONFIG[footnote.source_label] || LABEL_CONFIG.Source;
    const LabelIcon = label.icon;

    return (
        <button
            onClick={onClick}
            className={`w-full text-left px-3 py-2.5 border-b border-border/50 hover:bg-muted/50 transition-colors flex items-start gap-2.5 ${
                isSelected ? "bg-muted/70 border-l-2 border-l-[var(--gold)]" : ""
            }`}
        >
            {/* Footnote number badge */}
            <span className={`shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                isSelected ? "bg-[var(--gold)] text-white" : "bg-muted text-muted-foreground"
            }`}>
                {footnote.number}
            </span>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium leading-tight line-clamp-2">
                    {footnote.title || footnote.citation}
                </p>
                {footnote.court && (
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">
                        {footnote.citation}{footnote.court ? ` (${footnote.court}` : ""}{footnote.year ? ` ${footnote.year})` : footnote.court ? ")" : ""}
                    </p>
                )}
            </div>

            {/* Source type badge */}
            <span className={`shrink-0 text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${label.bg} ${label.color}`}>
                {footnote.source_label}
            </span>
        </button>
    );
}
```

**Step 2: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/footnote-list-item.tsx
git commit -m "feat: add FootnoteListItem component for footnotes panel"
```

---

### Task 4: Create FootnotePreview Component (Case Law)

The detailed preview panel showing case metadata, summaries, and PDF viewer — like Jhana's Preview tab.

**Files:**
- Create: `frontend/src/components/footnote-preview.tsx`

**Step 1: Create the component**

```tsx
"use client";

import { useState, useMemo } from "react";
import { ExternalLink, Scale, Globe, BookOpen, FileText, ChevronDown, ChevronRight, CheckCircle2, XCircle } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";
import type { ResearchFootnote } from "@/lib/types";
import { getCasePdfUrl } from "@/lib/api";

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const LABEL_CONFIG: Record<string, { icon: React.ElementType; color: string }> = {
    Case: { icon: Scale, color: "text-green-600 dark:text-green-400" },
    Web: { icon: Globe, color: "text-blue-600 dark:text-blue-400" },
    Statute: { icon: BookOpen, color: "text-purple-600 dark:text-purple-400" },
    Constitution: { icon: BookOpen, color: "text-amber-600 dark:text-amber-400" },
    Source: { icon: FileText, color: "text-muted-foreground" },
};

const VERIFICATION_CONFIG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    verified_pg: { icon: CheckCircle2, color: "text-green-500", label: "Verified (Database)" },
    verified_ik: { icon: CheckCircle2, color: "text-green-500", label: "Verified (Indian Kanoon)" },
    verified_neo4j: { icon: CheckCircle2, color: "text-green-500", label: "Verified (Citation Graph)" },
    unverified: { icon: XCircle, color: "text-amber-500", label: "Unverified" },
};

interface FootnotePreviewProps {
    footnote: ResearchFootnote;
}

export function FootnotePreview({ footnote }: FootnotePreviewProps) {
    const [summaryOpen, setSummaryOpen] = useState(true);
    const [numPages, setNumPages] = useState<number | null>(null);

    const label = LABEL_CONFIG[footnote.source_label] || LABEL_CONFIG.Source;
    const LabelIcon = label.icon;
    const verification = VERIFICATION_CONFIG[footnote.verification_status] || VERIFICATION_CONFIG.unverified;
    const VerifyIcon = verification.icon;

    // Construct IK URL if we have ik_doc_id
    const ikUrl = footnote.ik_doc_id
        ? `https://indiankanoon.org/doc/${footnote.ik_doc_id}/`
        : null;

    // Construct open link: prefer IK, fallback to source_url
    const openUrl = ikUrl || footnote.source_url || null;

    // PDF URL for internal cases
    const pdfUrl = footnote.pdf_available && footnote.case_id
        ? getCasePdfUrl(footnote.case_id)
        : null;

    // Determine if this is a web source
    const isWeb = footnote.source_label === "Web";
    const isCase = footnote.source_label === "Case";

    return (
        <div className="h-full flex flex-col">
            {/* Header bar */}
            <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
                <div className="flex items-center gap-2">
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-[var(--gold)] text-white text-xs font-bold">
                        {footnote.number}
                    </span>
                    <LabelIcon className={`h-4 w-4 ${label.color}`} />
                    <span className={`text-xs font-semibold uppercase ${label.color}`}>
                        {footnote.source_label === "Case" ? "CASE LAW" : footnote.source_label.toUpperCase()}
                    </span>
                </div>
                {openUrl && (
                    <a
                        href={openUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium text-[var(--gold)] hover:underline inline-flex items-center gap-1"
                    >
                        Open <ExternalLink className="h-3 w-3" />
                    </a>
                )}
            </div>

            {/* Content — scrollable */}
            <div className="flex-1 overflow-y-auto">
                {/* Title & metadata */}
                <div className="px-4 py-3 border-b">
                    <h3 className="text-base font-semibold leading-snug">
                        {footnote.title || footnote.citation}
                    </h3>
                    {isCase && (
                        <p className="text-xs text-muted-foreground mt-1.5 space-x-1">
                            {footnote.citation && <span>{footnote.citation}</span>}
                            {footnote.court && <span>· {footnote.court}</span>}
                            {footnote.year && <span>· {footnote.year}</span>}
                        </p>
                    )}
                    {footnote.author && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                            <span className="font-medium">Bench:</span> {footnote.author}
                            {footnote.bench && ` (${footnote.bench})`}
                        </p>
                    )}
                    {/* Verification badge */}
                    <div className="flex items-center gap-1 mt-2">
                        <VerifyIcon className={`h-3.5 w-3.5 ${verification.color}`} />
                        <span className="text-xs text-muted-foreground">{verification.label}</span>
                    </div>
                </div>

                {/* Web source: show URL + content preview */}
                {isWeb && (
                    <div className="px-4 py-3 border-b">
                        {footnote.source_url && (
                            <a
                                href={footnote.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-[var(--gold)] hover:underline break-all"
                            >
                                {footnote.source_url}
                            </a>
                        )}
                        {footnote.excerpt && (
                            <div className="mt-3">
                                <h4 className="text-xs uppercase tracking-wider font-semibold text-muted-foreground mb-1.5">
                                    Page Content
                                </h4>
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {footnote.excerpt}
                                </p>
                            </div>
                        )}
                        {footnote.source_url && (
                            <a
                                href={footnote.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="mt-4 flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-muted hover:bg-muted/80 text-sm font-medium transition-colors"
                            >
                                <ExternalLink className="h-4 w-4" />
                                View Full Document
                            </a>
                        )}
                    </div>
                )}

                {/* Case: Summaries section (collapsible) */}
                {isCase && footnote.excerpt && (
                    <div className="px-4 py-3 border-b">
                        <button
                            onClick={() => setSummaryOpen(!summaryOpen)}
                            className="flex items-center gap-1 text-xs uppercase tracking-wider font-semibold text-muted-foreground hover:text-foreground"
                        >
                            {summaryOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                            Summaries
                            <span className="ml-2 text-[10px] font-normal lowercase">
                                {summaryOpen ? "▼ collapse" : "► expand"}
                            </span>
                        </button>
                        {summaryOpen && (
                            <div className="mt-2 text-sm text-muted-foreground leading-relaxed">
                                {footnote.excerpt}
                            </div>
                        )}
                    </div>
                )}

                {/* Case: IK link */}
                {isCase && ikUrl && (
                    <div className="px-4 py-3 border-b">
                        <a
                            href={ikUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-muted hover:bg-muted/80 text-sm font-medium transition-colors"
                        >
                            <ExternalLink className="h-4 w-4" />
                            View on Indian Kanoon
                        </a>
                    </div>
                )}

                {/* Case: Embedded PDF viewer */}
                {pdfUrl && (
                    <div className="px-4 py-3">
                        <div className="flex items-center justify-between mb-2">
                            <p className="text-xs font-medium text-muted-foreground">
                                📄 {footnote.title || "Judgment"}.pdf
                            </p>
                            <a
                                href={pdfUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-[var(--gold)] hover:underline inline-flex items-center gap-1"
                            >
                                View <ExternalLink className="h-3 w-3" />
                            </a>
                        </div>
                        <div className="border rounded-lg overflow-hidden bg-white dark:bg-zinc-900 max-h-[400px] overflow-y-auto">
                            <Document
                                file={pdfUrl}
                                onLoadSuccess={({ numPages: n }) => setNumPages(n)}
                                loading={
                                    <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
                                        Loading PDF...
                                    </div>
                                }
                                error={
                                    <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                                        PDF not available.{" "}
                                        <a href={pdfUrl} target="_blank" rel="noopener noreferrer" className="text-[var(--gold)] underline ml-1">
                                            Download instead
                                        </a>
                                    </div>
                                }
                            >
                                <Page pageNumber={1} width={380} />
                            </Document>
                        </div>
                    </div>
                )}

                {/* Statute: Show section text */}
                {footnote.source_label === "Statute" && footnote.excerpt && (
                    <div className="px-4 py-3 border-b">
                        <h4 className="text-xs uppercase tracking-wider font-semibold text-muted-foreground mb-1.5">
                            Section Text
                        </h4>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">
                            {footnote.excerpt}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
```

**Step 2: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds (may need to verify react-pdf worker setup)

**Step 3: Commit**

```bash
git add frontend/src/components/footnote-preview.tsx
git commit -m "feat: add FootnotePreview component with case metadata, PDF viewer, web preview"
```

---

### Task 5: Create FootnotesPanel Component (Container)

The right-side panel container with "Footnotes" and "Preview" tabs — the main orchestration component.

**Files:**
- Create: `frontend/src/components/footnotes-panel.tsx`

**Step 1: Create the component**

```tsx
"use client";

import { useState, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { FootnoteListItem } from "@/components/footnote-list-item";
import { FootnotePreview } from "@/components/footnote-preview";
import type { ResearchFootnote } from "@/lib/types";

interface FootnotesPanelProps {
    footnotes: ResearchFootnote[];
    /** Called when user clicks a footnote number in the memo */
    selectedFootnoteNumber: number | null;
    onFootnoteSelect: (num: number | null) => void;
    /** Panel open/close state */
    isOpen: boolean;
    onToggle: () => void;
}

export function FootnotesPanel({
    footnotes,
    selectedFootnoteNumber,
    onFootnoteSelect,
    isOpen,
    onToggle,
}: FootnotesPanelProps) {
    const [activeTab, setActiveTab] = useState<string>("footnotes");

    const usedFootnotes = footnotes.filter((fn) => fn.is_used);
    const unusedFootnotes = footnotes.filter((fn) => !fn.is_used);

    const selectedFootnote = footnotes.find((fn) => fn.number === selectedFootnoteNumber) || null;

    const handleFootnoteClick = useCallback((num: number) => {
        onFootnoteSelect(num);
        setActiveTab("preview");
    }, [onFootnoteSelect]);

    if (!isOpen) {
        return (
            <button
                onClick={onToggle}
                className="fixed right-4 top-20 z-40 p-2 rounded-lg border bg-card shadow-md hover:bg-muted/50 transition-colors"
                title="Open Footnotes"
            >
                <PanelRightOpen className="h-4 w-4" />
            </button>
        );
    }

    return (
        <div className="h-full flex flex-col border-l bg-card">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
                {/* Tab header */}
                <div className="flex items-center justify-between px-2 border-b">
                    <TabsList className="bg-transparent h-10">
                        <TabsTrigger value="footnotes" className="text-xs data-[state=active]:border-b-2 data-[state=active]:border-[var(--gold)] rounded-none">
                            Footnotes
                            <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-muted text-[10px] font-bold">
                                {usedFootnotes.length}
                            </span>
                        </TabsTrigger>
                        <TabsTrigger value="preview" className="text-xs data-[state=active]:border-b-2 data-[state=active]:border-[var(--gold)] rounded-none">
                            Preview
                        </TabsTrigger>
                    </TabsList>
                    <button
                        onClick={onToggle}
                        className="p-1.5 rounded hover:bg-muted/50 transition-colors"
                        title="Close Panel"
                    >
                        <PanelRightClose className="h-4 w-4" />
                    </button>
                </div>

                {/* Footnotes list tab */}
                <TabsContent value="footnotes" className="flex-1 m-0 overflow-hidden">
                    <ScrollArea className="h-full">
                        {usedFootnotes.map((fn) => (
                            <FootnoteListItem
                                key={fn.number}
                                footnote={fn}
                                isSelected={fn.number === selectedFootnoteNumber}
                                onClick={() => handleFootnoteClick(fn.number)}
                            />
                        ))}
                        {unusedFootnotes.length > 0 && (
                            <>
                                <div className="px-3 py-2 text-[10px] uppercase tracking-wider font-semibold text-muted-foreground bg-muted/30">
                                    Searched but Not Cited ({unusedFootnotes.length})
                                </div>
                                {unusedFootnotes.map((fn) => (
                                    <FootnoteListItem
                                        key={fn.number}
                                        footnote={fn}
                                        isSelected={fn.number === selectedFootnoteNumber}
                                        onClick={() => handleFootnoteClick(fn.number)}
                                    />
                                ))}
                            </>
                        )}
                    </ScrollArea>
                </TabsContent>

                {/* Preview tab */}
                <TabsContent value="preview" className="flex-1 m-0 overflow-hidden">
                    {selectedFootnote ? (
                        <ScrollArea className="h-full">
                            <FootnotePreview footnote={selectedFootnote} />
                        </ScrollArea>
                    ) : (
                        <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                            Select a footnote to preview
                        </div>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}
```

**Step 2: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/footnotes-panel.tsx
git commit -m "feat: add FootnotesPanel container with Footnotes/Preview tabs"
```

---

### Task 6: Make Memo Footnote References Clickable

Modify the AgentMemoViewer to convert `[^N]` and `[N]` references in memo text into clickable elements that trigger the footnotes panel.

**Files:**
- Modify: `frontend/src/components/agent-memo-viewer.tsx`

**Step 1: Add footnote click callback prop**

Add to the component's props:

```typescript
interface AgentMemoViewerProps {
    content: string;
    confidence?: number;
    onFootnoteClick?: (num: number) => void;  // NEW
}
```

**Step 2: Add markdown processing for footnote links**

In the markdown rendering section, use a custom `remarkPlugin` or post-processing step to convert `[^N]` and `[N]` patterns into clickable gold pill badges:

Add a `components` override to the react-markdown renderer:

```typescript
// In the react-markdown <ReactMarkdown> component, add custom link processing
// Replace [^1], [^2] etc. with clickable badges in the rendered output

// Before rendering, replace footnote patterns in the content:
const processedContent = content.replace(
    /\[\^?(\d+)\]/g,
    (match, num) => `<fn data-num="${num}">[${num}]</fn>`
);
```

Since react-markdown doesn't support custom HTML tags natively, use a simpler approach — split the text by footnote patterns and render inline:

```typescript
// Helper to render text with clickable footnote badges
function renderWithFootnotes(text: string, onFootnoteClick?: (n: number) => void) {
    const parts = text.split(/(\[\^?\d+\])/g);
    return parts.map((part, i) => {
        const match = part.match(/^\[\^?(\d+)\]$/);
        if (match && onFootnoteClick) {
            const num = parseInt(match[1], 10);
            return (
                <button
                    key={i}
                    onClick={() => onFootnoteClick(num)}
                    className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-[var(--gold)]/20 text-[var(--gold)] text-[10px] font-bold hover:bg-[var(--gold)]/30 transition-colors mx-0.5 align-super cursor-pointer"
                    title={`View source [${num}]`}
                >
                    {num}
                </button>
            );
        }
        return <span key={i}>{part}</span>;
    });
}
```

Apply this to all text nodes in the markdown rendering. The simplest approach: override the `p`, `li`, and `td` components in react-markdown to process their children through `renderWithFootnotes`.

**Step 3: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/components/agent-memo-viewer.tsx
git commit -m "feat: make [N] footnote references clickable gold pills in memo viewer"
```

---

### Task 7: Redesign Research Page Layout — Split Panel

The main integration task. Change the research page from sequential layout (memo → footnotes below) to a split-panel layout (memo left, footnotes panel right) like Jhana.

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx`

**Step 1: Add new state for footnotes panel**

Add to the state declarations (around line 60-81):

```typescript
const [footnotesPanelOpen, setFootnotesPanelOpen] = useState(false);
const [selectedFootnoteNum, setSelectedFootnoteNum] = useState<number | null>(null);
```

Auto-open the panel when footnotes arrive:
```typescript
// In the memo event handler (around line 143-164), after setting footnotes:
if (data.footnotes?.length > 0) {
    setFootnotesPanelOpen(true);
}
```

**Step 2: Change the grid layout**

Replace the current workspace grid (line 330-437) with a new three-column layout:

```
Timeline (240px) | Main Content (flex) | Footnotes Panel (380px, conditional)
```

Change the grid from:
```typescript
<div className="grid gap-6 md:grid-cols-[240px_1fr]">
```

To:
```typescript
<div className={`grid gap-6 md:grid-cols-[240px_1fr] ${
    footnotesPanelOpen && footnotes.length > 0 ? "lg:grid-cols-[240px_1fr_380px]" : ""
}`}>
```

**Step 3: Add FootnotesPanel as third column**

After the main content `</div>` (right column), add:

```typescript
{/* Right: Footnotes Panel */}
{footnotes.length > 0 && !isRunning && (
    <div className="hidden lg:block">
        <div className="sticky top-20 h-[calc(100vh-6rem)] rounded-lg border overflow-hidden">
            <FootnotesPanel
                footnotes={footnotes}
                selectedFootnoteNumber={selectedFootnoteNum}
                onFootnoteSelect={setSelectedFootnoteNum}
                isOpen={footnotesPanelOpen}
                onToggle={() => setFootnotesPanelOpen(!footnotesPanelOpen)}
            />
        </div>
    </div>
)}
```

**Step 4: Wire the memo viewer footnote clicks**

Update the AgentMemoViewer usage to pass the callback:

```typescript
<AgentMemoViewer
    content={displayMemo}
    confidence={confidence}
    onFootnoteClick={(num) => {
        setSelectedFootnoteNum(num);
        setFootnotesPanelOpen(true);
    }}
/>
```

**Step 5: Remove old sequential footnotes**

Remove the old `<ResearchFootnotes>` below the memo (lines 397-400). The footnotes are now in the side panel.

Keep the old component for mobile fallback:
```typescript
{/* Mobile: old footnotes below memo */}
{footnotes.length > 0 && !isRunning && (
    <div className="lg:hidden">
        <ResearchFootnotes footnotes={footnotes} />
    </div>
)}
```

**Step 6: Add imports**

```typescript
import { FootnotesPanel } from "@/components/footnotes-panel";
```

**Step 7: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 8: Commit**

```bash
git add frontend/src/app/agents/research/page.tsx
git commit -m "feat: split-panel research page with Jhana-style footnotes panel"
```

---

### Task 8: Mobile Drawer for Footnotes

On mobile/tablet (below `lg` breakpoint), show footnotes as a slide-up Sheet (drawer) instead of a side panel.

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx`

**Step 1: Add a mobile footnotes drawer**

Below the mobile fallback `<ResearchFootnotes>`, add a Sheet trigger button and drawer:

```typescript
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { FileText } from "lucide-react";

// In the mobile section (lg:hidden):
{footnotes.length > 0 && !isRunning && (
    <div className="lg:hidden">
        <Sheet>
            <SheetTrigger asChild>
                <Button variant="outline" size="sm" className="w-full">
                    <FileText className="h-4 w-4 mr-2" />
                    Footnotes & Sources ({footnotes.filter(f => f.is_used).length})
                </Button>
            </SheetTrigger>
            <SheetContent side="bottom" className="h-[80vh] p-0">
                <FootnotesPanel
                    footnotes={footnotes}
                    selectedFootnoteNumber={selectedFootnoteNum}
                    onFootnoteSelect={setSelectedFootnoteNum}
                    isOpen={true}
                    onToggle={() => {}}
                />
            </SheetContent>
        </Sheet>
    </div>
)}
```

**Step 2: Remove old mobile `<ResearchFootnotes>` render**

Remove the `<div className="lg:hidden"><ResearchFootnotes .../>` since the Sheet replaces it.

**Step 3: Verify it builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/app/agents/research/page.tsx
git commit -m "feat: mobile drawer for footnotes panel via shadcn Sheet"
```

---

### Task 9: Frontend Tests

**Files:**
- Create: `frontend/src/components/__tests__/footnote-list-item.test.tsx`
- Create: `frontend/src/components/__tests__/footnotes-panel.test.tsx`

**Step 1: Write FootnoteListItem tests**

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { FootnoteListItem } from "../footnote-list-item";
import type { ResearchFootnote } from "@/lib/types";

const mockFootnote: ResearchFootnote = {
    number: 1,
    citation: "(2023) 5 SCC 1",
    source_type: "case_law",
    source_url: "/case/abc-123",
    case_id: "abc-123",
    excerpt: "The court held that privacy is fundamental.",
    is_used: true,
    verification_status: "verified_pg",
    verified_against: "pg",
    title: "Puttaswamy v. Union of India",
    court: "Supreme Court of India",
    year: 2023,
    author: "D Y Chandrachud",
    bench: "Constitution Bench",
    ik_doc_id: "12345678",
    pdf_available: true,
    source_label: "Case",
};

describe("FootnoteListItem", () => {
    it("renders footnote number and title", () => {
        render(<FootnoteListItem footnote={mockFootnote} isSelected={false} onClick={jest.fn()} />);
        expect(screen.getByText("1")).toBeInTheDocument();
        expect(screen.getByText("Puttaswamy v. Union of India")).toBeInTheDocument();
    });

    it("shows Case badge for case_law source", () => {
        render(<FootnoteListItem footnote={mockFootnote} isSelected={false} onClick={jest.fn()} />);
        expect(screen.getByText("Case")).toBeInTheDocument();
    });

    it("shows Web badge for web source", () => {
        const webFn = { ...mockFootnote, source_label: "Web" };
        render(<FootnoteListItem footnote={webFn} isSelected={false} onClick={jest.fn()} />);
        expect(screen.getByText("Web")).toBeInTheDocument();
    });

    it("calls onClick when clicked", () => {
        const onClick = jest.fn();
        render(<FootnoteListItem footnote={mockFootnote} isSelected={false} onClick={onClick} />);
        fireEvent.click(screen.getByRole("button"));
        expect(onClick).toHaveBeenCalledTimes(1);
    });

    it("highlights when selected", () => {
        const { container } = render(<FootnoteListItem footnote={mockFootnote} isSelected={true} onClick={jest.fn()} />);
        expect(container.querySelector("button")?.className).toContain("border-l-[var(--gold)]");
    });
});
```

**Step 2: Write FootnotesPanel tests**

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { FootnotesPanel } from "../footnotes-panel";
import type { ResearchFootnote } from "@/lib/types";

const baseFn: ResearchFootnote = {
    number: 1, citation: "(2023) 5 SCC 1", source_type: "case_law",
    source_url: "/case/abc", case_id: "abc", excerpt: "Test excerpt",
    is_used: true, verification_status: "verified_pg", verified_against: "pg",
    title: "Test Case", court: "Supreme Court", year: 2023,
    author: "Judge", bench: "Bench", ik_doc_id: "123", pdf_available: false,
    source_label: "Case",
};

const mockFootnotes: ResearchFootnote[] = [
    baseFn,
    { ...baseFn, number: 2, citation: "IPC Section 302", source_type: "statute", source_label: "Statute", is_used: true },
    { ...baseFn, number: 3, title: "Legal blog", source_type: "web", source_label: "Web", is_used: false },
];

describe("FootnotesPanel", () => {
    it("shows footnotes count in tab", () => {
        render(
            <FootnotesPanel
                footnotes={mockFootnotes}
                selectedFootnoteNumber={null}
                onFootnoteSelect={jest.fn()}
                isOpen={true}
                onToggle={jest.fn()}
            />
        );
        expect(screen.getByText("2")).toBeInTheDocument(); // 2 used footnotes
    });

    it("shows Searched but Not Cited section", () => {
        render(
            <FootnotesPanel
                footnotes={mockFootnotes}
                selectedFootnoteNumber={null}
                onFootnoteSelect={jest.fn()}
                isOpen={true}
                onToggle={jest.fn()}
            />
        );
        expect(screen.getByText(/Searched but Not Cited/)).toBeInTheDocument();
    });

    it("switches to Preview tab on footnote click", () => {
        const onSelect = jest.fn();
        render(
            <FootnotesPanel
                footnotes={mockFootnotes}
                selectedFootnoteNumber={null}
                onFootnoteSelect={onSelect}
                isOpen={true}
                onToggle={jest.fn()}
            />
        );
        fireEvent.click(screen.getByText("Test Case"));
        expect(onSelect).toHaveBeenCalledWith(1);
    });
});
```

**Step 3: Run tests**

Run: `cd frontend && npx vitest run src/components/__tests__/footnote-list-item.test.tsx src/components/__tests__/footnotes-panel.test.tsx`
Expected: All pass

**Step 4: Commit**

```bash
git add frontend/src/components/__tests__/
git commit -m "test: add frontend tests for FootnoteListItem and FootnotesPanel"
```

---

### Task 10: Backend Tests for Enriched Footnotes

**Files:**
- Modify: `backend/tests/unit/test_research_v2_phase4.py`

**Step 1: Add test for source_label inference**

```python
def test_infer_source_label():
    from app.core.agents.nodes.research_nodes import _infer_source_label
    assert _infer_source_label("case_law") == "Case"
    assert _infer_source_label("ik_search") == "Case"
    assert _infer_source_label("statute") == "Statute"
    assert _infer_source_label("constitution") == "Constitution"
    assert _infer_source_label("web") == "Web"
    assert _infer_source_label("unknown") == "Source"
```

**Step 2: Add test for enriched fields in format_footnotes output**

Test that `format_footnotes_node` populates `title`, `court`, `year`, `ik_doc_id`, `source_label` from worker results.

**Step 3: Run all backend tests**

Run: `cd backend && python -m pytest tests/unit/ -x -q`
Expected: All pass

**Step 4: Commit**

```bash
git add backend/tests/unit/test_research_v2_phase4.py
git commit -m "test: add backend tests for enriched footnote fields and source_label"
```

---

### Task 11: Full Integration Test

**Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest tests/unit/ -x -q`
Expected: All tests pass (1811+)

**Step 2: Run full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: All tests pass (298+)

**Step 3: Build both projects**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration fixes for footnotes panel"
```

---

### Task 12: Final Cleanup & Verification

**Step 1: Remove old `<ResearchFootnotes>` import if no longer needed on desktop**

Check if it's still used for mobile fallback. If mobile uses Sheet+FootnotesPanel, remove the old component entirely. If kept for mobile, leave it.

**Step 2: Verify the full flow end-to-end**

Manual verification checklist:
- [ ] Research agent produces memo with `[^N]` references
- [ ] `[N]` references render as gold pill badges in memo
- [ ] Clicking a pill opens the footnotes panel on the right
- [ ] Footnotes panel shows "Footnotes" tab with Case/Web/Statute badges
- [ ] Clicking a footnote switches to "Preview" tab
- [ ] Case preview shows: title, citation, court, year, bench, verification badge
- [ ] Case preview shows "View on Indian Kanoon" link (if ik_doc_id present)
- [ ] Case preview shows embedded PDF viewer (if pdf_available)
- [ ] Web preview shows URL, content excerpt, "View Full Document" button
- [ ] Panel can be collapsed/expanded
- [ ] Mobile: footnotes open as bottom Sheet drawer
- [ ] All existing tests still pass

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: Jhana-style research footnotes panel — split layout, case preview, PDF viewer"
```
