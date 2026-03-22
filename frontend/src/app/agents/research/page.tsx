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
// ResearchFootnotes removed — superseded by FootnotesPanel
import { FootnotesPanel } from "@/components/footnotes-panel";
import { VerificationBanner } from "@/components/verification-banner";
import { ResearchAuditTrail } from "@/components/research-audit-trail";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Loader2, ArrowLeft, RotateCcw, FileText, XCircle, Scale, ScrollText, Building2, BarChart3, Users, PanelRightOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Expected research agent steps for the timeline (V2 pipeline)
// ---------------------------------------------------------------------------

// Common steps shared by both paths
const COMMON_START_STEPS = ["rewrite_query", "classify"];
const COMMON_END_STEPS = ["speculative_synthesis", "format_footnotes", "verify_v2", "quality_check", "checkpoint_memo"];

// Full pipeline steps (complex queries)
const FULL_PIPELINE_STEPS = [
    ...COMMON_START_STEPS,
    "plan_research", "checkpoint_plan", "dispatch_workers", "gather_results",
    "batch_cot_with_reflection", "evaluate_and_extract", "gap_analysis", "checkpoint_findings",
    ...COMMON_END_STEPS,
];

// Fast path steps (simple queries)
const FAST_PATH_STEPS = [
    ...COMMON_START_STEPS,
    "fast_path_search", "fast_path_synthesis",
    ...COMMON_END_STEPS,
];

// Fast path indicator steps
const FAST_PATH_INDICATORS = new Set(["fast_path_search", "fast_path_synthesis"]);
const FULL_PATH_INDICATORS = new Set(["plan_research", "dispatch_workers"]);

// T1 process event types
const PROCESS_EVENT_TYPES = new Set([
    "plan", "searching", "found", "evaluating", "reflection",
    "gap", "drafting", "verification", "quality", "progress",
]);

// D26-D30: Domain workflow presets
const DOMAIN_PRESETS = [
    { id: "criminal", label: "Criminal Defense", Icon: Scale, template: "Analyze criminal defense options for: " },
    { id: "constitutional", label: "Constitutional", Icon: ScrollText, template: "Constitutional petition analysis for: " },
    { id: "corporate", label: "Corporate Advisory", Icon: Building2, template: "Corporate law advisory on: " },
    { id: "tax", label: "Tax Dispute", Icon: BarChart3, template: "Tax dispute research on: " },
    { id: "family", label: "Family Law", Icon: Users, template: "Family law research on: " },
] as const;

