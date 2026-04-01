"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Check, CheckCircle2, ChevronDown, Clipboard, Copy, Download, HelpCircle, Info, Link as LinkIcon, Loader2, Pencil, Share2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { createMemoShare, getMemoShareStatus, revokeMemoShare } from "@/lib/api";
import type { ResearchFootnote } from "@/lib/types";

/** Verification status for a footnote — maps to color. */
type FootnoteVerification = "verified_pg" | "verified_ik" | "verified_neo4j" | "unverified" | "removed" | "flagged";

const VERIFICATION_COLORS: Record<string, string> = {
    verified_pg: "bg-green-500/20 text-green-700 dark:text-green-400",
    verified_ik: "bg-green-500/20 text-green-700 dark:text-green-400",
    verified_neo4j: "bg-green-500/20 text-green-700 dark:text-green-400",
    unverified: "bg-gray-400/20 text-gray-600 dark:text-gray-400",
    removed: "bg-red-500/20 text-red-700 dark:text-red-400 line-through",
    flagged: "bg-amber-500/20 text-amber-700 dark:text-amber-400",
};

const VERIFICATION_LABELS: Record<string, string> = {
    verified_pg: "Verified (database)",
    verified_ik: "Verified (Indian Kanoon)",
    verified_neo4j: "Verified (citation graph)",
    unverified: "Not yet verified",
    removed: "Removed — could not verify",
    flagged: "Flagged — may be inaccurate",
};

interface AgentMemoViewerProps {
    content: string;
    confidence?: number;
    onFootnoteClick?: (num: number) => void;
    maxFootnote?: number;
    /** Map footnote number → verification status for color-coding. */
    footnoteVerification?: Record<number, FootnoteVerification>;
    /** 3-dimensional confidence breakdown from research agent. */
    confidenceBreakdown?: {
        data_confidence?: number;
        legal_confidence?: number;
        consistency_confidence?: number;
    };
    /** Execution ID for server-side export (DOCX/PDF). */
    executionId?: string;
    /** Callback to revise a section — (heading, feedback) => Promise that resolves with revised content. */
    onReviseSection?: (heading: string, feedback: string) => Promise<string | null>;
    /** Full footnotes data for hover previews. */
    footnotes?: ResearchFootnote[];
}

/** Regex to match UUID-style case IDs in the memo content. */
const CASE_ID_RE = /\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b/gi;

/**
 * Process a string to replace UUID case IDs with links and [^N] with footnote pills.
 */
function processTextNode(
    text: string,
    onFootnoteClick?: (n: number) => void,
    maxFootnote?: number,
    footnoteVerification?: Record<number, FootnoteVerification>,
    footnotesMap?: Map<number, ResearchFootnote>,
): React.ReactNode[] {
    const result: React.ReactNode[] = [];
    let keyCounter = 0;

    // Combined regex: match either UUID case IDs or [^N] footnotes
    const combined = /(\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|\[\^\d+\])/gi;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = combined.exec(text)) !== null) {
        if (match.index > lastIndex) {
            result.push(text.slice(lastIndex, match.index));
        }

        const token = match[0];
        const fnMatch = token.match(/^\[\^(\d+)\]$/);
        if (fnMatch && onFootnoteClick) {
            const num = parseInt(fnMatch[1], 10);
            if (num >= 1 && (maxFootnote === undefined || num <= maxFootnote)) {
                const status = footnoteVerification?.[num];
                const colorClass = status
                    ? VERIFICATION_COLORS[status] || ""
                    : "bg-[var(--gold)]/20 text-[var(--gold)]";
                const tooltip = status
                    ? `[${num}] ${VERIFICATION_LABELS[status] || status}`
                    : `View source [${num}]`;
                const fnData = footnotesMap?.get(num);
                const pill = (
                    <button
                        onClick={(e) => {
                            e.preventDefault();
                            onFootnoteClick(num);
                        }}
                        className={`inline-flex items-center justify-center min-w-6 min-h-6 px-1.5 rounded-full text-[11px] font-bold hover:opacity-80 transition-colors mx-0.5 align-super cursor-pointer focus-visible:ring-2 focus-visible:ring-ring ${colorClass}`}
                        title={tooltip}
                        aria-label={`Footnote ${num}, ${tooltip}`}
                    >
                        {num}
                    </button>
                );
                if (fnData) {
                    const isVerified = status?.startsWith("verified");
                    result.push(
                        <HoverCard key={`fn-${num}-${keyCounter++}`}>
                            <HoverCardTrigger asChild>{pill}</HoverCardTrigger>
                            <HoverCardContent side="top" className="w-72 text-sm space-y-1.5 p-3">
                                <p className="font-semibold text-foreground leading-snug line-clamp-2">{fnData.title || fnData.citation}</p>
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                    {fnData.court && <span>{fnData.court}</span>}
                                    {fnData.year && <span>{fnData.year}</span>}
                                    {fnData.source_label && (
                                        <Badge variant="outline" className="text-[10px] px-1 py-0">{fnData.source_label}</Badge>
                                    )}
                                </div>
                                {fnData.excerpt && (
                                    <p className="text-xs text-muted-foreground line-clamp-2 italic">&ldquo;{fnData.excerpt}&rdquo;</p>
                                )}
                                <div className="flex items-center gap-1 text-xs pt-0.5">
                                    {isVerified ? (
                                        <><CheckCircle2 className="h-3 w-3 text-green-600" /><span className="text-green-700 dark:text-green-400">Verified</span></>
                                    ) : (
                                        <><HelpCircle className="h-3 w-3 text-amber-500" /><span className="text-amber-600 dark:text-amber-400">Not yet verified</span></>
                                    )}
                                </div>
                            </HoverCardContent>
                        </HoverCard>
                    );
                } else {
                    result.push(
                        <React.Fragment key={`fn-${num}-${keyCounter++}`}>{pill}</React.Fragment>
                    );
                }
            } else {
                result.push(token);
            }
        } else if (CASE_ID_RE.test(token)) {
            // Reset regex lastIndex since .test advances it
            CASE_ID_RE.lastIndex = 0;
            result.push(
                <Link
                    key={`case-${token}-${keyCounter++}`}
                    href={`/case/${token}`}
                    className="text-[var(--gold)] underline underline-offset-2 hover:text-[var(--gold)]/80"
                    title="Click to view case details"
                >
                    {token}
                </Link>
            );
        } else {
            result.push(token);
        }
        lastIndex = combined.lastIndex;
    }

    if (lastIndex < text.length) {
        result.push(text.slice(lastIndex));
    }
    return result;
}

