"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
    runResearchAgent,
    resumeAgentExecution,
    getAccessToken,
    createAgentSession,
    sendAgentFollowUp,
    getAgentSessions,
    getAgentSessionMessages,
    getAgentSessionDetail,
    deleteAgentSession,
} from "@/lib/api";
import type {
    AgentStreamEvent,
    AgentStep,
    ProcessEvent,
    ResearchFootnote,
    ResearchAudit,
    AgentSession,
    AgentSessionMessage,
} from "@/lib/types";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { PlanReview } from "@/components/plan-review";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { ResearchProgress } from "@/components/research-progress";
import { FootnotesPanel } from "@/components/footnotes-panel";
import { VerificationBanner } from "@/components/verification-banner";
import { ResearchAuditTrail } from "@/components/research-audit-trail";
import { AgentSessionSidebar } from "@/components/agents/AgentSessionSidebar";
import { AgentFollowUpThread } from "@/components/agents/AgentFollowUpThread";
import { AgentFollowUpInput } from "@/components/agents/AgentFollowUpInput";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import {
    Loader2, ArrowLeft, RotateCcw, FileText, XCircle, Scale, ScrollText,
    Building2, BarChart3, Users, PanelRightOpen, PanelLeftOpen, PanelLeftClose,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Expected research agent steps for the timeline (V2 pipeline)
// ---------------------------------------------------------------------------

const COMMON_START_STEPS = ["rewrite_query", "classify"];
const COMMON_END_STEPS = ["speculative_synthesis", "format_footnotes", "verify_v2", "quality_check", "checkpoint_memo"];

const FULL_PIPELINE_STEPS = [
    ...COMMON_START_STEPS,
    "plan_research", "checkpoint_plan", "dispatch_workers", "gather_results",
    "batch_cot_with_reflection", "evaluate_and_extract", "gap_analysis", "checkpoint_findings",
    ...COMMON_END_STEPS,
];

const FAST_PATH_STEPS = [
    ...COMMON_START_STEPS,
    "fast_path_search", "fast_path_synthesis",
    ...COMMON_END_STEPS,
];

const FAST_PATH_INDICATORS = new Set(["fast_path_search", "fast_path_synthesis"]);
const FULL_PATH_INDICATORS = new Set(["plan_research", "dispatch_workers"]);

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
    const searchParams = useSearchParams();

    // Session state
    const [sessions, setSessions] = useState<AgentSession[]>([]);
    const [sessionsLoading, setSessionsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [sessionMessages, setSessionMessages] = useState<AgentSessionMessage[]>([]);
    const [sidebarOpen, setSidebarOpen] = useState(true);

    // Follow-up state
    const [isFollowUp, setIsFollowUp] = useState(false);
    const [followUpStreaming, setFollowUpStreaming] = useState(false);
    const [followUpStreamContent, setFollowUpStreamContent] = useState("");

    // Research options
    const [steerResearch, setSteerResearch] = useState(false);

    // Original research state
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
    const streamQueueRef = useRef("");
    const rafIdRef = useRef<number | null>(null);
    const [confidence, setConfidence] = useState<number | undefined>();
    const [confidenceBreakdown, setConfidenceBreakdown] = useState<{
        data_confidence?: number;
        legal_confidence?: number;
        consistency_confidence?: number;
    } | undefined>();
    const [error, setError] = useState<string | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    const [processEvents, setProcessEvents] = useState<ProcessEvent[]>([]);
    const [completedNodes, setCompletedNodes] = useState<Set<string>>(new Set());
    const [startTime, setStartTime] = useState<number | null>(null);
    const [footnotes, setFootnotes] = useState<ResearchFootnote[]>([]);
    const [researchAudit, setResearchAudit] = useState<ResearchAudit | null>(null);
    const [verificationBanner, setVerificationBanner] = useState<string | null>(null);
    const [citationsVerified, setCitationsVerified] = useState(0);
    const [citationsRemoved, setCitationsRemoved] = useState(0);
    const [footnotesPanelOpen, setFootnotesPanelOpen] = useState(false);
    const [selectedFootnoteNum, setSelectedFootnoteNum] = useState<number | null>(null);
    const [isOffline, setIsOffline] = useState(false);
    const [currentStepLabel, setCurrentStepLabel] = useState("");
    const [_detectedPath, setDetectedPath] = useState<"full" | "fast" | null>(null);
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
        // Clear stale auth errors when user is authenticated (e.g. after re-login)
        if (!authLoading && isAuthenticated && error?.toLowerCase().includes("session expired")) {
            setError(null);
        }
    }, [authLoading, isAuthenticated, router, error]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            abortRef.current?.abort();
        };
    }, []);

    // Typewriter animation
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

    // ---------------------------------------------------------------------------
    // Session management
    // ---------------------------------------------------------------------------

    const fetchSessions = useCallback(async () => {
        setSessionsLoading(true);
        try {
            const data = await getAgentSessions("research");
            setSessions(data.sessions);
        } catch {
            // Silent — sidebar shows empty state
        } finally {
            setSessionsLoading(false);
        }
    }, []);

    // Load sessions on mount
    useEffect(() => {
        if (isAuthenticated) fetchSessions();
    }, [isAuthenticated, fetchSessions]);

    // Handle ?session= query param (e.g. navigating from history page)
    useEffect(() => {
        const paramSessionId = searchParams.get("session");
        if (paramSessionId && isAuthenticated) {
            loadSession(paramSessionId);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchParams, isAuthenticated]);

    const loadSession = useCallback(async (sid: string) => {
        // Clear ALL state immediately so old content doesn't flash
        setSessionId(sid);
        setIsFollowUp(true);
        setError(null);
        setMemo("");
        setStreamingMemo("");
        streamQueueRef.current = "";
        setFootnotes([]);
        setConfidence(undefined);
        setConfidenceBreakdown(undefined);
        setResearchAudit(null);
        setVerificationBanner(null);
        setCheckpoint(null);
        setSteps([]);
        setProcessEvents([]);
        setCompletedNodes(new Set());
        setIsRunning(false);
        setExecutionId(null);
        setSessionMessages([]);
        try {
            const [messagesResult, detailResult] = await Promise.allSettled([
                getAgentSessionMessages(sid),
                getAgentSessionDetail(sid),
            ]);

            const messages = messagesResult.status === "fulfilled" ? messagesResult.value : [];
            const detail = detailResult.status === "fulfilled" ? detailResult.value : null;

            if (messages.length > 0) {
                setSessionMessages(messages);
            }

            // Try memo from messages first
            const lastMemo = [...messages].reverse().find(
                (m) => m.role === "assistant" && m.message_type === "memo",
            );

            if (lastMemo) {
                setMemo(lastMemo.content);
                if (lastMemo.sources && lastMemo.sources.length > 0) {
                    setFootnotes(lastMemo.sources as ResearchFootnote[]);
                }
            }

            // Fallback: get memo from latest completed execution's result_data
            const completedExec = detail ? [...(detail.executions || [])].reverse().find(
                (e) => e.status === "completed" && e.result_data?.memo,
            ) : null;

            if (completedExec?.result_data) {
                const rd = completedExec.result_data;
                setExecutionId(completedExec.id);

                if (!lastMemo && rd.memo) {
                    setMemo(rd.memo);
                }
                if (rd.footnotes && rd.footnotes.length > 0 && (!lastMemo?.sources || lastMemo.sources.length === 0)) {
                    setFootnotes(rd.footnotes as ResearchFootnote[]);
                }
                if (rd.confidence !== undefined) {
                    setConfidence(rd.confidence);
                }
                if (rd.confidence_breakdown) {
                    setConfidenceBreakdown(rd.confidence_breakdown);
                }
                if (rd.research_audit) {
                    setResearchAudit(rd.research_audit as ResearchAudit);
                }
            }

            const firstQuery = messages.find(
                (m) => m.role === "user" && m.message_type === "query",
            );
            if (firstQuery) setQuery(firstQuery.content);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Failed to load session";
            setError(msg);
        }
    }, []);

    const handleDeleteSession = useCallback(async (sid: string) => {
        // Optimistic: remove from UI immediately, revert on error
        const prev = sessions;
        setSessions((s) => s.filter((x) => x.id !== sid));
        if (sessionId === sid) {
            // Inline reset instead of calling handleNewSession (declared later)
            abortRef.current?.abort();
            setSessionId(null);
            setIsFollowUp(false);
            setMemo("");
            setQuery("");
            setIsRunning(false);
        }
        try {
            await deleteAgentSession(sid);
        } catch {
            setSessions(prev);
        }
    }, [sessionId, sessions]);

    const handleNewSession = useCallback(() => {
        abortRef.current?.abort();
        setSessionId(null);
        setSessionMessages([]);
        setIsFollowUp(false);
        setQuery("");
        setIsRunning(false);
        setExecutionId(null);
        setSteps([]);
        setCheckpoint(null);
        setMemo("");
        setStreamingMemo("");
        streamQueueRef.current = "";
        setConfidence(undefined);
        setConfidenceBreakdown(undefined);
        setError(null);
        setProcessEvents([]);
        setCompletedNodes(new Set());
        setStartTime(null);
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
        setFollowUpStreaming(false);
        setFollowUpStreamContent("");
    }, []);

    // ---------------------------------------------------------------------------
    // SSE event handler (shared for initial run and session run)
    // ---------------------------------------------------------------------------

    const handleEvent = useCallback((event: AgentStreamEvent) => {
        if (event.execution_id) {
            setExecutionId(event.execution_id);
        }

        // Capture session_id from session event
        if (event.type === "session" && event.session_id) {
            setSessionId(event.session_id);
            setIsFollowUp(true);
        }

        if (PROCESS_EVENT_TYPES.has(event.type)) {
            setProcessEvents((prev) => [
                ...prev,
                { type: event.type, data: (event.data || {}) as Record<string, unknown>, timestamp: Date.now() },
            ]);
            return;
        }

        if (event.type === "memo_stream" && event.chunk) {
            streamQueueRef.current += event.chunk;
            return;
        }

        switch (event.type) {
            case "status": {
                const stepName = event.step;
                if (stepName) {
                    // Track completed nodes for the unified progress component
                    setCompletedNodes((prev) => {
                        const next = new Set(prev);
                        next.add(stepName);
                        return next;
                    });
                    // Push to processEvents so activity feed shows each step live.
                    // Skip if a richer event was JUST added (within last 500ms) —
                    // the backend sends process_events then status for the same node.
                    setProcessEvents((prev) => {
                        const now = Date.now();
                        // Skip if any recent event (last 2 entries, within 1s) covers this node
                        for (let i = prev.length - 1; i >= Math.max(0, prev.length - 3); i--) {
                            const recent = prev[i];
                            if (recent.timestamp && now - recent.timestamp < 1000) {
                                // A "found" or "plan" event already covers this node
                                if (recent.type === "found" || recent.type === "plan" ||
                                    recent.type === "evaluating" || recent.type === "reflection" ||
                                    recent.type === "gap" || recent.type === "drafting" ||
                                    recent.type === "verification" || recent.type === "quality") {
                                    return prev;
                                }
                                // Already have a status for this exact node
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
                    // Clean status label: strip "__interrupt__" and internal jargon
                    const rawLabel = event.message || stepName;
                    const cleanLabel = rawLabel
                        .replace(/__interrupt__/g, "")
                        .replace(/^Completed:\s*/i, "")
                        .trim();
                    setCurrentStepLabel(cleanLabel || stepName.replace(/_/g, " "));
                }
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
                if (ctx.draft_memo) {
                    streamQueueRef.current = "";
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
                streamQueueRef.current = "";
                setMemo(event.content || "");
                setStreamingMemo("");
                const data = event.data as Record<string, unknown> | undefined;
                if (data && "confidence" in data) {
                    setConfidence(data.confidence as number);
                }
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
                // Refresh sessions list to show updated session
                fetchSessions();
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
    }, [fetchSessions]);

    // ---------------------------------------------------------------------------
    // Submit research — uses session endpoint
    // ---------------------------------------------------------------------------

    const handleSubmit = useCallback(() => {
        if (!query.trim() || starting) return;
        setStarting(true);
        setIsRunning(true);
        setError(null);
        setMemo("");
        setStreamingMemo("");
        streamQueueRef.current = "";
        setConfidence(undefined);
        setConfidenceBreakdown(undefined);
        setCheckpoint(null);
        setExecutionId(null);
        setProcessEvents([]);
        setCompletedNodes(new Set());
        setStartTime(Date.now());
        setFootnotes([]);
        setResearchAudit(null);
        setVerificationBanner(null);
        setCitationsVerified(0);
        setCitationsRemoved(0);
        setDetectedPath(null);
        setCurrentStepLabel("");
        setCancelled(false);
        setSessionMessages([]);
        setSteps(
            FULL_PIPELINE_STEPS.map((name, i) => ({
                name,
                status: i === 0 ? ("active" as const) : ("pending" as const),
            })),
        );
        try {
            // Use session-based endpoint for new research
            abortRef.current = createAgentSession(
                "research",
                {
                    query: query.trim(),
                    steer_research: steerResearch,
                    auto_approve: !steerResearch,
                    skip_verification: true,
                },
                handleEvent,
                (err) => {
                    const msg = err.message || "Research failed";
                    // Replace generic auth errors with a more helpful message
                    if (msg.toLowerCase().includes("session expired") || msg.toLowerCase().includes("unauthorized")) {
                        setError("Authentication error. Please sign in again.");
                    } else {
                        setError(msg);
                    }
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

    // ---------------------------------------------------------------------------
    // Follow-up handler
    // ---------------------------------------------------------------------------

    const handleFollowUp = useCallback(async (message: string) => {
        if (!sessionId || followUpStreaming) return;
        setFollowUpStreaming(true);
        setFollowUpStreamContent("");
        setError(null);

        // Optimistically add user message to the thread
        const tempUserMsg: AgentSessionMessage = {
            id: `temp-${Date.now()}`,
            role: "user",
            content: message,
            sources: null,
            message_type: "follow_up",
            execution_id: null,
            created_at: new Date().toISOString(),
        };
        setSessionMessages((prev) => [...prev, tempUserMsg]);

        abortRef.current = sendAgentFollowUp(
            sessionId,
            message,
            (event) => {
                if (event.type === "memo_stream" && event.chunk) {
                    setFollowUpStreamContent((prev) => prev + event.chunk);
                }
                if (event.type === "memo" || event.type === "done") {
                    setFollowUpStreaming(false);
                    setFollowUpStreamContent("");
                    // Reload messages from server to get properly stored messages
                    getAgentSessionMessages(sessionId).then((msgs) => {
                        setSessionMessages(msgs);
                    }).catch(() => {
                        // Keep optimistic messages on failure
                    });
                    fetchSessions();
                }
                if (event.type === "error") {
                    setFollowUpStreaming(false);
                    setFollowUpStreamContent("");
                    setError(event.message || "Follow-up failed");
                }
            },
            (err) => {
                setFollowUpStreaming(false);
                setFollowUpStreamContent("");
                setError(err.message);
            },
        );
    }, [sessionId, followUpStreaming, fetchSessions]);

    const handleCancel = useCallback(() => {
        abortRef.current?.abort();
        setIsRunning(false);
        setCancelled(true);
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

    const showInputForm = !isRunning && !memo && !checkpoint && steps.length === 0 && !isFollowUp;
    const showWorkspace = isRunning || memo || checkpoint || steps.length > 0 || isFollowUp;
    const displayMemo = memo || streamingMemo;
    const isStreaming = !memo && !!streamingMemo;
    const showFollowUpArea = isFollowUp && !isRunning && !!memo && !checkpoint;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1 flex">
                {/* Session sidebar — desktop */}
                <div
                    className={cn(
                        "hidden md:flex flex-col transition-all duration-200",
                        sidebarOpen ? "w-64 min-w-[16rem]" : "w-0 min-w-0 overflow-hidden",
                    )}
                >
                    <AgentSessionSidebar
                        sessions={sessions}
                        activeSessionId={sessionId}
                        onSelectSession={loadSession}
                        onDeleteSession={handleDeleteSession}
                        onNewSession={handleNewSession}
                        loading={sessionsLoading}
                    />
                </div>

                {/* Main content area */}
                <div className="flex-1 min-w-0">
                    <div className="mx-auto px-4 py-8 max-w-[1400px]">
                        <div className="flex items-center gap-3 mb-6">
                            <Button variant="ghost" size="sm" asChild>
                                <Link href="/agents">
                                    <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Agents
                                </Link>
                            </Button>
                            {/* Sidebar toggle */}
                            <Button
                                variant="ghost"
                                size="sm"
                                className="hidden md:flex"
                                onClick={() => setSidebarOpen((prev) => !prev)}
                            >
                                {sidebarOpen ? (
                                    <PanelLeftClose className="h-4 w-4" />
                                ) : (
                                    <PanelLeftOpen className="h-4 w-4" />
                                )}
                            </Button>
                        </div>

                        <h1 className="text-2xl font-semibold font-[family-name:var(--font-lora)] mb-1">
                            Research Agent
                        </h1>
                        <p className="text-sm text-muted-foreground mb-6">
                            AI-powered legal research with citation verification and adversarial analysis.
                        </p>

                        {/* D21: Offline banner */}
                        {isOffline && (
                            <div className="bg-destructive/10 border border-destructive/30 text-destructive rounded-md px-4 py-2 text-sm mb-4" role="alert">
                                You are offline. Please check your internet connection.
                            </div>
                        )}

                        {/* Input form */}
                        {showInputForm && (
                            <Card className="max-w-4xl mx-auto">
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
                                    {/* Example queries */}
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
                                        <div className="flex items-center gap-3">
                                            <span id="query-char-count" className={`text-xs ${query.length > 1800 ? "text-amber-500" : "text-muted-foreground"}`}>
                                                {query.length}/2000
                                            </span>
                                            <span className="text-xs text-muted-foreground hidden sm:inline">Ctrl+Enter to submit</span>
                                            <label className="flex items-center gap-1.5 cursor-pointer select-none" title="Pause at checkpoints to review and steer the research plan, findings, and draft memo">
                                                <input
                                                    type="checkbox"
                                                    checked={steerResearch}
                                                    onChange={(e) => setSteerResearch(e.target.checked)}
                                                    className="h-3.5 w-3.5 rounded border-border accent-primary"
                                                />
                                                <span className="text-xs text-muted-foreground">Steer research</span>
                                            </label>
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
                            <>
                            <div className={cn(
                                "transition-[margin] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
                                footnotesPanelOpen ? "lg:mr-[400px]" : "",
                            )}>
                                {/* Full-width main content */}
                                <div className="space-y-4 max-w-4xl mx-auto">
                                    {/* Query display */}
                                    <div className="rounded-lg border bg-card px-5 py-4">
                                        <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">
                                            Query
                                        </p>
                                        <p className="text-sm font-medium">{query}</p>
                                    </div>

                                    {/* Unified progress (stages + live activity) */}
                                    <ResearchProgress
                                        events={processEvents}
                                        completedNodes={completedNodes}
                                        isRunning={isRunning}
                                        isFastPath={_detectedPath === "fast"}
                                        startTime={startTime ?? undefined}
                                    />

                                    {/* Checkpoint prompt */}
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

                                    {/* Verification Banner */}
                                    {verificationBanner && !isRunning && (
                                        <VerificationBanner
                                            banner={verificationBanner}
                                            citationsVerified={citationsVerified}
                                            citationsRemoved={citationsRemoved}
                                        />
                                    )}

                                    {/* Skeleton shimmer while waiting — only show when no checkpoint visible */}
                                    {isRunning && !displayMemo && !checkpoint && (
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

                                    {/* Memo result */}
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

                                    {/* Follow-up conversation thread */}
                                    {showFollowUpArea && sessionMessages.length > 0 && (
                                        <Card>
                                            <CardContent className="p-0">
                                                <div className="border-b px-4 py-2">
                                                    <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                                                        Follow-up Conversation
                                                    </h3>
                                                </div>
                                                <AgentFollowUpThread
                                                    messages={sessionMessages.filter(
                                                        (m) => m.message_type === "follow_up" || m.message_type === "follow_up_response",
                                                    )}
                                                    isStreaming={followUpStreaming}
                                                    streamingContent={followUpStreamContent}
                                                />
                                                <AgentFollowUpInput
                                                    onSend={handleFollowUp}
                                                    disabled={followUpStreaming || isRunning}
                                                    placeholder="Ask a follow-up question about this research..."
                                                />
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Follow-up input when no follow-ups yet */}
                                    {showFollowUpArea && sessionMessages.filter(m => m.message_type === "follow_up" || m.message_type === "follow_up_response").length === 0 && (
                                        <Card>
                                            <CardContent className="p-0">
                                                <div className="px-4 py-2">
                                                    <p className="text-xs text-muted-foreground">
                                                        Have a follow-up question? Ask below for a quick targeted response.
                                                    </p>
                                                </div>
                                                <AgentFollowUpInput
                                                    onSend={handleFollowUp}
                                                    disabled={followUpStreaming || isRunning}
                                                    placeholder="Ask a follow-up question about this research..."
                                                />
                                            </CardContent>
                                        </Card>
                                    )}

                                    {/* Error + Retry */}
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

                                    {/* Cancel button — progress is already shown above */}
                                    {isRunning && !checkpoint && (
                                        <div className="flex justify-end">
                                            <Button variant="ghost" size="sm" onClick={handleCancel} className="text-muted-foreground hover:text-destructive">
                                                <XCircle className="h-3.5 w-3.5 mr-1" />
                                                Cancel research
                                            </Button>
                                        </div>
                                    )}

                                    {/* Cancellation notice */}
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

                                    {/* Session loaded but no memo (failed/incomplete) */}
                                    {isFollowUp && !isRunning && !memo && !checkpoint && !error && (
                                        <div className="rounded-lg border bg-card p-6 text-center space-y-3">
                                            <p className="text-sm text-muted-foreground">
                                                This research session did not complete successfully.
                                            </p>
                                            <Button size="sm" onClick={handleNewSession}>
                                                <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                                                Start New Research
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
                                                onClick={handleNewSession}
                                            >
                                                <RotateCcw className="h-3.5 w-3.5 mr-1.5" />{" "}
                                                New Research
                                            </Button>
                                        </>
                                    )}
                                </div>
                            </div>

                            {/* Desktop slide-out footnotes panel */}
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

                            {/* Floating reopen tab */}
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
                            </>
                        )}
                    </div>
                </div>
            </main>

            <Footer />
        </div>
    );
}
