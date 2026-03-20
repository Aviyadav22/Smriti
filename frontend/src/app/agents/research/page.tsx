"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { runResearchAgent, resumeAgentExecution } from "@/lib/api";
import type { AgentStreamEvent, AgentStep, ProcessEvent, ResearchFootnote, ResearchAudit } from "@/lib/types";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { ResearchProcessPanel } from "@/components/research-process-panel";
import { ResearchFootnotes } from "@/components/research-footnotes";
import { FootnotesPanel } from "@/components/footnotes-panel";
import { VerificationBanner } from "@/components/verification-banner";
import { ResearchAuditTrail } from "@/components/research-audit-trail";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Loader2, ArrowLeft, RotateCcw, FileText } from "lucide-react";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Expected research agent steps for the timeline (V2 pipeline)
// ---------------------------------------------------------------------------

const RESEARCH_STEPS = [
    "rewrite_query",
    "classify",
    "plan_research",
    "checkpoint_plan",
    "dispatch_workers",
    "gather_results",
    "batch_cot_with_reflection",
    "evaluate_and_extract",
    "gap_analysis",
    "checkpoint_findings",
    "speculative_synthesis",
    "format_footnotes",
    "verify_v2",
    "quality_check",
    "checkpoint_memo",
];

// T1 process event types
const PROCESS_EVENT_TYPES = new Set([
    "plan", "searching", "found", "evaluating", "reflection",
    "gap", "drafting", "verification", "quality",
]);

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
    const [streamingMemo, setStreamingMemo] = useState("");
    const [confidence, setConfidence] = useState<number | undefined>();
    const [error, setError] = useState<string | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    // Phase 4 state
    const [processEvents, setProcessEvents] = useState<ProcessEvent[]>([]);
    const [footnotes, setFootnotes] = useState<ResearchFootnote[]>([]);
    const [researchAudit, setResearchAudit] = useState<ResearchAudit | null>(null);
    const [verificationBanner, setVerificationBanner] = useState<string | null>(null);
    const [citationsVerified, setCitationsVerified] = useState(0);
    const [citationsRemoved, setCitationsRemoved] = useState(0);
    const [footnotesPanelOpen, setFootnotesPanelOpen] = useState(false);
    const [selectedFootnoteNum, setSelectedFootnoteNum] = useState<number | null>(null);

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

        // [T1] Handle process visualization events
        if (PROCESS_EVENT_TYPES.has(event.type)) {
            setProcessEvents((prev) => [
                ...prev,
                { type: event.type, data: (event.data || {}) as Record<string, unknown>, timestamp: Date.now() },
            ]);
            return;
        }

        // [S5] Handle streaming memo chunks
        if (event.type === "memo_stream" && event.chunk) {
            setStreamingMemo((prev) => prev + event.chunk);
            return;
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
            case "memo": {
                setMemo(event.content || "");
                setStreamingMemo(""); // Replace streaming content with final
                const data = event.data as Record<string, unknown> | undefined;
                if (data && "confidence" in data) {
                    setConfidence(data.confidence as number);
                }
                // Extract Phase 4 structured data
                if (data?.footnotes) {
                    setFootnotes(data.footnotes as ResearchFootnote[]);
                    if ((data.footnotes as ResearchFootnote[]).length > 0) {
                        setFootnotesPanelOpen(true);
                    }
                }
                if (data?.research_audit) {
                    const audit = data.research_audit as ResearchAudit;
                    setResearchAudit(audit);
                    if (audit.verification_banner) {
                        setVerificationBanner(audit.verification_banner);
                        setCitationsVerified(audit.citations_verified ?? 0);
                        setCitationsRemoved(audit.citations_removed ?? 0);
                    }
                }
                break;
            }
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
        setStreamingMemo("");
        setConfidence(undefined);
        setCheckpoint(null);
        setExecutionId(null);
        setProcessEvents([]);
        setFootnotes([]);
        setResearchAudit(null);
        setVerificationBanner(null);
        setCitationsVerified(0);
        setCitationsRemoved(0);
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
        setStreamingMemo("");
        setConfidence(undefined);
        setError(null);
        setProcessEvents([]);
        setFootnotes([]);
        setResearchAudit(null);
        setVerificationBanner(null);
        setCitationsVerified(0);
        setCitationsRemoved(0);
        setFootnotesPanelOpen(false);
        setSelectedFootnoteNum(null);
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
    const displayMemo = memo || streamingMemo;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                <div className={`mx-auto px-4 py-8 ${
                    footnotesPanelOpen && footnotes.length > 0 && !isRunning ? "max-w-[1400px]" : "max-w-6xl"
                }`}>
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
                <div className={`grid gap-6 md:grid-cols-[240px_1fr] ${
                    footnotesPanelOpen && footnotes.length > 0 && !isRunning ? "lg:grid-cols-[240px_1fr_380px]" : ""
                }`}>
                    {/* Left: Step Timeline + Process Panel */}
                    <div className="hidden md:block">
                        <div className="sticky top-20 space-y-4">
                            <div>
                                <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-3">
                                    Progress
                                </h3>
                                <AgentStepTimeline steps={steps} />
                            </div>
                            {/* [T1] Process Visualization Panel */}
                            <ResearchProcessPanel events={processEvents} isRunning={isRunning} />
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

                        {/* Mobile step timeline + process panel */}
                        <div className="md:hidden space-y-3">
                            <AgentStepTimeline steps={steps} />
                            <ResearchProcessPanel events={processEvents} isRunning={isRunning} />
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

                        {/* [T4] Verification Banner */}
                        {verificationBanner && !isRunning && (
                            <VerificationBanner
                                banner={verificationBanner}
                                citationsVerified={citationsVerified}
                                citationsRemoved={citationsRemoved}
                            />
                        )}

                        {/* Memo result (final or streaming) */}
                        {displayMemo && (
                            <Card>
                                <CardContent className="pt-6">
                                    <AgentMemoViewer
                                        content={displayMemo}
                                        confidence={confidence}
                                        onFootnoteClick={(num) => {
                                            setSelectedFootnoteNum(num);
                                            setFootnotesPanelOpen(true);
                                        }}
                                    />
                                </CardContent>
                            </Card>
                        )}

                        {/* Mobile: Footnotes Sheet Drawer */}
                        {footnotes.length > 0 && !isRunning && (
                            <div className="lg:hidden">
                                <Sheet>
                                    <SheetTrigger asChild>
                                        <Button variant="outline" size="sm" className="w-full">
                                            <FileText className="h-4 w-4 mr-2" />
                                            Footnotes & Sources ({footnotes.filter(f => f.is_used).length})
                                        </Button>
                                    </SheetTrigger>
                                    <SheetContent side="bottom" className="h-[80vh] p-0">
                                        <FootnotesPanel
                                            footnotes={footnotes}
                                            selectedFootnoteNumber={selectedFootnoteNum}
                                            onFootnoteSelect={setSelectedFootnoteNum}
                                            isOpen={true}
                                            onToggle={() => {}}
                                        />
                                    </SheetContent>
                                </Sheet>
                            </div>
                        )}

                        {/* Research Audit Trail */}
                        {researchAudit && !isRunning && (
                            <ResearchAuditTrail audit={researchAudit} />
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

                    {/* Desktop: Footnotes Side Panel */}
                    {footnotes.length > 0 && !isRunning && (
                        <div className="hidden lg:block">
                            <div className="sticky top-20 h-[calc(100vh-6rem)] rounded-lg border overflow-hidden">
                                <FootnotesPanel
                                    footnotes={footnotes}
                                    selectedFootnoteNumber={selectedFootnoteNum}
                                    onFootnoteSelect={setSelectedFootnoteNum}
                                    isOpen={footnotesPanelOpen}
                                    onToggle={() => setFootnotesPanelOpen(!footnotesPanelOpen)}
                                />
                            </div>
                        </div>
                    )}
                </div>
            )}
                </div>
            </main>

            <Footer />
        </div>
    );
}