/**
 * Strip footnote definition lines from memo content.
 * These are rendered structurally by the footnotes panel, not inline.
 */
function stripFootnoteDefinitions(content: string): string {
    return content.replace(/^\[\^\d+\]:\s*.+$/gm, "").replace(/\n{3,}/g, "\n\n");
}

/** Extract h2 headings from markdown for TOC. */
function extractHeadings(md: string): string[] {
    const headings: string[] = [];
    for (const line of md.split("\n")) {
        const m = line.match(/^##\s+(.+)/);
        if (m) headings.push(m[1].trim());
    }
    return headings;
}

/** Slug for heading anchor IDs. */
function slugify(text: string): string {
    return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

/** Extract section content between h2 headings. */
function extractSectionContent(md: string, heading: string): string {
    const lines = md.split("\n");
    let start: number | null = null;
    let end: number | null = null;
    for (let i = 0; i < lines.length; i++) {
        const m = lines[i].match(/^##\s+(.+)/);
        if (m) {
            if (m[1].trim().toLowerCase() === heading.toLowerCase()) {
                start = i;
            } else if (start !== null && end === null) {
                end = i;
            }
        }
    }
    if (start === null) return "";
    return lines.slice(start, end ?? lines.length).join("\n").trim();
}

function MemoTOC({ headings }: { headings: string[] }) {
    const [activeId, setActiveId] = useState("");

    useEffect(() => {
        if (typeof window === "undefined") return;
        const observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        setActiveId(entry.target.id);
                    }
                }
            },
            { rootMargin: "-80px 0px -60% 0px", threshold: 0.1 },
        );
        const els = document.querySelectorAll(".memo-body h2[id], .memo-body div[id]");
        els.forEach((el) => observer.observe(el));
        return () => observer.disconnect();
    }, [headings]);

    return (
        <nav className="memo-toc hidden lg:block w-44 shrink-0 sticky top-20 self-start max-h-[calc(100vh-8rem)] overflow-y-auto">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Contents</p>
            <ul className="space-y-1">
                {headings.map((h) => (
                    <li key={h}>
                        <a
                            href={`#${slugify(h)}`}
                            className={cn(
                                "text-[11px] block truncate transition-colors",
                                activeId === slugify(h)
                                    ? "text-[var(--gold)] font-medium"
                                    : "text-muted-foreground hover:text-foreground",
                            )}
                            title={h}
                        >
                            {h}
                        </a>
                    </li>
                ))}
            </ul>
        </nav>
    );
}

