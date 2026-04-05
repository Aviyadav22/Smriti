"use client";

import { useCallback, useMemo, useRef } from "react";
import dynamic from "next/dynamic";
import type { GraphNode, GraphEdge } from "@/lib/types";
import { getEdgeColor } from "@/lib/graph-utils";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
    ssr: false,
});

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface NetworkViewProps {
    nodes: GraphNode[];
    edges: GraphEdge[];
    queryCaseId: string | null;
    selectedNodeId: string | null;
    onNodeClick: (node: GraphNode) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COMMUNITY_HALO_COLORS_LIGHT = [
    "#FEF3C7",
    "#DBEAFE",
    "#D1FAE5",
    "#FCE7F3",
    "#E0E7FF",
    "#FEE2E2",
    "#ECFCCB",
    "#F3E8FF",
    "#CFFAFE",
    "#FFF7ED",
];

const COMMUNITY_HALO_COLORS_DARK = [
    "#78350F",
    "#1E3A5F",
    "#064E3B",
    "#831843",
    "#312E81",
    "#7F1D1D",
    "#365314",
    "#581C87",
    "#164E63",
    "#7C2D12",
];

function getMainNodeColor(
    node: GraphNode,
    queryCaseId: string | null,
): string {
    const isDark = typeof window !== "undefined" && document.documentElement.classList.contains("dark");
    if (queryCaseId && node.id === queryCaseId) return isDark ? "#D9B97A" : "#B89B6A"; // gold
    const pct = node.treatment_positive_pct;
    if (pct == null) return isDark ? "#9B9080" : "#6B7280";
    if (pct >= 0.8) return "#22C55E";
    if (pct >= 0.5) return "#F97316";
    return "#EF4444";
}

function nodeRadius(citedByCount: number): number {
    return Math.max(4, Math.min(20, 4 + Math.log2(Math.max(1, citedByCount)) * 2));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function NetworkView({
    nodes,
    edges,
    queryCaseId,
    selectedNodeId,
    onNodeClick,
}: NetworkViewProps) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fgRef = useRef<any>(null);

    // Build graph data for react-force-graph-2d
    const graphData = useMemo(() => {
        const graphNodes = nodes.map((n) => ({
            id: n.id,
            _node: n,
        }));
        const nodeIdSet = new Set(nodes.map((n) => n.id));
        const graphLinks = edges
            .filter((e) => nodeIdSet.has(e.from) && nodeIdSet.has(e.to))
            .map((e) => ({
                source: e.from,
                target: e.to,
                _type: e.type,
            }));
        return { nodes: graphNodes, links: graphLinks };
    }, [nodes, edges]);

    // Custom node rendering
    const nodeCanvasObject = useCallback(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (fgNode: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const gn = fgNode._node as GraphNode;
            const x = fgNode.x as number;
            const y = fgNode.y as number;
            const r = nodeRadius(gn.cited_by_count);

            // Community halo
            const isDarkMode = typeof window !== "undefined" && document.documentElement.classList.contains("dark");
            const haloColors = isDarkMode ? COMMUNITY_HALO_COLORS_DARK : COMMUNITY_HALO_COLORS_LIGHT;
            if (gn.community_id != null) {
                const haloColor =
                    haloColors[gn.community_id % haloColors.length];
                ctx.beginPath();
                ctx.arc(x, y, r + 4, 0, Math.PI * 2);
                ctx.fillStyle = haloColor;
                ctx.fill();
            }

            // Main node
            const color = getMainNodeColor(gn, queryCaseId);
            ctx.beginPath();
            ctx.arc(x, y, r, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();

            // Selection ring
            if (selectedNodeId && gn.id === selectedNodeId) {
                ctx.beginPath();
                ctx.arc(x, y, r + 2, 0, Math.PI * 2);
                ctx.strokeStyle = "#3B82F6";
                ctx.lineWidth = 2 / globalScale;
                ctx.stroke();
            }

            // Authority score inside large nodes
            if (r >= 12 && gn.pagerank_global != null) {
                const fontSize = Math.max(8, r * 0.6) / globalScale;
                ctx.font = `bold ${fontSize}px system-ui, sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillStyle = "#FFFFFF";
                ctx.fillText(gn.pagerank_global.toFixed(2), x, y);
            }
        },
        [queryCaseId, selectedNodeId],
    );

    // Hit area for pointer
    const nodePointerAreaPaint = useCallback(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (fgNode: any, color: string, ctx: CanvasRenderingContext2D) => {
            const gn = fgNode._node as GraphNode;
            const r = nodeRadius(gn.cited_by_count) + 4;
            ctx.beginPath();
            ctx.arc(fgNode.x as number, fgNode.y as number, r, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
        },
        [],
    );

    // Link color
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const linkColor = useCallback((link: any) => {
        return getEdgeColor(link._type);
    }, []);

    // Node label
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const nodeLabel = useCallback((fgNode: any) => {
        const gn = fgNode._node as GraphNode;
        const parts: string[] = [];
        if (gn.title) parts.push(gn.title);
        if (gn.citation) parts.push(gn.citation);
        if (gn.year) parts.push(`Year: ${gn.year}`);
        if (gn.pagerank_global != null) parts.push(`Authority: ${gn.pagerank_global.toFixed(4)}`);
        return parts.join("\n");
    }, []);

    // Node click handler
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const handleNodeClick = useCallback(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (fgNode: any) => {
            onNodeClick(fgNode._node as GraphNode);
        },
        [onNodeClick],
    );

    return (
        <div className="h-full w-full">
            <ForceGraph2D
                ref={fgRef}
                graphData={graphData}
                nodeCanvasObject={nodeCanvasObject}
                nodePointerAreaPaint={nodePointerAreaPaint}
                linkColor={linkColor}
                linkDirectionalArrowLength={4}
                linkDirectionalArrowRelPos={1}
                nodeLabel={nodeLabel}
                onNodeClick={handleNodeClick}
                cooldownTicks={100}
                enableNodeDrag={true}
            />
        </div>
    );
}
