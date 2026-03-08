"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import {
    getGraphNeighborhood,
    getGraphChain,
    getGraphAuthorities,
    getGraphStats,
    search as searchApi,
} from "@/lib/api";
import type { GraphNode, GraphEdge, GraphData, GraphStats } from "@/lib/types";
import {
    Loader2,
    Search,
    GitBranch,
    ExternalLink,
    BarChart3,
    Network,
} from "lucide-react";

// react-force-graph-2d uses canvas/DOM APIs — must load client-side only
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
    ssr: false,
    loading: () => (
        <div className="flex items-center justify-center h-full">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
    ),
});

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EDGE_COLORS: Record<string, string> = {
    cites: "#9CA3AF",         // gray
    overrules: "#EF4444",     // red
    affirms: "#22C55E",       // green
    distinguishes: "#F97316", // orange
};

const DEPTH_OPTIONS = [1, 2, 3];

// ---------------------------------------------------------------------------
// Graph Page
// ---------------------------------------------------------------------------

export default function GraphPage() {
    const router = useRouter();

    // Search state
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<{ id: string; title: string }[]>([]);
    const [searching, setSearching] = useState(false);
    const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Graph data state
    const [graphData, setGraphData] = useState<GraphData | null>(null);
    const [graphLoading, setGraphLoading] = useState(false);
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
    const [authorities, setAuthorities] = useState<GraphNode[]>([]);

    // Controls
    const [depth, setDepth] = useState(1);
    const [mode, setMode] = useState<"neighborhood" | "chain">("neighborhood");
    const [activeCaseId, setActiveCaseId] = useState<string | null>(null);

    // Stats
    const [stats, setStats] = useState<GraphStats | null>(null);

    // Load global stats on mount
    useEffect(() => {
        getGraphStats().then(setStats).catch(() => {});
    }, []);

    // Debounced search
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
                    })),
                );
            } catch {
                setSearchResults([]);
            } finally {
                setSearching(false);
            }
        }, 400);
    }

    const loadGraph = useCallback(
        async (caseId: string, d: number = depth, m: string = mode) => {
            setGraphLoading(true);
            setActiveCaseId(caseId);
            setSearchResults([]);
            try {
                const [data, auth] = await Promise.allSettled([
                    m === "chain"
                        ? getGraphChain(caseId, d)
                        : getGraphNeighborhood(caseId, d),
                    getGraphAuthorities(caseId),
                ]);
                if (data.status === "fulfilled") setGraphData(data.value);
                if (auth.status === "fulfilled") setAuthorities(auth.value);
            } catch {
                // ignore
            } finally {
                setGraphLoading(false);
            }
        },
        [depth, mode],
    );

    function handleSelectCase(caseId: string) {
        setSearchQuery("");
        setSearchResults([]);
        loadGraph(caseId);
    }

    function handleDepthChange(d: number) {
        setDepth(d);
        if (activeCaseId) loadGraph(activeCaseId, d, mode);
    }

    function handleModeChange(m: "neighborhood" | "chain") {
        setMode(m);
        if (activeCaseId) loadGraph(activeCaseId, depth, m);
    }

    // Prepare data for force-graph (it needs {id, ...} nodes and {source, target} links)
    const fgData = graphData
        ? {
              nodes: graphData.nodes.map((n) => ({
                  ...n,
                  val: Math.max(2, Math.log2((n.cited_by_count || 0) + 1) * 3),
              })),
              links: graphData.edges.map((e) => ({
                  source: e.from,
                  target: e.to,
                  type: e.type,
                  context: e.context,
              })),
          }
        : { nodes: [], links: [] };

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1 flex flex-col">
                {/* Top bar: search + controls */}
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
                                    <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-card border rounded-md shadow-lg max-h-48 overflow-y-auto">
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
                                                    {r.title}
                                                </button>
                                            ))
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Depth control */}
                            <div className="flex items-center gap-1.5">
                                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Depth:</span>
                                {DEPTH_OPTIONS.map((d) => (
                                    <Button
                                        key={d}
                                        variant={depth === d ? "default" : "outline"}
                                        size="sm"
                                        className="h-7 w-7 p-0 text-xs rounded-md"
                                        onClick={() => handleDepthChange(d)}
                                    >
                                        {d}
                                    </Button>
                                ))}
                            </div>

                            {/* Mode toggle */}
                            <div className="flex items-center gap-1.5">
                                <Button
                                    variant={mode === "neighborhood" ? "default" : "outline"}
                                    size="sm"
                                    className="h-7 text-xs rounded-md gap-1"
                                    onClick={() => handleModeChange("neighborhood")}
                                >
                                    <Network className="h-3 w-3" /> Network
                                </Button>
                                <Button
                                    variant={mode === "chain" ? "default" : "outline"}
                                    size="sm"
                                    className="h-7 text-xs rounded-md gap-1"
                                    onClick={() => handleModeChange("chain")}
                                >
                                    <GitBranch className="h-3 w-3" /> Chain
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Main content */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Graph canvas */}
                    <div className="flex-1 relative bg-background">
                        {graphLoading ? (
                            <div className="flex items-center justify-center h-full">
                                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                            </div>
                        ) : graphData && graphData.nodes.length > 0 ? (
                            <>
                                <ForceGraph2D
                                    graphData={fgData}
                                    nodeLabel={(node: Record<string, unknown>) =>
                                        (node.title as string) || (node.citation as string) || (node.id as string)
                                    }
                                    nodeColor={(node: Record<string, unknown>) =>
                                        node.id === activeCaseId
                                            ? "#B89B6A"
                                            : node.id === selectedNode?.id
                                              ? "#60A5FA"
                                              : "#6B7280"
                                    }
                                    linkColor={(link: Record<string, unknown>) =>
                                        EDGE_COLORS[(link.type as string) || "cites"] || "#9CA3AF"
                                    }
                                    linkDirectionalArrowLength={4}
                                    linkDirectionalArrowRelPos={0.9}
                                    onNodeClick={(node: Record<string, unknown>) => {
                                        const gNode = graphData.nodes.find(
                                            (n) => n.id === node.id,
                                        );
                                        setSelectedNode(gNode || null);
                                    }}
                                    onNodeRightClick={(node: Record<string, unknown>) => {
                                        router.push(`/case/${node.id}`);
                                    }}
                                    enableZoomInteraction={true}
                                    enablePanInteraction={true}
                                />

                                {/* Legend */}
                                <div className="absolute bottom-4 left-4 bg-card/90 border rounded-md px-3 py-2 text-[10px] space-y-1">
                                    {Object.entries(EDGE_COLORS).map(([type, color]) => (
                                        <div key={type} className="flex items-center gap-2">
                                            <span
                                                className="w-4 h-0.5 inline-block rounded"
                                                style={{ backgroundColor: color }}
                                            />
                                            <span className="capitalize text-muted-foreground">{type}</span>
                                        </div>
                                    ))}
                                    <div className="text-muted-foreground/50 mt-1 pt-1 border-t">
                                        Right-click node to view case
                                    </div>
                                </div>

                                {/* Node count */}
                                <div className="absolute top-4 left-4 text-[10px] text-muted-foreground bg-card/80 rounded px-2 py-1">
                                    {graphData.nodes.length} nodes &middot; {graphData.edges.length} edges
                                </div>
                            </>
                        ) : (
                            /* Empty state */
                            <div className="flex items-center justify-center h-full">
                                <div className="text-center max-w-sm">
                                    <GitBranch className="h-8 w-8 mx-auto text-muted-foreground/30 mb-4" />
                                    <h2 className="text-lg font-semibold font-[family-name:var(--font-lora)] mb-2">
                                        Citation Graph Explorer
                                    </h2>
                                    <p className="text-sm text-muted-foreground mb-4">
                                        Search for a case above to visualize its citation network.
                                    </p>
                                    {stats && (
                                        <div className="flex justify-center gap-4 text-xs text-muted-foreground">
                                            <div className="flex items-center gap-1">
                                                <BarChart3 className="h-3 w-3" />
                                                {stats.total_judgments.toLocaleString()} judgments
                                            </div>
                                            <div className="flex items-center gap-1">
                                                <GitBranch className="h-3 w-3" />
                                                {stats.total_edges.toLocaleString()} citations
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Detail panel */}
                    {selectedNode && (
                        <aside className="w-72 xl:w-80 border-l bg-card overflow-y-auto p-4 space-y-4">
                            <div>
                                <h3 className="text-sm font-semibold font-[family-name:var(--font-lora)] leading-snug">
                                    {selectedNode.title || "Untitled"}
                                </h3>
                                {selectedNode.citation && (
                                    <p className="text-xs text-muted-foreground mt-1">
                                        {selectedNode.citation}
                                    </p>
                                )}
                            </div>

                            <div className="flex flex-wrap gap-1.5">
                                {selectedNode.court && (
                                    <Badge variant="secondary" className="text-[10px]">
                                        {selectedNode.court}
                                    </Badge>
                                )}
                                {selectedNode.year && (
                                    <Badge variant="secondary" className="text-[10px]">
                                        {selectedNode.year}
                                    </Badge>
                                )}
                                <Badge variant="outline" className="text-[10px]">
                                    Cited by: {selectedNode.cited_by_count}
                                </Badge>
                            </div>

                            <Button
                                size="sm"
                                variant="outline"
                                className="w-full text-xs rounded-md gap-1.5"
                                onClick={() => router.push(`/case/${selectedNode.id}`)}
                            >
                                View Full Case <ExternalLink className="h-3 w-3" />
                            </Button>

                            <Button
                                size="sm"
                                variant="outline"
                                className="w-full text-xs rounded-md gap-1.5"
                                onClick={() => loadGraph(selectedNode.id)}
                            >
                                <Network className="h-3 w-3" /> Explore This Node
                            </Button>

                            {/* Authorities */}
                            {authorities.length > 0 && (
                                <div>
                                    <h4 className="text-[10px] uppercase tracking-wider font-medium text-muted-foreground mb-2">
                                        Top Authorities in Network
                                    </h4>
                                    <div className="space-y-1.5">
                                        {authorities.slice(0, 10).map((a) => (
                                            <div
                                                key={a.id}
                                                className="text-xs p-2 border rounded cursor-pointer hover:bg-muted/50 transition-colors"
                                                onClick={() => {
                                                    setSelectedNode(a);
                                                    loadGraph(a.id);
                                                }}
                                            >
                                                <span className="font-medium line-clamp-2">
                                                    {a.title || a.citation || "Untitled"}
                                                </span>
                                                <div className="text-[10px] text-muted-foreground mt-0.5">
                                                    {a.court} {a.year && `· ${a.year}`} · Cited {a.cited_by_count}x
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </aside>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
}
