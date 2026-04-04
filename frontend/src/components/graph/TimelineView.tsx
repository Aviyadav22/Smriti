"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { GraphNode, GraphEdge } from "@/lib/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TimelineViewProps {
    nodes: GraphNode[];
    edges: GraphEdge[];
    queryCaseId: string | null;
    selectedNodeId: string | null;
    onNodeClick: (node: GraphNode) => void;
    onNodeHover: (node: GraphNode | null) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function nodeRadius(citedByCount: number): number {
    return Math.max(4, Math.min(20, 4 + Math.log2(Math.max(1, citedByCount)) * 2));
}

function nodeColor(
    node: GraphNode,
    queryCaseId: string | null,
    negativeEdgeTargets: Set<string>,
    distinguishedTargets: Set<string>,
    positiveTargets: Set<string>,
): string {
    if (queryCaseId && node.id === queryCaseId) return "#B89B6A"; // gold
    if (negativeEdgeTargets.has(node.id)) return "#EF4444"; // red
    if (distinguishedTargets.has(node.id)) return "#F97316"; // orange
    if (positiveTargets.has(node.id)) return "#22C55E"; // green
    return "#6B7280"; // gray
}

interface LayoutNode {
    node: GraphNode;
    x: number;
    y: number;
    r: number;
    color: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TimelineView({
    nodes,
    edges,
    queryCaseId,
    selectedNodeId,
    onNodeClick,
    onNodeHover,
}: TimelineViewProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [size, setSize] = useState({ w: 800, h: 500 });
    const [tooltip, setTooltip] = useState<{
        node: GraphNode;
        x: number;
        y: number;
    } | null>(null);
    const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
    const layoutRef = useRef<LayoutNode[]>([]);

    // Classify edges
    const negativeTypes = new Set(["overrules", "not_followed", "per_incuriam"]);
    const distinguishedTypes = new Set(["distinguishes", "doubted"]);
    const positiveTypes = new Set(["affirms", "followed", "applied"]);

    const negativeTargets = new Set(
        edges.filter((e) => negativeTypes.has(e.type)).map((e) => e.to),
    );
    const distinguishedTargets = new Set(
        edges.filter((e) => distinguishedTypes.has(e.type)).map((e) => e.to),
    );
    const positiveTargets = new Set(
        edges.filter((e) => positiveTypes.has(e.type)).map((e) => e.to),
    );

    // Resize observer
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;
        const ro = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const { width, height } = entry.contentRect;
                if (width > 0 && height > 0) {
                    setSize({ w: Math.round(width), h: Math.round(height) });
                }
            }
        });
        ro.observe(container);
        return () => ro.disconnect();
    }, []);

    // Compute layout
    const computeLayout = useCallback(() => {
        if (nodes.length === 0) return [];

        const padding = { top: 40, right: 30, bottom: 50, left: 70 };
        const plotW = size.w - padding.left - padding.right;
        const plotH = size.h - padding.top - padding.bottom;

        const years = nodes.map((n) => n.year ?? 2000);
        const minYear = Math.min(...years);
        const maxYear = Math.max(...years);
        const yearSpan = maxYear - minYear || 1;

        const scores = nodes.map(
            (n) => n.pagerank_global ?? n.cited_by_count ?? 0,
        );
        const maxScore = Math.max(...scores, 0.001);

        const result: LayoutNode[] = nodes.map((n) => {
            const year = n.year ?? 2000;
            const score = n.pagerank_global ?? n.cited_by_count ?? 0;
            const x =
                padding.left + ((year - minYear) / yearSpan) * plotW;
            const y =
                padding.top + plotH - (score / maxScore) * plotH;
            const r = nodeRadius(n.cited_by_count);
            const color = nodeColor(
                n,
                queryCaseId,
                negativeTargets,
                distinguishedTargets,
                positiveTargets,
            );
            return { node: n, x, y, r, color };
        });
        return result;
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [nodes, edges, queryCaseId, size]);

    // Draw
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = size.w * dpr;
        canvas.height = size.h * dpr;
        canvas.style.width = `${size.w}px`;
        canvas.style.height = `${size.h}px`;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        // Clear
        ctx.clearRect(0, 0, size.w, size.h);

        const layout = computeLayout();
        layoutRef.current = layout;
        if (layout.length === 0) return;

        // Apply transform
        ctx.save();
        ctx.translate(transform.x, transform.y);
        ctx.scale(transform.k, transform.k);

        // Build node lookup for edges
        const nodeMap = new Map<string, LayoutNode>();
        for (const ln of layout) nodeMap.set(ln.node.id, ln);

        // Draw axes
        const padding = { top: 40, right: 30, bottom: 50, left: 70 };
        const plotW = size.w - padding.left - padding.right;
        const plotH = size.h - padding.top - padding.bottom;

        const years = nodes.map((n) => n.year ?? 2000);
        const minYear = Math.min(...years);
        const maxYear = Math.max(...years);

        ctx.strokeStyle = "#D6D3D1"; // stone-300
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding.left, padding.top);
        ctx.lineTo(padding.left, padding.top + plotH);
        ctx.lineTo(padding.left + plotW, padding.top + plotH);
        ctx.stroke();

        // Year ticks
        ctx.fillStyle = "#78716C"; // stone-500
        ctx.font = "11px system-ui, sans-serif";
        ctx.textAlign = "center";
        const yearSpan = maxYear - minYear || 1;
        const tickCount = Math.min(10, yearSpan);
        for (let i = 0; i <= tickCount; i++) {
            const yr = Math.round(minYear + (i / tickCount) * yearSpan);
            const x = padding.left + (i / tickCount) * plotW;
            ctx.fillText(String(yr), x, padding.top + plotH + 20);
            ctx.beginPath();
            ctx.moveTo(x, padding.top + plotH);
            ctx.lineTo(x, padding.top + plotH + 5);
            ctx.stroke();
        }

        // Y-axis label
        ctx.save();
        ctx.translate(16, padding.top + plotH / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.textAlign = "center";
        ctx.fillStyle = "#78716C";
        ctx.font = "12px system-ui, sans-serif";
        ctx.fillText("Authority Score", 0, 0);
        ctx.restore();

        // Draw edges
        for (const edge of edges) {
            const fromLn = nodeMap.get(edge.from);
            const toLn = nodeMap.get(edge.to);
            if (!fromLn || !toLn) continue;

            const isNeg = negativeTypes.has(edge.type);
            ctx.strokeStyle = isNeg ? "#EF4444" : "#D6D3D1";
            ctx.lineWidth = isNeg ? 1.5 : 0.5;
            ctx.globalAlpha = 0.4;

            if (isNeg) {
                ctx.setLineDash([4, 3]);
            } else {
                ctx.setLineDash([]);
            }

            ctx.beginPath();
            ctx.moveTo(fromLn.x, fromLn.y);
            const cpx = (fromLn.x + toLn.x) / 2;
            const cpy = Math.min(fromLn.y, toLn.y) - 30;
            ctx.quadraticCurveTo(cpx, cpy, toLn.x, toLn.y);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1;
        }

        // Draw nodes
        for (const ln of layout) {
            // Selection ring
            if (selectedNodeId && ln.node.id === selectedNodeId) {
                ctx.beginPath();
                ctx.arc(ln.x, ln.y, ln.r + 4, 0, Math.PI * 2);
                ctx.strokeStyle = "#3B82F6"; // blue
                ctx.lineWidth = 2.5;
                ctx.stroke();
            }
            // Query case border
            if (queryCaseId && ln.node.id === queryCaseId) {
                ctx.beginPath();
                ctx.arc(ln.x, ln.y, ln.r + 3, 0, Math.PI * 2);
                ctx.strokeStyle = "#B89B6A"; // gold
                ctx.lineWidth = 2;
                ctx.stroke();
            }

            // Main circle
            ctx.beginPath();
            ctx.arc(ln.x, ln.y, ln.r, 0, Math.PI * 2);
            ctx.fillStyle = ln.color;
            ctx.fill();

            // Authority score inside large nodes
            if (ln.r >= 12 && ln.node.pagerank_global != null) {
                ctx.fillStyle = "#FFFFFF";
                ctx.font = `bold ${Math.max(8, ln.r * 0.7)}px system-ui, sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                const score = ln.node.pagerank_global;
                ctx.fillText(score.toFixed(2), ln.x, ln.y);
            }
        }

        ctx.restore();
    }, [nodes, edges, queryCaseId, selectedNodeId, size, transform, computeLayout]);

    // Hit test
    const hitTest = useCallback(
        (clientX: number, clientY: number): LayoutNode | null => {
            const canvas = canvasRef.current;
            if (!canvas) return null;
            const rect = canvas.getBoundingClientRect();
            const mx = (clientX - rect.left - transform.x) / transform.k;
            const my = (clientY - rect.top - transform.y) / transform.k;

            for (let i = layoutRef.current.length - 1; i >= 0; i--) {
                const ln = layoutRef.current[i];
                const dx = mx - ln.x;
                const dy = my - ln.y;
                if (dx * dx + dy * dy <= (ln.r + 3) * (ln.r + 3)) {
                    return ln;
                }
            }
            return null;
        },
        [transform],
    );

    const handleMouseMove = useCallback(
        (e: React.MouseEvent) => {
            const hit = hitTest(e.clientX, e.clientY);
            if (hit) {
                setTooltip({ node: hit.node, x: e.clientX, y: e.clientY });
                onNodeHover(hit.node);
            } else {
                setTooltip(null);
                onNodeHover(null);
            }
        },
        [hitTest, onNodeHover],
    );

    const handleClick = useCallback(
        (e: React.MouseEvent) => {
            const hit = hitTest(e.clientX, e.clientY);
            if (hit) onNodeClick(hit.node);
        },
        [hitTest, onNodeClick],
    );

    const handleWheel = useCallback((e: React.WheelEvent) => {
        e.preventDefault();
        const scaleFactor = e.deltaY > 0 ? 0.9 : 1.1;
        setTransform((prev) => {
            const newK = Math.max(0.2, Math.min(5, prev.k * scaleFactor));
            return { ...prev, k: newK };
        });
    }, []);

    return (
        <div ref={containerRef} className="relative h-full w-full min-h-[400px]">
            <canvas
                ref={canvasRef}
                className="cursor-crosshair"
                onMouseMove={handleMouseMove}
                onClick={handleClick}
                onWheel={handleWheel}
            />

            {/* Tooltip */}
            {tooltip && (
                <div
                    className="pointer-events-none fixed z-30 rounded-lg border border-stone-200 bg-white px-3 py-2 shadow-lg"
                    style={{
                        left: tooltip.x + 12,
                        top: tooltip.y - 10,
                    }}
                >
                    <p className="text-sm font-medium text-stone-900 max-w-[240px] line-clamp-2">
                        {tooltip.node.title ?? "Untitled"}
                    </p>
                    {tooltip.node.citation && (
                        <p className="text-xs text-stone-500">{tooltip.node.citation}</p>
                    )}
                    <div className="mt-1 flex items-center gap-3 text-xs text-stone-400">
                        {tooltip.node.year && <span>{tooltip.node.year}</span>}
                        {tooltip.node.pagerank_global != null && (
                            <span>★ {tooltip.node.pagerank_global.toFixed(4)}</span>
                        )}
                        <span>{tooltip.node.cited_by_count} citations</span>
                    </div>
                </div>
            )}
        </div>
    );
}
