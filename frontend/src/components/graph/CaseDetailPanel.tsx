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
    followed: "bg-green-100 text-green-800",
    affirmed: "bg-green-100 text-green-800",
    applied: "bg-green-100 text-green-800",
    explained: "bg-blue-100 text-blue-800",
    distinguished: "bg-amber-100 text-amber-800",
    doubted: "bg-amber-100 text-amber-800",
    overruled: "bg-red-100 text-red-800",
    not_followed: "bg-red-100 text-red-800",
    per_incuriam: "bg-red-100 text-red-800",
    cites: "bg-stone-100 text-stone-600",
};

function getBadgeStyle(type: string): string {
    return TREATMENT_BADGE_STYLES[type] ?? "bg-stone-100 text-stone-600";
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

    // Treatment bar color
    const pct = node.treatment_positive_pct;
    let barColor = "bg-stone-300";
    if (pct != null) {
        if (pct >= 0.8) barColor = "bg-green-500";
        else if (pct >= 0.5) barColor = "bg-amber-500";
        else barColor = "bg-red-500";
    }

    return (
        <div className="w-80 flex-shrink-0 border-l border-stone-200 bg-white overflow-y-auto">
            {/* Header */}
            <div className="sticky top-0 z-10 flex items-start justify-between border-b border-stone-100 bg-white p-4">
                <div className="min-w-0 flex-1 pr-2">
                    <h2 className="text-sm font-semibold text-stone-900 line-clamp-3">
                        {node.title ?? "Untitled"}
                    </h2>
                    {node.citation && (
                        <p className="mt-0.5 text-xs text-stone-500">
                            {node.citation}
                        </p>
                    )}
                </div>
                <button
                    type="button"
                    onClick={onClose}
                    className="flex-shrink-0 rounded p-1 text-stone-400 transition hover:bg-stone-100 hover:text-stone-600"
                    aria-label="Close panel"
                >
                    &#x2715;
                </button>
            </div>

            <div className="space-y-5 p-4">
                {/* Treatment summary bar */}
                {pct != null && (
                    <div>
                        <p className="mb-1 text-xs font-medium text-stone-500">
                            Treatment
                        </p>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-stone-100">
                            <div
                                className={`h-full rounded-full ${barColor}`}
                                style={{ width: `${Math.round(pct * 100)}%` }}
                            />
                        </div>
                        <p className="mt-1 text-xs text-stone-500">
                            {Math.round(pct * 100)}% positive
                            {treatment ? ` — ${treatment.verdict}` : ""}
                        </p>
                    </div>
                )}

                {/* Authority scores */}
                <div>
                    <p className="mb-1 text-xs font-medium text-stone-500">
                        Authority Scores
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                        <div className="rounded-md bg-stone-50 p-2">
                            <p className="text-xs text-stone-400">Overall</p>
                            <p className="text-sm font-semibold text-stone-800">
                                {node.pagerank_global?.toFixed(4) ?? "N/A"}
                            </p>
                        </div>
                        <div className="rounded-md bg-stone-50 p-2">
                            <p className="text-xs text-stone-400">Community</p>
                            <p className="text-sm font-semibold text-stone-800">
                                {node.pagerank_community?.toFixed(4) ?? "N/A"}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Metadata */}
                <div>
                    <p className="mb-1 text-xs font-medium text-stone-500">
                        Metadata
                    </p>
                    <dl className="space-y-1 text-xs">
                        {node.bench_type && (
                            <div className="flex justify-between">
                                <dt className="text-stone-400">Bench</dt>
                                <dd className="text-stone-700">{node.bench_type}</dd>
                            </div>
                        )}
                        {node.year && (
                            <div className="flex justify-between">
                                <dt className="text-stone-400">Year</dt>
                                <dd className="text-stone-700">{node.year}</dd>
                            </div>
                        )}
                        {node.case_type && (
                            <div className="flex justify-between">
                                <dt className="text-stone-400">Case Type</dt>
                                <dd className="text-stone-700">{node.case_type}</dd>
                            </div>
                        )}
                        {node.court && (
                            <div className="flex justify-between">
                                <dt className="text-stone-400">Court</dt>
                                <dd className="text-stone-700">{node.court}</dd>
                            </div>
                        )}
                        <div className="flex justify-between">
                            <dt className="text-stone-400">Cited by</dt>
                            <dd className="text-stone-700">
                                {node.cited_by_count} cases
                            </dd>
                        </div>
                        {node.community_label && (
                            <div className="flex justify-between">
                                <dt className="text-stone-400">Topic</dt>
                                <dd className="text-stone-700 text-right max-w-[140px] truncate">
                                    {node.community_label}
                                </dd>
                            </div>
                        )}
                    </dl>
                </div>

                {/* Ratio excerpt */}
                {node.ratio && (
                    <div>
                        <p className="mb-1 text-xs font-medium text-stone-500">
                            Ratio Decidendi
                        </p>
                        <p className="text-xs leading-relaxed text-stone-600 line-clamp-6">
                            {node.ratio}
                        </p>
                    </div>
                )}

                {/* Treatment breakdown */}
                <div>
                    <p className="mb-1 text-xs font-medium text-stone-500">
                        Treatment Breakdown
                    </p>
                    {treatmentLoading && (
                        <div className="flex items-center gap-2 text-xs text-stone-400">
                            <div className="h-3 w-3 animate-spin rounded-full border border-stone-300 border-t-stone-600" />
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
                                <span className="text-xs text-stone-400">
                                    No treatment data.
                                </span>
                            )}
                        </div>
                    )}
                    {!treatmentLoading && !treatment && (
                        <span className="text-xs text-stone-400">
                            Treatment data unavailable.
                        </span>
                    )}
                </div>

                {/* Action buttons */}
                <div className="flex gap-2 pt-2">
                    <Link
                        href={`/cases/${node.id}`}
                        className="flex-1 rounded-md bg-stone-800 px-3 py-2 text-center text-xs font-medium text-white transition hover:bg-stone-700"
                    >
                        View Full Case
                    </Link>
                    <button
                        type="button"
                        onClick={() => onExplore(node.id)}
                        className="flex-1 rounded-md border border-stone-300 px-3 py-2 text-xs font-medium text-stone-700 transition hover:bg-stone-50"
                    >
                        Explore from here
                    </button>
                </div>
            </div>
        </div>
    );
}
