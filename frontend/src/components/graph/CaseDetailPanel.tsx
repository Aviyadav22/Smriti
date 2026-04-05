"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { GraphNode } from "@/lib/types";
import { getGraphTreatmentSummary } from "@/lib/api";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CaseDetailPanelProps {
    node: GraphNode;
    onClose: () => void;
    onExplore: (caseId: string) => void;
}

// ---------------------------------------------------------------------------
// Treatment color mapping
// ---------------------------------------------------------------------------

const TREATMENT_BADGE_STYLES: Record<string, string> = {
    followed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    affirmed: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    applied: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    explained: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    distinguished: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
    doubted: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
    overruled: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    not_followed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    per_incuriam: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    cites: "bg-muted text-muted-foreground",
};

function getBadgeStyle(type: string): string {
    return TREATMENT_BADGE_STYLES[type] ?? "bg-muted text-muted-foreground";
}

// ---------------------------------------------------------------------------
// Issue tag colors (rotate through a palette)
// ---------------------------------------------------------------------------

const TAG_COLORS = [
    "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
    "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
    "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300",
    "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
    "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300",
    "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
];

function getTagColor(index: number): string {
    return TAG_COLORS[index % TAG_COLORS.length];
}

// ---------------------------------------------------------------------------
// Treatment summary type
// ---------------------------------------------------------------------------

