"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, Clipboard, Download } from "lucide-react";

interface AgentMemoViewerProps {
    content: string;
    confidence?: number;
    onFootnoteClick?: (num: number) => void;
}

/** Regex to match UUID-style case IDs in the memo content. */
const CASE_ID_RE = /\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b/gi;

function renderTextWithCitations(text: string): React.ReactNode[] {
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    const re = new RegExp(CASE_ID_RE.source, "gi");
    while ((match = re.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push(text.slice(lastIndex, match.index));
        }
        const caseId = match[1];
        parts.push(
            <Link
                key={`${caseId}-${match.index}`}
                href={`/case/${caseId}`}
                className="text-[var(--gold)] underline underline-offset-2 hover:text-[var(--gold)]/80"
            >
                {caseId}
            </Link>
        );
        lastIndex = re.lastIndex;
    }
    if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex));
    }
    return parts;
}

/**
 * Convert footnote references like [^1] and [1] in text into clickable gold pill badges.
 * When onFootnoteClick is not provided, returns the input nodes unchanged.
 */
function renderWithFootnotes(
    nodes: React.ReactNode[],
    onFootnoteClick?: (n: number) => void
): React.ReactNode[] {
    if (!onFootnoteClick) return nodes;

    const result: React.ReactNode[] = [];
    let keyCounter = 0;

    for (const node of nodes) {
        if (typeof node !== "string") {
            result.push(node);
            continue;
        }

        const parts = node.split(/(\[\^?\d+\])/g);
        for (const part of parts) {
            const match = part.match(/^\[\^?(\d+)\]$/);
            if (match) {
                const num = parseInt(match[1], 10);
                result.push(
                    <button
                        key={`fn-${num}-${keyCounter++}`}
                        onClick={(e) => {
                            e.preventDefault();
                            onFootnoteClick(num);
                        }}
                        className="inline-flex items-center justify-center min-w-[1.25rem] h-5 rounded-full bg-[var(--gold)]/20 text-[var(--gold)] text-[10px] font-bold hover:bg-[var(--gold)]/30 transition-colors mx-0.5 align-super cursor-pointer"
                        title={`View source [${num}]`}
                    >
                        {num}
                    </button>
                );
            } else if (part.length > 0) {
                result.push(part);
            }
        }
    }

    return result;
}

export function AgentMemoViewer({ content, confidence, onFootnoteClick }: AgentMemoViewerProps) {
    const [copied, setCopied] = useState(false);

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

    // Split content by ## headings to render as sections
    const sections = content.split(/^## /m);

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
                {confidence !== undefined && (
                    <Badge variant={confidence >= 0.8 ? "default" : confidence >= 0.5 ? "secondary" : "outline"}>
                        Confidence: {Math.round(confidence * 100)}%
                    </Badge>
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
                </div>
            </div>

            {sections.map((section, i) => {
                if (i === 0 && !section.trim()) return null;

                // First section (before any ##) has no heading
                if (i === 0) {
                    return (
                        <div key={i} className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                            {renderWithFootnotes(renderTextWithCitations(section.trim()), onFootnoteClick)}
                        </div>
                    );
                }

                // Sections with ## headings
                const newlineIdx = section.indexOf("\n");
                const heading = newlineIdx !== -1 ? section.slice(0, newlineIdx).trim() : section.trim();
                const body = newlineIdx !== -1 ? section.slice(newlineIdx + 1).trim() : "";

                return (
                    <div key={i} className="space-y-1.5">
                        <h3 className="text-sm font-semibold text-foreground">{heading}</h3>
                        {body && (
                            <div className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                                {renderWithFootnotes(renderTextWithCitations(body), onFootnoteClick)}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
