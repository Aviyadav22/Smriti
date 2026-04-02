import { describe, it, expect } from "vitest";
import { EDGE_COLORS, isPlaceholderNode, getEdgeColor } from "../graph-utils";

describe("EDGE_COLORS", () => {
    it("has colors for all treatment types", () => {
        const required = ["cites", "overrules", "affirms", "distinguishes", "followed", "not_followed", "doubted", "explained", "per_incuriam"];
        for (const type of required) {
            expect(EDGE_COLORS[type]).toBeDefined();
        }
    });
});

describe("getEdgeColor", () => {
    it("returns correct color for known types", () => {
        expect(getEdgeColor("overrules")).toBe("#EF4444");
        expect(getEdgeColor("affirms")).toBe("#22C55E");
        expect(getEdgeColor("cites")).toBe("#9CA3AF");
    });

    it("returns gray for unknown types", () => {
        expect(getEdgeColor("unknown")).toBe("#9CA3AF");
    });

    it("returns gray for null/undefined", () => {
        expect(getEdgeColor(null)).toBe("#9CA3AF");
        expect(getEdgeColor(undefined)).toBe("#9CA3AF");
    });
});

describe("isPlaceholderNode", () => {
    it("detects ref_ prefixed IDs as placeholder", () => {
        expect(isPlaceholderNode({ id: "ref_a1b2c3d4e5f6", year: null, court: null })).toBe(true);
    });

    it("detects nodes with no year and no court as placeholder", () => {
        expect(isPlaceholderNode({ id: "some-uuid", year: null, court: null })).toBe(true);
    });

    it("does not flag real nodes with year and court", () => {
        expect(isPlaceholderNode({ id: "some-uuid", year: 2020, court: "SC" })).toBe(false);
    });

    it("does not flag nodes with only year set", () => {
        expect(isPlaceholderNode({ id: "some-uuid", year: 2020, court: null })).toBe(false);
    });
});
