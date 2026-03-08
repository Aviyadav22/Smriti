"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ChevronDown, ChevronRight, Pencil, FileText, File } from "lucide-react";

interface DraftSectionViewerProps {
    sections: Record<string, string>;
    onRevise?: (sectionName: string, feedback: string) => void;
    onExport?: (format: "docx" | "pdf") => void;
    disabled?: boolean;
}

function formatSectionName(name: string): string {
    return name
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function DraftSectionViewer({ sections, onRevise, onExport, disabled }: DraftSectionViewerProps) {
    const [expandedSections, setExpandedSections] = useState<Set<string>>(
        new Set(Object.keys(sections)),
    );
    const [revisingSection, setRevisingSection] = useState<string | null>(null);
    const [revisionFeedback, setRevisionFeedback] = useState("");

    const toggleSection = (name: string) => {
        setExpandedSections((prev) => {
            const next = new Set(prev);
            if (next.has(name)) {
                next.delete(name);
            } else {
                next.add(name);
            }
            return next;
        });
    };

    const handleStartRevision = (name: string) => {
        setRevisingSection(name);
        setRevisionFeedback("");
    };

    const handleCancelRevision = () => {
        setRevisingSection(null);
        setRevisionFeedback("");
    };

    const handleSubmitRevision = () => {
        if (!revisingSection || !revisionFeedback.trim() || !onRevise) return;
        onRevise(revisingSection, revisionFeedback.trim());
        setRevisingSection(null);
        setRevisionFeedback("");
    };

    return (
        <div className="space-y-3">
            {/* Export toolbar */}
            {onExport && (
                <div className="flex gap-2 justify-end">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onExport("docx")}
                        disabled={disabled}
                    >
                        <FileText className="h-3.5 w-3.5 mr-1.5" /> Download DOCX
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onExport("pdf")}
                        disabled={disabled}
                    >
                        <File className="h-3.5 w-3.5 mr-1.5" /> Download PDF
                    </Button>
                </div>
            )}

            {/* Section cards */}
            {Object.entries(sections).map(([name, content]) => {
                const isExpanded = expandedSections.has(name);
                const isRevising = revisingSection === name;

                return (
                    <Card key={name}>
                        <CardHeader
                            className="cursor-pointer select-none py-3 px-4"
                            role="button"
                            tabIndex={0}
                            aria-expanded={isExpanded}
                            onClick={() => toggleSection(name)}
                            onKeyDown={(e: React.KeyboardEvent) => {
                                if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    toggleSection(name);
                                }
                            }}
                        >
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    {isExpanded ? (
                                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                    ) : (
                                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                                    )}
                                    <CardTitle className="text-sm font-medium">
                                        {formatSectionName(name)}
                                    </CardTitle>
                                </div>
                                {onRevise && isExpanded && !isRevising && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-7 px-2 text-xs"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleStartRevision(name);
                                        }}
                                        disabled={disabled}
                                    >
                                        <Pencil className="h-3 w-3 mr-1" /> Revise
                                    </Button>
                                )}
                            </div>
                        </CardHeader>
                        {isExpanded && (
                            <CardContent className="pt-0 px-4 pb-4">
                                <div className="text-sm whitespace-pre-wrap leading-relaxed">
                                    {content}
                                </div>

                                {/* Inline revision textarea */}
                                {isRevising && (
                                    <div className="mt-4 space-y-2 border-t pt-3">
                                        <label
                                            htmlFor={`revision-${name}`}
                                            className="text-xs font-medium text-muted-foreground"
                                        >
                                            Revision feedback for {formatSectionName(name)}
                                        </label>
                                        <Textarea
                                            id={`revision-${name}`}
                                            placeholder="Describe what changes you want for this section..."
                                            value={revisionFeedback}
                                            onChange={(e) => setRevisionFeedback(e.target.value)}
                                            className="min-h-[80px] text-sm"
                                            disabled={disabled}
                                        />
                                        <div className="flex gap-2">
                                            <Button
                                                size="sm"
                                                onClick={handleSubmitRevision}
                                                disabled={disabled || !revisionFeedback.trim()}
                                            >
                                                Submit Revision
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={handleCancelRevision}
                                                disabled={disabled}
                                            >
                                                Cancel
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        )}
                    </Card>
                );
            })}
        </div>
    );
}
