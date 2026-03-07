"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";

interface AgentMemoViewerProps {
    content: string;
    confidence?: number;
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

export function AgentMemoViewer({ content, confidence }: AgentMemoViewerProps) {
    // Split content by ## headings to render as sections
    const sections = content.split(/^## /m);

    return (
        <div className="space-y-4">
            {confidence !== undefined && (
                <div className="flex items-center gap-2">
                    <Badge variant={confidence >= 0.8 ? "default" : confidence >= 0.5 ? "secondary" : "outline"}>
                        Confidence: {Math.round(confidence * 100)}%
                    </Badge>
                </div>
            )}

            {sections.map((section, i) => {
                if (i === 0 && !section.trim()) return null;

                // First section (before any ##) has no heading
                if (i === 0) {
                    return (
                        <div key={i} className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                            {renderTextWithCitations(section.trim())}
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
                                {renderTextWithCitations(body)}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