// Example queries to guide new users
const EXAMPLE_QUERIES = [
    "Can an FIR be quashed under Section 482 CrPC after a compromise between parties?",
    "What is the scope of judicial review under Article 226 for contractual disputes?",
    "Analyze the law on anticipatory bail under Section 438 CrPC for economic offences",
    "Is specific performance available when time is not the essence of a contract under Section 10 of the Specific Relief Act?",
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
    const [currentStepLabel, setCurrentStepLabel] = useState("");
    const [detectedPath, setDetectedPath] = useState<"full" | "fast" | null>(null);
    const [cancelled, setCancelled] = useState(false);

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
            case "status": {
                const stepName = event.step;
                if (stepName) {
                    // Detect pipeline path and filter steps dynamically
                    if (FAST_PATH_INDICATORS.has(stepName)) {
                        setDetectedPath((prev) => {
                            if (prev !== "fast") {
                                setSteps(FAST_PATH_STEPS.map((name, i) => ({
                                    name,
                                    status: i === 0 ? ("active" as const) : ("pending" as const),
                                })));
                            }
                            return "fast";
                        });
                    } else if (FULL_PATH_INDICATORS.has(stepName)) {
                        setDetectedPath((prev) => {
                            if (prev !== "full") {
                                setSteps(FULL_PIPELINE_STEPS.map((name, i) => ({
                                    name,
                                    status: i === 0 ? ("active" as const) : ("pending" as const),
                                })));
                            }
                            return "full";
                        });
                    }
                    setCurrentStepLabel(event.message || stepName);
                }
                // Mark completed step and activate next by name match
                setSteps((prev) => {
                    const stepIdx = prev.findIndex((s) => s.name === stepName);
                    return prev.map((s, i) => ({
                        ...s,
                        status:
                            s.name === stepName
                                ? "completed"
                                : i === stepIdx + 1 && s.status === "pending"
                                    ? "active"
                                    : s.status,
                        message:
                            s.name === stepName
                                ? event.message || s.message
                                : s.message,
                    }));
                });
                break;
            }
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
                const evData = event.data as Record<string, unknown> | undefined;
                const category = evData?.category as string | undefined;
                const recoverable = event.recoverable ?? (evData?.recoverable as boolean | undefined);
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
        setDetectedPath(null);
        setCurrentStepLabel("");
        setCancelled(false);
        setSteps(
            FULL_PIPELINE_STEPS.map((name, i) => ({
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
            if (!executionId) {
                return;
            }
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
        if (!executionId) {
            setError("No active execution — cannot revise section.");
            return null;
        }
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
            if (!res.ok) {
                const errBody = await res.json().catch(() => ({}));
                const msg = (errBody as Record<string, string>).detail || (errBody as Record<string, string>).error || `Revision failed (${res.status})`;
                setError(`Section revision failed: ${msg}`);
                return null;
            }
            const reader = res.body?.getReader();
            if (!reader) {
                setError("Section revision failed: no response stream.");
                return null;
            }
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
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.type === "section_delta") {
                            revisedContent = data.content;
                        }
                    } catch {
                        // Skip malformed SSE line
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
            } else {
                setError("Section revision returned no content. Please try again.");
            }
            return revisedContent;
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Unknown error";
            setError(`Section revision failed: ${msg}`);
            return null;
        }
    }, [executionId]);

    const handleCancel = useCallback(() => {
        abortRef.current?.abort();
        setIsRunning(false);
        setCancelled(true);
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
        setDetectedPath(null);
        setCurrentStepLabel("");
        setCancelled(false);
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
    const isStreaming = !memo && !!streamingMemo;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                <div className="mx-auto px-4 py-8 max-w-[1400px]">
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
                        <label htmlFor="research-query" className="text-sm font-medium text-foreground">
                            What legal question are you investigating?
                        </label>
                        <Textarea
                            id="research-query"
                            placeholder="Enter your legal research question..."
                            value={query}
                            onChange={(e) => {
                                if (e.target.value.length <= 2000) setQuery(e.target.value);
                            }}
                            onKeyDown={(e) => {
                                if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && query.trim() && !starting) {
                                    e.preventDefault();
                                    handleSubmit();
                                }
                            }}
                            className="min-h-[120px] text-sm"
                            maxLength={2000}
                            aria-describedby="query-char-count"
                        />
                        {/* D26-D30: Domain preset chips */}
                        <div className="flex flex-wrap gap-1.5">
                            {DOMAIN_PRESETS.map((preset) => (
                                <button
                                    key={preset.id}
                                    className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-full border border-border hover:bg-accent transition-colors focus-visible:ring-2 focus-visible:ring-ring"
                                    onClick={() => setQuery(preset.template)}
                                    type="button"
                                >
                                    <preset.Icon className="h-3 w-3" /> {preset.label}
                                </button>
                            ))}
                        </div>
                        {/* Example queries for guidance */}
                        {!query && (
                            <div className="space-y-2">
                                <p className="text-xs text-muted-foreground font-medium">Try an example:</p>
                                <div className="grid gap-1.5">
                                    {EXAMPLE_QUERIES.map((eq) => (
                                        <button
                                            key={eq}
                                            type="button"
                                            className="text-left text-xs text-muted-foreground hover:text-foreground px-3 py-2 rounded-md border border-border/50 hover:border-border hover:bg-accent/50 transition-colors"
                                            onClick={() => setQuery(eq)}
                                        >
                                            {eq}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <span id="query-char-count" className={`text-xs ${query.length > 1800 ? "text-amber-500" : "text-muted-foreground"}`}>
                                    {query.length}/2000
                                </span>
                                <span className="text-xs text-muted-foreground hidden sm:inline">Ctrl+Enter to submit</span>
                            </div>
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
                <div className={cn(
                    "grid gap-6 md:grid-cols-[240px_1fr]",
                    "transition-[margin] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
                    footnotesPanelOpen ? "lg:mr-[400px]" : "",
                )}>
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
                                error={checkpointError}
                                onClearError={() => setCheckpointError(null)}
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

                        {/* Skeleton shimmer while waiting for first chunk */}
                        {isRunning && !displayMemo && (
                            <div className="space-y-4 animate-pulse">
                                <div className="h-6 w-3/4 bg-muted rounded" />
                                <div className="h-4 w-full bg-muted rounded" />
                                <div className="h-4 w-full bg-muted rounded" />
                                <div className="h-4 w-5/6 bg-muted rounded" />
                                <div className="h-6 w-2/3 bg-muted rounded mt-6" />
                                <div className="h-4 w-full bg-muted rounded" />
                                <div className="h-4 w-4/5 bg-muted rounded" />
                            </div>
                        )}

                        {/* Memo result (final or streaming) */}
                        {displayMemo && (
                            <Card>
                                <CardContent className="pt-6">
                                    <AgentMemoViewer
                                        content={displayMemo}
                                        confidence={isStreaming ? 0 : confidence}
                                        maxFootnote={footnotes.length}
                                        onFootnoteClick={(num) => {
                                            setSelectedFootnoteNum(num);
                                            setFootnotesPanelOpen(true);
                                        }}
                                        confidenceBreakdown={isStreaming ? undefined : confidenceBreakdown}
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
                                        onReviseSection={isStreaming ? undefined : (!isRunning ? handleReviseSection : undefined)}
                                        footnotes={footnotes}
                                    />
                                    {isStreaming && (
                                        <span className="inline-block w-1.5 h-5 bg-[var(--gold)] animate-pulse ml-0.5 align-text-bottom" />
                                    )}
                                </CardContent>
                            </Card>
                        )}

                        {/* Mobile: Footnotes Sheet Drawer */}
                        {footnotes.length > 0 && (
                            <div className="lg:hidden">
                                <Sheet>
                                    <SheetTrigger asChild>
                                        <Button variant="outline" size="sm" className="w-full">
                                            <FileText className="h-4 w-4 mr-2" />
                                            Footnotes & Sources ({footnotes.filter(f => f.is_used).length})
                                        </Button>
                                    </SheetTrigger>
                                    <SheetContent side="bottom" className="h-[80vh] p-0">
                                        <SheetTitle className="sr-only">Footnotes & Sources</SheetTitle>
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
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    <span>{currentStepLabel || "Agent is working..."}</span>
                                </div>
                                <Button variant="outline" size="sm" onClick={handleCancel} className="text-destructive border-destructive/30 hover:bg-destructive/10">
                                    <XCircle className="h-3.5 w-3.5 mr-1" />
                                    Cancel
                                </Button>
                            </div>
                        )}

                        {/* Cancellation notice (info, not error) */}
                        {cancelled && !isRunning && (
                            <div className="text-sm text-blue-600 dark:text-blue-400 p-3 rounded-md bg-blue-50 dark:bg-blue-950/20 flex items-center justify-between">
                                <span>Research cancelled.</span>
                                {query.trim() && (
                                    <Button variant="outline" size="sm" onClick={handleSubmit} className="ml-2 shrink-0">
                                        Restart Research
                                    </Button>
                                )}
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

                {/* Desktop slide-out footnotes panel — OUTSIDE the grid */}
                <div
                    className={cn(
                        "hidden lg:block fixed right-0 top-20 h-[calc(100vh-5rem)] w-[400px] z-40",
                        "border-l bg-background shadow-xl",
                        "transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
                        footnotesPanelOpen ? "translate-x-0" : "translate-x-full",
                    )}
                >
                    <FootnotesPanel
                        footnotes={footnotes}
                        selectedFootnoteNumber={selectedFootnoteNum}
                        onFootnoteSelect={setSelectedFootnoteNum}
                        isOpen={true}
                        onToggle={() => setFootnotesPanelOpen(false)}
                    />
                </div>

                {/* Floating reopen tab when panel is closed */}
                {footnotes.length > 0 && !footnotesPanelOpen && (
                    <button
                        onClick={() => setFootnotesPanelOpen(true)}
                        className="hidden lg:flex fixed right-0 top-1/2 -translate-y-1/2 z-30 items-center gap-1.5 bg-background/95 border border-r-0 rounded-l-lg shadow-md px-2 py-3 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors backdrop-blur-sm"
                        style={{ writingMode: "vertical-rl" }}
                    >
                        <PanelRightOpen className="h-3.5 w-3.5" />
                        Sources ({footnotes.filter(f => f.is_used).length})
                    </button>
                )}
            )}
                </div>
            </main>

            <Footer />
        </div>
    );
}
