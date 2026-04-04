"use client";

import { useCallback } from "react";
import type { DashboardData, GraphNode } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface GraphDashboardProps {
    data: DashboardData | null;
    loading: boolean;
    selectedCommunity: number | null;
    onSelectCommunity: (id: number | null) => void;
    onSelectCase: (caseId: string) => void;
    stats: { total_judgments: number; total_edges: number } | null;
}

// ---------------------------------------------------------------------------
// Inline sub-components
// ---------------------------------------------------------------------------

function TreatmentBadge({ pct }: { pct: number | null }) {
    if (pct == null) return null;
    const rounded = Math.round(pct * 100);
    let bg: string;
    let text: string;
    if (pct >= 0.8) {
        bg = "bg-green-100 text-green-800";
        text = `${rounded}% positive`;
    } else if (pct >= 0.5) {
        bg = "bg-amber-100 text-amber-800";
        text = `${rounded}% positive`;
    } else {
        bg = "bg-red-100 text-red-800";
        text = `${rounded}% positive`;
    }
    return (
        <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${bg}`}>
            {text}
        </span>
    );
}

function AuthorityScore({ score }: { score: number | null }) {
    if (score == null) return null;
    return (
        <span className="text-xs text-stone-500" title="Authority score (PageRank)">
            ★ {score.toFixed(4)}
        </span>
    );
}

function CaseCard({
    node,
    onClick,
    extra,
}: {
    node: GraphNode;
    onClick: (id: string) => void;
    extra?: React.ReactNode;
}) {
    const title = node.title
        ? node.title.length > 80
            ? node.title.slice(0, 77) + "..."
            : node.title
        : "Untitled";

    return (
        <button
            type="button"
            onClick={() => onClick(node.id)}
            className="w-full rounded-lg border border-stone-200 bg-white p-3 text-left transition hover:border-stone-400 hover:shadow-sm"
        >
            <p className="text-sm font-medium text-stone-900 line-clamp-2">{title}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
                {node.citation && (
                    <span className="text-xs text-stone-500">{node.citation}</span>
                )}
                {node.year && (
                    <span className="text-xs text-stone-400">({node.year})</span>
                )}
            </div>
            <div className="mt-1.5 flex items-center gap-2">
                <AuthorityScore score={node.pagerank_global} />
                <TreatmentBadge pct={node.treatment_positive_pct} />
            </div>
            {extra && <div className="mt-1.5">{extra}</div>}
        </button>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function GraphDashboard({
    data,
    loading,
    selectedCommunity,
    onSelectCommunity,
    onSelectCase,
    stats,
}: GraphDashboardProps) {
    const handleCommunityClick = useCallback(
        (id: number | null) => {
            onSelectCommunity(id);
        },
        [onSelectCommunity],
    );

    // Loading state
    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-stone-300 border-t-stone-800" />
            </div>
        );
    }

    if (!data) {
        return (
            <div className="flex h-64 items-center justify-center text-stone-400">
                No dashboard data available.
            </div>
        );
    }

    // Filter nodes by community if one is selected
    const filterByCommunity = (nodes: GraphNode[]) =>
        selectedCommunity == null
            ? nodes
            : nodes.filter((n) => n.community_id === selectedCommunity);

    const mostCited = filterByCommunity(data.most_cited);
    const rising = filterByCommunity(data.rising);
    const negative =
        selectedCommunity == null
            ? data.recently_negative
            : data.recently_negative.filter(
                  (r) => r.case.community_id === selectedCommunity,
              );

    return (
        <div className="space-y-6">
            {/* Topic filter pills */}
            <div className="flex flex-wrap gap-2">
                <button
                    type="button"
                    onClick={() => handleCommunityClick(null)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                        selectedCommunity == null
                            ? "bg-stone-800 text-white"
                            : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                    }`}
                >
                    All Topics
                </button>
                {data.communities.map((c) => (
                    <button
                        key={c.id}
                        type="button"
                        onClick={() => handleCommunityClick(c.id)}
                        className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                            selectedCommunity === c.id
                                ? "bg-stone-800 text-white"
                                : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                        }`}
                    >
                        {c.label} ({c.case_count})
                    </button>
                ))}
            </div>

            {/* Three-column dashboard */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                {/* Most Cited Authorities */}
                <div>
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">
                        Most Cited Authorities
                    </h3>
                    <div className="space-y-2">
                        {mostCited.length === 0 && (
                            <p className="text-xs text-stone-400">No cases found.</p>
                        )}
                        {mostCited.map((node) => (
                            <CaseCard
                                key={node.id}
                                node={node}
                                onClick={onSelectCase}
                            />
                        ))}
                    </div>
                </div>

                {/* Rising Authorities */}
                <div>
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">
                        Rising Authorities
                    </h3>
                    <div className="space-y-2">
                        {rising.length === 0 && (
                            <p className="text-xs text-stone-400">No cases found.</p>
                        )}
                        {rising.map((node) => (
                            <CaseCard
                                key={node.id}
                                node={node}
                                onClick={onSelectCase}
                                extra={
                                    node.recent_citation_ratio != null ? (
                                        <span className="text-xs text-emerald-600">
                                            ↑{" "}
                                            {Math.round(
                                                node.recent_citation_ratio * 100,
                                            )}
                                            % citations from recent cases
                                        </span>
                                    ) : null
                                }
                            />
                        ))}
                    </div>
                </div>

                {/* Recently Overruled / Distinguished */}
                <div>
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-stone-500">
                        Recently Overruled / Distinguished
                    </h3>
                    <div className="space-y-2">
                        {negative.length === 0 && (
                            <p className="text-xs text-stone-400">No cases found.</p>
                        )}
                        {negative.map((item) => (
                            <CaseCard
                                key={item.case.id}
                                node={item.case}
                                onClick={onSelectCase}
                                extra={
                                    <span className="text-xs text-red-600">
                                        {item.negative_treatment} by{" "}
                                        {item.by_case_title ?? "Unknown"}{" "}
                                        {item.by_case_year
                                            ? `(${item.by_case_year})`
                                            : ""}
                                    </span>
                                }
                            />
                        ))}
                    </div>
                </div>
            </div>

            {/* Stats footer */}
            {stats && (
                <div className="flex items-center gap-6 border-t border-stone-200 pt-4 text-xs text-stone-400">
                    <span>{stats.total_judgments.toLocaleString()} judgments</span>
                    <span>{stats.total_edges.toLocaleString()} citation links</span>
                </div>
            )}
        </div>
    );
}
