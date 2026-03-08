"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { search as apiSearch, searchFacets } from "@/lib/api";
import type { SearchResponse, FacetsResponse, JudgmentSection } from "@/lib/types";
import { Search, ChevronLeft, ChevronRight, Filter, X, Loader2, AlertTriangle, Download } from "lucide-react";
import { PrecedentBadge } from "@/components/precedent-badge";
import { BenchStrength } from "@/components/bench-strength";
import { EquivalentCitations } from "@/components/equivalent-citations";
import { ConfidenceMeter } from "@/components/confidence-meter";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { SearchResultSkeleton } from "@/components/skeleton";

const SECTION_TABS: { value: JudgmentSection; label: string }[] = [
    { value: "FACTS", label: "Facts" },
    { value: "ISSUES", label: "Issues" },
    { value: "ARGUMENTS", label: "Arguments" },
    { value: "HOLDINGS", label: "Holdings" },
    { value: "REASONING", label: "Reasoning" },
    { value: "ORDER", label: "Order" },
];

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
    const [sectionFilter, setSectionFilter] = useState<JudgmentSection | null>(null);

    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
                section: sectionFilter || undefined,
            });
            setResults(res);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Search failed");
        } finally {
            setLoading(false);
        }
    }, [court, yearFrom, yearTo, caseType, sectionFilter]);

    // Initial search from URL params
    useEffect(() => {
        if (initialQuery) {
            executeSearch(initialQuery, 1);
            setQuery(initialQuery);
        }
    }, [initialQuery, executeSearch]);

    useEffect(() => {
        searchFacets().then(setFacets).catch(() => { });
    }, []);

    // Auto-apply filters with 300ms debounce (Gap 3)
    const isInitialMount = useRef(true);
    useEffect(() => {
        if (isInitialMount.current) {
            isInitialMount.current = false;
            return;
        }
        if (!query.trim()) return;
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
            setPage(1);
            executeSearch(query.trim(), 1);
        }, 300);
        return () => {
            if (debounceRef.current) clearTimeout(debounceRef.current);
        };
    }, [court, yearFrom, yearTo, caseType, sectionFilter]); // eslint-disable-line react-hooks/exhaustive-deps

    // Compute low-relevance signal (Gap 12)
    const allLowRelevance = results && results.results.length > 0 &&
        results.results.every((r) => r.score < 0.3);

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

    function exportResults() {
        if (!results || results.results.length === 0) return;

        let md = `# Search Results: "${query}"\n\n`;
        md += `*${results.results.length} of ${results.total_count} results shown*\n\n---\n\n`;

        results.results.forEach((r, i) => {
            md += `## ${i + 1}. ${r.title || "Untitled"}\n\n`;
            if (r.citation) md += `**Citation:** ${r.citation}\n`;
            if (r.court) md += `**Court:** ${r.court}\n`;
            if (r.year || r.date) md += `**Year:** ${r.year || r.date}\n`;
            if (r.case_type) md += `**Case Type:** ${r.case_type}\n`;
            if (r.score) md += `**Relevance:** ${(r.score * 100).toFixed(0)}%\n`;
            md += `\n`;
            if (r.snippet) md += `> ${r.snippet}\n\n`;
            md += `---\n\n`;
        });

        const blob = new Blob([md], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `smriti-search-${new Date().toISOString().slice(0, 10)}.md`;
        a.click();
        URL.revokeObjectURL(url);
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
                                <label htmlFor="search-input" className="sr-only">Search Indian case law</label>
                                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                                <Input
                                    id="search-input"
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    placeholder="Search Indian case law…"
                                    maxLength={500}
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
                                aria-label={showFilters ? "Hide filters" : "Show filters"}
                            >
                                <Filter className="h-3.5 w-3.5" />
                            </Button>
                        </form>

                        {/* Section pill tabs — always visible (Gap 2) */}
                        <div className="flex flex-wrap items-center gap-1.5 mt-3" role="tablist" aria-label="Filter by judgment section">
                            <button
                                type="button"
                                role="tab"
                                aria-selected={!sectionFilter}
                                onClick={() => setSectionFilter(null)}
                                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                                    !sectionFilter
                                        ? "bg-primary text-primary-foreground border-primary"
                                        : "bg-background text-muted-foreground border-border hover:border-primary/50"
                                }`}
                            >
                                All Sections
                            </button>
                            {SECTION_TABS.map((s) => (
                                <button
                                    key={s.value}
                                    type="button"
                                    role="tab"
                                    aria-selected={sectionFilter === s.value}
                                    onClick={() => setSectionFilter(sectionFilter === s.value ? null : s.value)}
                                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                                        sectionFilter === s.value
                                            ? "bg-primary text-primary-foreground border-primary"
                                            : "bg-background text-muted-foreground border-border hover:border-primary/50"
                                    }`}
                                >
                                    {s.label}
                                </button>
                            ))}
                        </div>

                        {/* Filter bar (court, case type, years) */}
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
                                    <Input type="number" value={yearFrom} onChange={(e) => setYearFrom(e.target.value)} placeholder="1950" min={1950} max={2026} className="h-8 text-xs" />
                                </div>
                                <div>
                                    <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Year To</label>
                                    <Input type="number" value={yearTo} onChange={(e) => setYearTo(e.target.value)} placeholder="2026" min={1950} max={2026} className="h-8 text-xs" />
                                </div>
                            </div>
                        )}

                        {/* Active filter pills */}
                        {(court || caseType || yearFrom || yearTo || sectionFilter) && (
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
                                {sectionFilter && (
                                    <Badge variant="secondary" className="text-[11px] gap-1 cursor-pointer" onClick={() => setSectionFilter(null)}>
                                        {sectionFilter} <X className="h-3 w-3" />
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
                    {loading && <SearchResultSkeleton />}

                    {/* Error */}
                    {error && (
                        <div className="text-center py-20" role="alert">
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
                                {results.results.length > 0 && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-7 text-xs gap-1.5"
                                        onClick={exportResults}
                                    >
                                        <Download className="h-3 w-3" />
                                        Export Results
                                    </Button>
                                )}
                            </div>

                            {/* Low-relevance banner (Gap 12) */}
                            {allLowRelevance && (
                                <div className="flex items-center gap-2 mb-4 p-3 rounded-md border border-yellow-500/30 bg-yellow-50 dark:bg-yellow-950/20 text-yellow-800 dark:text-yellow-200" role="alert">
                                    <AlertTriangle className="h-4 w-4 shrink-0" />
                                    <p className="text-xs">
                                        No highly relevant results found. Try broadening your search terms or adjusting filters.
                                    </p>
                                </div>
                            )}

                            {/* Result cards */}
                            {results.results.length === 0 ? (
                                <div className="text-center py-12">
                                    <Search className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
                                    <h3 className="text-lg font-medium mb-2">No results found</h3>
                                    <p className="text-sm text-muted-foreground mb-4">Try these suggestions:</p>
                                    <ul className="text-sm text-muted-foreground space-y-1">
                                        <li>Use broader search terms (e.g., &ldquo;right to privacy&rdquo; instead of specific case names)</li>
                                        <li>Remove filters to widen your search</li>
                                        <li>Check spelling of legal terms</li>
                                        <li>Try searching by citation number (e.g., &ldquo;AIR 2017 SC 4161&rdquo;)</li>
                                    </ul>
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
                                                    <div className="flex items-center gap-2">
                                                        <h3 className="text-sm font-semibold leading-snug line-clamp-2 font-[family-name:var(--font-lora)]" title={r.title || "Untitled Case"}>
                                                            {r.title || "Untitled Case"}
                                                        </h3>
                                                        {r.precedent_strength && (
                                                            <PrecedentBadge strength={r.precedent_strength} />
                                                        )}
                                                    </div>
                                                    <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                                                        {r.citation && (
                                                            <Badge variant="outline" className="text-[10px] font-normal">
                                                                {r.citation}
                                                            </Badge>
                                                        )}
                                                        {r.court && (
                                                            <span className="text-[11px] text-muted-foreground">{r.court}</span>
                                                        )}
                                                        {r.bench_type && (
                                                            <BenchStrength benchType={r.bench_type} />
                                                        )}
                                                        {r.year && (
                                                            <span className="text-[11px] text-muted-foreground">· {r.year}</span>
                                                        )}
                                                        {r.case_type && (
                                                            <span className="text-[11px] text-muted-foreground">· {r.case_type}</span>
                                                        )}
                                                    </div>
                                                    {r.equivalent_citations && r.equivalent_citations.length > 0 && (
                                                        <EquivalentCitations
                                                            citations={r.equivalent_citations}
                                                            primaryCitation={r.citation}
                                                            className="mt-1"
                                                        />
                                                    )}
                                                    {r.snippet && (
                                                        <p className="text-xs text-muted-foreground mt-2 line-clamp-2 leading-relaxed">
                                                            {/* Section label pill (Gap 5) */}
                                                            {r.section_type && (
                                                                <span className="inline-flex items-center mr-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-muted text-muted-foreground/80 align-middle">
                                                                    {r.section_type}
                                                                </span>
                                                            )}
                                                            {r.snippet}
                                                        </p>
                                                    )}
                                                </div>
                                                {/* ConfidenceMeter replacing raw score (Gap 18) */}
                                                <div className="shrink-0 pt-0.5">
                                                    <ConfidenceMeter score={r.score} />
                                                </div>
                                            </div>
                                        </Card>
                                    ))}
                                </div>
                            )}

                            <LegalDisclaimer className="mt-4" />

                            {/* Pagination */}
                            {totalPages > 1 && (
                                <div className="flex items-center justify-center gap-2 mt-6">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-8 text-xs"
                                        onClick={() => handlePageChange(page - 1)}
                                        disabled={page <= 1}
                                        aria-label="Previous page"
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
                                        aria-label="Next page"
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
            <div className="min-h-screen flex flex-col">
                <Header />
                <div className="mx-auto max-w-5xl px-4 py-6 flex-1">
                    <SearchResultSkeleton />
                </div>
            </div>
        }>
            <SearchContent />
        </Suspense>
    );
}
