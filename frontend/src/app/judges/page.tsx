"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { getJudges } from "@/lib/api";
import type { JudgeListResponse } from "@/lib/types";
import { Search, Gavel, Loader2, Users, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function JudgesPage() {
    const [data, setData] = useState<JudgeListResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [searchInput, setSearchInput] = useState("");
    const [searchQuery, setSearchQuery] = useState("");
    const [page, setPage] = useState(1);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const fetchJudges = useCallback(async (search: string, p: number) => {
        setLoading(true);
        try {
            const res = await getJudges({
                search: search || undefined,
                page: p,
                page_size: 20,
            });
            setData(res);
        } catch {
            setData(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchJudges(searchQuery, page);
    }, [searchQuery, page, fetchJudges]);

    function handleSearchChange(value: string) {
        setSearchInput(value);
        if (debounceRef.current) {
            clearTimeout(debounceRef.current);
        }
        debounceRef.current = setTimeout(() => {
            setPage(1);
            setSearchQuery(value);
        }, 300);
    }

    const totalPages = data?.total_pages ?? 0;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                <div className="max-w-5xl mx-auto px-4 py-8">
                    {/* Page header */}
                    <div className="flex items-center gap-2 mb-6">
                        <Gavel className="h-5 w-5 text-muted-foreground" />
                        <h1 className="text-xl font-semibold font-[family-name:var(--font-lora)]">
                            Judge Directory
                        </h1>
                    </div>

                    {/* Search bar */}
                    <div className="relative mb-6">
                        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <input
                            type="text"
                            value={searchInput}
                            onChange={(e) => handleSearchChange(e.target.value)}
                            placeholder="Search judges"
                            className="w-full h-10 pl-9 pr-4 text-sm bg-background border rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                    </div>

                    {/* Loading */}
                    {loading && (
                        <div className="flex items-center justify-center py-20">
                            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                            <span className="ml-2 text-sm text-muted-foreground">Loading judges…</span>
                        </div>
                    )}

                    {/* Results */}
                    {!loading && data && (
                        <>
                            {data.judges.length === 0 ? (
                                <div className="text-center py-20">
                                    <Users className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
                                    <p className="text-sm text-muted-foreground">No judges found.</p>
                                </div>
                            ) : (
                                <>
                                    {/* Column headers */}
                                    <div className="grid grid-cols-[1fr,80px,80px,32px] gap-2 px-3 pb-2 border-b text-[11px] uppercase tracking-wider text-muted-foreground">
                                        <span>Judge</span>
                                        <span className="text-right">Cases</span>
                                        <span className="text-right">Authored</span>
                                        <span />
                                    </div>

                                    {/* Rows */}
                                    <div className="divide-y">
                                        {data.judges.map((judge) => (
                                            <Link
                                                key={judge.name}
                                                href={`/judge/${encodeURIComponent(judge.name)}`}
                                                className="grid grid-cols-[1fr,80px,80px,32px] gap-2 px-3 py-3 items-center hover:bg-accent/50 rounded-md transition-colors"
                                            >
                                                <span className="text-sm font-medium truncate">
                                                    {judge.name}
                                                </span>
                                                <span className="text-sm text-muted-foreground text-right tabular-nums">
                                                    {judge.total_cases}
                                                </span>
                                                <span className="text-sm text-muted-foreground text-right tabular-nums">
                                                    {judge.cases_authored}
                                                </span>
                                                <ChevronRight className="h-4 w-4 text-muted-foreground/50" />
                                            </Link>
                                        ))}
                                    </div>

                                    {/* Pagination */}
                                    {totalPages > 1 && (
                                        <div className="flex items-center justify-center gap-2 mt-6">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="h-8 text-xs"
                                                onClick={() => setPage((p) => p - 1)}
                                                disabled={page <= 1}
                                            >
                                                Previous
                                            </Button>
                                            <span className="text-xs text-muted-foreground tabular-nums px-2">
                                                {page} / {totalPages}
                                            </span>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="h-8 text-xs"
                                                onClick={() => setPage((p) => p + 1)}
                                                disabled={page >= totalPages}
                                            >
                                                Next
                                            </Button>
                                        </div>
                                    )}
                                </>
                            )}
                        </>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
}
