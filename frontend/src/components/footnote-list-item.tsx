"use client";

import { Scale, Globe, BookOpen, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ResearchFootnote } from "@/lib/types";

interface FootnoteListItemProps {
    footnote: ResearchFootnote;
    isSelected: boolean;
    onClick: () => void;
}

const SOURCE_CONFIG: Record<string, { icon: typeof Scale; color: string }> = {
    Case: {
        icon: Scale,
        color: "bg-green-500/15 text-green-700 dark:text-green-400",
    },
    Web: {
        icon: Globe,
        color: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
    },
    Statute: {
        icon: BookOpen,
        color: "bg-purple-500/15 text-purple-700 dark:text-purple-400",
    },
    Constitution: {
        icon: BookOpen,
        color: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    },
};

const FALLBACK_CONFIG = {
    icon: FileText,
    color: "bg-muted text-muted-foreground",
};

export function FootnoteListItem({
    footnote,
    isSelected,
    onClick,
}: FootnoteListItemProps) {
    const config = SOURCE_CONFIG[footnote.source_label] ?? FALLBACK_CONFIG;
    const SourceIcon = config.icon;

    const displayTitle = footnote.title || footnote.citation;

    const secondaryParts: string[] = [];
    if (footnote.citation && footnote.title) {
        secondaryParts.push(footnote.citation);
    }
    if (footnote.court) {
        secondaryParts.push(footnote.court);
    }
    if (footnote.year) {
        secondaryParts.push(String(footnote.year));
    }
    const secondaryText = secondaryParts.join(" \u00b7 ");

    return (
        <button
            type="button"
            onClick={onClick}
            className={cn(
                "w-full text-left px-3 py-2.5 flex items-start gap-3 rounded-md transition-colors",
                "hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                isSelected
                    ? "border-l-2 border-l-[var(--gold)] bg-muted/40"
                    : "border-l-2 border-l-transparent"
            )}
        >
            {/* Number badge */}
            <span
                className={cn(
                    "shrink-0 flex items-center justify-center h-6 w-6 rounded-full text-xs font-semibold mt-0.5",
                    isSelected
                        ? "bg-[var(--gold)] text-white"
                        : "bg-muted text-muted-foreground"
                )}
            >
                {footnote.number}
            </span>

            {/* Text content */}
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium leading-snug line-clamp-2">
                    {displayTitle}
                </p>
                {secondaryText && (
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">
                        {secondaryText}
                    </p>
                )}
            </div>

            {/* Source label badge */}
            <Badge
                variant="outline"
                className={cn(
                    "shrink-0 mt-0.5 border-0 text-[10px] font-medium gap-1",
                    config.color
                )}
            >
                <SourceIcon className="h-3 w-3" />
                {footnote.source_label}
            </Badge>
        </button>
    );
}