export function AgentMemoViewer({ content, confidence, onFootnoteClick, maxFootnote, footnoteVerification, confidenceBreakdown, executionId, onReviseSection, footnotes }: AgentMemoViewerProps) {
    const [copied, setCopied] = useState(false);
    const [revisingSection, setRevisingSection] = useState<string | null>(null);
    const [revisionFeedback, setRevisionFeedback] = useState("");
    const [revisionLoading, setRevisionLoading] = useState(false);
    const [copiedSection, setCopiedSection] = useState<string | null>(null);
    const [shareUrl, setShareUrl] = useState<string | null>(null);
    const [sharing, setSharing] = useState(false);

    // Check share status on mount
    useEffect(() => {
        if (!executionId) return;
        getMemoShareStatus(executionId)
            .then((status) => {
                if (status.shared && status.share_url) {
                    setShareUrl(status.share_url);
                }
            })
            .catch(() => {
                // Not shared or endpoint unavailable — ignore
            });
    }, [executionId]);

    const handleShare = useCallback(async () => {
        if (!executionId) return;
        setSharing(true);
        try {
            const result = await createMemoShare(executionId);
            const fullUrl = window.location.origin + result.share_url;
            setShareUrl(result.share_url);
            await navigator.clipboard.writeText(fullUrl);
        } catch {
            // Share failed — could surface error to user in future
        } finally {
            setSharing(false);
        }
    }, [executionId]);

    const handleCopyShareUrl = useCallback(async () => {
        if (!shareUrl) return;
        const fullUrl = window.location.origin + shareUrl;
        try {
            await navigator.clipboard.writeText(fullUrl);
        } catch {
            // Clipboard API unavailable
        }
    }, [shareUrl]);

    const handleRevokeShare = useCallback(async () => {
        if (!executionId) return;
        try {
            await revokeMemoShare(executionId);
            setShareUrl(null);
        } catch {
            // Revoke failed
        }
    }, [executionId]);

    const headings = useMemo(() => extractHeadings(content), [content]);

    const footnotesMap = useMemo(() => {
        const m = new Map<number, ResearchFootnote>();
        footnotes?.forEach((f) => m.set(f.number, f));
        return m;
    }, [footnotes]);

    const handleCopy = useCallback(async () => {
        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Fallback for older browsers
            const ta = document.createElement("textarea");
            ta.value = content;
            ta.style.position = "fixed";
            ta.style.left = "-9999px";
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            document.body.removeChild(ta);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    }, [content]);

    const handleCopySection = useCallback(async (heading: string) => {
        const sectionText = extractSectionContent(content, heading);
        if (sectionText) {
            try {
                await navigator.clipboard.writeText(sectionText);
                setCopiedSection(heading);
                setTimeout(() => setCopiedSection(null), 2000);
            } catch {
                // Clipboard API unavailable (e.g. HTTP context)
            }
        }
    }, [content]);

    const handleDownload = useCallback(() => {
        const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "research-memo.md";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [content]);

    const cleanContent = useMemo(() => stripFootnoteDefinitions(content), [content]);

    // Custom markdown components to inject footnote pills and case links
    const components = useMemo(() => ({
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        p: ({ children, ...props }: any) => (
            <p className="text-base leading-relaxed mb-4" {...props}>
                {processChildren(children, onFootnoteClick, maxFootnote, footnoteVerification, footnotesMap)}
            </p>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        li: ({ children, ...props }: any) => (
            <li className="text-base leading-relaxed" {...props}>
                {processChildren(children, onFootnoteClick, maxFootnote, footnoteVerification, footnotesMap)}
            </li>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        h1: ({ children, ...props }: any) => (
            <h1 className="text-xl font-bold mt-6 mb-3" {...props}>{children}</h1>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        h2: ({ children, ...props }: any) => {
            const headingText = typeof children === "string" ? children : Array.isArray(children) ? children.join("") : String(children ?? "");
            return (
                <div className="mt-8 mb-2 border-t border-border/40 pt-5" id={slugify(headingText)}>
                    <div className="flex items-center gap-2 group">
                        <h2 className="text-lg font-semibold text-foreground" {...props}>{children}</h2>
                        <button
                            className="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity text-muted-foreground hover:text-foreground focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-ring rounded"
                            title={copiedSection === headingText ? "Copied!" : `Copy "${headingText}"`}
                            aria-label={copiedSection === headingText ? "Copied" : `Copy section: ${headingText}`}
                            onClick={() => handleCopySection(headingText)}
                        >
                            {copiedSection === headingText ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
                        </button>
                        {onReviseSection && (
                            <button
                                className="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity text-muted-foreground hover:text-foreground focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-ring rounded"
                                title={`Revise "${headingText}"`}
                                aria-label={`Revise section: ${headingText}`}
                                onClick={() => {
                                    setRevisingSection((prev) => prev === headingText ? null : headingText);
                                    setRevisionFeedback("");
                                }}
                            >
                                <Pencil className="h-3 w-3" />
                            </button>
                        )}
                    </div>
                    {revisingSection === headingText && (
                        <div className="flex gap-2 mt-1.5 mb-2">
                            <Input
                                className="flex-1 text-xs h-8"
                                placeholder="What should change in this section?"
                                value={revisionFeedback}
                                onChange={(e) => setRevisionFeedback(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && revisionFeedback.trim() && onReviseSection) {
                                        setRevisionLoading(true);
                                        onReviseSection(headingText, revisionFeedback.trim()).finally(() => {
                                            setRevisionLoading(false);
                                            setRevisingSection(null);
                                            setRevisionFeedback("");
                                        });
                                    }
                                }}
                                disabled={revisionLoading}
                            />
                            <Button
                                variant="outline"
                                size="sm"
                                className="text-xs h-7"
                                disabled={!revisionFeedback.trim() || revisionLoading}
                                onClick={() => {
                                    if (!onReviseSection) return;
                                    setRevisionLoading(true);
                                    onReviseSection(headingText, revisionFeedback.trim()).finally(() => {
                                        setRevisionLoading(false);
                                        setRevisingSection(null);
                                        setRevisionFeedback("");
                                    });
                                }}
                            >
                                {revisionLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : "Revise"}
                            </Button>
                        </div>
                    )}
                </div>
            );
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        h3: ({ children, ...props }: any) => (
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mt-4 mb-1.5" {...props}>{children}</h3>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        strong: ({ children, ...props }: any) => (
            <strong className="font-semibold text-foreground" {...props}>{children}</strong>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        blockquote: ({ children, ...props }: any) => (
            <blockquote className="border-l-2 border-[var(--gold)] pl-4 my-3 text-base text-muted-foreground italic" {...props}>
                {children}
            </blockquote>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ul: ({ children, ...props }: any) => (
            <ul className="list-disc list-outside pl-5 space-y-1.5 my-3" {...props}>{children}</ul>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ol: ({ children, ...props }: any) => (
            <ol className="list-decimal list-outside pl-5 space-y-1.5 my-3" {...props}>{children}</ol>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        table: ({ children, ...props }: any) => (
            <div className="overflow-x-auto my-2">
                <table className="text-sm border-collapse border border-border w-full" {...props}>{children}</table>
            </div>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        th: ({ children, ...props }: any) => (
            <th className="border border-border px-3 py-1.5 bg-muted text-left text-sm font-semibold" {...props}>{children}</th>
        ),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        td: ({ children, ...props }: any) => (
            <td className="border border-border px-3 py-1.5 text-sm" {...props}>{children}</td>
        ),
    }), [onFootnoteClick, maxFootnote, footnotesMap, onReviseSection, revisingSection, revisionFeedback, revisionLoading, copiedSection, handleCopySection]);

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
                {confidence !== undefined && (
                    <div className="flex items-center gap-2">
                        <Badge
                            variant={confidence >= 0.8 ? "default" : confidence >= 0.5 ? "secondary" : "outline"}
                            className={
                                confidence >= 0.8
                                    ? "bg-green-600 hover:bg-green-700"
                                    : confidence >= 0.6
                                        ? "bg-amber-500 hover:bg-amber-600 text-white"
                                        : "border-red-300 text-red-700 dark:border-red-700 dark:text-red-400"
                            }
                        >
                            {confidence >= 0.8 ? "High" : confidence >= 0.6 ? "Moderate" : "Low"} Confidence: {Math.round(confidence * 100)}%
                        </Badge>
                        <span className="text-muted-foreground cursor-help" title="Confidence reflects source coverage (Data), precedent strength (Legal), and internal coherence (Consistency)">
                            <Info className="h-3.5 w-3.5" aria-label="What does confidence mean?" />
                        </span>
                        {confidenceBreakdown && (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                {[
                                    { label: "Data", value: confidenceBreakdown.data_confidence, tip: "Source coverage and relevance of retrieved documents" },
                                    { label: "Legal", value: confidenceBreakdown.legal_confidence, tip: "Precedent strength and statutory accuracy" },
                                    { label: "Consistency", value: confidenceBreakdown.consistency_confidence, tip: "Internal coherence — absence of contradictions" },
                                ].map(({ label, value, tip }) => value !== undefined ? (
                                    <span key={label} className="flex items-center gap-1" title={tip}>
                                        <span className="font-medium">{label}</span>
                                        <span
                                            className={`inline-block h-2 rounded-full ${
                                                value >= 0.8 ? "bg-green-500" : value >= 0.6 ? "bg-amber-400" : "bg-red-400"
                                            }`}
                                            style={{ width: `${Math.max(12, value * 64)}px` }}
                                        />
                                        <span>{Math.round(value * 100)}%</span>
                                    </span>
                                ) : null)}
                            </div>
                        )}
                    </div>
                )}
                <div className="ml-auto flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={handleCopy}>
                        {copied ? (
                            <Check className="h-3.5 w-3.5 mr-1.5" />
                        ) : (
                            <Clipboard className="h-3.5 w-3.5 mr-1.5" />
                        )}
                        {copied ? "Copied" : "Copy"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleDownload}>
                        <Download className="h-3.5 w-3.5 mr-1.5" />
                        Download MD
                    </Button>
                    {executionId && (
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="outline" size="sm" className="gap-1">
                                    <Download className="h-3.5 w-3.5" />
                                    Export
                                    <ChevronDown className="h-3 w-3" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                {(["docx", "pdf"] as const).map((fmt) => (
                                    <DropdownMenuItem
                                        key={fmt}
                                        onClick={() => window.open(`/api/agents/research/export/${executionId}?format=${fmt}`, "_blank")}
                                    >
                                        Download {fmt.toUpperCase()}
                                    </DropdownMenuItem>
                                ))}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}
                    {executionId && !shareUrl && (
                        <Button variant="outline" size="sm" onClick={handleShare} disabled={sharing}>
                            {sharing ? (
                                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                            ) : (
                                <Share2 className="h-3.5 w-3.5 mr-1.5" />
                            )}
                            {sharing ? "Sharing..." : "Share"}
                        </Button>
                    )}
                    {executionId && shareUrl && (
                        <div className="flex items-center gap-1.5">
                            <Badge variant="secondary" className="text-xs font-normal gap-1 py-1 px-2">
                                <LinkIcon className="h-3 w-3" />
                                Shared
                            </Badge>
                            <Button variant="outline" size="sm" onClick={handleCopyShareUrl} title="Copy share link">
                                <Copy className="h-3.5 w-3.5 mr-1.5" />
                                Copy Link
                            </Button>
                            <Button variant="outline" size="sm" onClick={handleRevokeShare} title="Revoke share link">
                                <X className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    )}
                </div>
            </div>

            <div className="flex gap-6">
                {/* D11: Table of Contents sidebar */}
                {headings.length > 2 && <MemoTOC headings={headings} />}

                <div className="memo-body max-w-[65ch] text-foreground flex-1 min-w-0">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                        {cleanContent}
                    </ReactMarkdown>
                </div>
            </div>
        </div>
    );
}

/**
 * Recursively process React children to replace text nodes with
 * footnote pills and case ID links.
 */
function processChildren(
    children: React.ReactNode,
    onFootnoteClick?: (n: number) => void,
    maxFootnote?: number,
    footnoteVerification?: Record<number, FootnoteVerification>,
    footnotesMap?: Map<number, ResearchFootnote>,
): React.ReactNode {
    if (typeof children === "string") {
        return processTextNode(children, onFootnoteClick, maxFootnote, footnoteVerification, footnotesMap);
    }
    if (Array.isArray(children)) {
        return children.map((child, i) => {
            if (typeof child === "string") {
                return <span key={i}>{processTextNode(child, onFootnoteClick, maxFootnote, footnoteVerification, footnotesMap)}</span>;
            }
            // Recurse into React elements (e.g., <strong>, <em>) so footnote pills render inside them
            if (React.isValidElement(child)) {
                const childProps = child.props as Record<string, unknown>;
                if (childProps.children) {
                    return React.cloneElement(
                        child,
                        { ...childProps, key: child.key ?? i },
                        processChildren(childProps.children as React.ReactNode, onFootnoteClick, maxFootnote, footnoteVerification, footnotesMap),
                    );
                }
            }
            return child;
        });
    }
    // Single React element — recurse into it
    if (React.isValidElement(children)) {
        const childProps = children.props as Record<string, unknown>;
        if (childProps.children) {
            return React.cloneElement(
                children,
                childProps as React.Attributes,
                processChildren(childProps.children as React.ReactNode, onFootnoteClick, maxFootnote, footnoteVerification, footnotesMap),
            );
        }
    }
    return children;
}
