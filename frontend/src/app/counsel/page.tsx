"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import Link from "next/link";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { searchCounsel } from "@/lib/api";
import { Search, Briefcase, Loader2, Users, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface CounselEntry {
    name: string;
    total_cases: number;
    designation: string;
}

export default function CounselPage() {
    const [counsels, setCounsels] = useState<CounselEntry[]>([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchInput, setSearchInput] = useState("");
    const [searchQuery, setSearchQuery] = useState("");
    const [page, setPage] = useState(1);
    const pageSize = 20;
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const fetchCounsels = useCallback(async (query: string, p: number) => {
        setLoading(true);
        setError(null);
        try {
            const res = await searchCounsel(query, p, pageSize);
            setCounsels(res.counsels);
            setTotal(res.total);
        } catch (err: unknown) {
            setCounsels([]);
            setTotal(0);
            setError(err instanceof Error ? err.message : "Failed to load counsel directory");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (searchQuery.trim()) {
            fetchCounsels(searchQuery, page);
        } else {
            setCounsels([]);
            setTotal(0);
            setLoading(false);
        }
    }, [searchQuery, page, fetchCounsels]);

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

    const totalPages = Math.ceil(total / pageSize);

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                <div className="max-w-5xl mx-auto px-4 py-8">
                    {/* Page header */}
                    <div className="flex items-center gap-2 mb-6">
                        <Briefcase className="h-5 w-5 text-muted-foreground" />
                        <h1 className="text-xl font-semibold font-[family-name:var(--font-lora)]">
                            Counsel Directory
                        </h1>
                    </div>

                    {/* Search bar */}
                    <div className="relative mb-6">
                        <label htmlFor="counsel-search" className="sr-only">Search counsel</label>
                        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <input
                            id="counsel-search"
                            type="text"
                            value={searchInput}
                            onChange={(e) => handleSearchChange(e.target.value)}
                            placeholder="Search counsel by name"
                            className="w-full h-10 pl-9 pr-4 text-sm bg-background border rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                    </div>

                    {/* Loading */}
                    {loading && (
                        <div className="flex items-center justify-center py-20">
                            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                            <span className="ml-2 text-sm text-muted-foreground">Loading counsel...</span>
                        </div>
                    )}

                    {/* Error */}
                    {!loading && error && (
                        <div className="text-center py-20">
                            <p className="text-sm text-destructive font-medium">{error}</p>
                            <Button variant="outline" size="sm" className="mt-3" onClick={() => fetchCounsels(searchQuery, page)}>
                                Retry
                            </Button>
                        </div>
                    )}

                    {/* Results */}
                    {!loading && !error && (
                        <>
                            {counsels.length === 0 ? (
                                <div className="text-center py-20">
                                    <Users className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
                                    <p className="text-sm text-muted-foreground">No counsel found.</p>
                                </div>
                            ) : (
                                <>
                                    {/* Column headers */}
                                    <div className="grid grid-cols-[1fr,100px,100px,32px] gap-2 px-3 pb-2 border-b text-[11px] uppercase tracking-wider text-muted-foreground">
                                        <span>Name</span>
                                        <span className="text-right">Cases</span>
                                        <span className="text-right">Designation</span>
                                        <span />
                                    </div>

                                    {/* Rows */}
                                    <div className="divide-y">
                                        {counsels.map((counsel) => (
                                            <Link
                                                key={counsel.name}
                                                href={`/counsel/${encodeURIComponent(counsel.name)}`}
                                                className="grid grid-cols-[1fr,100px,100px,32px] gap-2 px-3 py-3 items-center hover:bg-accent/50 rounded-md transition-colors"
                                            >
                                                <span className="text-sm font-medium truncate" title={counsel.name}>
                                                    {counsel.name}
                                                </span>
                                                <span className="text-sm text-muted-foreground text-right tabular-nums">
                                                    {counsel.total_cases}
                                                </span>
                                                <span className="text-right">
                                                    {counsel.designation && (
                                                        <Badge variant="secondary" className="text-[10px]">
                                                            {counsel.designation}
                                                        </Badge>
                                                    )}
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
