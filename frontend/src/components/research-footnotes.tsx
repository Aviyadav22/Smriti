"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, ExternalLink, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import type { ResearchFootnote } from "@/lib/types";

interface ResearchFootnotesProps {
    footnotes: ResearchFootnote[];
}

const STATUS_CONFIG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    verified_pg: { icon: CheckCircle2, color: "text-green-500", label: "Verified (Database)" },
    verified_ik: { icon: CheckCircle2, color: "text-green-500", label: "Verified (Indian Kanoon)" },
    verified_neo4j: { icon: CheckCircle2, color: "text-green-500", label: "Verified (Citation Graph)" },
    unverified: { icon: XCircle, color: "text-red-500", label: "Unverified" },
    removed: { icon: XCircle, color: "text-red-500", label: "Removed" },
};

export function ResearchFootnotes({ footnotes }: ResearchFootnotesProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [hoveredFn, setHoveredFn] = useState<number | null>(null);

    const usedFootnotes = footnotes.filter((fn) => fn.is_used);
    const unusedFootnotes = footnotes.filter((fn) => !fn.is_used);

    if (footnotes.length === 0) return null;

    return (
        <div className="border rounded-lg bg-card">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium text-left hover:bg-muted/50 transition-colors"
            >
                {isOpen ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                Footnotes & Sources
                <span className="ml-auto text-xs text-muted-foreground">
                    {usedFootnotes.length} cited, {unusedFootnotes.length} unused
                </span>
            </button>

            {isOpen && (
                <div className="px-4 pb-3 space-y-3">
                    {/* Cited footnotes */}
                    {usedFootnotes.length > 0 && (
                        <div className="space-y-2">
                            <h4 className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                                Cited Sources
                            </h4>
                            {usedFootnotes.map((fn) => {
                                const status = STATUS_CONFIG[fn.verification_status] || STATUS_CONFIG.unverified;
                                const StatusIcon = status.icon;
                                return (
                                    <div
                                        key={fn.number}
                                        className="relative text-xs border-l-2 border-muted pl-3 py-1"
                                        onMouseEnter={() => setHoveredFn(fn.number)}
                                        onMouseLeave={() => setHoveredFn(null)}
                                    >
                                        <div className="flex items-start gap-1.5">
                                            <span className="font-mono text-muted-foreground shrink-0">[{fn.number}]</span>
                                            {fn.case_id ? (
                                                <Link
                                                    href={`/case/${fn.case_id}`}
                                                    className="text-[var(--gold)] underline underline-offset-2 hover:text-[var(--gold)]/80"
                                                >
                                                    {fn.citation}
                                                </Link>
                                            ) : fn.source_url ? (
                                                <a
                                                    href={fn.source_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-[var(--gold)] underline underline-offset-2 hover:text-[var(--gold)]/80 inline-flex items-center gap-1"
                                                >
                                                    {fn.citation}
                                                    <ExternalLink className="h-3 w-3" />
                                                </a>
                                            ) : (
                                                <span>{fn.citation}</span>
                                            )}
                                            <StatusIcon className={`h-3.5 w-3.5 shrink-0 ml-auto ${status.color}`} title={status.label} />
                                        </div>
                                        {/* Hover preview */}
                                        {hoveredFn === fn.number && fn.excerpt && (
                                            <div className="mt-1 text-muted-foreground italic leading-relaxed line-clamp-3">
                                                &quot;{fn.excerpt}&quot;
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Unused sources */}
                    {unusedFootnotes.length > 0 && (
                        <div className="space-y-1">
                            <h4 className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                                Searched but Not Cited
                            </h4>
                            {unusedFootnotes.slice(0, 10).map((fn) => (
                                <div key={fn.number} className="text-xs text-muted-foreground pl-3">
                                    <span className="font-mono">[{fn.number}]</span> {fn.citation}
                                    {fn.verification_status === "unverified" && (
                                        <AlertCircle className="h-3 w-3 inline ml-1 text-amber-500" />
                                    )}
                                </div>
                            ))}
                            {unusedFootnotes.length > 10 && (
                                <div className="text-xs text-muted-foreground pl-3">
                                    ...and {unusedFootnotes.length - 10} more
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
