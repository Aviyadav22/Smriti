"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import { getJudges, compareJudges } from "@/lib/api";
import type { JudgeListItem, JudgeProfile } from "@/lib/types";
import { Scale, ArrowLeft, Loader2, Plus, X, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from "recharts";

const CHART_COLORS = [
    "hsl(var(--chart-1))",
    "hsl(var(--chart-2))",
    "hsl(var(--chart-3))",
];

export default function JudgeComparePage() {
    const [selectedJudges, setSelectedJudges] = useState<string[]>([]);
    const [searchInput, setSearchInput] = useState("");
    const [suggestions, setSuggestions] = useState<JudgeListItem[]>([]);
    const [showDropdown, setShowDropdown] = useState(false);
    const [searchLoading, setSearchLoading] = useState(false);
    const [comparing, setComparing] = useState(false);
    const [profiles, setProfiles] = useState<JudgeProfile[]>([]);
    const [error, setError] = useState<string | null>(null);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown on outside click
    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (
                dropdownRef.current &&
                !dropdownRef.current.contains(e.target as Node)
            ) {
                setShowDropdown(false);
            }
        }
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, []);

    const searchJudges = useCallback(async (query: string) => {
        if (!query.trim()) {
            setSuggestions([]);
            setShowDropdown(false);
            return;
        }
        setSearchLoading(true);
        try {
            const res = await getJudges({ search: query, page_size: 8 });
            setSuggestions(res.judges);
            setShowDropdown(true);
        } catch {
            setSuggestions([]);
        } finally {
            setSearchLoading(false);
        }
    }, []);

    function handleSearchChange(value: string) {
        setSearchInput(value);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
            searchJudges(value);
        }, 300);
    }

    function addJudge(name: string) {
        if (selectedJudges.includes(name) || selectedJudges.length >= 3) return;
        setSelectedJudges((prev) => [...prev, name]);
        setSearchInput("");
        setSuggestions([]);
        setShowDropdown(false);
    }

    function removeJudge(name: string) {
        setSelectedJudges((prev) => prev.filter((n) => n !== name));
    }

    async function handleCompare() {
        if (selectedJudges.length < 2) return;
        setComparing(true);
        setError(null);
        setProfiles([]);
        try {
            const res = await compareJudges(selectedJudges);
            const valid = res.judges.filter(
                (j): j is JudgeProfile => j !== null,
            );
            if (valid.length < 2) {
                setError(
                    "Could not find profiles for the selected judges. Please try different judges.",
                );
            } else {
                setProfiles(valid);
            }
        } catch {
            setError("Failed to compare judges. Please try again.");
        } finally {
            setComparing(false);
        }
    }

    // Build disposal comparison chart data
    const disposalCompare = (() => {
        if (profiles.length === 0) return [];
        const allNatures = new Set<string>();
        profiles.forEach((p) =>
            Object.keys(p.disposal_patterns).forEach((k) =>
                allNatures.add(k),
            ),
        );
        return Array.from(allNatures).map((nature) => {
            const row: Record<string, string | number> = {
                disposal_nature: nature,
            };
            profiles.forEach((p) => {
                row[p.name] = p.disposal_patterns[nature] ?? 0;
            });
            return row;
        });
    })();

    return (
        <div className="max-w-6xl mx-auto px-4 py-8">
                    {/* Back link */}
                    <Link
                        href="/judges"
                        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
                    >
                        <ArrowLeft className="h-3.5 w-3.5" />
                        Back to Judge Directory
                    </Link>

                    {/* Page header */}
                    <div className="flex items-center gap-2 mb-6">
                        <Scale className="h-5 w-5 text-muted-foreground" />
                        <h1 className="text-xl font-semibold font-[family-name:var(--font-lora)]">
                            Compare Judges
                        </h1>
                    </div>

                    {/* Judge selection card */}
                    <div className="border rounded-lg p-6 mb-8">
                        <p className="text-sm text-muted-foreground mb-4">
                            Select judges to compare (2-3 judges)
                        </p>

                        {/* Selected judge pills */}
                        {selectedJudges.length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-4">
                                {selectedJudges.map((name) => (
                                    <span
                                        key={name}
                                        className="inline-flex items-center gap-1 px-3 py-1.5 text-sm bg-primary/10 text-primary rounded-full"
                                    >
                                        {name}
                                        <button
                                            onClick={() => removeJudge(name)}
                                            className="ml-1 hover:text-destructive"
                                            aria-label={`Remove ${name}`}
                                        >
                                            <X className="h-3.5 w-3.5" />
                                        </button>
                                    </span>
                                ))}
                            </div>
                        )}

                        {/* Search input with dropdown */}
                        {selectedJudges.length < 3 && (
                            <div className="relative" ref={dropdownRef}>
                                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                                <input
                                    type="text"
                                    value={searchInput}
                                    onChange={(e) =>
                                        handleSearchChange(e.target.value)
                                    }
                                    placeholder="Search judges to add..."
                                    className="w-full h-10 pl-9 pr-4 text-sm bg-background border rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
                                />
                                {searchLoading && (
                                    <Loader2 className="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />
                                )}

                                {/* Dropdown */}
                                {showDropdown && suggestions.length > 0 && (
                                    <div className="absolute z-10 top-full left-0 right-0 mt-1 bg-background border rounded-md shadow-lg max-h-60 overflow-y-auto">
                                        {suggestions
                                            .filter(
                                                (s) =>
                                                    !selectedJudges.includes(
                                                        s.name,
                                                    ),
                                            )
                                            .map((judge) => (
                                                <button
                                                    key={judge.name}
                                                    onClick={() =>
                                                        addJudge(judge.name)
                                                    }
                                                    className="w-full text-left px-3 py-2 hover:bg-accent/50 flex items-center justify-between text-sm"
                                                >
                                                    <span className="flex items-center gap-2">
                                                        <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                                                        {judge.name}
                                                    </span>
                                                    <span className="text-xs text-muted-foreground tabular-nums">
                                                        {judge.total_cases}{" "}
                                                        cases
                                                    </span>
                                                </button>
                                            ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Compare button */}
                        <div className="mt-4">
                            <Button
                                onClick={handleCompare}
                                disabled={
                                    selectedJudges.length < 2 || comparing
                                }
                                className="gap-2"
                            >
                                {comparing ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Scale className="h-4 w-4" />
                                )}
                                {comparing ? "Comparing..." : "Compare"}
                            </Button>
                        </div>
                    </div>

                    {/* Error */}
                    {error && (
                        <div className="text-sm text-destructive mb-6">
                            {error}
                        </div>
                    )}

                    {/* Loading state */}
                    {comparing && (
                        <div className="flex items-center justify-center py-20">
                            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                            <span className="ml-2 text-sm text-muted-foreground">
                                Comparing judges...
                            </span>
                        </div>
                    )}

                    {/* Results */}
                    {profiles.length >= 2 && !comparing && (
                        <div>
                            {/* Summary cards */}
                            <h2 className="text-lg font-semibold mb-4">
                                Comparison Results
                            </h2>
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 mb-8">
                                {profiles.map((profile) => (
                                    <div
                                        key={profile.name}
                                        className="border rounded-lg p-4"
                                    >
                                        <h3 className="font-medium text-sm mb-3 truncate">
                                            {profile.name}
                                        </h3>
                                        <div className="space-y-2 text-sm">
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">
                                                    Total Cases
                                                </span>
                                                <span className="font-medium tabular-nums">
                                                    {profile.total_cases}
                                                </span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">
                                                    Authored
                                                </span>
                                                <span className="font-medium tabular-nums">
                                                    {profile.cases_authored}
                                                </span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-muted-foreground">
                                                    Case Types
                                                </span>
                                                <span className="font-medium tabular-nums">
                                                    {
                                                        Object.keys(
                                                            profile.case_types,
                                                        ).length
                                                    }
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Disposal patterns chart */}
                            {disposalCompare.length > 0 && (
                                <div className="border rounded-lg p-6">
                                    <h3 className="font-medium text-sm mb-4">
                                        Disposal Patterns Comparison
                                    </h3>
                                    <ResponsiveContainer
                                        width="100%"
                                        height={350}
                                    >
                                        <BarChart data={disposalCompare}>
                                            <XAxis
                                                dataKey="disposal_nature"
                                                tick={{ fontSize: 12 }}
                                                interval={0}
                                                angle={-30}
                                                textAnchor="end"
                                                height={80}
                                            />
                                            <YAxis tick={{ fontSize: 12 }} />
                                            <Tooltip />
                                            <Legend />
                                            {profiles.map((p, i) => (
                                                <Bar
                                                    key={p.name}
                                                    dataKey={p.name}
                                                    fill={
                                                        CHART_COLORS[
                                                            i %
                                                                CHART_COLORS.length
                                                        ]
                                                    }
                                                />
                                            ))}
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            )}
                        </div>
                    )}
        </div>
    );
}
