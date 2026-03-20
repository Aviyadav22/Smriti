"use client";

import { Clock, RefreshCw } from "lucide-react";

interface SemanticCacheBannerProps {
    originalQuery: string;
    cachedAt: number;
    cacheType: "exact" | "semantic";
    onRunFresh?: () => void;
}

export function SemanticCacheBanner({
    originalQuery,
    cachedAt,
    cacheType,
    onRunFresh,
}: SemanticCacheBannerProps) {
    const timestamp = cachedAt
        ? new Date(cachedAt * 1000).toLocaleString()
        : "unknown";

    if (cacheType === "exact") {
        return (
            <div className="flex items-start gap-2 px-4 py-3 rounded-lg text-sm bg-blue-50 dark:bg-blue-950/20 text-blue-800 dark:text-blue-300">
                <Clock className="h-4 w-4 shrink-0 mt-0.5" />
                <div className="flex-1">
                    <p>Showing cached result from {timestamp}</p>
                    {onRunFresh && (
                        <button
                            onClick={onRunFresh}
                            className="mt-1 text-xs underline opacity-75 hover:opacity-100 inline-flex items-center gap-1"
                        >
                            <RefreshCw className="h-3 w-3" />
                            Run Fresh
                        </button>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className="flex items-start gap-2 px-4 py-3 rounded-lg text-sm bg-purple-50 dark:bg-purple-950/20 text-purple-800 dark:text-purple-300">
            <Clock className="h-4 w-4 shrink-0 mt-0.5" />
            <div className="flex-1">
                <p>
                    Similar query found in cache
                    {originalQuery && (
                        <span className="opacity-75"> (original: &ldquo;{originalQuery}&rdquo;)</span>
                    )}
                </p>
                <p className="text-xs mt-0.5 opacity-75">
                    Cached {timestamp}
                </p>
                {onRunFresh && (
                    <button
                        onClick={onRunFresh}
                        className="mt-1 text-xs underline opacity-75 hover:opacity-100 inline-flex items-center gap-1"
                    >
                        <RefreshCw className="h-3 w-3" />
                        Run Fresh
                    </button>
                )}
            </div>
        </div>
    );
}
