"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getCourtStats, searchFacets } from "@/lib/api";
import type { CourtStats } from "@/lib/types";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
    Legend,
} from "recharts";
import { Building2, ChevronDown, FileText, Loader2, Search, Users } from "lucide-react";

function useChartColors(): string[] {
    const [colors, setColors] = useState<string[]>([
        "#B89B6A", "#8B7355", "#6B6458", "#9B8B75", "#A69478",
        "#C49A6C", "#7A6B5D", "#A8926E", "#6B5E50", "#8B7D6A",
    ]);

    useEffect(() => {
        const root = document.documentElement;
        const style = getComputedStyle(root);
        const resolved = [
            style.getPropertyValue("--chart-1").trim(),
            style.getPropertyValue("--chart-2").trim(),
            style.getPropertyValue("--chart-3").trim(),
            style.getPropertyValue("--chart-4").trim(),
            style.getPropertyValue("--chart-5").trim(),
        ].filter(Boolean);
        if (resolved.length === 5) {
            setColors([...resolved, "#C49A6C", "#7A6B5D", "#A8926E", "#6B5E50", "#8B7D6A"]);
        }
    }, []);

    return colors;
}

function useThemeColors() {
    const [theme, setTheme] = useState({ fg: "#4D4839", border: "#D8D0C4", card: "#FFFDF7", text: "#1A1A1A" });

    useEffect(() => {
        const style = getComputedStyle(document.documentElement);
        setTheme({
            fg: style.getPropertyValue("--muted-foreground").trim() || "#4D4839",
            border: style.getPropertyValue("--border").trim() || "#D8D0C4",
            card: style.getPropertyValue("--card").trim() || "#FFFDF7",
            text: style.getPropertyValue("--foreground").trim() || "#1A1A1A",
        });
    }, []);

    // Re-resolve on theme change
    useEffect(() => {
        const observer = new MutationObserver(() => {
            const style = getComputedStyle(document.documentElement);
            setTheme({
                fg: style.getPropertyValue("--muted-foreground").trim() || "#4D4839",
                border: style.getPropertyValue("--border").trim() || "#D8D0C4",
                card: style.getPropertyValue("--card").trim() || "#FFFDF7",
                text: style.getPropertyValue("--foreground").trim() || "#1A1A1A",
            });
        });
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
        return () => observer.disconnect();
    }, []);

    return theme;
}

const FALLBACK_COURTS = [
    "Supreme Court of India",
    "High Court of Delhi",
    "High Court of Bombay",
    "High Court of Madras",
    "High Court of Calcutta",
    "High Court of Karnataka",
];

