"use client";

import { useMemo, useState } from "react";
import { PanelRightClose, Search } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FootnoteListItem } from "@/components/footnote-list-item";
import { FootnotePreview } from "@/components/footnote-preview";
import { cn } from "@/lib/utils";
import type { ResearchFootnote } from "@/lib/types";

interface FootnotesPanelProps {
    footnotes: ResearchFootnote[];
    selectedFootnoteNumber: number | null;
    onFootnoteSelect: (num: number | null) => void;
    isOpen: boolean;
    onToggle: () => void;
}

export function FootnotesPanel({
    footnotes,
    selectedFootnoteNumber,
    onFootnoteSelect,
    isOpen: _isOpen,
    onToggle,
}: FootnotesPanelProps) {
    const [activeTab, setActiveTab] = useState<string>("footnotes");
    const [searchQuery, setSearchQuery] = useState("");
    const [sourceFilter, setSourceFilter] = useState<string>("all");

    const SOURCE_FILTERS = ["all", "Case", "Statute", "Web"] as const;

    const filteredFootnotes = useMemo(() => {
        let filtered = footnotes;
        if (sourceFilter !== "all") {
            filtered = filtered.filter((f) => f.source_label === sourceFilter);
        }
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            filtered = filtered.filter(
                (f) =>
                    f.title?.toLowerCase().includes(q) ||
                    f.citation?.toLowerCase().includes(q) ||
                    f.court?.toLowerCase().includes(q),
            );
        }
        return filtered;
    }, [footnotes, searchQuery, sourceFilter]);

    const usedFootnotes = filteredFootnotes.filter((f) => f.is_used);
    const unusedFootnotes = filteredFootnotes.filter((f) => !f.is_used);
    const selectedFootnote =
        selectedFootnoteNumber !== null
            ? footnotes.find((f) => f.number === selectedFootnoteNumber) ?? null
            : null;

    function handleFootnoteClick(num: number) {
        onFootnoteSelect(num);
        setActiveTab("preview");
    }

    return (
        <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex h-full flex-col"
        >
            {/* Tab header */}
            <div className="flex items-center border-b px-2">
                <TabsList className="flex-1 bg-transparent h-10">
                    <TabsTrigger
                        value="footnotes"
                        className={cn(
                            "rounded-none bg-transparent px-3",
                            "data-[state=active]:border-b-2 data-[state=active]:border-[var(--gold)]",
                            "data-[state=active]:bg-transparent data-[state=active]:shadow-none"
                        )}
                    >
                        Footnotes
                        {usedFootnotes.length > 0 && (
                            <span className="ml-1.5 flex items-center justify-center h-5 min-w-5 rounded-full bg-[var(--gold)] text-white text-[10px] font-semibold px-1">
                                {usedFootnotes.length}
                            </span>
                        )}
                    </TabsTrigger>
                    <TabsTrigger
                        value="preview"
                        className={cn(
                            "rounded-none bg-transparent px-3",
                            "data-[state=active]:border-b-2 data-[state=active]:border-[var(--gold)]",
                            "data-[state=active]:bg-transparent data-[state=active]:shadow-none"
                        )}
                    >
                        Preview
                    </TabsTrigger>
                </TabsList>
                <button
                    type="button"
                    onClick={onToggle}
                    className="ml-auto shrink-0 p-1.5 rounded-md hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    aria-label="Close footnotes panel"
                >
                    <PanelRightClose className="h-4 w-4" />
                </button>
            </div>

            {/* Footnotes list tab */}
            <TabsContent value="footnotes" className="mt-0 flex-1 min-h-0 flex flex-col">
                {/* Search & filter */}
                <div className="px-2 pt-2 pb-1 space-y-1.5 border-b">
                    <div className="relative">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Search footnotes..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-7 pr-2 py-1.5 text-xs rounded-md border bg-background focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                        />
                    </div>
                    <div className="flex gap-1">
                        {SOURCE_FILTERS.map((f) => (
                            <button
                                key={f}
                                onClick={() => setSourceFilter(f)}
                                className={cn(
                                    "px-2 py-0.5 text-[10px] rounded-full border transition-colors",
                                    sourceFilter === f
                                        ? "bg-[var(--gold)] text-foreground border-[var(--gold)]"
                                        : "bg-transparent text-muted-foreground border-border hover:bg-muted",
                                )}
                            >
                                {f === "all" ? "All" : f}
                            </button>
                        ))}
                    </div>
                </div>
                <ScrollArea className="flex-1 min-h-0">
                    <div className="py-1">
                        {usedFootnotes.map((f) => (
                            <FootnoteListItem
                                key={f.number}
                                footnote={f}
                                isSelected={f.number === selectedFootnoteNumber}
                                onClick={() => handleFootnoteClick(f.number)}
                            />
                        ))}

                        {unusedFootnotes.length > 0 && (
                            <>
                                <div className="px-3 pt-4 pb-2">
                                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                        Searched but Not Cited
                                    </p>
                                </div>
                                {unusedFootnotes.map((f) => (
                                    <FootnoteListItem
                                        key={f.number}
                                        footnote={f}
                                        isSelected={
                                            f.number === selectedFootnoteNumber
                                        }
                                        onClick={() =>
                                            handleFootnoteClick(f.number)
                                        }
                                    />
                                ))}
                            </>
                        )}

                        {filteredFootnotes.length === 0 && (
                            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
                                {footnotes.length === 0 ? "No footnotes yet" : "No matching footnotes"}
                            </div>
                        )}
                    </div>
                </ScrollArea>
            </TabsContent>

            {/* Preview tab */}
            <TabsContent value="preview" className="mt-0 flex-1 min-h-0">
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
    );
}
