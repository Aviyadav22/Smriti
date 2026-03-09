"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { runResearchAgent, resumeAgentExecution } from "@/lib/api";
import type { AgentStreamEvent, AgentStep } from "@/lib/types";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, ArrowLeft, RotateCcw } from "lucide-react";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Expected research agent steps for the timeline
// ---------------------------------------------------------------------------

const RESEARCH_STEPS = [
    "classify",
    "decompose",
    "checkpoint_plan",
    "search",
    "gather",
    "contradictions",
    "checkpoint_findings",
    "synthesize",
    "verify",
    "checkpoint_memo",
];

// ---------------------------------------------------------------------------
// Research Agent Workspace
// ---------------------------------------------------------------------------

export default function ResearchAgentPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();

    const [query, setQuery] = useState("");
    const [starting, setStarting] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [executionId, setExecutionId] = useState<string | null>(null);
    const [steps, setSteps] = useState<AgentStep[]>([]);
    const [checkpoint, setCheckpoint] = useState<{
        question: string;
        context: Record<string, unknown>;
    } | null>(null);
    const [memo, setMemo] = useState("");
    const [confidence, setConfidence] = useState<number | undefined>();
    const [error, setError] = useState<string | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push("/login");
    }, [authLoading, isAuthenticated, router]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            abortRef.current?.abort();
        };
    }, []);

    const handleEvent = useCallback((event: AgentStreamEvent) => {
        // Capture execution_id from the first event that carries it,
        // so it's available before "done" (e.g. at checkpoint time).
        if (event.execution_id) {
            setExecutionId(event.execution_id);
        }

        switch (event.type) {
            case "status":
                setSteps((prev) =>
                    prev.map((s) => ({
                        ...s,
                        status:
                            s.name === event.step
                                ? "completed"
                                : RESEARCH_STEPS.indexOf(s.name) ===
                                    RESEARCH_STEPS.indexOf(event.step!) + 1
                                  ? "active"
                                  : s.status,
                        message:
                            s.name === event.step
                                ? event.message || s.message
                                : s.message,
                    })),
                );
                break;
            case "checkpoint":
                if (event.execution_id) setExecutionId(event.execution_id);
                setCheckpoint({
                    question: event.question || "",
                    context: event.context || {},
                });
                setIsRunning(false);
                break;
            case "memo":
                setMemo(event.content || "");
                if (
                    event.data &&
                    typeof event.data === "object" &&
                    "confidence" in (event.data as Record<string, unknown>)
                ) {
                    setConfidence(
                        (event.data as Record<string, unknown>)
                            .confidence as number,
                    );
                }
                break;
            case "done":
                setExecutionId(event.execution_id || null);
                setIsRunning(false);
                setSteps((prev) =>
                    prev.map((s) => ({
                        ...s,
                        status:
                            s.status === "active" || s.status === "pending"
                                ? "completed"
                                : s.status,
                    })),
                );
                break;
            case "error":
                setError(event.message || "Agent encountered an error");
                setIsRunning(false);
                break;
        }
    }, []);

    const handleSubmit = useCallback(() => {
        if (!query.trim() || starting) return;
        setStarting(true);
        setIsRunning(true);
        setError(null);
        setMemo("");
        setConfidence(undefined);
        setCheckpoint(null);
        setExecutionId(null);
        setSteps(
            RESEARCH_STEPS.map((name, i) => ({
                name,
                status: i === 0 ? ("active" as const) : ("pending" as const),
            })),
        );
        try {
            abortRef.current = runResearchAgent(
                query.trim(),
                handleEvent,
                (err) => {
                    setError(err.message);
                    setIsRunning(false);
                },
            );
        } finally {
            setStarting(false);
        }
    }, [query, starting, handleEvent]);

    const [checkpointError, setCheckpointError] = useState<string | null>(null);

    const handleResume = useCallback(
        (input: string) => {
            if (!executionId) return;
            // Keep checkpoint state so it can be re-shown on error
            const savedCheckpoint = checkpoint;
            setCheckpoint(null);
            setCheckpointError(null);
            setIsRunning(true);
            abortRef.current = resumeAgentExecution(
                executionId,
                input,
                handleEvent,
                (err) => {
                    // Restore checkpoint prompt so user can retry
                    setCheckpoint(savedCheckpoint);
                    setCheckpointError(err.message);
                    setIsRunning(false);
                },
            );
        },
        [executionId, checkpoint, handleEvent],
    );

    const handleReset = useCallback(() => {
        abortRef.current?.abort();
        setQuery("");
        setIsRunning(false);
        setExecutionId(null);
        setSteps([]);
        setCheckpoint(null);
        setMemo("");
        setConfidence(undefined);
        setError(null);
    }, []);

    if (authLoading || !isAuthenticated) return null;

    const showInputForm = !isRunning && !memo && !checkpoint && steps.length === 0;
    const showWorkspace = isRunning || memo || checkpoint || steps.length > 0;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                <div className="mx-auto max-w-6xl px-4 py-8">
            <div className="flex items-center gap-3 mb-6">
                <Button variant="ghost" size="sm" asChild>
                    <Link href="/agents">
                        <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Agents
                    </Link>
                </Button>
            </div>

            <h1 className="text-2xl font-semibold font-[family-name:var(--font-lora)] mb-2">
                Research Agent
            </h1>
            <p className="text-sm text-muted-foreground mb-6">
                Enter a legal research question. The agent will decompose it,
                search case law, detect contradictions, and generate a
                structured memo.
            </p>

            {/* Input form (shown when not running and no memo) */}
            {showInputForm && (
                <Card>
                    <CardContent className="pt-6 space-y-4">
                        <label htmlFor="research-query" className="sr-only">Enter your legal research question</label>
                        <Textarea
                            id="research-query"
                            placeholder="Enter your legal research question..."
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className="min-h-[120px] text-sm"
                        />
                        <Button
                            onClick={handleSubmit}
                            disabled={starting || !query.trim()}
                        >
                            {starting ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                "Start Research"
                            )}
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* Running or completed state */}
            {showWorkspace && (
                <div className="grid gap-6 md:grid-cols-[240px_1fr]">
                    {/* Left: Step Timeline */}
                    <div className="hidden md:block">
                        <div className="sticky top-20">
                            <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-3">
                                Progress
                            </h3>
                            <AgentStepTimeline steps={steps} />
                        </div>
                    </div>

                    {/* Right: Main content */}
                    <div className="space-y-4">
                        {/* Query display */}
                        <Card>
                            <CardContent className="pt-4">
                                <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">
                                    Query
                                </p>
                                <p className="text-sm">{query}</p>
                            </CardContent>
                        </Card>

                        {/* Mobile step timeline */}
                        <div className="md:hidden">
                            <AgentStepTimeline steps={steps} />
                        </div>

                        {/* Checkpoint prompt */}
                        {checkpoint && (
                            <AgentCheckpointPrompt
                                question={checkpoint.question}
                                context={checkpoint.context}
                                onSubmit={handleResume}
                                disabled={isRunning}
                                error={checkpointError}
                                onClearError={() => setCheckpointError(null)}
                            />
                        )}

                        {/* Memo result */}
                        {memo && (
                            <Card>
                                <CardContent className="pt-6">
                                    <AgentMemoViewer
                                        content={memo}
                                        confidence={confidence}
                                    />
                                </CardContent>
                            </Card>
                        )}

                        {/* Error */}
                        {error && (
                            <div className="text-sm text-red-500 p-3 rounded-md bg-red-50 dark:bg-red-950/20" role="alert">
                                {error}
                            </div>
                        )}

                        {/* Loading indicator */}
                        {isRunning && !checkpoint && (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />{" "}
                                Agent is working...
                            </div>
                        )}

                        {/* New Research button after completion */}
                        {!isRunning && (memo || error) && (
                            <>
                                <LegalDisclaimer className="mt-2" />
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleReset}
                                >
                                    <RotateCcw className="h-3.5 w-3.5 mr-1.5" />{" "}
                                    New Research
                                </Button>
                            </>
                        )}
                    </div>
                </div>
            )}
                </div>
            </main>

            <Footer />
        </div>
    );
}