interface TreatmentData {
    treatment_positive_pct: number;
    verdict: string;
    total_citations: number;
    breakdown: Record<
        string,
        Array<{
            id: string;
            title: string | null;
            year: number | null;
            citation: string | null;
            context: string | null;
        }>
    >;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CaseDetailPanel({
    node,
    onClose,
    onExplore,
}: CaseDetailPanelProps) {
    const [treatment, setTreatment] = useState<TreatmentData | null>(null);
    const [treatmentLoading, setTreatmentLoading] = useState(false);
    const [showFacts, setShowFacts] = useState(false);

    useEffect(() => {
        let cancelled = false;
        setTreatmentLoading(true);
        setTreatment(null);

        getGraphTreatmentSummary(node.id)
            .then((data) => {
                if (!cancelled) setTreatment(data);
            })
            .catch(() => {
                // Silently ignore — panel still shows other info
            })
            .finally(() => {
                if (!cancelled) setTreatmentLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [node.id]);

    // Reset fact toggle when node changes
    useEffect(() => {
        setShowFacts(false);
    }, [node.id]);

    // Treatment bar color
    const pct = node.treatment_positive_pct;
    let barColor = "bg-muted";
    if (pct != null) {
        if (pct >= 0.8) barColor = "bg-green-500";
        else if (pct >= 0.5) barColor = "bg-amber-500";
        else barColor = "bg-red-500";
    }

    // Parse issue tags
    const issueTags = node.issue_tags
        ? node.issue_tags.split(",").map((t) => t.trim()).filter(Boolean)
        : [];

    return (
        <div className="w-80 flex-shrink-0 border-l border-border bg-card overflow-y-auto">
            {/* Header */}
            <div className="sticky top-0 z-10 flex items-start justify-between border-b border-border bg-card p-4">
                <div className="min-w-0 flex-1 pr-2">
                    <h2 className="text-sm font-semibold text-foreground line-clamp-3">
                        {node.title ?? "Untitled"}
                    </h2>
                    {node.citation && (
                        <p className="mt-0.5 text-xs text-muted-foreground">
                            {node.citation}
                        </p>
                    )}
                </div>
                <button
                    type="button"
                    onClick={onClose}
                    className="flex-shrink-0 rounded p-1 text-muted-foreground transition hover:bg-accent hover:text-foreground"
                    aria-label="Close panel"
                >
                    &#x2715;
                </button>
            </div>

            <div className="space-y-5 p-4">
                {/* Treatment summary bar */}
                {pct != null && (
                    <div>
                        <p className="mb-1 text-xs font-medium text-muted-foreground">
                            Treatment
                        </p>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                            <div
                                className={`h-full rounded-full ${barColor}`}
                                style={{ width: `${Math.round(pct * 100)}%` }}
                            />
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                            {Math.round(pct * 100)}% positive
                            {treatment ? ` — ${treatment.verdict}` : ""}
                        </p>
                    </div>
                )}

                {/* Primary legal issue */}
                {node.primary_legal_issue && (
                    <div>
                        <p className="mb-1 text-xs font-medium text-muted-foreground">
                            Legal Question
                        </p>
                        <p className="text-sm font-medium text-foreground italic">
                            {node.primary_legal_issue}
                        </p>
                    </div>
                )}

                {/* Authority scores */}
                <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                        Authority Scores
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                        <div className="rounded-md bg-muted p-2">
                            <p className="text-xs text-muted-foreground">Overall</p>
                            <p className="text-sm font-semibold text-foreground">
                                {node.pagerank_global?.toFixed(4) ?? "N/A"}
                            </p>
                        </div>
                        <div className="rounded-md bg-muted p-2">
                            <p className="text-xs text-muted-foreground">Community</p>
                            <p className="text-sm font-semibold text-foreground">
                                {node.pagerank_community?.toFixed(4) ?? "N/A"}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Issue tags */}
                {issueTags.length > 0 && (
                    <div>
                        <p className="mb-1 text-xs font-medium text-muted-foreground">
                            Issue Tags
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                            {issueTags.map((tag, i) => (
                                <span
                                    key={tag}
                                    className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${getTagColor(i)}`}
                                >
                                    {tag}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Key Holding (headnote) */}
                {node.headnote_text && (
                    <div>
                        <p className="mb-1 text-xs font-medium text-muted-foreground">
                            Key Holding
                        </p>
                        <p className="text-xs leading-relaxed text-muted-foreground line-clamp-4">
                            {node.headnote_text}
                        </p>
                    </div>
                )}

                {/* Metadata */}
                <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                        Metadata
                    </p>
                    <dl className="space-y-1 text-xs">
                        {node.bench_type && (
                            <div className="flex justify-between">
                                <dt className="text-muted-foreground">Bench</dt>
                                <dd className="text-foreground">{node.bench_type}</dd>
                            </div>
                        )}
                        {node.coram_size != null && node.coram_size > 0 && (
                            <div className="flex justify-between">
                                <dt className="text-muted-foreground">Coram</dt>
                                <dd className="text-foreground">{node.coram_size} judges</dd>
                            </div>
                        )}
                        {node.year && (
                            <div className="flex justify-between">
                                <dt className="text-muted-foreground">Year</dt>
                                <dd className="text-foreground">{node.year}</dd>
                            </div>
                        )}
                        {node.case_type && (
                            <div className="flex justify-between">
                                <dt className="text-muted-foreground">Case Type</dt>
                                <dd className="flex items-center gap-1.5 text-foreground">
                                    {node.case_type}
                                    {node.is_reportable && (
                                        <span className="inline-block rounded bg-blue-100 px-1 py-0.5 text-[9px] font-semibold text-blue-700">
                                            R
                                        </span>
                                    )}
                                </dd>
                            </div>
                        )}
                        {node.opinion_type && (
                            <div className="flex justify-between">
                                <dt className="text-muted-foreground">Opinion</dt>
                                <dd className="text-foreground">{node.opinion_type}</dd>
                            </div>
                        )}
                        {node.jurisdiction && (
                            <div className="flex justify-between">
                                <dt className="text-muted-foreground">Jurisdiction</dt>
                                <dd className="text-foreground text-right max-w-[140px] truncate">
                                    {node.jurisdiction}
                                </dd>
                            </div>
                        )}
                        {node.court && (
                            <div className="flex justify-between">
                                <dt className="text-muted-foreground">Court</dt>
                                <dd className="text-foreground">{node.court}</dd>
                            </div>
                        )}
                        <div className="flex justify-between">
                            <dt className="text-muted-foreground">Cited by</dt>
                            <dd className="text-foreground">
                                {node.cited_by_count} cases
                            </dd>
                        </div>
                        {node.community_label && (
                            <div className="flex justify-between">
                                <dt className="text-muted-foreground">Topic</dt>
                                <dd className="text-foreground text-right max-w-[140px] truncate">
                                    {node.community_label}
                                </dd>
                            </div>
                        )}
                    </dl>
                </div>

                {/* Ratio excerpt */}
                {node.ratio && (
                    <div>
                        <p className="mb-1 text-xs font-medium text-muted-foreground">
                            Ratio Decidendi
                        </p>
                        <p className="text-xs leading-relaxed text-muted-foreground line-clamp-6">
                            {node.ratio}
                        </p>
                    </div>
                )}

                {/* Fact pattern (collapsible) */}
                {node.fact_pattern_summary && (
                    <div>
                        <button
                            type="button"
                            onClick={() => setShowFacts((p) => !p)}
                            className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition"
                        >
                            <span
                                className={`inline-block transition-transform text-[10px] ${showFacts ? "rotate-90" : ""}`}
                            >
                                &#x25B6;
                            </span>
                            Fact Pattern
                        </button>
                        {showFacts && (
                            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                                {node.fact_pattern_summary}
                            </p>
                        )}
                    </div>
                )}

                {/* Treatment breakdown */}
                <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                        Treatment Breakdown
                    </p>
                    {treatmentLoading && (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <div className="h-3 w-3 animate-spin rounded-full border border-border border-t-foreground" />
                            Loading...
                        </div>
                    )}
                    {treatment && (
                        <div className="flex flex-wrap gap-1.5">
                            {Object.entries(treatment.breakdown).map(
                                ([type, cases]) => (
                                    <span
                                        key={type}
                                        className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${getBadgeStyle(type)}`}
                                    >
                                        {type.replace(/_/g, " ")}
                                        <span className="font-semibold">
                                            {cases.length}
                                        </span>
                                    </span>
                                ),
                            )}
                            {Object.keys(treatment.breakdown).length === 0 && (
                                <span className="text-xs text-muted-foreground">
                                    No treatment data.
                                </span>
                            )}
                        </div>
                    )}
                    {!treatmentLoading && !treatment && (
                        <span className="text-xs text-muted-foreground">
                            Treatment data unavailable.
                        </span>
                    )}
                </div>

                {/* Action buttons */}
                <div className="flex gap-2 pt-2">
                    <Link
                        href={`/cases/${node.id}`}
                        className="flex-1 rounded-md bg-primary px-3 py-2 text-center text-xs font-medium text-primary-foreground transition hover:bg-primary/90"
                    >
                        View Full Case
                    </Link>
                    <button
                        type="button"
                        onClick={() => onExplore(node.id)}
                        className="flex-1 rounded-md border border-border px-3 py-2 text-xs font-medium text-foreground transition hover:bg-accent"
                    >
                        Explore from here
                    </button>
                </div>
            </div>
        </div>
    );
}
