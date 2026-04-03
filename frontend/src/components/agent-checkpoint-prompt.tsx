"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    MessageSquare, AlertTriangle, BookOpen, Search,
    ChevronDown, ChevronRight,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface AgentCheckpointPromptProps {
    question: string;
    context?: Record<string, unknown>;
    onSubmit: (input: string) => void;
    disabled?: boolean;
    error?: string | null;
    onClearError?: () => void;
    suggestions?: string[];
}

// ---------------------------------------------------------------------------
// Detect checkpoint type from context shape
// ---------------------------------------------------------------------------

type CheckpointType = "findings" | "memo" | "generic";

function detectCheckpointType(context?: Record<string, unknown>): CheckpointType {
    if (!context) return "generic";
    if (context.draft_memo) return "memo";
    if (context.result_count !== undefined || context.top_cases || context.evidence_gaps) return "findings";
    return "generic";
}

// ---------------------------------------------------------------------------
// Context-aware suggestion chips
// ---------------------------------------------------------------------------

function inferSuggestions(type: CheckpointType, context?: Record<string, unknown>): string[] {
    switch (type) {
        case "findings": {
            const chips = ["Looks good, proceed to synthesis"];
            if (Array.isArray(context?.evidence_gaps) && (context!.evidence_gaps as unknown[]).length > 0) {
                chips.push("Fill the evidence gaps first");
            }
            chips.push("Search for more recent cases");
            return chips;
        }
        case "memo":
            return [
                "Looks good, finalize",
                "Make it more concise",
                "Add more case citations",
                "Strengthen the analysis",
            ];
        default:
            return [
                "Looks good, proceed",
                "Focus more on constitutional aspects",
                "Add cases from the last 5 years",
            ];
    }
}

// ---------------------------------------------------------------------------
// Findings context renderer — curated, not raw dump
// ---------------------------------------------------------------------------

interface TopCase {
    case_id?: string;
    title?: string;
    citation?: string;
    court?: string;
    year?: number | string;
    relevance_score?: number;
}

