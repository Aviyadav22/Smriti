"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { getCourtStats } from "@/lib/api";
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
import { Building2, FileText, Loader2, Users } from "lucide-react";

const CHART_COLORS = [
    "hsl(var(--chart-1))",
    "hsl(var(--chart-2))",
    "hsl(var(--chart-3))",
    "hsl(var(--chart-4))",
    "hsl(var(--chart-5))",
];

const DEFAULT_COURT = "Supreme Court of India";

export default function CourtsPage() {
    const [stats, setStats] = useState<CourtStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            setLoading(true);
            try {
                const data = await getCourtStats(DEFAULT_COURT);
                setStats(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load court statistics");
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <div className="flex-1 flex items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
        </div>
    );

    if (error || !stats) return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                    <p className="text-sm text-destructive">{error || "Failed to load court statistics"}</p>
                </div>
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
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                <div className="max-w-6xl mx-auto px-4 py-8">
                    {/* Title */}
                    <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight mb-6 flex items-center gap-2">
                        <Building2 className="h-7 w-7" /> Court Statistics
                    </h1>

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
                                        <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                                        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                                        <Tooltip />
                                        <Bar dataKey="count" fill={CHART_COLORS[0]} radius={[2, 2, 0, 0]} />
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
                                            label={({ name }: { name?: string }) => name ?? ""}
                                        >
                                            {disposalData.map((_, idx) => (
                                                <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <Tooltip />
                                        <Legend />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <p className="text-xs text-muted-foreground">No disposal data available.</p>
                            )}
                        </div>
                    </div>

                    {/* Top Judges */}
                    {stats.top_judges.length > 0 && (
                        <div className="border rounded-lg bg-card p-5 mb-8">
                            <h2 className="text-sm font-medium mb-4 flex items-center gap-1.5">
                                <Users className="h-4 w-4" /> Top Judges
                            </h2>
                            <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
                                {stats.top_judges.map((j) => (
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
                        </div>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
}
