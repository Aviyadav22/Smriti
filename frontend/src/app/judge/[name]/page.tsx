"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { getJudgeProfile, getJudgeCases } from "@/lib/api";
import { JudgePredictionCard } from "@/components/judge-prediction-card";
import type { JudgeProfile, JudgeCasesResponse } from "@/lib/types";
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
import { ArrowLeft, Gavel, FileText, Users, Scale, BookOpen, Loader2 } from "lucide-react";

const CHART_COLORS = [
    "hsl(var(--chart-1))",
    "hsl(var(--chart-2))",
    "hsl(var(--chart-3))",
    "hsl(var(--chart-4))",
    "hsl(var(--chart-5))",
];

export default function JudgeProfilePage() {
    const params = useParams();
    const router = useRouter();
    const judgeName = decodeURIComponent(params.name as string);

    const [profile, setProfile] = useState<JudgeProfile | null>(null);
    const [cases, setCases] = useState<JudgeCasesResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            setLoading(true);
            try {
                const [p, c] = await Promise.allSettled([
                    getJudgeProfile(judgeName),
                    getJudgeCases(judgeName, { page: 1, page_size: 10 }),
                ]);
                if (p.status === "fulfilled") setProfile(p.value);
                else throw new Error("Judge not found");
                if (c.status === "fulfilled") setCases(c.value);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load judge profile");
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [judgeName]);

    if (loading) return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <div className="flex-1 flex items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
        </div>
    );

    if (error || !profile) return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                    <p className="text-sm text-destructive">{error || "Judge not found"}</p>
                    <button
                        className="mt-3 text-xs text-muted-foreground hover:text-foreground underline"
                        onClick={() => router.back()}
                    >
                        Go Back
                    </button>
                </div>
            </div>
        </div>
    );

    const yearData = Object.entries(profile.cases_by_year)
        .map(([year, count]) => ({ year, count }))
        .sort((a, b) => a.year.localeCompare(b.year));

    const disposalData = Object.entries(profile.disposal_patterns).map(
        ([name, count]) => ({ name, count }),
    );

    const caseTypeData = Object.entries(profile.case_types)
        .map(([type, count]) => ({ type, count }))
        .sort((a, b) => b.count - a.count);

    const actsEntries = Object.entries(profile.acts_frequency)
        .sort(([, a], [, b]) => b - a);
    const maxActCount = actsEntries.length > 0 ? actsEntries[0][1] : 1;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                <div className="max-w-6xl mx-auto px-4 py-8">
                    {/* Back link + Judge name */}
                    <Link
                        href="/judges"
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-4"
                    >
                        <ArrowLeft className="h-3 w-3" /> Back to judges
                    </Link>

                    <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight mb-6">
                        {profile.name}
                    </h1>

                    {/* Stats cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <Gavel className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Total Cases</span>
                            </div>
                            <p className="text-2xl font-semibold">{profile.total_cases}</p>
                        </div>
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <FileText className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Cases Authored</span>
                            </div>
                            <p className="text-2xl font-semibold">{profile.cases_authored}</p>
                        </div>
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <Users className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Bench Combinations</span>
                            </div>
                            <p className="text-2xl font-semibold">{profile.bench_combinations.length}</p>
                        </div>
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <Scale className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Case Types</span>
                            </div>
                            <p className="text-2xl font-semibold">{Object.keys(profile.case_types).length}</p>
                        </div>
                    </div>

                    {/* Prediction card */}
                    <div className="mb-8">
                        <JudgePredictionCard judgeName={judgeName} />
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

                    <div className="grid md:grid-cols-2 gap-6 mb-8">
                        {/* Case Types horizontal bar chart */}
                        <div className="border rounded-lg bg-card p-5">
                            <h2 className="text-sm font-medium mb-4">Case Types</h2>
                            {caseTypeData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={280}>
                                    <BarChart data={caseTypeData} layout="vertical">
                                        <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                                        <YAxis
                                            type="category"
                                            dataKey="type"
                                            tick={{ fontSize: 11 }}
                                            width={120}
                                        />
                                        <Tooltip />
                                        <Bar dataKey="count" fill={CHART_COLORS[2]} radius={[0, 2, 2, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <p className="text-xs text-muted-foreground">No case type data available.</p>
                            )}
                        </div>

                        {/* Acts / Statutes frequency */}
                        <div className="border rounded-lg bg-card p-5">
                            <h2 className="text-sm font-medium mb-4 flex items-center gap-1.5">
                                <BookOpen className="h-4 w-4" /> Acts &amp; Statutes
                            </h2>
                            {actsEntries.length > 0 ? (
                                <div className="space-y-2 max-h-[280px] overflow-y-auto">
                                    {actsEntries.map(([act, count]) => (
                                        <div key={act}>
                                            <div className="flex justify-between text-xs mb-0.5">
                                                <span className="truncate mr-2">{act}</span>
                                                <span className="text-muted-foreground shrink-0">{count}</span>
                                            </div>
                                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                                                <div
                                                    className="h-full rounded-full"
                                                    style={{
                                                        width: `${(count / maxActCount) * 100}%`,
                                                        backgroundColor: CHART_COLORS[1],
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-xs text-muted-foreground">No acts data available.</p>
                            )}
                        </div>
                    </div>

                    {/* Bench Combinations */}
                    {profile.bench_combinations.length > 0 && (
                        <div className="border rounded-lg bg-card p-5 mb-8">
                            <h2 className="text-sm font-medium mb-4 flex items-center gap-1.5">
                                <Users className="h-4 w-4" /> Bench Combinations
                            </h2>
                            <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
                                {profile.bench_combinations.map((combo) => (
                                    <Link
                                        key={combo.judge}
                                        href={`/judge/${encodeURIComponent(combo.judge)}`}
                                        className="flex items-center justify-between border rounded-md p-3 hover:bg-muted/50 transition-colors"
                                    >
                                        <span className="text-sm truncate mr-2">{combo.judge}</span>
                                        <span className="text-xs text-muted-foreground shrink-0">
                                            {combo.cases_together} cases
                                        </span>
                                    </Link>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Top Cited Judgments */}
                    {profile.top_cited_judgments.length > 0 && (
                        <div className="border rounded-lg bg-card p-5 mb-8">
                            <h2 className="text-sm font-medium mb-4 flex items-center gap-1.5">
                                <Scale className="h-4 w-4" /> Top Cited Judgments
                            </h2>
                            <div className="space-y-2">
                                {profile.top_cited_judgments.map((j) => (
                                    <Link
                                        key={j.id}
                                        href={`/case/${j.id}`}
                                        className="flex items-center justify-between border rounded-md p-3 hover:bg-muted/50 transition-colors"
                                    >
                                        <div className="min-w-0 mr-3">
                                            <p className="text-sm font-medium truncate">{j.title}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {[j.citation, j.year].filter(Boolean).join(" - ")}
                                            </p>
                                        </div>
                                        {j.citation_count != null && (
                                            <span className="text-xs text-muted-foreground shrink-0">
                                                {j.citation_count} citations
                                            </span>
                                        )}
                                    </Link>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Recent Cases */}
                    {cases && cases.cases.length > 0 && (
                        <div className="border rounded-lg bg-card p-5 mb-8">
                            <h2 className="text-sm font-medium mb-4 flex items-center gap-1.5">
                                <FileText className="h-4 w-4" /> Recent Cases
                            </h2>
                            <div className="space-y-2">
                                {cases.cases.map((c) => (
                                    <Link
                                        key={c.id}
                                        href={`/case/${c.id}`}
                                        className="flex items-center justify-between border rounded-md p-3 hover:bg-muted/50 transition-colors"
                                    >
                                        <div className="min-w-0 mr-3">
                                            <p className="text-sm font-medium truncate">{c.title}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {[c.citation, c.court, c.year].filter(Boolean).join(" - ")}
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            {c.is_author && (
                                                <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                                                    Author
                                                </span>
                                            )}
                                            {c.case_type && (
                                                <span className="text-xs text-muted-foreground">
                                                    {c.case_type}
                                                </span>
                                            )}
                                        </div>
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
