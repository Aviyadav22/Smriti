"use client";

import { useCallback, useState } from "react";
import type { DashboardData, DashboardFilters, GraphNode } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface GraphDashboardProps {
    data: DashboardData | null;
    loading: boolean;
    selectedCommunity: string | null;
    onSelectCommunity: (label: string | null) => void;
    onSelectCase: (caseId: string) => void;
    stats: { total_judgments: number; total_edges: number } | null;
    // v2.1 additions
    onFilterChange: (filters: Partial<DashboardFilters>) => void;
    currentFilters: DashboardFilters;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BENCH_OPTIONS = ["Any", "single", "division", "full", "constitutional"] as const;
const DISPOSAL_OPTIONS = [
    "Any",
    "Allowed",
    "Dismissed",
    "Partly Allowed",
    "Remanded",
    "Disposed Of",
] as const;

// ---------------------------------------------------------------------------
// Inline sub-components
// ---------------------------------------------------------------------------

function TreatmentBadge({ pct }: { pct: number | null }) {
    if (pct == null) return null;
    const rounded = Math.round(pct * 100);
    let bg: string;
    let text: string;
    if (pct >= 0.8) {
        bg = "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300";
        text = `${rounded}% positive`;
    } else if (pct >= 0.5) {
        bg = "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300";
        text = `${rounded}% positive`;
    } else {
        bg = "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300";
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
        <span className="text-xs text-muted-foreground" title="Authority score (PageRank)">
            ★ {score.toFixed(4)}
        </span>
    );
}

function DisposalBadge({ disposal }: { disposal: string | null | undefined }) {
    if (!disposal) return null;
    const lower = disposal.toLowerCase();
    let cls = "bg-muted text-muted-foreground";
    if (lower.includes("allowed") && !lower.includes("partly")) {
        cls = "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300";
    } else if (lower.includes("dismissed")) {
        cls = "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300";
    } else if (lower.includes("partly")) {
        cls = "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300";
    }
    return (
        <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${cls}`}>
            {disposal}
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
            className="w-full rounded-lg border border-border bg-card p-3 text-left transition hover:border-foreground/30 hover:shadow-sm"
        >
            <div className="flex items-start gap-2">
                <p className="text-sm font-medium text-foreground line-clamp-2 flex-1">
                    {title}
                </p>
                <div className="flex items-center gap-1 flex-shrink-0">
                    {node.coram_size != null && node.coram_size > 0 && (
                        <span className="inline-block rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                            {node.coram_size}J
                        </span>
                    )}
                    {node.is_reportable && (
                        <span className="inline-block rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700">
                            R
                        </span>
                    )}
                </div>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2">
                {node.citation && (
                    <span className="text-xs text-muted-foreground">{node.citation}</span>
                )}
                {node.year && (
                    <span className="text-xs text-muted-foreground">({node.year})</span>
                )}
                <DisposalBadge disposal={node.case_type} />
            </div>
            {node.primary_legal_issue && (
                <p className="mt-1 text-xs text-muted-foreground italic line-clamp-1">
                    {node.primary_legal_issue}
                </p>
            )}
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
    onFilterChange,
    currentFilters,
}: GraphDashboardProps) {
    const [viewMode, setViewMode] = useState<"topic" | "statute">("topic");
    const [filtersExpanded, setFiltersExpanded] = useState(false);

    const handleCommunityClick = useCallback(
        (label: string | null) => {
            onSelectCommunity(label);
            // Clear subtopic when switching community
            if (currentFilters.subtopic) {
                onFilterChange({ subtopic: undefined });
            }
        },
        [onSelectCommunity, onFilterChange, currentFilters.subtopic],
    );

    const handleSubtopicClick = useCallback(
        (tag: string | null) => {
            onFilterChange({ subtopic: tag ?? undefined });
        },
        [onFilterChange],
    );

    const handleStatuteSectionClick = useCallback(
        (id: string | null) => {
            onFilterChange({ statuteSection: id ?? undefined });
        },
        [onFilterChange],
    );

    // Loading state
    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-foreground" />
            </div>
        );
    }

    if (!data) {
        return (
            <div className="flex h-64 items-center justify-center text-muted-foreground">
                No dashboard data available.
            </div>
        );
    }

    // Subtopics for the currently selected community
    const subtopicsForCommunity = selectedCommunity
        ? data.subtopics.filter((s) => s.category === selectedCommunity)
        : [];

    // Data comes pre-filtered from the API when a community is selected
    const mostCited = data.most_cited;
    const rising = data.rising;
    const negative = data.recently_negative;

    return (
        <div className="space-y-4">
            {/* View mode toggle: By Topic / By Statute */}
            <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    Browse:
                </span>
                {(["topic", "statute"] as const).map((mode) => (
                    <button
                        key={mode}
                        type="button"
                        onClick={() => {
                            setViewMode(mode);
                            // Clear the other mode's filter
                            if (mode === "topic") {
                                onFilterChange({ statuteSection: undefined });
                            } else {
                                onSelectCommunity(null);
                                onFilterChange({ subtopic: undefined });
                            }
                        }}
                        className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                            viewMode === mode
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted text-muted-foreground hover:bg-accent"
                        }`}
                    >
                        {mode === "topic" ? "By Topic" : "By Statute"}
                    </button>
                ))}
            </div>

            {/* Topic pills (communities) */}
            {viewMode === "topic" && (
                <div className="space-y-2">
                    <div className="flex flex-wrap gap-2">
                        <button
                            type="button"
                            onClick={() => handleCommunityClick(null)}
                            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                                selectedCommunity == null
                                    ? "bg-primary text-primary-foreground"
                                    : "bg-muted text-muted-foreground hover:bg-accent"
                            }`}
                        >
                            All Topics
                        </button>
                        {data.communities.slice(0, 15).map((c) => (
                            <button
                                key={c.community_label}
                                type="button"
                                onClick={() => handleCommunityClick(c.community_label)}
                                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                                    selectedCommunity === c.community_label
                                        ? "bg-primary text-primary-foreground"
                                        : "bg-muted text-muted-foreground hover:bg-accent"
                                }`}
                            >
                                {c.community_label} ({c.count})
                            </button>
                        ))}
                    </div>

                    {/* Subtopic row (only when a community is selected) */}
                    {selectedCommunity && subtopicsForCommunity.length > 0 && (
                        <div className="ml-4 flex flex-wrap gap-1.5">
                            {currentFilters.subtopic && (
                                <button
                                    type="button"
                                    onClick={() => handleSubtopicClick(null)}
                                    className="rounded-full border border-border px-2 py-0.5 text-[11px] font-medium text-muted-foreground transition hover:bg-accent"
                                >
                                    Clear subtopic
                                </button>
                            )}
                            {subtopicsForCommunity.map((s) => (
                                <button
                                    key={s.tag}
                                    type="button"
                                    onClick={() => handleSubtopicClick(s.tag)}
                                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium transition ${
                                        currentFilters.subtopic === s.tag
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-muted text-muted-foreground hover:bg-accent"
                                    }`}
                                >
                                    {s.subtopic} ({s.count})
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Statute section pills */}
            {viewMode === "statute" && (
                <div className="flex flex-wrap gap-2">
                    <button
                        type="button"
                        onClick={() => handleStatuteSectionClick(null)}
                        className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                            !currentFilters.statuteSection
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted text-muted-foreground hover:bg-accent"
                        }`}
                    >
                        All Statutes
                    </button>
                    {data.statute_sections.slice(0, 20).map((s) => (
                        <button
                            key={s.id}
                            type="button"
                            onClick={() => handleStatuteSectionClick(s.id)}
                            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                                currentFilters.statuteSection === s.id
                                    ? "bg-primary text-primary-foreground"
                                    : "bg-muted text-muted-foreground hover:bg-accent"
                            }`}
                        >
                            {s.section} {s.act} ({s.count})
                        </button>
                    ))}
                </div>
            )}

            {/* Collapsible filter bar */}
            <div>
                <button
                    type="button"
                    onClick={() => setFiltersExpanded((p) => !p)}
                    className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground transition"
                >
                    <span className={`inline-block transition-transform ${filtersExpanded ? "rotate-90" : ""}`}>
                        &#x25B6;
                    </span>
                    Filters
                </button>

                {filtersExpanded && (
                    <div className="mt-2 flex flex-wrap items-center gap-4 rounded-lg border border-border bg-muted px-4 py-3">
                        {/* Bench */}
                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            Bench:
                            <select
                                value={currentFilters.benchType ?? "Any"}
                                onChange={(e) =>
                                    onFilterChange({
                                        benchType:
                                            e.target.value === "Any"
                                                ? undefined
                                                : e.target.value,
                                    })
                                }
                                className="rounded border border-border bg-card px-2 py-1 text-xs text-foreground"
                            >
                                {BENCH_OPTIONS.map((o) => (
                                    <option key={o} value={o}>
                                        {o === "Any" ? "Any" : o.charAt(0).toUpperCase() + o.slice(1)}
                                    </option>
                                ))}
                            </select>
                        </label>

                        {/* Disposal */}
                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            Disposal:
                            <select
                                value={currentFilters.disposalNature ?? "Any"}
                                onChange={(e) =>
                                    onFilterChange({
                                        disposalNature:
                                            e.target.value === "Any"
                                                ? undefined
                                                : e.target.value,
                                    })
                                }
                                className="rounded border border-border bg-card px-2 py-1 text-xs text-foreground"
                            >
                                {DISPOSAL_OPTIONS.map((o) => (
                                    <option key={o} value={o}>
                                        {o}
                                    </option>
                                ))}
                            </select>
                        </label>

                        {/* Year range */}
                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            Year:
                            <input
                                type="number"
                                placeholder="From"
                                min={1947}
                                max={2026}
                                value={currentFilters.yearFrom ?? ""}
                                onChange={(e) =>
                                    onFilterChange({
                                        yearFrom: e.target.value
                                            ? Number(e.target.value)
                                            : undefined,
                                    })
                                }
                                className="w-16 rounded border border-border bg-card px-2 py-1 text-xs text-foreground [&::-webkit-inner-spin-button]:appearance-none"
                            />
                            <span className="text-muted-foreground">to</span>
                            <input
                                type="number"
                                placeholder="To"
                                min={1947}
                                max={2026}
                                value={currentFilters.yearTo ?? ""}
                                onChange={(e) =>
                                    onFilterChange({
                                        yearTo: e.target.value
                                            ? Number(e.target.value)
                                            : undefined,
                                    })
                                }
                                className="w-16 rounded border border-border bg-card px-2 py-1 text-xs text-foreground [&::-webkit-inner-spin-button]:appearance-none"
                            />
                        </label>

                        {/* Reportable only */}
                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
                            <input
                                type="checkbox"
                                checked={currentFilters.isReportable ?? false}
                                onChange={(e) =>
                                    onFilterChange({
                                        isReportable: e.target.checked || undefined,
                                    })
                                }
                                className="rounded border-border"
                            />
                            Reportable only
                        </label>
                    </div>
                )}
            </div>

            {/* Three-column dashboard */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                {/* Most Cited Authorities */}
                <div>
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        Most Cited Authorities
                    </h3>
                    <div className="space-y-2">
                        {mostCited.length === 0 && (
                            <p className="text-xs text-muted-foreground">No cases found.</p>
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
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        Rising Authorities
                    </h3>
                    <div className="space-y-2">
                        {rising.length === 0 && (
                            <p className="text-xs text-muted-foreground">No cases found.</p>
                        )}
                        {rising.map((node) => (
                            <CaseCard
                                key={node.id}
                                node={node}
                                onClick={onSelectCase}
                                extra={
                                    node.recent_citation_ratio != null ? (
                                        <span className="text-xs text-emerald-600 dark:text-emerald-400">
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
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        Recently Overruled / Distinguished
                    </h3>
                    <div className="space-y-2">
                        {negative.length === 0 && (
                            <p className="text-xs text-muted-foreground">No cases found.</p>
                        )}
                        {negative.map((item) => (
                            <CaseCard
                                key={item.case.id}
                                node={item.case}
                                onClick={onSelectCase}
                                extra={
                                    <span className="text-xs text-red-600 dark:text-red-400">
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
                <div className="flex items-center gap-6 border-t border-border pt-4 text-xs text-muted-foreground">
                    <span>{stats.total_judgments.toLocaleString()} judgments</span>
                    <span>{stats.total_edges.toLocaleString()} citation links</span>
                </div>
            )}
        </div>
    );
}
