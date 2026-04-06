"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getCounselProfile, getCounselCases, getCounselMatchups } from "@/lib/api";
import {
    ArrowLeft,
    Briefcase,
    FileText,
    TrendingUp,
    Users,
    Loader2,
    ChevronLeft,
    ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface CounselProfileData {
    name: string;
    designation: string;
    total_cases: number;
    win_rate: number;
    petitioner_cases: number;
    respondent_cases: number;
    active_years: [number, number];
    case_types: Record<string, number>;
    [key: string]: unknown;
}

interface CounselCase {
    id: string;
    title: string;
    year: number;
    case_type: string;
    side: string;
    outcome: string;
    won: boolean;
}

interface Matchup {
    opponent: string;
    total: number;
    wins: number;
    losses: number;
    win_rate: number;
}

function winRateColor(rate: number): string {
    if (rate > 60) return "text-green-600 dark:text-green-400";
    if (rate < 40) return "text-red-600 dark:text-red-400";
    return "text-muted-foreground";
}

export default function CounselProfilePage() {
    const params = useParams();
    const router = useRouter();
    const counselName = decodeURIComponent(params.name as string);

    const [profile, setProfile] = useState<CounselProfileData | null>(null);
    const [cases, setCases] = useState<{ cases: CounselCase[]; total: number } | null>(null);
    const [matchups, setMatchups] = useState<Matchup[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [casePage, setCasePage] = useState(1);
    const [casesLoading, setCasesLoading] = useState(false);
    const pageSize = 20;

    useEffect(() => {
        async function load() {
            setLoading(true);
            try {
                const [p, c, m] = await Promise.allSettled([
                    getCounselProfile(counselName),
                    getCounselCases(counselName, 1, pageSize),
                    getCounselMatchups(counselName),
                ]);
                if (p.status === "fulfilled") setProfile(p.value as CounselProfileData);
                else throw new Error("Counsel not found");
                if (c.status === "fulfilled") setCases(c.value as { cases: CounselCase[]; total: number });
                if (m.status === "fulfilled") setMatchups((m.value as { matchups: Matchup[] }).matchups);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load counsel profile");
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [counselName]);

    const fetchCasesPage = useCallback(async (p: number) => {
        setCasesLoading(true);
        try {
            const res = await getCounselCases(counselName, p, pageSize);
            setCases(res as { cases: CounselCase[]; total: number });
            setCasePage(p);
        } catch {
            // Keep existing cases on pagination error
        } finally {
            setCasesLoading(false);
        }
    }, [counselName]);

    if (loading) return (
        <div className="flex-1 flex items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
    );

    if (error || !profile) return (
        <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
                <p className="text-sm text-destructive">{error || "Counsel not found"}</p>
                <button
                    className="mt-3 text-xs text-muted-foreground hover:text-foreground underline"
                    onClick={() => router.back()}
                >
                    Go Back
                </button>
            </div>
        </div>
    );

    const caseTypeEntries = profile.case_types
        ? Object.entries(profile.case_types).sort(([, a], [, b]) => b - a)
        : [];
    const caseTypeTotal = caseTypeEntries.reduce((sum, [, count]) => sum + count, 0);

    const totalCasePages = cases ? Math.ceil(cases.total / pageSize) : 0;

    return (
        <div className="max-w-6xl mx-auto px-4 py-8">
                    {/* Back link */}
                    <Link
                        href="/counsel"
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-4"
                    >
                        <ArrowLeft className="h-3 w-3" /> Back to counsel directory
                    </Link>

                    {/* Header area */}
                    <div className="mb-6">
                        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">
                            {profile.name}
                        </h1>
                        <div className="flex items-center gap-3 mt-2">
                            {profile.designation && (
                                <Badge variant="secondary" className="text-xs">
                                    {profile.designation}
                                </Badge>
                            )}
                            {profile.active_years && profile.active_years[0] > 0 && (
                                <span className="text-xs text-muted-foreground">
                                    Active: {profile.active_years[0]}–{profile.active_years[1]}
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Stats cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <Briefcase className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Total Cases</span>
                            </div>
                            <p className="text-2xl font-semibold">{profile.total_cases}</p>
                        </div>
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <TrendingUp className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Win Rate</span>
                            </div>
                            <p className={`text-2xl font-semibold ${winRateColor(profile.win_rate)}`}>
                                {profile.win_rate != null && Number.isFinite(profile.win_rate) ? `${profile.win_rate.toFixed(1)}%` : "N/A"}
                            </p>
                        </div>
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <FileText className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Petitioner</span>
                            </div>
                            <p className="text-2xl font-semibold">{profile.petitioner_cases ?? 0}</p>
                        </div>
                        <div className="border rounded-lg bg-card p-4">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                                <Users className="h-4 w-4" />
                                <span className="text-xs uppercase tracking-wider">Respondent</span>
                            </div>
                            <p className="text-2xl font-semibold">{profile.respondent_cases ?? 0}</p>
                        </div>
                    </div>

                    {/* Two columns: Case types + Matchups */}
                    <div className="grid md:grid-cols-2 gap-6 mb-8">
                        {/* Case type distribution */}
                        <div className="border rounded-lg bg-card p-5">
                            <h2 className="text-sm font-medium mb-4">Case Type Distribution</h2>
                            {caseTypeEntries.length > 0 ? (
                                <div className="space-y-2 max-h-[320px] overflow-y-auto">
                                    {caseTypeEntries.map(([type, count]) => (
                                        <div key={type}>
                                            <div className="flex justify-between text-xs mb-0.5">
                                                <span className="truncate mr-2">{type}</span>
                                                <span className="text-muted-foreground shrink-0">
                                                    {count} ({caseTypeTotal > 0 ? ((count / caseTypeTotal) * 100).toFixed(0) : 0}%)
                                                </span>
                                            </div>
                                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                                                <div
                                                    className="h-full rounded-full bg-primary/60"
                                                    style={{
                                                        width: `${caseTypeTotal > 0 ? (count / caseTypeTotal) * 100 : 0}%`,
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-xs text-muted-foreground">No case type data available.</p>
                            )}
                        </div>

                        {/* Top matchups */}
                        <div className="border rounded-lg bg-card p-5">
                            <h2 className="text-sm font-medium mb-4">Top Matchups</h2>
                            {matchups.length > 0 ? (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="border-b text-[11px] uppercase tracking-wider text-muted-foreground">
                                                <th className="text-left pb-2 font-medium">Opponent</th>
                                                <th className="text-right pb-2 font-medium">W</th>
                                                <th className="text-right pb-2 font-medium">L</th>
                                                <th className="text-right pb-2 font-medium">Win%</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y">
                                            {matchups.map((m) => (
                                                <tr key={m.opponent} className="hover:bg-accent/50">
                                                    <td className="py-2">
                                                        <Link
                                                            href={`/counsel/${encodeURIComponent(m.opponent)}`}
                                                            className="text-sm hover:underline truncate block max-w-[200px]"
                                                            title={m.opponent}
                                                        >
                                                            {m.opponent}
                                                        </Link>
                                                    </td>
                                                    <td className="text-right py-2 tabular-nums text-green-600 dark:text-green-400">
                                                        {m.wins}
                                                    </td>
                                                    <td className="text-right py-2 tabular-nums text-red-600 dark:text-red-400">
                                                        {m.losses}
                                                    </td>
                                                    <td className={`text-right py-2 tabular-nums font-medium ${winRateColor(m.win_rate)}`}>
                                                        {m.win_rate.toFixed(0)}%
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <p className="text-xs text-muted-foreground">No matchup data available.</p>
                            )}
                        </div>
                    </div>

                    {/* Cases table */}
                    {cases && cases.cases.length > 0 && (
                        <div className="border rounded-lg bg-card p-5 mb-8">
                            <h2 className="text-sm font-medium mb-4 flex items-center gap-1.5">
                                <FileText className="h-4 w-4" /> Cases ({cases.total})
                            </h2>

                            {casesLoading ? (
                                <div className="flex items-center justify-center py-10">
                                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                </div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="border-b text-[11px] uppercase tracking-wider text-muted-foreground">
                                                <th className="text-left pb-2 font-medium">Title</th>
                                                <th className="text-left pb-2 font-medium">Year</th>
                                                <th className="text-left pb-2 font-medium">Type</th>
                                                <th className="text-left pb-2 font-medium">Side</th>
                                                <th className="text-left pb-2 font-medium">Outcome</th>
                                                <th className="text-right pb-2 font-medium">Result</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y">
                                            {cases.cases.map((c: CounselCase) => (
                                                <tr key={c.id} className="hover:bg-accent/50">
                                                    <td className="py-2 max-w-[300px]">
                                                        <Link
                                                            href={`/case/${c.id}`}
                                                            className="hover:underline truncate block"
                                                            title={c.title}
                                                        >
                                                            {c.title}
                                                        </Link>
                                                    </td>
                                                    <td className="py-2 tabular-nums text-muted-foreground">{c.year}</td>
                                                    <td className="py-2 text-muted-foreground">{c.case_type || "-"}</td>
                                                    <td className="py-2 text-muted-foreground">{c.side || "-"}</td>
                                                    <td className="py-2 text-muted-foreground">{c.outcome || "-"}</td>
                                                    <td className="py-2 text-right">
                                                        {c.won != null && (
                                                            <Badge
                                                                variant={c.won ? "default" : "destructive"}
                                                                className={`text-[10px] ${c.won ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-100" : ""}`}
                                                            >
                                                                {c.won ? "Won" : "Lost"}
                                                            </Badge>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}

                            {/* Pagination */}
                            {totalCasePages > 1 && (
                                <div className="flex items-center justify-center gap-2 mt-4 pt-4 border-t">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-8 text-xs"
                                        onClick={() => fetchCasesPage(casePage - 1)}
                                        disabled={casePage <= 1 || casesLoading}
                                    >
                                        <ChevronLeft className="h-3 w-3 mr-1" />
                                        Previous
                                    </Button>
                                    <span className="text-xs text-muted-foreground tabular-nums px-2">
                                        {casePage} / {totalCasePages}
                                    </span>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-8 text-xs"
                                        onClick={() => fetchCasesPage(casePage + 1)}
                                        disabled={casePage >= totalCasePages || casesLoading}
                                    >
                                        Next
                                        <ChevronRight className="h-3 w-3 ml-1" />
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}
        </div>
    );
}
