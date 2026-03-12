"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { runStrategyAgent, resumeAgentExecution } from "@/lib/api";
import type { AgentStreamEvent, AgentStep } from "@/lib/types";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Loader2, ArrowLeft, RotateCcw } from "lucide-react";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Expected strategy agent steps for the timeline
// ---------------------------------------------------------------------------

const STRATEGY_STEPS = [
    "analyze_facts",
    "fetch_judge",
    "checkpoint_analysis",
    "search_precedents",
    "assess_strength",
    "generate_arguments",
    "checkpoint_arguments",
    "counter_arguments",
    "judge_considerations",
    "synthesize_strategy",
    "verify",
    "checkpoint_memo",
];

// ---------------------------------------------------------------------------
// Strategy Agent Workspace
// ---------------------------------------------------------------------------

export default function StrategyAgentPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();

    const [caseFacts, setCaseFacts] = useState("");
    const [desiredRelief, setDesiredRelief] = useState("");
    const [targetJudge, setTargetJudge] = useState("");
    const [targetBench, setTargetBench] = useState("");
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
                                : STRATEGY_STEPS.indexOf(s.name) ===
                                    STRATEGY_STEPS.indexOf(event.step!) + 1
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
        if (!caseFacts.trim() || !desiredRelief.trim() || starting) return;
        setStarting(true);
        setIsRunning(true);
        setError(null);
        setMemo("");
        setConfidence(undefined);
        setCheckpoint(null);
        setExecutionId(null);
        setSteps(
            STRATEGY_STEPS.map((name, i) => ({
                name,
                status: i === 0 ? ("active" as const) : ("pending" as const),
            })),
        );
        try {
            abortRef.current = runStrategyAgent(
                caseFacts.trim(),
                desiredRelief.trim(),
                handleEvent,
                (err) => {
                    setError(err.message);
                    setIsRunning(false);
                },
                targetJudge.trim() || undefined,
                targetBench || undefined,
            );
        } finally {
            setStarting(false);
        }
    }, [caseFacts, desiredRelief, targetJudge, targetBench, starting, handleEvent]);

    const [checkpointError, setCheckpointError] = useState<string | null>(null);

    const handleResume = useCallback(
        (input: string) => {
            if (!executionId) return;
            const savedCheckpoint = checkpoint;
            setCheckpoint(null);
            setCheckpointError(null);
            setIsRunning(true);
            abortRef.current = resumeAgentExecution(
                executionId,
                input,
                handleEvent,
                (err) => {
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
        setCaseFacts("");
        setDesiredRelief("");
        setTargetJudge("");
        setTargetBench("");
        setIsRunning(false);
        setExecutionId(null);
        setSteps([]);
        setCheckpoint(null);
        setMemo("");
        setConfidence(undefined);
        setError(null);
    }, []);

    if (authLoading || !isAuthenticated) {
        return (
            <div className="min-h-screen flex flex-col">
                <Header />
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            </div>
        );
    }

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
                Strategy Agent
            </h1>
            <p className="text-sm text-muted-foreground mb-6">
                Enter your case facts and desired relief. The agent will analyze
                strengths, generate arguments, anticipate counter-arguments, and
                create a strategic memo.
            </p>

            {/* Input form (shown when not running and no memo) */}
            {showInputForm && (
                <Card>
                    <CardContent className="pt-6 space-y-4">
                        <div>
                            <label htmlFor="strategy-case-facts" className="sr-only">
                                Case facts
                            </label>
                            <Textarea
                                id="strategy-case-facts"
                                placeholder="Describe the facts of your case..."
                                value={caseFacts}
                                onChange={(e) => setCaseFacts(e.target.value)}
                                className="min-h-[120px] text-sm"
                            />
                        </div>

                        <div>
                            <label htmlFor="strategy-desired-relief" className="sr-only">
                                Desired relief
                            </label>
                            <Input
                                id="strategy-desired-relief"
                                placeholder="What relief are you seeking?"
                                value={desiredRelief}
                                onChange={(e) => setDesiredRelief(e.target.value)}
                            />
                        </div>

                        <div className="grid gap-4 sm:grid-cols-2">
                            <div>
                                <label htmlFor="strategy-target-judge" className="sr-only">
                                    Target judge (optional)
                                </label>
                                <Input
                                    id="strategy-target-judge"
                                    placeholder="Target judge name (optional)"
                                    value={targetJudge}
                                    onChange={(e) => setTargetJudge(e.target.value)}
                                />
                            </div>

                            <div>
                                <label htmlFor="strategy-target-bench" className="sr-only">
                                    Target bench type (optional)
                                </label>
                                <Select
                                    value={targetBench}
                                    onValueChange={setTargetBench}
                                >
                                    <SelectTrigger id="strategy-target-bench" className="w-full">
                                        <SelectValue placeholder="Bench type (optional)" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="single">Single Bench</SelectItem>
                                        <SelectItem value="division">Division Bench</SelectItem>
                                        <SelectItem value="full">Full Bench</SelectItem>
                                        <SelectItem value="constitutional">Constitutional Bench</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <Button
                            onClick={handleSubmit}
                            disabled={starting || !caseFacts.trim() || !desiredRelief.trim()}
                        >
                            {starting ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                "Analyze Strategy"
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
                        {/* Input summary display */}
                        <Card>
                            <CardContent className="pt-4">
                                <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">
                                    Case Facts
                                </p>
                                <p className="text-sm mb-3">{caseFacts}</p>
                                <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">
                                    Desired Relief
                                </p>
                                <p className="text-sm">{desiredRelief}</p>
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

                        {/* New Analysis button after completion */}
                        {!isRunning && (memo || error) && (
                            <>
                                <LegalDisclaimer className="mt-2" />
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleReset}
                                >
                                    <RotateCcw className="h-3.5 w-3.5 mr-1.5" />{" "}
                                    New Analysis
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
