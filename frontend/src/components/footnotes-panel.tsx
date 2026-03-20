"use client";

import { useState } from "react";
import { PanelRightOpen, PanelRightClose } from "lucide-react";
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
    isOpen,
    onToggle,
}: FootnotesPanelProps) {
    const [activeTab, setActiveTab] = useState<string>("footnotes");

    const usedFootnotes = footnotes.filter((f) => f.is_used);
    const unusedFootnotes = footnotes.filter((f) => !f.is_used);
    const selectedFootnote =
        selectedFootnoteNumber !== null
            ? footnotes.find((f) => f.number === selectedFootnoteNumber) ?? null
            : null;

    function handleFootnoteClick(num: number) {
        onFootnoteSelect(num);
        setActiveTab("preview");
    }

    if (!isOpen) {
        return (
            <button
                type="button"
                onClick={onToggle}
                className={cn(
                    "fixed right-4 top-20 z-40 flex items-center gap-2 rounded-lg",
                    "bg-background/95 border shadow-md backdrop-blur-sm",
                    "px-3 py-2 text-sm font-medium",
                    "hover:bg-muted transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                )}
            >
                <PanelRightOpen className="h-4 w-4" />
                <span>Footnotes</span>
                {usedFootnotes.length > 0 && (
                    <span className="flex items-center justify-center h-5 min-w-5 rounded-full bg-[var(--gold)] text-white text-xs font-semibold px-1">
                        {usedFootnotes.length}
                    </span>
                )}
            </button>
        );
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
            <TabsContent value="footnotes" className="mt-0 flex-1 min-h-0">
                <ScrollArea className="h-full">
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

                        {footnotes.length === 0 && (
                            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
                                No footnotes yet
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
