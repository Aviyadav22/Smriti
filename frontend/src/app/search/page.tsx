"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { search as apiSearch, searchFacets } from "@/lib/api";
import type { SearchResponse, FacetsResponse } from "@/lib/types";
import { Search, ChevronLeft, ChevronRight, Filter, X, Loader2 } from "lucide-react";

function SearchContent() {
    const searchParams = useSearchParams();
    const router = useRouter();

    const initialQuery = searchParams.get("q") || "";
    const [query, setQuery] = useState(initialQuery);
    const [results, setResults] = useState<SearchResponse | null>(null);
    const [facets, setFacets] = useState<FacetsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [showFilters, setShowFilters] = useState(false);

    // Active filters
    const [court, setCourt] = useState<string>("");
    const [yearFrom, setYearFrom] = useState<string>("");
    const [yearTo, setYearTo] = useState<string>("");
    const [caseType, setCaseType] = useState<string>("");

    const executeSearch = useCallback(async (q: string, p: number) => {
        if (!q.trim()) return;
        setLoading(true);
        setError(null);
        try {
            const res = await apiSearch({
                q,
                page: p,
                page_size: 10,
                court: court || undefined,
                year_from: yearFrom ? parseInt(yearFrom) : undefined,
                year_to: yearTo ? parseInt(yearTo) : undefined,
                case_type: caseType || undefined,
            });
            setResults(res);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Search failed");
        } finally {
            setLoading(false);
        }
    }, [court, yearFrom, yearTo, caseType]);

    useEffect(() => {
        if (initialQuery) {
            executeSearch(initialQuery, 1);
            setQuery(initialQuery);
        }
    }, [initialQuery, executeSearch]);

    useEffect(() => {
        searchFacets().then(setFacets).catch(() => { });
    }, []);

    function handleSearch(e: React.FormEvent) {
        e.preventDefault();
        if (query.trim()) {
            setPage(1);
            router.push(`/search?q=${encodeURIComponent(query.trim())}`, { scroll: false });
            executeSearch(query.trim(), 1);
        }
    }

    function handlePageChange(newPage: number) {
        setPage(newPage);
        executeSearch(query, newPage);
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    const totalPages = results ? Math.ceil(results.total_count / results.page_size) : 0;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                {/* Search bar */}
                <div className="border-b bg-card/50">
                    <div className="mx-auto max-w-5xl px-4 py-4">
                        <form onSubmit={handleSearch} className="flex gap-2">
                            <div className="relative flex-1">
                                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    placeholder="Search Indian case law…"
                                    className="pl-9 h-10 text-sm bg-background rounded-md"
                                />
                            </div>
                            <Button type="submit" className="h-10 px-5 text-xs rounded-md">Search</Button>
                            <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="h-10 w-10 shrink-0 rounded-md"
                                onClick={() => setShowFilters(!showFilters)}
                            >
                                <Filter className="h-3.5 w-3.5" />
                            </Button>
                        </form>

                        {/* Filter bar */}
                        {showFilters && (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 pt-3 border-t">
                                <div>
                                    <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Court</label>
                                    <select
                                        value={court}
                                        onChange={(e) => setCourt(e.target.value)}
                                        className="w-full h-8 text-xs bg-background border rounded-md px-2"
                                    >
                                        <option value="">All courts</option>
                                        {facets?.courts.map((c) => <option key={c} value={c}>{c}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Case Type</label>
                                    <select
                                        value={caseType}
                                        onChange={(e) => setCaseType(e.target.value)}
                                        className="w-full h-8 text-xs bg-background border rounded-md px-2"
                                    >
                                        <option value="">All types</option>
                                        {facets?.case_types.map((t) => <option key={t} value={t}>{t}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Year From</label>
                                    <Input type="number" value={yearFrom} onChange={(e) => setYearFrom(e.target.value)} placeholder="1950" className="h-8 text-xs" />
                                </div>
                                <div>
                                    <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Year To</label>
                                    <Input type="number" value={yearTo} onChange={(e) => setYearTo(e.target.value)} placeholder="2025" className="h-8 text-xs" />
                                </div>
                            </div>
                        )}

                        {/* Active filter pills */}
                        {(court || caseType || yearFrom || yearTo) && (
                            <div className="flex flex-wrap gap-1.5 mt-2">
                                {court && (
                                    <Badge variant="secondary" className="text-[11px] gap-1 cursor-pointer" onClick={() => setCourt("")}>
                                        {court} <X className="h-3 w-3" />
                                    </Badge>
                                )}
                                {caseType && (
                                    <Badge variant="secondary" className="text-[11px] gap-1 cursor-pointer" onClick={() => setCaseType("")}>
                                        {caseType} <X className="h-3 w-3" />
                                    </Badge>
                                )}
                                {yearFrom && (
                                    <Badge variant="secondary" className="text-[11px] gap-1 cursor-pointer" onClick={() => setYearFrom("")}>
                                        From {yearFrom} <X className="h-3 w-3" />
                                    </Badge>
                                )}
                                {yearTo && (
                                    <Badge variant="secondary" className="text-[11px] gap-1 cursor-pointer" onClick={() => setYearTo("")}>
                                        To {yearTo} <X className="h-3 w-3" />
                                    </Badge>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* Results */}
                <div className="mx-auto max-w-5xl px-4 py-6">
                    {/* Query understanding */}
                    {results?.query_understanding && results.query_understanding.intent !== "general" && (
                        <div className="mb-4 text-xs text-muted-foreground border-l-2 border-[var(--gold)] pl-3 py-1">
                            <span className="uppercase tracking-wider font-medium">
                                {results.query_understanding.intent.replace("_", " ")}
                            </span>
                            {results.query_understanding.expanded_query !== results.query_understanding.original_query && (
                                <span className="ml-2 text-muted-foreground/70">
                                    — expanded to: &ldquo;{results.query_understanding.expanded_query}&rdquo;
                                </span>
                            )}
                        </div>
                    )}

                    {/* Loading */}
                    {loading && (
                        <div className="flex items-center justify-center py-20">
                            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                            <span className="ml-2 text-sm text-muted-foreground">Searching…</span>
                        </div>
                    )}

                    {/* Error */}
                    {error && (
                        <div className="text-center py-20">
                            <p className="text-sm text-destructive">{error}</p>
                            <Button variant="outline" size="sm" className="mt-3 text-xs" onClick={() => executeSearch(query, page)}>
                                Retry
                            </Button>
                        </div>
                    )}

                    {/* Results header */}
                    {results && !loading && (
                        <>
                            <div className="flex items-center justify-between mb-4">
                                <span className="text-xs text-muted-foreground">
                                    {results.total_count} result{results.total_count !== 1 && "s"}
                                </span>
                            </div>

                            {/* Result cards */}
                            {results.results.length === 0 ? (
                                <div className="text-center py-16">
                                    <p className="text-sm text-muted-foreground">No results found.</p>
                                    <p className="text-xs text-muted-foreground/60 mt-1">Try different search terms or adjust filters.</p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {results.results.map((r) => (
                                        <Card
                                            key={r.case_id}
                                            className="p-4 hover:shadow-sm cursor-pointer border rounded-md"
                                            onClick={() => router.push(`/case/${r.case_id}`)}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="flex-1 min-w-0">
                                                    <h3 className="text-sm font-semibold leading-snug line-clamp-2 font-[family-name:var(--font-lora)]">
                                                        {r.title || "Untitled Case"}
                                                    </h3>
                                                    <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                                                        {r.citation && (
                                                            <Badge variant="outline" className="text-[10px] font-normal">
                                                                {r.citation}
                                                            </Badge>
                                                        )}
                                                        {r.court && (
                                                            <span className="text-[11px] text-muted-foreground">{r.court}</span>
                                                        )}
                                                        {r.year && (
                                                            <span className="text-[11px] text-muted-foreground">· {r.year}</span>
                                                        )}
                                                        {r.case_type && (
                                                            <span className="text-[11px] text-muted-foreground">· {r.case_type}</span>
                                                        )}
                                                    </div>
                                                    {r.snippet && (
                                                        <p className="text-xs text-muted-foreground mt-2 line-clamp-2 leading-relaxed">
                                                            {r.snippet}
                                                        </p>
                                                    )}
                                                </div>
                                                <div className="text-right shrink-0">
                                                    <div className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">Score</div>
                                                    <div className="text-sm font-medium tabular-nums">{r.score.toFixed(2)}</div>
                                                </div>
                                            </div>
                                        </Card>
                                    ))}
                                </div>
                            )}

                            {/* Pagination */}
                            {totalPages > 1 && (
                                <div className="flex items-center justify-center gap-2 mt-6">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-8 text-xs"
                                        onClick={() => handlePageChange(page - 1)}
                                        disabled={page <= 1}
                                    >
                                        <ChevronLeft className="h-3.5 w-3.5" />
                                    </Button>
                                    <span className="text-xs text-muted-foreground tabular-nums px-2">
                                        {page} / {totalPages}
                                    </span>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-8 text-xs"
                                        onClick={() => handlePageChange(page + 1)}
                                        disabled={page >= totalPages}
                                    >
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </Button>
                                </div>
                            )}
                        </>
                    )}

                    {/* Empty state — no query */}
                    {!results && !loading && !error && (
                        <div className="text-center py-20">
                            <Search className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
                            <p className="text-sm text-muted-foreground">Enter a query to search Indian case law.</p>
                        </div>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
}

export default function SearchPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen flex items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
        }>
            <SearchContent />
        </Suspense>
    );
}
