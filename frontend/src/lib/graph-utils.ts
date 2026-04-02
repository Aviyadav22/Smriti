/** Shared constants and helpers for citation graph rendering. */

export const EDGE_COLORS: Record<string, string> = {
    cites:          "#9CA3AF", // gray
    overrules:      "#EF4444", // red
    affirms:        "#22C55E", // green
    distinguishes:  "#F97316", // orange
    followed:       "#60A5FA", // blue
    not_followed:   "#F87171", // light red
    doubted:        "#FBBF24", // amber
    explained:      "#A78BFA", // purple
    per_incuriam:   "#EF4444", // red (equally severe)
};

/** Top-level legend entries for compact display. */
export const LEGEND_TYPES = ["cites", "overrules", "affirms", "distinguishes", "followed", "doubted"] as const;

/** Detect whether a graph node is a placeholder (unresolved citation). */
export function isPlaceholderNode(node: Record<string, unknown>): boolean {
    if (typeof node.id === "string" && node.id.startsWith("ref_")) return true;
    if (node.year == null && node.court == null) return true;
    return false;
}

/** Get edge color by type, with fallback to gray. */
export function getEdgeColor(type: string | undefined | null): string {
    return EDGE_COLORS[type || "cites"] || "#9CA3AF";
}
