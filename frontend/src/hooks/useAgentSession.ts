"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
    createAgentSession,
    resumeAgentExecution,
    getAgentSessions,
    getAgentSessionMessages,
    getAgentSessionDetail,
    deleteAgentSession,
} from "@/lib/api";
import type {
    AgentStreamEvent,
    AgentSession,
    AgentSessionMessage,
    ResearchFootnote,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentSessionState {
    // Session list
    sessions: AgentSession[];
    sessionsLoading: boolean;
    sessionId: string | null;
    sessionMessages: AgentSessionMessage[];

    // Execution
    executionId: string | null;
    isRunning: boolean;
    memo: string;
    confidence: number | undefined;
    footnotes: ResearchFootnote[];
    error: string | null;
    isFollowUp: boolean;

    // Checkpoint
    checkpoint: { question: string; context: Record<string, unknown> } | null;
    checkpointError: string | null;
}

export interface AgentSessionActions {
    /** Start a new agent execution within a session. */
    startSession: (body: Record<string, unknown>, onEvent: (e: AgentStreamEvent) => void) => void;
    /** Resume from a checkpoint. */
    resume: (input: string) => void;
    /** Load a past session from the sidebar. */
    loadSession: (sid: string) => Promise<void>;
    /** Delete a session (optimistic). */
    deleteSession: (sid: string) => Promise<void>;
    /** Reset to blank state for new session. */
    newSession: () => void;
    /** Cancel running execution. */
    cancel: () => void;
    /** Refresh sessions list. */
    refreshSessions: () => Promise<void>;
    /** Set error (used by event handlers). */
    setError: (msg: string | null) => void;
    /** Set memo (used by event handlers). */
    setMemo: (memo: string) => void;
    /** Set confidence (used by event handlers). */
    setConfidence: (c: number | undefined) => void;
    /** Set footnotes (used by event handlers). */
    setFootnotes: (f: ResearchFootnote[]) => void;
    /** Set checkpoint (used by event handlers). */
    setCheckpoint: (cp: { question: string; context: Record<string, unknown> } | null) => void;
    /** Set checkpoint error. */
    setCheckpointError: (msg: string | null) => void;
    /** Set execution ID. */
    setExecutionId: (id: string | null) => void;
    /** Set isRunning. */
    setIsRunning: (running: boolean) => void;
    /** Abort ref for cleanup. */
    abortRef: React.MutableRefObject<AbortController | null>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAgentSession(agentType: string): AgentSessionState & AgentSessionActions {
    // Session list
    const [sessions, setSessions] = useState<AgentSession[]>([]);
    const [sessionsLoading, setSessionsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [sessionMessages, setSessionMessages] = useState<AgentSessionMessage[]>([]);

    // Execution
    const [executionId, setExecutionId] = useState<string | null>(null);
    const [isRunning, setIsRunning] = useState(false);
    const [memo, setMemo] = useState("");
    const [confidence, setConfidence] = useState<number | undefined>();
    const [footnotes, setFootnotes] = useState<ResearchFootnote[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [isFollowUp, setIsFollowUp] = useState(false);

    // Checkpoint
    const [checkpoint, setCheckpoint] = useState<{
        question: string;
        context: Record<string, unknown>;
    } | null>(null);
    const [checkpointError, setCheckpointError] = useState<string | null>(null);

    const abortRef = useRef<AbortController | null>(null);

    // Cleanup on unmount
    useEffect(() => {
        return () => { abortRef.current?.abort(); };
    }, []);

    // ---------------------------------------------------------------------------
    // Fetch sessions
    // ---------------------------------------------------------------------------

    const refreshSessions = useCallback(async () => {
        setSessionsLoading(true);
        try {
            const data = await getAgentSessions(agentType);
            setSessions(data.sessions);
        } catch {
            // Silent — sidebar shows empty state
        } finally {
            setSessionsLoading(false);
        }
    }, [agentType]);

    // ---------------------------------------------------------------------------
    // Start new session
    // ---------------------------------------------------------------------------

    const startSession = useCallback(
        (body: Record<string, unknown>, onEvent: (e: AgentStreamEvent) => void) => {
            setIsRunning(true);
            setError(null);
            setMemo("");
            setConfidence(undefined);
            setCheckpoint(null);
            setExecutionId(null);
            setFootnotes([]);
            setSessionMessages([]);
            setCheckpointError(null);

            // Wrap onEvent to capture session_id and execution_id
            const wrappedOnEvent = (event: AgentStreamEvent) => {
                if (event.execution_id) setExecutionId(event.execution_id);
                if (event.type === "session" && event.session_id) {
                    setSessionId(event.session_id);
                    setIsFollowUp(true);
                }
                onEvent(event);
            };

            abortRef.current = createAgentSession(
                agentType,
                body,
                wrappedOnEvent,
                (err) => {
                    const msg = err.message || "Agent failed";
                    if (msg.toLowerCase().includes("session expired") || msg.toLowerCase().includes("unauthorized")) {
                        setError("Authentication error. Please sign in again.");
                    } else {
                        setError(msg);
                    }
                    setIsRunning(false);
                },
            );
        },
        [agentType],
    );

    // ---------------------------------------------------------------------------
    // Resume from checkpoint
    // ---------------------------------------------------------------------------

    const resume = useCallback(
        (input: string) => {
            if (!executionId) return;
            const savedCheckpoint = checkpoint;
            setCheckpoint(null);
            setCheckpointError(null);
            setIsRunning(true);

            abortRef.current = resumeAgentExecution(
                executionId,
                input,
                (event) => {
                    if (event.execution_id) setExecutionId(event.execution_id);

                    switch (event.type) {
                        case "status":
                            // Let page handle step updates
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
                            if (event.data && "confidence" in (event.data as Record<string, unknown>)) {
                                setConfidence((event.data as Record<string, unknown>).confidence as number);
                            }
                            if ((event.data as Record<string, unknown>)?.footnotes) {
                                setFootnotes((event.data as Record<string, unknown>).footnotes as ResearchFootnote[]);
                            }
                            break;
                        case "done":
                            setIsRunning(false);
                            refreshSessions();
                            break;
                        case "error":
                            setError(event.message || "Agent error");
                            if (!event.recoverable) setIsRunning(false);
                            break;
                    }
                },
                (err) => {
                    setCheckpoint(savedCheckpoint);
                    setCheckpointError(err.message);
                    setIsRunning(false);
                },
            );
        },
        [executionId, checkpoint, refreshSessions],
    );

    // ---------------------------------------------------------------------------
    // Load past session
    // ---------------------------------------------------------------------------

    const loadSession = useCallback(async (sid: string) => {
        // Clear ALL state immediately
        setSessionId(sid);
        setIsFollowUp(true);
        setError(null);
        setMemo("");
        setFootnotes([]);
        setConfidence(undefined);
        setCheckpoint(null);
        setIsRunning(false);
        setExecutionId(null);
        setSessionMessages([]);
        setCheckpointError(null);

        try {
            const [messagesResult, detailResult] = await Promise.allSettled([
                getAgentSessionMessages(sid),
                getAgentSessionDetail(sid),
            ]);

            const messages = messagesResult.status === "fulfilled" ? messagesResult.value : [];
            const detail = detailResult.status === "fulfilled" ? detailResult.value : null;

            if (messages.length > 0) setSessionMessages(messages);

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

            // Fallback: get memo from latest completed execution
            const completedExec = detail
                ? [...(detail.executions || [])].reverse().find(
                    (e) => e.status === "completed" && e.result_data?.memo,
                )
                : null;

            if (completedExec?.result_data) {
                const rd = completedExec.result_data;
                setExecutionId(completedExec.id);
                if (!lastMemo && rd.memo) setMemo(rd.memo);
                if (rd.footnotes && (rd.footnotes as unknown[]).length > 0 && (!lastMemo?.sources || lastMemo.sources.length === 0)) {
                    setFootnotes(rd.footnotes as ResearchFootnote[]);
                }
                if (rd.confidence !== undefined) setConfidence(rd.confidence);
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to load session");
        }
    }, []);

    // ---------------------------------------------------------------------------
    // Delete session (optimistic)
    // ---------------------------------------------------------------------------

    const deleteSession = useCallback(async (sid: string) => {
        const prev = sessions;
        setSessions((s) => s.filter((x) => x.id !== sid));
        if (sessionId === sid) {
            abortRef.current?.abort();
            setSessionId(null);
            setIsFollowUp(false);
            setMemo("");
            setIsRunning(false);
        }
        try {
            await deleteAgentSession(sid);
        } catch {
            setSessions(prev);
        }
    }, [sessionId, sessions]);

    // ---------------------------------------------------------------------------
    // New session (reset)
    // ---------------------------------------------------------------------------

    const newSession = useCallback(() => {
        abortRef.current?.abort();
        setSessionId(null);
        setSessionMessages([]);
        setIsFollowUp(false);
        setIsRunning(false);
        setExecutionId(null);
        setCheckpoint(null);
        setMemo("");
        setConfidence(undefined);
        setError(null);
        setFootnotes([]);
        setCheckpointError(null);
    }, []);

    // ---------------------------------------------------------------------------
    // Cancel
    // ---------------------------------------------------------------------------

    const cancel = useCallback(() => {
        abortRef.current?.abort();
        setIsRunning(false);
    }, []);

    return {
        // State
        sessions, sessionsLoading, sessionId, sessionMessages,
        executionId, isRunning, memo, confidence, footnotes, error,
        isFollowUp, checkpoint, checkpointError,
        // Actions
        startSession, resume, loadSession, deleteSession, newSession,
        cancel, refreshSessions, setError, setMemo, setConfidence,
        setFootnotes, setCheckpoint, setCheckpointError, setExecutionId,
        setIsRunning, abortRef,
    };
}
