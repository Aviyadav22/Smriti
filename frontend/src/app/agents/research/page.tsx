"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { runResearchAgent, resumeAgentExecution, getAccessToken } from "@/lib/api";
import type { AgentStreamEvent, AgentStep, ProcessEvent, ResearchFootnote, ResearchAudit } from "@/lib/types";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { PlanReview } from "@/components/plan-review";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { ResearchProcessPanel } from "@/components/research-process-panel";
import { ResearchProgressBar } from "@/components/research-progress-bar";
import { ResearchFootnotes } from "@/components/research-footnotes";
import { FootnotesPanel } from "@/components/footnotes-panel";
import { VerificationBanner } from "@/components/verification-banner";
import { ResearchAuditTrail } from "@/components/research-audit-trail";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Loader2, ArrowLeft, RotateCcw, FileText, XCircle } from "lucide-react";
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
    // Full pipeline steps
    "plan_research",
    "checkpoint_plan",
    "dispatch_workers",
    "gather_results",
    "batch_cot_with_reflection",
    "evaluate_and_extract",
    "gap_analysis",
    "checkpoint_findings",
    // Fast path steps (used for simple queries)
    "fast_path_search",
    "fast_path_synthesis",
    // Phase 4 pipeline (shared by both paths)
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

// D26-D30: Domain workflow presets
const DOMAIN_PRESETS = [
    { id: "criminal", label: "Criminal Defense", icon: "⚖️", template: "Analyze criminal defense options for: " },
    { id: "constitutional", label: "Constitutional", icon: "📜", template: "Constitutional petition analysis for: " },
    { id: "corporate", label: "Corporate Advisory", icon: "🏢", template: "Corporate law advisory on: " },
    { id: "tax", label: "Tax Dispute", icon: "📊", template: "Tax dispute research on: " },
    { id: "family", label: "Family Law", icon: "👨‍👩‍👧", template: "Family law research on: " },
] as const;

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
    const [confidenceBreakdown, setConfidenceBreakdown] = useState<{
        data_confidence?: number;
        legal_confidence?: number;
        consistency_confidence?: number;
    } | undefined>();
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
    const [isOffline, setIsOffline] = useState(false);

    // D21: Offline detection
    useEffect(() => {
        const goOffline = () => setIsOffline(true);
        const goOnline = () => setIsOffline(false);
        window.addEventListener("offline", goOffline);
        window.addEventListener("online", goOnline);
        setIsOffline(!navigator.onLine);
        return () => {
            window.removeEventListener("offline", goOffline);
            window.removeEventListener("online", goOnline);
        };
    }, []);

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

        // [S5] Handle streaming memo chunks (currently unused — backend emits
        // final memo as "done" event, not incremental chunks. Kept for future
        // streaming wire-up)
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
            case "checkpoint": {
                if (event.execution_id) setExecutionId(event.execution_id);
                const ctx = event.context || {};
                setCheckpoint({
                    question: event.question || "",
                    context: ctx,
                });
                // Extract memo + footnotes from checkpoint context (e.g. checkpoint_memo)
                if (ctx.draft_memo) {
                    setMemo(ctx.draft_memo as string);
                    setStreamingMemo("");
                }
                if (ctx.confidence !== undefined) {
                    setConfidence(ctx.confidence as number);
                }
                if (ctx.footnotes && (ctx.footnotes as ResearchFootnote[]).length > 0) {
                    setFootnotes(ctx.footnotes as ResearchFootnote[]);
                    setFootnotesPanelOpen(true);
                }
                if (ctx.research_audit) {
                    const audit = ctx.research_audit as ResearchAudit;
                    setResearchAudit(audit);
                    if (audit.verification_banner) {
                        setVerificationBanner(audit.verification_banner);
                        setCitationsVerified(audit.citations_verified ?? 0);
                        setCitationsRemoved(audit.citations_removed ?? 0);
                    }
                }
                setIsRunning(false);
                break;
            }
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
            case "done": {
                setExecutionId(event.execution_id || null);
                setIsRunning(false);
                // Parse confidence breakdown from done event data
                const doneData = event.data as Record<string, unknown> | undefined;
                if (doneData?.confidence_breakdown) {
                    setConfidenceBreakdown(doneData.confidence_breakdown as {
                        data_confidence?: number;
                        legal_confidence?: number;
                        consistency_confidence?: number;
                    });
                }
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
            }
            case "error": {
                const category = (event as Record<string, unknown>).category as string | undefined;
                const recoverable = (event as Record<string, unknown>).recoverable as boolean | undefined;
                const prefix = category ? `[${category}] ` : "";
                setError(prefix + (event.message || "Agent encountered an error"));
                if (!recoverable) {
                    setIsRunning(false);
                }
                break;
            }
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
        setConfidenceBreakdown(undefined);
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

    const handleReviseSection = useCallback(async (heading: string, feedback: string): Promise<string | null> => {
        if (!executionId) return null;
        try {
            const token = getAccessToken();
            const res = await fetch(`/api/agents/research/revise-section/${executionId}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({ section_heading: heading, feedback }),
            });
            if (!res.ok) return null;
            const reader = res.body?.getReader();
            if (!reader) return null;
            const decoder = new TextDecoder();
            let revisedContent: string | null = null;
            let buffer = "";
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";
                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const data = JSON.parse(line.slice(6));
                    if (data.type === "section_delta") {
                        revisedContent = data.content;
                    }
                }
            }
            // Update memo in-place
            if (revisedContent) {
                setMemo((prev) => {
                    const memoLines = prev.split("\n");
                    let startIdx: number | null = null;
                    let endIdx: number | null = null;
                    for (let i = 0; i < memoLines.length; i++) {
                        const stripped = memoLines[i].trim();
                        if (stripped.startsWith("##") && !stripped.startsWith("###")) {
                            const h = stripped.replace(/^#+\s*/, "");
                            if (h.toLowerCase() === heading.toLowerCase()) {
                                startIdx = i;
                            } else if (startIdx !== null && endIdx === null) {
                                endIdx = i;
                            }
                        }
                    }
                    if (startIdx === null) return prev;
                    if (endIdx === null) endIdx = memoLines.length;
                    return [...memoLines.slice(0, startIdx), ...revisedContent!.split("\n"), ...memoLines.slice(endIdx)].join("\n");
                });
            }
            return revisedContent;
        } catch {
            return null;
        }
    }, [executionId]);

    const handleCancel = useCallback(() => {
        abortRef.current?.abort();
        setIsRunning(false);
        setError("Research cancelled by user.");
    }, []);

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
        setConfidenceBreakdown(undefined);
        setError(null);
        setCheckpointError(null);
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
                    footnotes.length > 0 && !isRunning ? "max-w-[1400px]" : "max-w-6xl"
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
            {/* D21: Offline banner */}
            {isOffline && (
                <div className="bg-destructive/10 border border-destructive/30 text-destructive rounded-md px-4 py-2 text-sm" role="alert">
                    You are offline. Please check your internet connection.
                </div>
            )}

            {showInputForm && (
                <Card>
                    <CardContent className="pt-6 space-y-4">
                        <label htmlFor="research-query" className="sr-only">Enter your legal research question</label>
                        <Textarea
                            id="research-query"
                            placeholder="Enter your legal research question..."
                            value={query}
                            onChange={(e) => {
                                if (e.target.value.length <= 2000) setQuery(e.target.value);
                            }}
                            className="min-h-[120px] text-sm"
                            maxLength={2000}
                            aria-label="Legal research question"
                            aria-describedby="query-char-count"
                        />
                        {/* D26-D30: Domain preset chips */}
                        <div className="flex flex-wrap gap-1.5">
                            {DOMAIN_PRESETS.map((preset) => (
                                <button
                                    key={preset.id}
                                    className="text-xs px-2.5 py-1 rounded-full border border-border hover:bg-accent transition-colors"
                                    onClick={() => setQuery(preset.template)}
                                    type="button"
                                >
                                    {preset.icon} {preset.label}
                                </button>
                            ))}
                        </div>
                        <div className="flex items-center justify-between">
                            <span id="query-char-count" className={`text-xs ${query.length > 1800 ? "text-amber-500" : "text-muted-foreground"}`}>
                                {query.length}/2000
                            </span>
                            <Button
                                onClick={handleSubmit}
                                disabled={starting || !query.trim() || isOffline}
                                aria-label="Start legal research"
                            >
                                {starting ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    "Start Research"
                                )}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Running or completed state */}
            {showWorkspace && (
                <div className={`grid gap-6 md:grid-cols-[240px_1fr] ${
                    footnotes.length > 0 && !isRunning ? "lg:grid-cols-[240px_1fr_380px]" : ""
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

                        {/* [D8] Progress bar — 5-stage weighted progress */}
                        {isRunning && (
                            <ResearchProgressBar events={processEvents} isRunning={isRunning} />
                        )}

                        {/* Mobile step timeline + process panel */}
                        <div className="md:hidden space-y-3">
                            <AgentStepTimeline steps={steps} />
                            <ResearchProcessPanel events={processEvents} isRunning={isRunning} />
                        </div>

                        {/* Checkpoint prompt — structured plan review or generic */}
                        {checkpoint && checkpoint.context?.research_plan ? (
                            <PlanReview
                                question={checkpoint.question}
                                researchPlan={checkpoint.context.research_plan as Array<{task_type: string; nl_query: string; rationale: string; named_cases?: Array<{name?: string; citation?: string}>; priority?: number}>}
                                classification={checkpoint.context.classification as Record<string, unknown> | null}
                                statuteContext={checkpoint.context.statute_context as Array<{act: string; section: string; title?: string; repealed?: boolean}>}
                                legalElements={checkpoint.context.legal_elements as Array<{id: string; description: string; contested?: boolean}>}
                                includeAdversarial={checkpoint.context.include_adversarial as boolean | undefined}
                                onSubmit={handleResume}
                                disabled={isRunning}
                            />
                        ) : checkpoint ? (
                            <AgentCheckpointPrompt
                                question={checkpoint.question}
                                context={checkpoint.context}
                                onSubmit={handleResume}
                                disabled={isRunning}
                                error={checkpointError}
                                onClearError={() => setCheckpointError(null)}
                            />
                        ) : null}

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
                                        maxFootnote={footnotes.length}
                                        onFootnoteClick={(num) => {
                                            setSelectedFootnoteNum(num);
                                            setFootnotesPanelOpen(true);
                                        }}
                                        confidenceBreakdown={confidenceBreakdown}
                                        footnoteVerification={
                                            footnotes.length > 0
                                                ? Object.fromEntries(
                                                    footnotes.map((f) => [
                                                        f.number,
                                                        f.verification_status as "verified_pg" | "verified_ik" | "verified_neo4j" | "unverified" | "removed" | "flagged",
                                                    ])
                                                )
                                                : undefined
                                        }
                                        executionId={executionId ?? undefined}
                                        onReviseSection={!isRunning ? handleReviseSection : undefined}
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

                        {/* Error + Retry [M49] */}
                        {error && (
                            <div className="text-sm text-red-500 p-3 rounded-md bg-red-50 dark:bg-red-950/20 flex items-center justify-between" role="alert">
                                <span>{error}</span>
                                {!isRunning && query.trim() && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleSubmit}
                                        className="ml-2 shrink-0"
                                    >
                                        Retry Research
                                    </Button>
                                )}
                            </div>
                        )}

                        {/* D16: Typing indicator + D19: Cancel button */}
                        {isRunning && !checkpoint && (
                            <div className="flex items-center gap-3">
                                <div className="flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    <span>Agent is working</span>
                                    <span className="inline-flex gap-0.5">
                                        <span className="animate-bounce" style={{ animationDelay: "0ms" }}>.</span>
                                        <span className="animate-bounce" style={{ animationDelay: "150ms" }}>.</span>
                                        <span className="animate-bounce" style={{ animationDelay: "300ms" }}>.</span>
                                    </span>
                                </div>
                                <Button variant="ghost" size="sm" onClick={handleCancel} className="text-muted-foreground hover:text-destructive">
                                    <XCircle className="h-3.5 w-3.5 mr-1" />
                                    Cancel
                                </Button>
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