function FindingsContext({ context }: { context: Record<string, unknown> }) {
    const [showAllCases, setShowAllCases] = useState(false);
    const [showGaps, setShowGaps] = useState(true);

    const resultCount = context.result_count as number | undefined;
    const workerCount = context.worker_count as number | undefined;
    const refinementRound = context.refinement_round as number | undefined;
    const summary = context.summary as string | undefined;
    const topCases = (context.top_cases as TopCase[] | undefined) || [];
    const evidenceGaps = (context.evidence_gaps as Array<{ description: string; priority?: number }> | undefined) || [];
    const crossRefs = (context.cross_references as unknown[] | undefined) || [];

    const displayCases = showAllCases ? topCases : topCases.slice(0, 8);

    return (
        <div className="space-y-4">
            {/* Summary stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {resultCount !== undefined && (
                    <div className="rounded-lg bg-muted/50 p-3 text-center">
                        <div className="text-xl font-semibold text-foreground">{resultCount}</div>
                        <div className="text-xs text-muted-foreground">Sources found</div>
                    </div>
                )}
                {workerCount !== undefined && (
                    <div className="rounded-lg bg-muted/50 p-3 text-center">
                        <div className="text-xl font-semibold text-foreground">{workerCount}</div>
                        <div className="text-xs text-muted-foreground">Workers ran</div>
                    </div>
                )}
                {crossRefs.length > 0 && (
                    <div className="rounded-lg bg-muted/50 p-3 text-center">
                        <div className="text-xl font-semibold text-foreground">{crossRefs.length}</div>
                        <div className="text-xs text-muted-foreground">Cross-references</div>
                    </div>
                )}
                {refinementRound !== undefined && refinementRound > 0 && (
                    <div className="rounded-lg bg-muted/50 p-3 text-center">
                        <div className="text-xl font-semibold text-foreground">{refinementRound}</div>
                        <div className="text-xs text-muted-foreground">Refinement rounds</div>
                    </div>
                )}
            </div>

            {/* Summary text */}
            {summary && (
                <p className="text-sm text-muted-foreground">{summary}</p>
            )}

            {/* Top cases — curated cards, not raw list */}
            {topCases.length > 0 && (
                <div>
                    <button
                        type="button"
                        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground mb-2"
                        onClick={() => setShowAllCases(!showAllCases)}
                    >
                        <BookOpen className="h-3.5 w-3.5" />
                        Top Cases ({topCases.length})
                        {topCases.length > 8 && (
                            showAllCases
                                ? <ChevronDown className="h-3 w-3" />
                                : <ChevronRight className="h-3 w-3" />
                        )}
                    </button>
                    <div className="grid gap-1.5">
                        {displayCases.map((c, i) => (
                            <div
                                key={c.case_id || i}
                                className="flex items-start gap-2 rounded-md border border-border/60 bg-background px-3 py-2 text-xs"
                            >
                                <span className="font-mono text-muted-foreground/60 mt-0.5 shrink-0 w-4 text-right">{i + 1}</span>
                                <div className="min-w-0 flex-1">
                                    <p className="font-medium text-foreground truncate">{c.title || "Untitled"}</p>
                                    <div className="flex items-center gap-2 mt-0.5 text-muted-foreground">
                                        {c.citation && <span>{c.citation}</span>}
                                        {c.court && <span>{c.court}</span>}
                                        {c.year && <span>{c.year}</span>}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                    {topCases.length > 8 && !showAllCases && (
                        <button
                            type="button"
                            onClick={() => setShowAllCases(true)}
                            className="text-xs text-muted-foreground hover:text-foreground mt-1.5"
                        >
                            Show all {topCases.length} cases...
                        </button>
                    )}
                </div>
            )}

            {/* Evidence gaps */}
            {evidenceGaps.length > 0 && (
                <div>
                    <button
                        type="button"
                        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground mb-2"
                        onClick={() => setShowGaps(!showGaps)}
                    >
                        <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                        Evidence Gaps ({evidenceGaps.length})
                        {showGaps ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    </button>
                    {showGaps && (
                        <div className="space-y-1.5">
                            {evidenceGaps.map((gap, i) => (
                                <div
                                    key={i}
                                    className="flex items-start gap-2 text-xs rounded-md bg-amber-50 dark:bg-amber-950/20 border border-amber-200/50 dark:border-amber-800/30 px-3 py-2"
                                >
                                    <span className="text-amber-500 mt-0.5 shrink-0">
                                        {gap.priority === 1 ? <Badge variant="destructive" className="text-[9px] px-1 py-0">High</Badge> : <Badge variant="secondary" className="text-[9px] px-1 py-0">Low</Badge>}
                                    </span>
                                    <span className="text-foreground/80">{gap.description}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Memo context renderer — rendered markdown, not raw text
// ---------------------------------------------------------------------------

function MemoContext({ context }: { context: Record<string, unknown> }) {
    const [showDraft, setShowDraft] = useState(false);
    const draftMemo = context.draft_memo as string | undefined;
    const confidence = context.confidence as number | undefined;
    const footnotes = (context.footnotes as unknown[] | undefined) || [];

    return (
        <div className="space-y-3">
            {/* Stats row */}
            <div className="flex items-center gap-4 text-sm">
                {confidence !== undefined && (
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">Confidence:</span>
                        <Badge
                            variant="secondary"
                            className={
                                confidence >= 0.7 ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                                : confidence >= 0.4 ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
                                : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                            }
                        >
                            {Math.round(confidence * 100)}%
                        </Badge>
                    </div>
                )}
                {footnotes.length > 0 && (
                    <span className="text-xs text-muted-foreground">{footnotes.length} citations</span>
                )}
            </div>

            {/* Draft memo preview — rendered */}
            {draftMemo && (
                <div>
                    <button
                        type="button"
                        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground mb-2"
                        onClick={() => setShowDraft(!showDraft)}
                    >
                        <Search className="h-3.5 w-3.5" />
                        {showDraft ? "Hide draft" : "Preview draft memo"}
                        {showDraft ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    </button>
                    {showDraft && (
                        <div className="rounded-lg border bg-muted/20 p-4 max-h-[400px] overflow-y-auto prose prose-sm dark:prose-invert prose-headings:font-semibold prose-p:text-foreground/80">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {draftMemo}
                            </ReactMarkdown>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Fallback generic context renderer — cleaner than raw dump
// ---------------------------------------------------------------------------

function GenericContext({ context }: { context: Record<string, unknown> }) {
    const entries = Object.entries(context).filter(([key]) => key !== "question" && key !== "draft_memo");

    if (entries.length === 0) return null;

    return (
        <div className="rounded-md bg-muted/30 p-3 space-y-2 text-xs">
            {entries.map(([key, value]) => (
                <div key={key}>
                    <p className="font-medium text-muted-foreground capitalize">{key.replace(/_/g, " ")}</p>
                    <div className="text-foreground mt-0.5">
                        {Array.isArray(value) ? (
                            <ul className="space-y-0.5 ml-3">
                                {(value as unknown[]).map((item, i) => (
                                    <li key={i} className="list-disc">{String(item)}</li>
                                ))}
                            </ul>
                        ) : typeof value === "object" && value !== null ? (
                            <span>{JSON.stringify(value, null, 2).slice(0, 200)}</span>
                        ) : (
                            <span>{String(value)}</span>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function AgentCheckpointPrompt({
    question,
    context,
    onSubmit,
    disabled,
    error,
    onClearError,
    suggestions,
}: AgentCheckpointPromptProps) {
    const [input, setInput] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [lastInput, setLastInput] = useState("");

    const checkpointType = detectCheckpointType(context);

    // Reset submitting when error arrives so user can retry
    // eslint-disable-next-line react-hooks/set-state-in-effect
    useEffect(() => { if (error) setSubmitting(false); }, [error]);

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (input.trim() && !submitting) {
            setSubmitting(true);
            const text = input.trim();
            setLastInput(text);
            onClearError?.();
            const trimmedFirst = text.split(",")[0].trim();
            const isProceed = /^(looks good|proceed|approve|lgtm|ok|yes)$/i.test(text.trim()) ||
                /^(looks good|proceed|approve|lgtm)$/i.test(trimmedFirst);
            const structured = JSON.stringify(
                isProceed
                    ? { action: "approve" }
                    : { action: "feedback", text }
            );
            onSubmit(structured);
            setInput("");
        }
    }

    function handleChipClick(suggestion: string) {
        if (submitting || disabled) return;
        setSubmitting(true);
        setLastInput(suggestion);
        onClearError?.();
        const chipFirst = suggestion.split(",")[0].trim();
        const isProceed = /^(looks good|proceed|approve|lgtm|ok|yes)$/i.test(suggestion.trim()) ||
            /^(looks good|proceed|approve|lgtm)$/i.test(chipFirst);
        const structured = JSON.stringify(
            isProceed
                ? { action: "approve" }
                : { action: "feedback", text: suggestion }
        );
        onSubmit(structured);
    }

    function handleRetry() {
        if (!lastInput || submitting) return;
        setSubmitting(true);
        onClearError?.();
        onSubmit(lastInput);
    }

    const checkpointTitle = checkpointType === "findings"
        ? "Review Search Findings"
        : checkpointType === "memo"
            ? "Review Draft Memo"
            : "Agent needs your input";

    return (
        <Card className="border-[var(--gold)]/30 shadow-sm">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                    <MessageSquare className="h-4 w-4 text-[var(--gold)]" />
                    {checkpointTitle}
                </CardTitle>
                <p className="text-sm text-muted-foreground">{question}</p>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Context — type-specific rendering */}
                {context && checkpointType === "findings" && (
                    <FindingsContext context={context} />
                )}
                {context && checkpointType === "memo" && (
                    <MemoContext context={context} />
                )}
                {context && checkpointType === "generic" && (
                    <GenericContext context={context} />
                )}

                {/* Action area */}
                <form onSubmit={handleSubmit} className="space-y-3">
                    {/* Quick suggestion chips */}
                    <div className="flex flex-wrap gap-2">
                        {(suggestions || inferSuggestions(checkpointType, context)).map((suggestion) => (
                            <button
                                key={suggestion}
                                type="button"
                                disabled={disabled || submitting}
                                onClick={() => handleChipClick(suggestion)}
                                className="rounded-full border border-border bg-muted/50 px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted hover:border-[var(--gold)]/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {suggestion}
                            </button>
                        ))}
                    </div>
                    <label htmlFor="checkpoint-response" className="sr-only">Type your response</label>
                    <Textarea
                        id="checkpoint-response"
                        placeholder="Additional instructions or modifications..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        disabled={disabled}
                        className="min-h-[70px] text-sm"
                    />
                    <div className="flex items-center gap-2">
                        <Button
                            type="submit"
                            size="sm"
                            disabled={disabled || submitting || !input.trim()}
                        >
                            {submitting ? "Submitting..." : "Submit"}
                        </Button>

                        {error && (
                            <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400" role="alert">
                                <span>{error}</span>
                                {lastInput && (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={handleRetry}
                                        disabled={submitting}
                                    >
                                        Retry
                                    </Button>
                                )}
                            </div>
                        )}
                    </div>
                </form>
            </CardContent>
        </Card>
    );
}
