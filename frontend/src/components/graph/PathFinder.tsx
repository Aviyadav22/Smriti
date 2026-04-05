"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PathResult, SearchResultItem } from "@/lib/types";
import { search, getGraphPath } from "@/lib/api";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PathFinderProps {
    onPathFound: (result: PathResult) => void;
    loading: boolean;
    setLoading: (l: boolean) => void;
}

// ---------------------------------------------------------------------------
// Debounce hook
// ---------------------------------------------------------------------------

function useDebouncedValue<T>(value: T, delay: number): T {
    const [debounced, setDebounced] = useState(value);
    useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);
    return debounced;
}

// ---------------------------------------------------------------------------
// Case search input sub-component
// ---------------------------------------------------------------------------

interface CaseSearchInputProps {
    label: string;
    selectedId: string | null;
    selectedTitle: string | null;
    onSelect: (id: string, title: string) => void;
    onClear: () => void;
}

function CaseSearchInput({
    label,
    selectedId,
    selectedTitle,
    onSelect,
    onClear,
}: CaseSearchInputProps) {
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<SearchResultItem[]>([]);
    const [open, setOpen] = useState(false);
    const [searching, setSearching] = useState(false);
    const debouncedQuery = useDebouncedValue(query, 300);
    const abortRef = useRef<AbortController | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Close dropdown on outside click
    useEffect(() => {
        function handleClickOutside(e: MouseEvent) {
            if (
                containerRef.current &&
                !containerRef.current.contains(e.target as Node)
            ) {
                setOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Search on debounced query
    useEffect(() => {
        if (debouncedQuery.length < 3) {
            setResults([]);
            setOpen(false);
            return;
        }

        // Cancel previous request
        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;

        setSearching(true);
        search({ q: debouncedQuery, page_size: 8, signal: controller.signal })
            .then((res) => {
                setResults(res.results);
                setOpen(true);
            })
            .catch(() => {
                // Ignore abort errors
            })
            .finally(() => setSearching(false));

        return () => controller.abort();
    }, [debouncedQuery]);

    if (selectedId) {
        return (
            <div className="flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2">
                <span className="flex-1 truncate text-sm text-stone-800">
                    {selectedTitle ?? selectedId}
                </span>
                <button
                    type="button"
                    onClick={() => {
                        onClear();
                        setQuery("");
                    }}
                    className="text-xs text-stone-400 hover:text-stone-600"
                >
                    &#x2715;
                </button>
            </div>
        );
    }

    return (
        <div ref={containerRef} className="relative">
            <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={label}
                className="w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-800 placeholder:text-stone-400 focus:border-stone-500 focus:outline-none focus:ring-1 focus:ring-stone-500"
            />
            {searching && (
                <div className="absolute right-3 top-2.5">
                    <div className="h-4 w-4 animate-spin rounded-full border border-stone-300 border-t-stone-600" />
                </div>
            )}

            {/* Dropdown */}
            {open && results.length > 0 && (
                <ul className="absolute z-20 mt-1 max-h-40 w-full overflow-y-auto rounded-md border border-stone-200 bg-white shadow-lg">
                    {results.map((r) => (
                        <li key={r.case_id}>
                            <button
                                type="button"
                                className="w-full px-3 py-2 text-left text-sm hover:bg-stone-50"
                                onClick={() => {
                                    onSelect(r.case_id, r.title ?? r.citation ?? r.case_id);
                                    setOpen(false);
                                    setQuery("");
                                }}
                            >
                                <p className="truncate font-medium text-stone-800">
                                    {r.title ?? "Untitled"}
                                </p>
                                <p className="truncate text-xs text-stone-400">
                                    {r.citation} {r.year ? `(${r.year})` : ""}
                                </p>
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PathFinder({
    onPathFound,
    loading,
    setLoading,
}: PathFinderProps) {
    const [fromId, setFromId] = useState<string | null>(null);
    const [fromTitle, setFromTitle] = useState<string | null>(null);
    const [toId, setToId] = useState<string | null>(null);
    const [toTitle, setToTitle] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleFindPath = useCallback(async () => {
        if (!fromId || !toId) return;
        setLoading(true);
        setError(null);
        try {
            const result = await getGraphPath(fromId, toId);
            onPathFound(result);
        } catch (err: unknown) {
            const message =
                err instanceof Error ? err.message : "Failed to find path";
            setError(message);
        } finally {
            setLoading(false);
        }
    }, [fromId, toId, onPathFound, setLoading]);

    return (
        <div className="rounded-lg border border-stone-200 bg-stone-50 p-4">
            <h3 className="mb-3 text-sm font-semibold text-stone-700">
                Find Citation Path
            </h3>
            <div className="space-y-3">
                <CaseSearchInput
                    label="From case..."
                    selectedId={fromId}
                    selectedTitle={fromTitle}
                    onSelect={(id, title) => {
                        setFromId(id);
                        setFromTitle(title);
                    }}
                    onClear={() => {
                        setFromId(null);
                        setFromTitle(null);
                    }}
                />
                <CaseSearchInput
                    label="To case..."
                    selectedId={toId}
                    selectedTitle={toTitle}
                    onSelect={(id, title) => {
                        setToId(id);
                        setToTitle(title);
                    }}
                    onClear={() => {
                        setToId(null);
                        setToTitle(null);
                    }}
                />
                <button
                    type="button"
                    disabled={!fromId || !toId || loading}
                    onClick={handleFindPath}
                    className="w-full rounded-md bg-stone-800 px-4 py-2 text-sm font-medium text-white transition hover:bg-stone-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {loading ? "Searching..." : "Find Path"}
                </button>
                {error && (
                    <p className="text-xs text-red-600">{error}</p>
                )}
            </div>
        </div>
    );
}
