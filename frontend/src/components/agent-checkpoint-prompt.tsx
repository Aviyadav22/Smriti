"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { MessageSquare } from "lucide-react";

interface AgentCheckpointPromptProps {
    question: string;
    context?: Record<string, unknown>;
    onSubmit: (input: string) => void;
    disabled?: boolean;
    /** When set, displays an inline error with a retry button. */
    error?: string | null;
    /** Called to clear the error state before retrying. */
    onClearError?: () => void;
    /** Custom suggestion chips. If not provided, inferred from context. */
    suggestions?: string[];
}

/** Infer context-aware chip suggestions from checkpoint data. */
function inferSuggestions(context?: Record<string, unknown>): string[] {
    if (!context) return ["Looks good, proceed"];
    // Findings checkpoint — has top_cases, evidence_gaps
    if (context.top_cases || context.evidence_gaps) {
        const chips = ["Looks good, proceed to synthesis"];
        if (Array.isArray(context.evidence_gaps) && context.evidence_gaps.length > 0) {
            chips.push("Fill the evidence gaps first");
        }
        if (context.contradictions && Array.isArray(context.contradictions) && context.contradictions.length > 0) {
            chips.push("Investigate contradictions further");
        }
        chips.push("Search for more recent cases");
        return chips;
    }
    // Memo checkpoint — has draft_memo
    if (context.draft_memo) {
        return [
            "Looks good, finalize",
            "Make it more concise",
            "Add more case citations",
            "Strengthen the analysis",
        ];
    }
    // Default
    return [
        "Looks good, proceed",
        "Focus more on constitutional aspects",
        "Add cases from the last 5 years",
    ];
}

function renderValue(v: unknown): React.ReactNode {
    if (v === null || v === undefined) return <span className="text-muted-foreground italic">—</span>;
    if (typeof v === "boolean") return String(v);
    if (typeof v === "number" || typeof v === "string") return String(v);
    if (Array.isArray(v)) {
        return (
            <ul className="space-y-0.5 mt-0.5">
                {v.map((item, i) => (
                    <li key={i} className="list-disc ml-4">{renderValue(item)}</li>
                ))}
            </ul>
        );
    }
    if (typeof v === "object") {
        return (
            <dl className="ml-2 border-l border-border pl-2 space-y-0.5 mt-0.5">
                {Object.entries(v as Record<string, unknown>).map(([k, val]) => (
                    <div key={k}>
                        <dt className="font-medium capitalize inline">{k.replace(/_/g, " ")}:</dt>{" "}
                        <dd className="inline">{renderValue(val)}</dd>
                    </div>
                ))}
            </dl>
        );
    }
    return String(v);
}

export function AgentCheckpointPrompt({ question, context, onSubmit, disabled, error, onClearError, suggestions }: AgentCheckpointPromptProps) {
    const [input, setInput] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [lastInput, setLastInput] = useState("");

    // Reset submitting state when an error arrives (so user can retry)
    useEffect(() => {
        if (error) setSubmitting(false);
    }, [error]);

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (input.trim() && !submitting) {
            setSubmitting(true);
            const text = input.trim();
            setLastInput(text);
            onClearError?.();
            // Send structured JSON for free-text input too
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
        // Send structured JSON — "proceed" chips send {action: "approve"},
        // feedback chips send {action: "feedback", text: "..."}
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

    return (
        <Card className="border-[var(--gold)]/30">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                    <MessageSquare className="h-4 w-4 text-[var(--gold)]" />
                    Agent needs your input
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <p className="text-sm text-foreground">{question}</p>

                {context && Object.keys(context).length > 0 && (
                    <div className="rounded-md bg-muted/50 p-3 space-y-2">
                        {Object.entries(context)
                            .filter(([key]) => key !== "question")
                            .map(([key, value]) => (
                            <div key={key}>
                                <p className="text-xs font-medium text-muted-foreground capitalize">
                                    {key.replace(/_/g, " ")}
                                </p>
                                <div className="text-xs text-foreground mt-0.5">
                                    {renderValue(value)}
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-3">
                    {/* Quick suggestion chips — context-aware */}
                    <div className="flex flex-wrap gap-2">
                        {(suggestions || inferSuggestions(context)).map((suggestion) => (
                            <button
                                key={suggestion}
                                type="button"
                                disabled={disabled || submitting}
                                onClick={() => handleChipClick(suggestion)}
                                className="rounded-full border border-border bg-muted/50 px-3 py-1 text-xs text-foreground hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {suggestion}
                            </button>
                        ))}
                    </div>
                    <label htmlFor="checkpoint-response" className="sr-only">Type your response</label>
                    <Textarea
                        id="checkpoint-response"
                        placeholder="Type your response..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        disabled={disabled}
                        className="min-h-[80px] text-sm"
                    />
                    <Button
                        type="submit"
                        size="sm"
                        disabled={disabled || submitting || !input.trim()}
                    >
                        {submitting ? "Submitting…" : "Submit"}
                    </Button>

                    {/* Error with retry */}
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
                </form>
            </CardContent>
        </Card>
    );
}
