"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import GraphDashboard from "@/components/graph/GraphDashboard";
import TimelineView from "@/components/graph/TimelineView";
import NetworkView from "@/components/graph/NetworkView";
import CaseDetailPanel from "@/components/graph/CaseDetailPanel";
import PathFinder from "@/components/graph/PathFinder";
import {
    getGraphNeighborhood,
    getGraphChain,
    getGraphStats,
    getGraphDashboard,
    search as searchApi,
} from "@/lib/api";
import type {
    GraphNode,
    GraphData,
    GraphStats,
    DashboardData,
    DashboardFilters,
    PathResult,
} from "@/lib/types";
import { EDGE_COLORS, LEGEND_TYPES } from "@/lib/graph-utils";
import {
    Loader2,
    Search,
    LayoutDashboard,
    Clock,
    Network,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEPTH_OPTIONS = [1, 2, 3];

type ViewMode = "dashboard" | "timeline" | "network";
type GraphMode = "neighborhood" | "chain" | "path";

// ---------------------------------------------------------------------------
// Graph Page
// ---------------------------------------------------------------------------

export default function GraphPage() {
    // View mode
    const [view, setView] = useState<ViewMode>("dashboard");

    // Search
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<
        Array<{ id: string; title: string; citation?: string }>
    >([]);
    const [searching, setSearching] = useState(false);
    const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Dashboard
    const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
    const [dashboardLoading, setDashboardLoading] = useState(true);
    const [filters, setFilters] = useState<DashboardFilters>({});

    // Graph data (for timeline and network views)
    const [graphData, setGraphData] = useState<GraphData | null>(null);
    const [graphLoading, setGraphLoading] = useState(false);
    const [graphError, setGraphError] = useState<string | null>(null);

    // Node selection
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
    const [activeCaseId, setActiveCaseId] = useState<string | null>(null);

    // Controls
    const [depth, setDepth] = useState(1);
    const [graphMode, setGraphMode] = useState<GraphMode>("neighborhood");

    // Stats
    const [stats, setStats] = useState<GraphStats | null>(null);

    // Path mode
    const [pathLoading, setPathLoading] = useState(false);

    // -----------------------------------------------------------------------
    // Effects
    // -----------------------------------------------------------------------

    // Load stats on mount
    useEffect(() => {
        getGraphStats()
            .then(setStats)
            .catch((err) => console.error("Failed to load graph stats:", err));
    }, []);

    // Load dashboard when filters change
    useEffect(() => {
        setDashboardLoading(true);
        getGraphDashboard(filters)
            .then(setDashboardData)
            .catch(() => setDashboardData(null))
            .finally(() => setDashboardLoading(false));
    }, [filters]);

    // Load graph data when activeCaseId, depth, or graphMode changes
    useEffect(() => {
        if (!activeCaseId || graphMode === "path") return;

        let cancelled = false;
        setGraphLoading(true);
        setGraphError(null);

        const loader =
            graphMode === "chain"
                ? getGraphChain(activeCaseId, depth)
                : getGraphNeighborhood(activeCaseId, depth);

        loader
            .then((data) => {
                if (!cancelled) setGraphData(data);
            })
            .catch((err) => {
                if (!cancelled) {
                    console.error("Failed to load graph data:", err);
                    setGraphError("Failed to load graph data. Please try again.");
                }
            })
            .finally(() => {
                if (!cancelled) setGraphLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [activeCaseId, depth, graphMode]);

    // -----------------------------------------------------------------------
    // Handlers
    // -----------------------------------------------------------------------

    function handleSearchInput(value: string) {
        setSearchQuery(value);
        if (searchTimerRef.current) clearTimeout(searchTimerRef.current);

        if (value.trim().length < 3) {
            setSearchResults([]);
            return;
        }

        searchTimerRef.current = setTimeout(async () => {
            setSearching(true);
            try {
                const res = await searchApi({ q: value, page_size: 5 });
                setSearchResults(
                    res.results.map((r) => ({
                        id: r.case_id,
                        title: r.title || r.citation || r.case_id,
                        citation: r.citation ?? undefined,
                    })),
                );
            } catch {
                setSearchResults([]);
            } finally {
                setSearching(false);
            }
        }, 400);
    }

    function handleSelectCase(caseId: string) {
        setSearchQuery("");
        setSearchResults([]);
        setActiveCaseId(caseId);
        setSelectedNode(null);
        if (view === "dashboard") {
            setView("timeline");
        }
    }

    function handleDepthChange(d: number) {
        setDepth(d);
    }

    function handleGraphModeChange(mode: GraphMode) {
        setGraphMode(mode);
        // When switching to path mode, clear graph data so PathFinder takes over
        if (mode === "path") {
            setGraphData(null);
            setGraphError(null);
        }
    }

    const handleNodeClick = useCallback((node: GraphNode) => {
        setSelectedNode(node);
    }, []);

    const handleNodeHover = useCallback((_node: GraphNode | null) => {
        // Tooltip handled internally by TimelineView
    }, []);

    function handleExploreFromNode(caseId: string) {
        setActiveCaseId(caseId);
        setSelectedNode(null);
        if (graphMode === "path") {
            setGraphMode("neighborhood");
        }
    }

    const handlePathFound = useCallback((result: PathResult) => {
        // Convert PathResult to GraphData by merging all paths
        const nodeMap = new Map<string, GraphNode>();
        const edgeSet = new Set<string>();
        const allEdges: GraphData["edges"] = [];

        for (const path of result.paths) {
            for (const node of path.nodes) {
                nodeMap.set(node.id, node);
            }
            for (const edge of path.edges) {
                const key = `${edge.from}-${edge.to}-${edge.type}`;
                if (!edgeSet.has(key)) {
                    edgeSet.add(key);
                    allEdges.push(edge);
                }
            }
        }

        setGraphData({
            nodes: Array.from(nodeMap.values()),
            edges: allEdges,
        });
        setGraphError(null);
        setView("network");
    }, []);

    function handleCommunitySelect(label: string | null) {
        setFilters(prev => ({ ...prev, communityLabel: label ?? undefined }));
    }

    function handleFilterChange(newFilters: Partial<DashboardFilters>) {
        setFilters(prev => ({ ...prev, ...newFilters }));
    }

    function handleViewChange(v: ViewMode) {
        setView(v);
        if (v === "dashboard") {
            // Clear graph state when returning to dashboard
            setSelectedNode(null);
        }
    }

    // -----------------------------------------------------------------------
    // Derived state
    // -----------------------------------------------------------------------

    const isGraphView = view === "timeline" || view === "network";
    const showSidePanel = isGraphView && selectedNode != null;
    const showGraphControls = isGraphView;
    const showEmptyGraphMessage = isGraphView && !activeCaseId && !graphLoading;

    // -----------------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------------

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 flex flex-col">
                {/* Top bar: search + controls + view toggle */}
                <div className="border-b bg-card/50">
                    <div className="mx-auto max-w-7xl px-4 py-3">
                        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                            {/* Search */}
                            <div className="relative flex-1 max-w-md">
                                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                                <Input
                                    placeholder="Search case to explore..."
                                    value={searchQuery}
                                    onChange={(e) => handleSearchInput(e.target.value)}
                                    className="h-9 pl-8 text-sm rounded-md"
                                />
                                {/* Dropdown results */}
                                {(searchResults.length > 0 || searching) && (
                                    <div className="absolute z-30 top-full left-0 right-0 mt-1 bg-card border rounded-md shadow-lg max-h-48 overflow-y-auto">
                                        {searching ? (
                                            <div className="flex items-center gap-2 p-3 text-xs text-muted-foreground">
                                                <Loader2 className="h-3 w-3 animate-spin" /> Searching...
                                            </div>
                                        ) : (
                                            searchResults.map((r) => (
                                                <button
                                                    key={r.id}
                                                    className="w-full text-left px-3 py-2 text-xs hover:bg-muted/50 transition-colors border-b last:border-b-0"
                                                    onClick={() => handleSelectCase(r.id)}
                                                >
                                                    <span className="block font-medium">{r.title}</span>
                                                    {r.citation && (
                                                        <span className="block text-muted-foreground text-[10px]">
                                                            {r.citation}
                                                        </span>
                                                    )}
                                                </button>
                                            ))
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Depth + mode controls (only in graph views) */}
                            {showGraphControls && (
                                <>
                                    {/* Depth control */}
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                                            Depth:
                                        </span>
                                        {DEPTH_OPTIONS.map((d) => (
                                            <Button
                                                key={d}
                                                variant="ghost"
                                                size="sm"
                                                className={`h-7 w-7 p-0 text-xs rounded-md ${
                                                    depth === d
                                                        ? "bg-stone-800 text-white hover:bg-stone-700 hover:text-white"
                                                        : "bg-white text-stone-600 border hover:bg-stone-50"
                                                }`}
                                                onClick={() => handleDepthChange(d)}
                                            >
                                                {d}
                                            </Button>
                                        ))}
                                    </div>

                                    {/* Mode toggle */}
                                    <div className="flex items-center gap-1.5">
                                        {(
                                            [
                                                ["neighborhood", "Neighborhood"],
                                                ["chain", "Chain"],
                                                ["path", "Path"],
                                            ] as const
                                        ).map(([mode, label]) => (
                                            <Button
                                                key={mode}
                                                variant="ghost"
                                                size="sm"
                                                className={`h-7 text-xs rounded-md ${
                                                    graphMode === mode
                                                        ? "bg-stone-800 text-white hover:bg-stone-700 hover:text-white"
                                                        : "bg-white text-stone-600 border hover:bg-stone-50"
                                                }`}
                                                onClick={() => handleGraphModeChange(mode)}
                                            >
                                                {label}
                                            </Button>
                                        ))}
                                    </div>
                                </>
                            )}

                            {/* View toggle (always visible) */}
                            <div className="flex items-center gap-1.5 sm:ml-auto">
                                {(
                                    [
                                        ["dashboard", "Dashboard", LayoutDashboard],
                                        ["timeline", "Timeline", Clock],
                                        ["network", "Network", Network],
                                    ] as const
                                ).map(([v, label, Icon]) => (
                                    <Button
                                        key={v}
                                        variant="ghost"
                                        size="sm"
                                        className={`h-7 text-xs rounded-md gap-1 ${
                                            view === v
                                                ? "bg-stone-800 text-white hover:bg-stone-700 hover:text-white"
                                                : "bg-white text-stone-600 border hover:bg-stone-50"
                                        }`}
                                        onClick={() => handleViewChange(v)}
                                    >
                                        <Icon className="h-3 w-3" /> {label}
                                    </Button>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Main content */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Primary content area */}
                    <div className="flex-1 relative bg-background overflow-hidden">
                        {/* Dashboard view */}
                        {view === "dashboard" && (
                            <div className="h-full overflow-y-auto p-6">
                                <div className="mx-auto max-w-7xl">
                                    <GraphDashboard
                                        data={dashboardData}
                                        loading={dashboardLoading}
                                        selectedCommunity={filters.communityLabel ?? null}
                                        onSelectCommunity={handleCommunitySelect}
                                        onSelectCase={handleSelectCase}
                                        stats={stats}
                                        onFilterChange={handleFilterChange}
                                        currentFilters={filters}
                                    />
                                </div>
                            </div>
                        )}

                        {/* Timeline / Network views */}
                        {isGraphView && (
                            <>
                                {/* Empty state: no case selected */}
                                {showEmptyGraphMessage && (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="text-center max-w-sm">
                                            <Search className="h-8 w-8 mx-auto text-muted-foreground/30 mb-4" />
                                            <p className="text-sm text-muted-foreground">
                                                Select a case to explore its citation graph.
                                            </p>
                                        </div>
                                    </div>
                                )}

                                {/* Loading spinner */}
                                {graphLoading && (
                                    <div className="flex items-center justify-center h-full">
                                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                                    </div>
                                )}

                                {/* Error state */}
                                {graphError && !graphLoading && (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="text-center max-w-sm">
                                            <p className="text-sm text-red-500 mb-2">{graphError}</p>
                                            {activeCaseId && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => {
                                                        setGraphError(null);
                                                        setGraphLoading(true);
                                                        // Trigger re-fetch by toggling a dep
                                                        setActiveCaseId((prev) => prev);
                                                    }}
                                                >
                                                    Retry
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* PathFinder (when in path mode) */}
                                {graphMode === "path" && activeCaseId && !graphLoading && (
                                    <div className="absolute top-4 left-4 z-20 w-80">
                                        <PathFinder
                                            onPathFound={handlePathFound}
                                            loading={pathLoading}
                                            setLoading={setPathLoading}
                                        />
                                    </div>
                                )}

                                {/* Graph content */}
                                {!graphLoading &&
                                    !graphError &&
                                    !showEmptyGraphMessage &&
                                    graphData &&
                                    graphData.nodes.length > 0 && (
                                        <>
                                            {view === "timeline" && (
                                                <TimelineView
                                                    nodes={graphData.nodes}
                                                    edges={graphData.edges}
                                                    queryCaseId={activeCaseId}
                                                    selectedNodeId={selectedNode?.id ?? null}
                                                    onNodeClick={handleNodeClick}
                                                    onNodeHover={handleNodeHover}
                                                />
                                            )}

                                            {view === "network" && (
                                                <NetworkView
                                                    nodes={graphData.nodes}
                                                    edges={graphData.edges}
                                                    queryCaseId={activeCaseId}
                                                    selectedNodeId={selectedNode?.id ?? null}
                                                    onNodeClick={handleNodeClick}
                                                />
                                            )}

                                            {/* Node count */}
                                            <div className="absolute top-4 right-4 text-[10px] text-muted-foreground bg-card/80 rounded px-2 py-1">
                                                {graphData.nodes.length} nodes &middot;{" "}
                                                {graphData.edges.length} edges
                                            </div>

                                            {/* Legend */}
                                            <div className="absolute bottom-4 left-4 bg-card/90 border rounded-md px-3 py-2 text-[10px] space-y-1">
                                                {LEGEND_TYPES.map((type) => (
                                                    <div key={type} className="flex items-center gap-2">
                                                        <span
                                                            className="w-4 h-0.5 inline-block rounded"
                                                            style={{
                                                                backgroundColor: EDGE_COLORS[type],
                                                            }}
                                                        />
                                                        <span className="capitalize text-muted-foreground">
                                                            {type.replace(/_/g, " ")}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>
                                        </>
                                    )}

                                {/* Path mode with no graph data yet — show PathFinder centered */}
                                {graphMode === "path" &&
                                    !activeCaseId &&
                                    !graphLoading &&
                                    !graphData && (
                                        <div className="flex items-center justify-center h-full">
                                            <div className="w-80">
                                                <PathFinder
                                                    onPathFound={handlePathFound}
                                                    loading={pathLoading}
                                                    setLoading={setPathLoading}
                                                />
                                            </div>
                                        </div>
                                    )}
                            </>
                        )}
                    </div>

                    {/* Side panel */}
                    {showSidePanel && selectedNode && (
                        <CaseDetailPanel
                            node={selectedNode}
                            onClose={() => setSelectedNode(null)}
                            onExplore={handleExploreFromNode}
                        />
                    )}
                </div>
            </div>
        </div>
    );
}