export default function CourtsPage() {
    const [selectedCourt, setSelectedCourt] = useState("Supreme Court of India");
    const [courts, setCourts] = useState<string[]>(FALLBACK_COURTS);
    const [stats, setStats] = useState<CourtStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const chartColors = useChartColors();
    const themeColors = useThemeColors();

    // Fetch available courts from facets API
    useEffect(() => {
        async function loadCourts() {
            try {
                const facets = await searchFacets();
                if (facets.courts && facets.courts.length > 0) {
                    setCourts(facets.courts);
                }
            } catch {
                // Keep fallback courts on error
            }
        }
        loadCourts();
    }, []);

    // Fetch stats when selected court changes
    useEffect(() => {
        async function load() {
            setLoading(true);
            setError(null);
            try {
                const data = await getCourtStats(selectedCourt);
                setStats(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load court statistics");
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [selectedCourt]);

    if (loading) return (
        <div className="flex-1 flex items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
    );

    if (error || !stats) return (
        <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
                <p className="text-sm text-destructive">{error || "Failed to load court statistics"}</p>
            </div>
        </div>
    );

    const yearData = Object.entries(stats.cases_by_year)
        .map(([year, count]) => ({ year, count }))
        .sort((a, b) => a.year.localeCompare(b.year));

    const disposalData = Object.entries(stats.disposal_patterns).map(
        ([name, count]) => ({ name, count }),
    );

    return (
        <div className="max-w-6xl mx-auto px-4 py-8">
                    {/* Title + Court Selector */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
                        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight flex items-center gap-2">
                            <Building2 className="h-7 w-7" /> Court Statistics
                        </h1>
                        <div className="relative">
                            <select
                                value={selectedCourt}
                                onChange={(e) => setSelectedCourt(e.target.value)}
                                className="appearance-none border rounded-md bg-card px-3 py-2 pr-8 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer min-w-[240px]"
                            >
                                {courts.map((court) => (
                                    <option key={court} value={court}>
                                        {court}
                                    </option>
                                ))}
                            </select>
                            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 pointer-events-none text-muted-foreground" />
                        </div>
                    </div>

                    {/* Stats cards */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <Building2 className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Court</span>
                            </div>
                            <p className="text-lg font-semibold">{stats.court}</p>
                        </div>
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <FileText className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Total Cases</span>
                            </div>
                            <p className="text-2xl font-semibold">{stats.total_cases}</p>
                        </div>
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <Users className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Total Judges</span>
                            </div>
                            <p className="text-2xl font-semibold">{stats.top_judges.length}</p>
                        </div>
                    </div>

                    {/* Charts row */}
                    <div className="grid md:grid-cols-2 gap-6 mb-8">
                        {/* Cases by Year */}
                        <div className="border rounded-lg bg-card p-5">
                            <h2 className="text-sm font-medium mb-4">Cases by Year</h2>
                            {yearData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={280}>
                                    <BarChart data={yearData}>
                                        <XAxis dataKey="year" tick={{ fontSize: 11, fill: themeColors.fg }} axisLine={{ stroke: themeColors.border }} tickLine={{ stroke: themeColors.border }} />
                                        <YAxis tick={{ fontSize: 11, fill: themeColors.fg }} axisLine={{ stroke: themeColors.border }} tickLine={{ stroke: themeColors.border }} allowDecimals={false} />
                                        <Tooltip contentStyle={{ backgroundColor: themeColors.card, border: `1px solid ${themeColors.border}`, borderRadius: 6, color: themeColors.text, fontSize: 12 }} />
                                        <Bar dataKey="count" fill={chartColors[0]} radius={[2, 2, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <p className="text-xs text-muted-foreground">No year data available.</p>
                            )}
                        </div>

                        {/* Disposal Patterns */}
                        <div className="border rounded-lg bg-card p-5">
                            <h2 className="text-sm font-medium mb-4">Disposal Patterns</h2>
                            {disposalData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={280}>
                                    <PieChart>
                                        <Pie
                                            data={disposalData}
                                            dataKey="count"
                                            nameKey="name"
                                            cx="50%"
                                            cy="50%"
                                            outerRadius={100}
                                            stroke={themeColors.card}
                                            label={({ name }: { name?: string }) => name ?? ""}
                                            labelLine={{ stroke: themeColors.fg }}
                                        >
                                            {disposalData.map((_, idx) => (
                                                <Cell key={idx} fill={chartColors[idx % chartColors.length]} />
                                            ))}
                                        </Pie>
                                        <Tooltip contentStyle={{ backgroundColor: themeColors.card, border: `1px solid ${themeColors.border}`, borderRadius: 6, color: themeColors.text, fontSize: 12 }} />
                                        <Legend wrapperStyle={{ color: themeColors.fg, fontSize: 12 }} />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <p className="text-xs text-muted-foreground">No disposal data available.</p>
                            )}
                        </div>
                    </div>

                    {/* Top Judges */}
                    {stats.top_judges.length > 0 && (
                        <TopJudgesSection judges={stats.top_judges} />
                    )}
        </div>
    );
}

function TopJudgesSection({ judges }: { judges: { judge: string; cases: number }[] }) {
    const [search, setSearch] = useState("");
    const [showAll, setShowAll] = useState(false);

    const filtered = judges.filter((j) =>
        j.judge.toLowerCase().includes(search.toLowerCase()),
    );

    const INITIAL_COUNT = 21;
    const displayed = showAll ? filtered : filtered.slice(0, INITIAL_COUNT);
    const hasMore = filtered.length > INITIAL_COUNT && !showAll;

    return (
        <div className="border rounded-lg bg-card p-5 mb-8">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-medium flex items-center gap-1.5">
                    <Users className="h-4 w-4" /> Top Judges
                </h2>
                <Link
                    href="/judges"
                    className="text-xs text-primary hover:underline"
                >
                    See All Judges &rarr;
                </Link>
            </div>

            {/* Search bar */}
            <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                    type="text"
                    value={search}
                    onChange={(e) => { setSearch(e.target.value); setShowAll(false); }}
                    placeholder="Search judges..."
                    className="w-full border rounded-md bg-background pl-9 pr-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
            </div>

            {displayed.length > 0 ? (
                <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
                    {displayed.map((j) => (
                        <Link
                            key={j.judge}
                            href={`/judge/${encodeURIComponent(j.judge)}`}
                            className="flex items-center justify-between border rounded-md p-3 hover:bg-muted/50 transition-colors"
                        >
                            <span className="text-sm truncate mr-2">{j.judge}</span>
                            <span className="text-xs text-muted-foreground shrink-0">
                                {j.cases} cases
                            </span>
                        </Link>
                    ))}
                </div>
            ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                    No judges found matching &ldquo;{search}&rdquo;
                </p>
            )}

            {hasMore && (
                <button
                    onClick={() => setShowAll(true)}
                    className="mt-4 w-full text-center text-sm text-primary hover:underline py-2"
                >
                    See all {filtered.length} judges
                </button>
            )}
        </div>
    );
}
