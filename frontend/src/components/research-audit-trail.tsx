"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { ResearchAudit } from "@/lib/types";

interface ResearchAuditTrailProps {
    audit: ResearchAudit;
}

export function ResearchAuditTrail({ audit }: ResearchAuditTrailProps) {
    const [isOpen, setIsOpen] = useState(false);

    const stats = [
        { label: "Sources searched", value: audit.total_sources_searched },
        { label: "Cited", value: audit.sources_cited },
        { label: "Searches run", value: audit.searches_executed },
        { label: "Refinements", value: audit.refinement_rounds },
        { label: "Verified", value: audit.citations_verified },
        { label: "Pivots", value: audit.strategy_pivots },
    ].filter((s) => s.value !== undefined && s.value !== null && s.value > 0);

    if (stats.length === 0) return null;

    return (
        <div className="rounded-lg border bg-card">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-xs font-medium text-muted-foreground text-left hover:text-foreground transition-colors"
            >
                {isOpen ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                )}
                Research Audit
                <span className="ml-auto tabular-nums">
                    {audit.total_sources_searched ?? 0} sources, {audit.citations_verified ?? 0} verified
                </span>
            </button>

            {isOpen && (
                <div className="px-4 pb-3 pt-1 space-y-3 border-t">
                    <div className="flex flex-wrap gap-x-6 gap-y-2">
                        {stats.map((s) => (
                            <div key={s.label} className="flex items-baseline gap-1.5">
                                <span className="text-sm font-semibold tabular-nums text-foreground">{s.value}</span>
                                <span className="text-xs text-muted-foreground">{s.label}</span>
                            </div>
                        ))}
                    </div>
                    {audit.source_counts && Object.keys(audit.source_counts).length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-border/50">
                            {Object.entries(audit.source_counts).map(([source, count]) => (
                                <span
                                    key={source}
                                    className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
                                >
                                    {source} <span className="font-semibold text-foreground">{count}</span>
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
