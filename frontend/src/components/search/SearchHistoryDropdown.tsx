"use client";

import { useCallback, useEffect, useState } from "react";
import { Clock, Loader2, Star, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
    deleteSearchHistoryEntry,
    getSearchHistory,
    toggleSearchBookmark,
} from "@/lib/api";
import type { SearchHistoryEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SearchHistoryDropdownProps {
    onSelectQuery: (query: string, filters?: Record<string, unknown>) => void;
    isOpen: boolean;
    onClose: () => void;
}

const MAX_ITEMS = 10;

export function SearchHistoryDropdown({
    onSelectQuery,
    isOpen,
    onClose,
}: SearchHistoryDropdownProps) {
    const [entries, setEntries] = useState<SearchHistoryEntry[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!isOpen) return;
        let cancelled = false;
        setLoading(true);
        getSearchHistory(1, MAX_ITEMS)
            .then(({ history }) => {
                if (!cancelled) {
                    // Sort: bookmarked first, then by created_at desc
                    const sorted = [...history].sort((a, b) => {
                        if (a.is_bookmarked !== b.is_bookmarked) {
                            return a.is_bookmarked ? -1 : 1;
                        }
                        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
                    });
                    setEntries(sorted.slice(0, MAX_ITEMS));
                }
            })
            .catch(() => {
                if (!cancelled) setEntries([]);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [isOpen]);

    const handleToggleBookmark = useCallback(
        async (e: React.MouseEvent, entry: SearchHistoryEntry) => {
            e.stopPropagation();
            try {
                const result = await toggleSearchBookmark(entry.id);
                setEntries((prev) =>
                    prev.map((item) =>
                        item.id === entry.id
                            ? { ...item, is_bookmarked: result.is_bookmarked }
                            : item,
                    ),
                );
            } catch {
                // Silently fail — user can retry
            }
        },
        [],
    );

    const handleDelete = useCallback(
        async (e: React.MouseEvent, entryId: string) => {
            e.stopPropagation();
            try {
                await deleteSearchHistoryEntry(entryId);
                setEntries((prev) => prev.filter((item) => item.id !== entryId));
            } catch {
                // Silently fail — user can retry
            }
        },
        [],
    );

    if (!isOpen) return null;

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 z-40"
                onClick={onClose}
                aria-hidden="true"
            />

            {/* Dropdown panel */}
            <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-md border bg-popover shadow-md">
                {loading ? (
                    <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading history...
                    </div>
                ) : entries.length === 0 ? (
                    <div className="py-6 text-center text-sm text-muted-foreground">
                        No search history
                    </div>
                ) : (
                    <ul className="max-h-80 overflow-y-auto py-1">
                        {entries.map((entry) => (
                            <li key={entry.id}>
                                <button
                                    type="button"
                                    onClick={() => {
                                        onSelectQuery(
                                            entry.query,
                                            entry.filters ?? undefined,
                                        );
                                        onClose();
                                    }}
                                    className="group flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-accent"
                                >
                                    <Clock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                    <span className="flex-1 truncate">
                                        {entry.query}
                                    </span>

                                    {/* Bookmark toggle */}
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-6 w-6 shrink-0"
                                        onClick={(e) => handleToggleBookmark(e, entry)}
                                        aria-label={
                                            entry.is_bookmarked
                                                ? "Remove bookmark"
                                                : "Bookmark query"
                                        }
                                    >
                                        <Star
                                            className={cn(
                                                "h-3.5 w-3.5",
                                                entry.is_bookmarked
                                                    ? "fill-yellow-400 text-yellow-400"
                                                    : "text-muted-foreground",
                                            )}
                                        />
                                    </Button>

                                    {/* Delete button */}
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100"
                                        onClick={(e) => handleDelete(e, entry.id)}
                                        aria-label={`Delete search: ${entry.query}`}
                                    >
                                        <X className="h-3.5 w-3.5 text-muted-foreground" />
                                    </Button>
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </>
    );
}
