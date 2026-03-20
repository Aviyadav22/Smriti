"use client";

import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import {
    ExternalLink,
    CheckCircle2,
    XCircle,
    AlertCircle,
    ChevronDown,
    ChevronRight,
    Download,
    Scale,
    Link2,
    BookOpen,
} from "lucide-react";
import { getCasePdfUrl } from "@/lib/api";
import type { ResearchFootnote } from "@/lib/types";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

// ---------------------------------------------------------------------------
// Verification status config
// ---------------------------------------------------------------------------
const STATUS_CONFIG: Record<
    string,
    { icon: React.ElementType; color: string; bgColor: string; label: string }
> = {
    verified_pg: {
        icon: CheckCircle2,
        color: "text-green-500",
        bgColor: "bg-green-50 dark:bg-green-950/20",
        label: "Verified (Database)",
    },
    verified_ik: {
        icon: CheckCircle2,
        color: "text-green-500",
        bgColor: "bg-green-50 dark:bg-green-950/20",
        label: "Verified (Indian Kanoon)",
    },
    verified_neo4j: {
        icon: CheckCircle2,
        color: "text-green-500",
        bgColor: "bg-green-50 dark:bg-green-950/20",
        label: "Verified (Citation Graph)",
    },
    unverified: {
        icon: XCircle,
        color: "text-red-500",
        bgColor: "bg-red-50 dark:bg-red-950/20",
        label: "Unverified",
    },
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
export interface FootnotePreviewProps {
    footnote: ResearchFootnote;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function FootnotePreview({ footnote }: FootnotePreviewProps) {
    const {
        number,
        source_label,
        title,
        citation,
        court,
        year,
        author,
        bench,
        excerpt,
        verification_status,
        ik_doc_id,
        pdf_available,
        case_id,
        source_url,
    } = footnote;

    if (source_label === "Case") {
        return <CasePreview {...{ number, title, citation, court, year, author, bench, excerpt, verification_status, ik_doc_id, pdf_available, case_id, source_url }} />;
    }

    if (source_label === "Web") {
        return <WebPreview {...{ number, title, excerpt, source_url }} />;
    }

    // Statute / Constitution / fallback
    return <StatutePreview {...{ number, title, excerpt, source_url, source_label }} />;
}

// ---------------------------------------------------------------------------
// Header bar (shared)
// ---------------------------------------------------------------------------
function HeaderBar({
    number,
    icon,
    label,
    openUrl,
}: {
    number: number;
    icon: React.ReactNode;
    label: string;
    openUrl?: string;
}) {
    return (
        <div className="flex items-center gap-2 px-4 py-2.5 border-b bg-muted/30">
            <span className="flex items-center justify-center h-6 w-6 rounded-full bg-[var(--gold)] text-white text-xs font-bold shrink-0">
                {number}
            </span>
            <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {icon}
                {label}
            </span>
            {openUrl && (
                <a
                    href={openUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto flex items-center gap-1 text-xs text-[var(--gold)] hover:text-[var(--gold)]/80 font-medium"
                >
                    Open
                    <ExternalLink className="h-3 w-3" />
                </a>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Case preview
// ---------------------------------------------------------------------------
function CasePreview({
    number,
    title,
    citation,
    court,
    year,
    author,
    bench,
    excerpt,
    verification_status,
    ik_doc_id,
    pdf_available,
    case_id,
    source_url,
}: {
    number: number;
    title: string;
    citation: string;
    court: string;
    year: number | null;
    author: string;
    bench: string;
    excerpt: string;
    verification_status: string;
    ik_doc_id: string;
    pdf_available: boolean;
    case_id: string | null;
    source_url: string;
}) {
    const [summaryOpen, setSummaryOpen] = useState(true);
    const [pdfError, setPdfError] = useState(false);

    const status = STATUS_CONFIG[verification_status] || STATUS_CONFIG.unverified;
    const StatusIcon = status.icon;

    const openUrl = case_id ? `/case/${case_id}` : source_url || undefined;
    const ikUrl = ik_doc_id ? `https://indiankanoon.org/doc/${ik_doc_id}/` : null;
    const pdfUrl = pdf_available && case_id ? getCasePdfUrl(case_id) : null;

    const metaParts = [citation, court, year].filter(Boolean).join(" \u00B7 ");

    return (
        <div className="flex flex-col h-full">
            <HeaderBar
                number={number}
                icon={<Scale className="h-3.5 w-3.5" />}
                label="Case Law"
                openUrl={openUrl}
            />

            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
                {/* Title & metadata */}
                <div>
                    <h3 className="text-sm font-semibold leading-snug">
                        {title || citation || "Untitled Case"}
                    </h3>
                    {metaParts && (
                        <p className="text-xs text-muted-foreground mt-1">{metaParts}</p>
                    )}
                    {(author || bench) && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                            Bench: {author}
                            {bench && author ? ` (${bench})` : bench ? bench : ""}
                        </p>
                    )}
                </div>

                {/* Verification badge */}
                <div
                    className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium ${status.bgColor}`}
                >
                    <StatusIcon className={`h-4 w-4 shrink-0 ${status.color}`} />
                    <span>{status.label}</span>
                </div>

                {/* Summaries / Excerpt (collapsible) */}
                {excerpt && (
                    <div className="border rounded-md">
                        <button
                            onClick={() => setSummaryOpen(!summaryOpen)}
                            className="w-full flex items-center gap-1.5 px-3 py-2 text-xs font-medium hover:bg-muted/50 transition-colors"
                        >
                            {summaryOpen ? (
                                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                            ) : (
                                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                            )}
                            Summary
                        </button>
                        {summaryOpen && (
                            <div className="px-3 pb-3 text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
                                {excerpt}
                            </div>
                        )}
                    </div>
                )}

                {/* View on Indian Kanoon */}
                {ikUrl && (
                    <a
                        href={ikUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-center gap-2 w-full px-3 py-2 text-xs font-medium rounded-md border border-[var(--gold)] text-[var(--gold)] hover:bg-[var(--gold)]/10 transition-colors"
                    >
                        View on Indian Kanoon
                        <ExternalLink className="h-3 w-3" />
                    </a>
                )}

                {/* Embedded PDF viewer */}
                {pdfUrl && !pdfError && (
                    <div className="border rounded-md overflow-hidden max-h-[400px]">
                        <Document
                            file={pdfUrl}
                            onLoadError={() => setPdfError(true)}
                            loading={
                                <div className="flex items-center justify-center h-48 text-xs text-muted-foreground">
                                    Loading PDF...
                                </div>
                            }
                        >
                            <Page pageNumber={1} width={380} />
                        </Document>
                    </div>
                )}

                {/* PDF error fallback */}
                {pdfUrl && pdfError && (
                    <a
                        href={pdfUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-center gap-2 w-full px-3 py-2 text-xs font-medium rounded-md border text-muted-foreground hover:bg-muted/50 transition-colors"
                    >
                        <Download className="h-3.5 w-3.5" />
                        Download PDF instead
                    </a>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Web preview
// ---------------------------------------------------------------------------
function WebPreview({
    number,
    title,
    excerpt,
    source_url,
}: {
    number: number;
    title: string;
    excerpt: string;
    source_url: string;
}) {
    return (
        <div className="flex flex-col h-full">
            <HeaderBar
                number={number}
                icon={<Link2 className="h-3.5 w-3.5" />}
                label="Source"
                openUrl={source_url || undefined}
            />

            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
                {/* Title */}
                <h3 className="text-sm font-semibold leading-snug">
                    {title || "Web Page"}
                </h3>

                {/* URL */}
                {source_url && (
                    <a
                        href={source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-xs text-[var(--gold)] underline underline-offset-2 truncate"
                    >
                        {source_url}
                    </a>
                )}

                {/* Page content / excerpt */}
                {excerpt && (
                    <div className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap border-l-2 border-muted pl-3">
                        {excerpt}
                    </div>
                )}

                {/* View Full Document */}
                {source_url && (
                    <a
                        href={source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-center gap-2 w-full px-3 py-2.5 text-xs font-medium rounded-md bg-[var(--gold)] text-white hover:bg-[var(--gold)]/90 transition-colors"
                    >
                        View Full Document
                        <ExternalLink className="h-3 w-3" />
                    </a>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Statute / Constitution preview
// ---------------------------------------------------------------------------
function StatutePreview({
    number,
    title,
    excerpt,
    source_url,
    source_label,
}: {
    number: number;
    title: string;
    excerpt: string;
    source_url: string;
    source_label: string;
}) {
    return (
        <div className="flex flex-col h-full">
            <HeaderBar
                number={number}
                icon={<BookOpen className="h-3.5 w-3.5" />}
                label={source_label || "Statute"}
                openUrl={source_url || undefined}
            />

            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
                {/* Title */}
                <h3 className="text-sm font-semibold leading-snug">
                    {title || "Statute"}
                </h3>

                {/* Section text */}
                {excerpt && (
                    <div className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap border-l-2 border-[var(--gold)] pl-3">
                        {excerpt}
                    </div>
                )}
            </div>
        </div>
    );
}
