"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { sendAgentFollowUp, getAgentSessionMessages } from "@/lib/api";
import type {
    AgentStreamEvent,
    AgentStep,
    ProcessEvent,
    ResearchFootnote,
    AgentSessionMessage,
} from "@/lib/types";
import { useAgentSession } from "@/hooks/useAgentSession";
import type { AgentSessionState, AgentSessionActions } from "@/hooks/useAgentSession";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { ResearchProgress } from "@/components/research-progress";
// AgentSessionSidebar removed — sessions now shown in the global AppSidebar
import { AgentFollowUpThread } from "@/components/agents/AgentFollowUpThread";
import { AgentFollowUpInput } from "@/components/agents/AgentFollowUpInput";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    AlertDialog,
    AlertDialogContent,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogCancel,
    AlertDialogAction,
} from "@/components/ui/alert-dialog";
import {
    Loader2, ArrowLeft, RotateCcw, XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { useSetAgentSidebar } from "@/hooks/useAgentSidebarContext";
import { useNavigationGuard } from "@/hooks/useNavigationGuard";
import { cancelExecution } from "@/lib/api";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Process event types that bypass the status switch and go straight to feed
// ---------------------------------------------------------------------------

const PROCESS_EVENT_TYPES = new Set([
    "plan", "searching", "found", "evaluating", "reflection",
    "gap", "drafting", "verification", "quality", "progress",
]);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentWorkspaceProps {
    agentType: "research" | "case_prep" | "strategy" | "drafting";
    title: string;
    description: string;
    /** Step names for the agent pipeline (used to initialize AgentStep[]) */
    steps: string[];

    /** Render the agent-specific input form. */
    renderInput: (props: {
        onSubmit: (body: Record<string, unknown>) => void;
        disabled: boolean;
    }) => React.ReactNode;

    /** Render agent-specific extras below the memo (e.g. footnotes, audit trail, section viewer). */
    renderResultExtras?: (props: {
        memo: string;
        confidence: number | undefined;
        executionId: string | null;
        isRunning: boolean;
        session: AgentSessionState & AgentSessionActions;
        processEvents: ProcessEvent[];
        completedNodes: Set<string>;
        startTime: number | null;
        steps: AgentStep[];
        /** The displayed memo content (may include streaming text). */
        displayMemo: string;
        /** Whether memo is still streaming via typewriter effect. */
        isStreaming: boolean;
    }) => React.ReactNode;

    /** Override the default checkpoint UI (e.g. for PlanReview in research). */
    renderCheckpoint?: (props: {
        checkpoint: { question: string; context: Record<string, unknown> };
        onSubmit: (input: string) => void;
        disabled: boolean;
        error: string | null;
        onClearError: () => void;
    }) => React.ReactNode;

    /** Called when user clicks "New Session" -- agent can reset form-specific state. */
    onReset?: () => void;

    /** Label for the new session / restart button. Defaults to "New Session". */
    newSessionLabel?: string;

    /** When true, the default memo Card is not rendered (extras handles its own memo display). */
    suppressDefaultMemo?: boolean;

    /** When true, the default progress feed is not rendered (extras handles its own, e.g. research 5-stage stepper). */
    suppressDefaultProgress?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AgentWorkspace({
    agentType,
    title,
    description,
    steps: stepNames,
    renderInput,
    renderResultExtras,
    renderCheckpoint,
    onReset,
    newSessionLabel = "New Session",
    suppressDefaultMemo = false,
    suppressDefaultProgress = false,
}: AgentWorkspaceProps) {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    // ---- session hook -------------------------------------------------------
    const session = useAgentSession(agentType);

    // ---- navigation guard (block leaving while agent is running) ------------
    const navGuard = useNavigationGuard(session.isRunning);

    // ---- local UI state -----------------------------------------------------
    // Session sidebar removed — sessions are now in the global AppSidebar
    const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
    const [processEvents, setProcessEvents] = useState<ProcessEvent[]>([]);
    const [completedNodes, setCompletedNodes] = useState<Set<string>>(new Set());
    const [startTime, setStartTime] = useState<number | null>(null);
    const [queryDisplay, setQueryDisplay] = useState("");
    const [cancelled, setCancelled] = useState(false);

    // Follow-up state
    const [followUpStreaming, setFollowUpStreaming] = useState(false);
    const [followUpStreamContent, setFollowUpStreamContent] = useState("");

    // Memo streaming (typewriter)
    const [streamingMemo, setStreamingMemo] = useState("");
    const streamQueueRef = useRef("");
    const rafIdRef = useRef<number | null>(null);

    // ---- auth guard ---------------------------------------------------------
    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push("/login");
        if (!authLoading && isAuthenticated && session.error?.toLowerCase().includes("session expired")) {
            session.setError(null);
        }
    }, [authLoading, isAuthenticated, router, session.error, session]);

    // ---- cleanup ------------------------------------------------------------
    useEffect(() => {
        return () => { session.abortRef.current?.abort(); };
    }, [session.abortRef]);

    // ---- typewriter animation -----------------------------------------------
    useEffect(() => {
        const CHARS_PER_FRAME = 30;
        const tick = () => {
            if (streamQueueRef.current.length > 0) {
                const batch = streamQueueRef.current.slice(0, CHARS_PER_FRAME);
                streamQueueRef.current = streamQueueRef.current.slice(CHARS_PER_FRAME);
                setStreamingMemo((prev) => prev + batch);
            }
            rafIdRef.current = requestAnimationFrame(tick);
        };
        rafIdRef.current = requestAnimationFrame(tick);
        return () => {
            if (rafIdRef.current !== null) cancelAnimationFrame(rafIdRef.current);
        };
    }, []);

    // ---- load sessions on mount ---------------------------------------------
    useEffect(() => {
        if (isAuthenticated) session.refreshSessions();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isAuthenticated]);

    // ---- handle ?session= query param --------------------------------------
    useEffect(() => {
        const paramSessionId = searchParams.get("session");
        if (paramSessionId && isAuthenticated) {
            session.loadSession(paramSessionId);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchParams, isAuthenticated]);

    // ---- Restore query display from loaded session messages -----------------
    useEffect(() => {
        if (session.sessionMessages.length > 0 && !queryDisplay) {
            const firstQuery = session.sessionMessages.find(
                (m) => m.role === "user" && m.message_type === "query",
            );
            if (firstQuery) setQueryDisplay(firstQuery.content);
        }
    }, [session.sessionMessages, queryDisplay]);

    // ---------------------------------------------------------------------------
    // SSE event handler (mirrors research page logic exactly)
    // ---------------------------------------------------------------------------

    const handleEvent = useCallback((event: AgentStreamEvent) => {
        // Process events go straight to the activity feed
        if (PROCESS_EVENT_TYPES.has(event.type)) {
            setProcessEvents((prev) => [
                ...prev,
                { type: event.type, data: (event.data || {}) as Record<string, unknown>, timestamp: Date.now() },
            ]);
            return;
        }

        // Memo stream chunks -> typewriter queue
        if (event.type === "memo_stream" && event.chunk) {
            streamQueueRef.current += event.chunk;
            return;
        }

        switch (event.type) {
            case "status": {
                const stepName = event.step;
                if (stepName) {
                    // Track completed nodes for progress display
                    setCompletedNodes((prev) => {
                        const next = new Set(prev);
                        next.add(stepName);
                        return next;
                    });
                    // Push to processEvents with dedup (same logic as research page)
                    setProcessEvents((prev) => {
                        const now = Date.now();
                        for (let i = prev.length - 1; i >= Math.max(0, prev.length - 3); i--) {
                            const recent = prev[i];
                            if (recent.timestamp && now - recent.timestamp < 1000) {
                                if (recent.type === "found" || recent.type === "plan" ||
                                    recent.type === "evaluating" || recent.type === "reflection" ||
                                    recent.type === "gap" || recent.type === "drafting" ||
                                    recent.type === "verification" || recent.type === "quality") {
                                    return prev;
                                }
                                if (recent.type === "status" && (recent.data as Record<string, unknown>).step === stepName) {
                                    return prev;
                                }
                            }
                        }
                        return [
                            ...prev,
                            {
                                type: "status",
                                data: { step: stepName } as Record<string, unknown>,
                                timestamp: Date.now(),
                            },
                        ];
                    });
                }
                // Update step timeline
                setAgentSteps((prev) => {
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
                if (event.execution_id) session.setExecutionId(event.execution_id);
                const ctx = event.context || {};
                session.setCheckpoint({
                    question: event.question || "",
                    context: ctx,
                });
                // Extract memo from checkpoint context — different agents use different keys
                const checkpointMemo = (ctx.draft_memo || ctx.strategy_memo || ctx.full_draft || ctx.memo) as string | undefined;
                if (checkpointMemo) {
                    streamQueueRef.current = "";
                    session.setMemo(checkpointMemo);
                    setStreamingMemo("");
                }
                if (ctx.confidence !== undefined) {
                    session.setConfidence(ctx.confidence as number);
                }
                if (ctx.footnotes && (ctx.footnotes as ResearchFootnote[]).length > 0) {
                    session.setFootnotes(ctx.footnotes as ResearchFootnote[]);
                }
                session.setIsRunning(false);
                break;
            }
            case "memo": {
                // If we already have streamed content (from memo_stream events), finalize it.
                // Otherwise, feed the memo through the typewriter queue for a smooth reveal.
                const memoContent = event.content || "";
                if (streamingMemo || streamQueueRef.current) {
                    // Already streaming — finalize immediately
                    streamQueueRef.current = "";
                    session.setMemo(memoContent);
                    setStreamingMemo("");
                } else {
                    // No prior streaming — feed through typewriter for smooth display
                    streamQueueRef.current = memoContent;
                    // Set final memo after a delay so typewriter can render
                    setTimeout(() => {
                        streamQueueRef.current = "";
                        session.setMemo(memoContent);
                        setStreamingMemo("");
                    }, Math.min(memoContent.length / 30 * 16, 5000)); // ~30 chars/frame, capped at 5s
                }
                const data = event.data as Record<string, unknown> | undefined;
                if (data && "confidence" in data) {
                    session.setConfidence(data.confidence as number);
                }
                if (data?.footnotes) {
                    session.setFootnotes(data.footnotes as ResearchFootnote[]);
                }
                break;
            }
            case "done": {
                session.setExecutionId(event.execution_id || null);
                session.setIsRunning(false);
                setAgentSteps((prev) =>
                    prev.map((s) => ({
                        ...s,
                        status:
                            s.status === "active" || s.status === "pending"
                                ? "completed"
                                : s.status,
                    })),
                );
                session.refreshSessions();
                break;
            }
            case "error": {
                const evData = event.data as Record<string, unknown> | undefined;
                const category = evData?.category as string | undefined;
                const recoverable = event.recoverable ?? (evData?.recoverable as boolean | undefined);
                const prefix = category ? `[${category}] ` : "";
                session.setError(prefix + (event.message || "Agent encountered an error"));
                if (!recoverable) {
                    session.setIsRunning(false);
                }
                break;
            }
        }
    }, [session]);

    // ---------------------------------------------------------------------------
    // Submit handler
    // ---------------------------------------------------------------------------

    const handleSubmit = useCallback((body: Record<string, unknown>) => {
        // Capture query for display
        const displayText = (body.query as string) || (body.case_facts as string) || "";
        setQueryDisplay(displayText);

        setAgentSteps(
            stepNames.map((name, i) => ({
                name,
                status: i === 0 ? ("active" as const) : ("pending" as const),
            })),
        );
        setProcessEvents([]);
        setCompletedNodes(new Set());
        setStartTime(Date.now());
        setStreamingMemo("");
        streamQueueRef.current = "";
        setCancelled(false);

        session.startSession(body, handleEvent);
    }, [stepNames, session, handleEvent]);

    // ---------------------------------------------------------------------------
    // Follow-up handler
    // ---------------------------------------------------------------------------

    const handleFollowUp = useCallback((message: string) => {
        if (!session.sessionId || followUpStreaming) return;
        setFollowUpStreaming(true);
        setFollowUpStreamContent("");
        session.setError(null);

        const tempUserMsg: AgentSessionMessage = {
            id: `temp-${Date.now()}`,
            role: "user",
            content: message,
            sources: null,
            message_type: "follow_up",
            execution_id: null,
            created_at: new Date().toISOString(),
        };
        session.sessionMessages.push(tempUserMsg);
        // Force re-render by updating session messages (the hook stores them)
        // We manipulate the array directly since the hook doesn't expose setSessionMessages
        // The effect will re-derive from server after done event

        session.abortRef.current = sendAgentFollowUp(
            session.sessionId,
            message,
            (event) => {
                if (event.type === "memo_stream" && event.chunk) {
                    setFollowUpStreamContent((prev) => prev + event.chunk);
                }
                if (event.type === "memo" || event.type === "done") {
                    setFollowUpStreaming(false);
                    setFollowUpStreamContent("");
                    getAgentSessionMessages(session.sessionId!).then((msgs) => {
                        // Reload via loadSession to refresh messages
                        session.loadSession(session.sessionId!);
                    }).catch(() => {
                        // Keep optimistic messages on failure
                    });
                    session.refreshSessions();
                }
                if (event.type === "error") {
                    setFollowUpStreaming(false);
                    setFollowUpStreamContent("");
                    session.setError(event.message || "Follow-up failed");
                }
            },
            (err) => {
                setFollowUpStreaming(false);
                setFollowUpStreamContent("");
                session.setError(err.message);
            },
        );
    }, [session, followUpStreaming]);

    // ---------------------------------------------------------------------------
    // New session / cancel
    // ---------------------------------------------------------------------------

    const handleNewSession = useCallback(() => {
        session.newSession();
        setAgentSteps([]);
        setProcessEvents([]);
        setCompletedNodes(new Set());
        setStartTime(null);
        setStreamingMemo("");
        streamQueueRef.current = "";
        setQueryDisplay("");
        setCancelled(false);
        setFollowUpStreaming(false);
        setFollowUpStreamContent("");
        onReset?.();
    }, [session, onReset]);

    const handleCancel = useCallback(() => {
        session.abortRef.current?.abort();
        session.setIsRunning(false);
        setCancelled(true);
    }, [session]);

    /** Cancel the running execution and proceed with the pending navigation. */
    const handleCancelAndLeave = useCallback(async () => {
        session.abortRef.current?.abort();
        session.setIsRunning(false);
        if (session.executionId) {
            try {
                await cancelExecution(session.executionId);
            } catch {
                // Best-effort — navigate anyway
            }
        }
        navGuard.confirmLeave();
    }, [session, navGuard]);

    // ---------------------------------------------------------------------------
    // Derived state
    // ---------------------------------------------------------------------------

    const displayMemo = session.memo || streamingMemo;
    const isStreaming = !session.memo && !!streamingMemo;
    const showInputForm = !session.isRunning && !session.memo && !session.checkpoint && completedNodes.size === 0 && processEvents.length === 0 && !session.isFollowUp;
    const showWorkspace = session.isRunning || session.isBackgroundRunning || !!session.memo || !!session.checkpoint || completedNodes.size > 0 || processEvents.length > 0 || session.isFollowUp;
    const showFollowUpArea = session.isFollowUp && !session.isRunning && !!session.memo && !session.checkpoint;

    // ---------------------------------------------------------------------------
    // Auth loading
    // ---------------------------------------------------------------------------

    if (authLoading || !isAuthenticated) {
        return null;
    }

    // ---------------------------------------------------------------------------
    // Render
    // ---------------------------------------------------------------------------

    // Push session data up to the global sidebar via context
    // Use refs for callbacks to avoid infinite re-render loops
    const setAgentSidebar = useSetAgentSidebar();
    const loadSessionRef = useRef(session.loadSession);
    loadSessionRef.current = session.loadSession;
    const deleteSessionRef = useRef(session.deleteSession);
    deleteSessionRef.current = session.deleteSession;
    const newSessionRef = useRef(handleNewSession);
    newSessionRef.current = handleNewSession;

    const guardedActionRef = useRef(navGuard.guardedAction);
    guardedActionRef.current = navGuard.guardedAction;

    useEffect(() => {
        setAgentSidebar({
            sessions: session.sessions,
            activeSessionId: session.sessionId,
            loading: session.sessionsLoading,
            onSelectSession: (id: string) => guardedActionRef.current(() => loadSessionRef.current(id)),
            onDeleteSession: (id: string) => deleteSessionRef.current(id),
            onNewSession: () => guardedActionRef.current(() => newSessionRef.current()),
        });
        return () => setAgentSidebar(null);
    }, [session.sessions, session.sessionId, session.sessionsLoading, setAgentSidebar]);

    return (
        <div className="flex-1 flex flex-col h-full">
            <div className="flex-1 flex h-full">
                {/* Main content area */}
                <div className="flex-1 min-w-0 relative h-full">
                    {/* Back arrow — pinned top-left */}
                    <div className="absolute top-4 left-4 z-10">
                        {session.isRunning ? (
                            <Button variant="ghost" size="sm" onClick={() => navGuard.guardedNavigate("/dashboard")}>
                                <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Agents
                            </Button>
                        ) : (
                            <Button variant="ghost" size="sm" asChild>
                                <Link href="/dashboard">
                                    <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Agents
                                </Link>
                            </Button>
                        )}
                    </div>

                    <div className={cn(
                        "mx-auto px-4 max-w-[1400px]",
                        showInputForm ? "flex flex-col items-center justify-center h-full" : "py-16",
                    )}>

                        {/* Input form with title */}
                        {showInputForm && (
                            <div className="w-full">
                                <div className="text-center mb-8">
                                    <h1 className="text-2xl font-semibold font-[family-name:var(--font-lora)] mb-1">
                                        {title}
                                    </h1>
                                    <p className="text-sm text-muted-foreground">
                                        {description}
                                    </p>
                                </div>
                                {renderInput({ onSubmit: handleSubmit, disabled: session.isRunning })}
                            </div>
                        )}

                        {/* Workspace (running / completed) */}
                        {showWorkspace && (
                            <div className="space-y-4 max-w-4xl mx-auto">
                                {/* Query display */}
                                {queryDisplay && (
                                    <div className="rounded-lg border bg-card px-5 py-4">
                                        <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">
                                            Query
                                        </p>
                                        <p className="text-sm font-medium">{queryDisplay}</p>
                                    </div>
                                )}

                                {/* Live progress — activity feed with streaming events */}
                                {!suppressDefaultProgress && (
                                    <ResearchProgress
                                        events={processEvents}
                                        completedNodes={completedNodes}
                                        isRunning={session.isRunning}
                                        startTime={startTime ?? undefined}
                                    />
                                )}

                                {/* Checkpoint */}
                                {session.checkpoint && (
                                    renderCheckpoint
                                        ? renderCheckpoint({
                                            checkpoint: session.checkpoint,
                                            onSubmit: session.resume,
                                            disabled: session.isRunning,
                                            error: session.checkpointError,
                                            onClearError: () => session.setCheckpointError(null),
                                        })
                                        : (
                                            <AgentCheckpointPrompt
                                                question={session.checkpoint.question}
                                                context={session.checkpoint.context}
                                                onSubmit={session.resume}
                                                disabled={session.isRunning}
                                                error={session.checkpointError}
                                                onClearError={() => session.setCheckpointError(null)}
                                            />
                                        )
                                )}

                                {/* Agent-specific extras (rendered before skeleton so progress bar is always on top) */}
                                {renderResultExtras?.({
                                    memo: session.memo,
                                    confidence: session.confidence,
                                    executionId: session.executionId,
                                    isRunning: session.isRunning,
                                    session,
                                    processEvents,
                                    completedNodes,
                                    startTime,
                                    steps: agentSteps,
                                    displayMemo,
                                    isStreaming,
                                })}

                                {/* Skeleton shimmer while waiting (after extras so progress stays on top) */}
                                {session.isRunning && !displayMemo && !session.checkpoint && (
                                    <div className="rounded-lg border bg-card p-6 space-y-4">
                                        <div className="space-y-3 animate-pulse">
                                            <div className="h-5 w-2/3 bg-muted rounded" />
                                            <div className="h-3 w-full bg-muted/70 rounded" />
                                            <div className="h-3 w-full bg-muted/70 rounded" />
                                            <div className="h-3 w-5/6 bg-muted/70 rounded" />
                                            <div className="h-5 w-1/2 bg-muted rounded mt-4" />
                                            <div className="h-3 w-full bg-muted/70 rounded" />
                                            <div className="h-3 w-4/5 bg-muted/70 rounded" />
                                        </div>
                                    </div>
                                )}

                                {/* Memo result (skipped when extras handles its own memo) */}
                                {!suppressDefaultMemo && displayMemo && (
                                    <Card>
                                        <CardContent className="pt-6">
                                            <AgentMemoViewer
                                                content={displayMemo}
                                                confidence={isStreaming ? 0 : session.confidence}
                                            />
                                            {isStreaming && (
                                                <span className="inline-block w-1.5 h-5 bg-[var(--gold)] animate-pulse ml-0.5 align-text-bottom" />
                                            )}
                                        </CardContent>
                                    </Card>
                                )}

                                {/* Follow-up conversation thread */}
                                {showFollowUpArea && session.sessionMessages.length > 0 && (
                                    <Card>
                                        <CardContent className="p-0">
                                            <div className="border-b px-4 py-2">
                                                <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                                                    Follow-up Conversation
                                                </h3>
                                            </div>
                                            <AgentFollowUpThread
                                                messages={session.sessionMessages.filter(
                                                    (m) => m.message_type === "follow_up" || m.message_type === "follow_up_response",
                                                )}
                                                isStreaming={followUpStreaming}
                                                streamingContent={followUpStreamContent}
                                            />
                                            <AgentFollowUpInput
                                                onSend={handleFollowUp}
                                                disabled={followUpStreaming || session.isRunning}
                                                placeholder="Ask a follow-up question..."
                                            />
                                        </CardContent>
                                    </Card>
                                )}

                                {/* Follow-up input when no follow-ups yet */}
                                {showFollowUpArea && session.sessionMessages.filter(
                                    (m) => m.message_type === "follow_up" || m.message_type === "follow_up_response",
                                ).length === 0 && (
                                    <Card>
                                        <CardContent className="p-0">
                                            <div className="px-4 py-2">
                                                <p className="text-xs text-muted-foreground">
                                                    Have a follow-up question? Ask below for a quick targeted response.
                                                </p>
                                            </div>
                                            <AgentFollowUpInput
                                                onSend={handleFollowUp}
                                                disabled={followUpStreaming || session.isRunning}
                                                placeholder="Ask a follow-up question..."
                                            />
                                        </CardContent>
                                    </Card>
                                )}

                                {/* Background execution still running — show progress + poll */}
                                {session.isBackgroundRunning && (
                                    <div className="rounded-lg border bg-card p-6 text-center space-y-3">
                                        <div className="flex items-center justify-center gap-2">
                                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                            <p className="text-sm text-muted-foreground">
                                                Research in progress&hellip;
                                            </p>
                                        </div>
                                        <p className="text-xs text-muted-foreground/70">
                                            Results will appear automatically when ready.
                                        </p>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={async () => {
                                                if (session.executionId) {
                                                    try { await cancelExecution(session.executionId); } catch { /* ignore */ }
                                                }
                                                handleNewSession();
                                            }}
                                            className="text-muted-foreground hover:text-destructive"
                                        >
                                            <XCircle className="h-3.5 w-3.5 mr-1" />
                                            Cancel
                                        </Button>
                                    </div>
                                )}

                                {/* Session loaded but no memo (failed/incomplete) */}
                                {session.isFollowUp && !session.isRunning && !session.isBackgroundRunning && !session.memo && !session.checkpoint && !session.error && (
                                    <div className="rounded-lg border bg-card p-6 text-center space-y-3">
                                        <p className="text-sm text-muted-foreground">
                                            This session did not complete successfully.
                                        </p>
                                        <Button size="sm" onClick={handleNewSession}>
                                            <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                                            {newSessionLabel}
                                        </Button>
                                    </div>
                                )}

                                {/* Error */}
                                {session.error && (
                                    <div className="text-sm text-red-500 p-3 rounded-md bg-red-50 dark:bg-red-950/20" role="alert">
                                        {session.error}
                                    </div>
                                )}

                                {/* Cancel button */}
                                {session.isRunning && !session.checkpoint && (
                                    <div className="flex justify-end">
                                        <Button variant="ghost" size="sm" onClick={handleCancel} className="text-muted-foreground hover:text-destructive">
                                            <XCircle className="h-3.5 w-3.5 mr-1" />
                                            Cancel
                                        </Button>
                                    </div>
                                )}

                                {/* Cancellation notice */}
                                {cancelled && !session.isRunning && (
                                    <div className="text-sm text-blue-600 dark:text-blue-400 p-3 rounded-md bg-blue-50 dark:bg-blue-950/20">
                                        Cancelled.
                                    </div>
                                )}

                                {/* New session + disclaimer after completion */}
                                {!session.isRunning && (session.memo || session.error) && (
                                    <>
                                        <LegalDisclaimer className="mt-2" />
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={handleNewSession}
                                        >
                                            <RotateCcw className="h-3.5 w-3.5 mr-1.5" />{" "}
                                            {newSessionLabel}
                                        </Button>
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Navigation guard dialog */}
            <AlertDialog open={navGuard.showDialog} onOpenChange={(open) => { if (!open) navGuard.cancelLeave(); }}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Research in progress</AlertDialogTitle>
                        <AlertDialogDescription>
                            Your research agent is still running. You can let it continue in the background and come back later, or cancel it.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel onClick={navGuard.cancelLeave}>Stay</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleCancelAndLeave}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            Cancel Research
                        </AlertDialogAction>
                        <AlertDialogAction onClick={navGuard.confirmLeave}>
                            Continue in Background
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
