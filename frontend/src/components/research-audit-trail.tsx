"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, BarChart3 } from "lucide-react";
import type { ResearchAudit } from "@/lib/types";

interface ResearchAuditTrailProps {
    audit: ResearchAudit;
}

export function ResearchAuditTrail({ audit }: ResearchAuditTrailProps) {
    const [isOpen, setIsOpen] = useState(true);

    const stats = [
        { label: "Sources Searched", value: audit.total_sources_searched },
        { label: "Sources Cited", value: audit.sources_cited },
        { label: "Sources Unused", value: audit.sources_unused },
        { label: "Searches Executed", value: audit.searches_executed },
        { label: "Refinement Rounds", value: audit.refinement_rounds },
        { label: "Deep Reads", value: audit.deep_reads_performed },
        { label: "Citations Verified", value: audit.citations_verified },
        { label: "Citations Removed", value: audit.citations_removed },
        { label: "Strategy Pivots", value: audit.strategy_pivots },
    ].filter((s) => s.value !== undefined && s.value !== null);

    if (stats.length === 0) return null;

    return (
        <div className="border rounded-lg bg-card">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium text-left hover:bg-muted/50 transition-colors"
            >
                {isOpen ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
                Research Audit Trail
            </button>

            {isOpen && (
                <div className="px-4 pb-3 space-y-3">
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        {stats.map((s) => (
                            <div key={s.label} className="text-center">
                                <div className="text-lg font-semibold text-foreground">{s.value}</div>
                                <div className="text-xs text-muted-foreground">{s.label}</div>
                            </div>
                        ))}
                    </div>
                    {audit.source_counts && Object.keys(audit.source_counts).length > 0 && (
                        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border">
                            <span className="text-xs text-muted-foreground font-medium">Sources:</span>
                            {Object.entries(audit.source_counts).map(([source, count]) => (
                                <span
                                    key={source}
                                    className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground"
                                >
                                    <span className="font-semibold text-foreground">{source}</span>
                                    <span>{count}</span>
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
