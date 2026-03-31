"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
    getAgentExecutions,
    cancelExecution,
    exportResearchMemo,
    getAgentSessions,
    deleteAgentSession,
} from "@/lib/api";
import type { AgentExecution, AgentSession } from "@/lib/types";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    ArrowLeft,
    Download,
    Loader2,
    Square,
    X,
    MessageSquare,
    Trash2,
} from "lucide-react";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Status badge styling
// ---------------------------------------------------------------------------

function statusColor(status: string): string {
    switch (status) {
        case "running":
            return "bg-blue-500/10 text-blue-700 border-blue-200";
        case "waiting_input":
            return "bg-yellow-500/10 text-yellow-700 border-yellow-200";
        case "completed":
            return "bg-green-500/10 text-green-700 border-green-200";
        case "failed":
            return "bg-red-500/10 text-red-700 border-red-200";
        case "cancelled":
            return "bg-gray-500/10 text-gray-600 border-gray-200";
        default:
            return "bg-gray-500/10 text-gray-600 border-gray-200";
    }
}

function statusBadgeVariant(
    status: string,
): "default" | "secondary" | "destructive" | "outline" {
    switch (status) {
        case "completed":
            return "default";
        case "failed":
            return "destructive";
        case "running":
        case "waiting_input":
            return "secondary";
        default:
            return "outline";
    }
}

function agentTypeLabel(type: string): string {
    switch (type) {
        case "research":
            return "Research";
        case "case_prep":
            return "Case Prep";
        case "strategy":
            return "Strategy";
        case "drafting":
            return "Drafting";
        default:
            return type;
    }
}

function getInputSummary(execution: AgentExecution): string {
    const data = execution.input_data;
    if (data.query && typeof data.query === "string") {
        return data.query.length > 80
            ? data.query.slice(0, 80) + "..."
            : data.query;
    }
    if (data.document_id && typeof data.document_id === "string") {
        return `Document: ${data.document_id.slice(0, 8)}...`;
    }
    return "N/A";
}

function timeAgo(dateStr: string): string {
    const seconds = Math.floor(
        (Date.now() - new Date(dateStr).getTime()) / 1000,
    );
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    const months = Math.floor(days / 30);
    return `${months}mo ago`;
}

type TabType = "sessions" | "executions";

// ---------------------------------------------------------------------------
// Agent History Page
// ---------------------------------------------------------------------------

export default function AgentHistoryPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();

    const [activeTab, setActiveTab] = useState<TabType>("sessions");

    // Executions state
    const [executions, setExecutions] = useState<AgentExecution[]>([]);
    const [execLoading, setExecLoading] = useState(true);
    const [execPage, setExecPage] = useState(1);
    const [execTotalPages, setExecTotalPages] = useState(1);
    const [error, setError] = useState<string | null>(null);
    const [viewingMemo, setViewingMemo] = useState<AgentExecution | null>(null);
    const [cancellingId, setCancellingId] = useState<string | null>(null);
    const [exportingId, setExportingId] = useState<string | null>(null);

    // Sessions state
    const [sessions, setSessions] = useState<AgentSession[]>([]);
    const [sessionsLoading, setSessionsLoading] = useState(true);
    const [sessionsPage, setSessionsPage] = useState(1);
    const [sessionsTotalPages, setSessionsTotalPages] = useState(1);
    const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push("/login");
    }, [authLoading, isAuthenticated, router]);

    // Fetch executions
    const fetchExecutions = useCallback(async (p: number) => {
        setExecLoading(true);
        setError(null);
        try {
            const data = await getAgentExecutions(p);
            setExecutions(data.executions);
            setExecTotalPages(
                Math.max(1, Math.ceil(data.total / data.page_size)),
            );
            setExecPage(data.page);
        } catch (err: unknown) {
            const message =
                err instanceof Error
                    ? err.message
                    : "Failed to load executions.";
            setError(message);
        } finally {
            setExecLoading(false);
        }
    }, []);

    // Fetch sessions
    const fetchSessions = useCallback(async (p: number) => {
        setSessionsLoading(true);
        setError(null);
        try {
            const data = await getAgentSessions(undefined, p, 20);
            setSessions(data.sessions);
            setSessionsTotalPages(Math.max(1, Math.ceil(data.total / 20)));
            setSessionsPage(p);
        } catch (err: unknown) {
            const message =
                err instanceof Error
                    ? err.message
                    : "Failed to load sessions.";
            setError(message);
        } finally {
            setSessionsLoading(false);
        }
    }, []);

    useEffect(() => {
        if (isAuthenticated) {
            fetchExecutions(1);
            fetchSessions(1);
        }
    }, [isAuthenticated, fetchExecutions, fetchSessions]);

    const handleCancel = useCallback(async (executionId: string) => {
        setCancellingId(executionId);
        try {
            await cancelExecution(executionId);
            await fetchExecutions(execPage);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to cancel execution.";
            setError(message);
        } finally {
            setCancellingId(null);
        }
    }, [fetchExecutions, execPage]);

    const handleExport = useCallback(async (executionId: string, format: "docx" | "pdf" | "md") => {
        setExportingId(executionId);
        try {
            const blob = await exportResearchMemo(executionId, format);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `research-memo-${executionId.slice(0, 8)}.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Export failed.";
            setError(message);
        } finally {
            setExportingId(null);
        }
    }, []);

    const handleDeleteSession = useCallback(async (sid: string) => {
        setDeletingSessionId(sid);
        try {
            await deleteAgentSession(sid);
            setSessions((prev) => prev.filter((s) => s.id !== sid));
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to delete session.";
            setError(message);
        } finally {
            setDeletingSessionId(null);
        }
    }, []);

    // Close modal on Escape key
    useEffect(() => {
        if (!viewingMemo) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") setViewingMemo(null);
        };
        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [viewingMemo]);

    if (authLoading || !isAuthenticated) return null;

    const memoContent =
        viewingMemo?.result_data &&
        typeof viewingMemo.result_data === "object" &&
        "memo" in viewingMemo.result_data
            ? String(viewingMemo.result_data.memo)
            : null;

    const loading = activeTab === "sessions" ? sessionsLoading : execLoading;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                <div className="mx-auto max-w-4xl px-4 py-8">
                    <div className="flex items-center gap-3 mb-6">
                        <Button variant="ghost" size="sm" asChild>
                            <Link href="/agents">
                                <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Agents
                            </Link>
                        </Button>
                    </div>

                    <h1 className="text-2xl font-semibold font-[family-name:var(--font-lora)] mb-6">
                        Agent History
                    </h1>

                    {/* Tab switcher */}
                    <div className="flex gap-1 mb-6 border-b">
                        <button
                            type="button"
                            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                                activeTab === "sessions"
                                    ? "border-primary text-primary"
                                    : "border-transparent text-muted-foreground hover:text-foreground"
                            }`}
                            onClick={() => setActiveTab("sessions")}
                        >
                            Sessions
                        </button>
                        <button
                            type="button"
                            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                                activeTab === "executions"
                                    ? "border-primary text-primary"
                                    : "border-transparent text-muted-foreground hover:text-foreground"
                            }`}
                            onClick={() => setActiveTab("executions")}
                        >
                            Executions
                        </button>
                    </div>

                    {loading && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
                        </div>
                    )}

                    {error && (
                        <p className="text-sm text-destructive font-medium mb-4">{error}</p>
                    )}

                    {/* ============== Sessions Tab ============== */}
                    {activeTab === "sessions" && !sessionsLoading && (
                        <>
                            {sessions.length === 0 ? (
                                <Card>
                                    <CardContent className="py-12 text-center">
                                        <p className="text-muted-foreground">
                                            No agent sessions yet. Start a research agent to see sessions here.
                                        </p>
                                    </CardContent>
                                </Card>
                            ) : (
                                <div className="space-y-3">
                                    {sessions.map((session) => (
                                        <Card key={session.id} className="hover:shadow-sm transition-shadow">
                                            <CardContent className="py-4">
                                                <div className="flex items-start justify-between gap-4">
                                                    <Link
                                                        href={`/agents/research?session=${session.id}`}
                                                        className="flex-1 min-w-0 space-y-1.5 group"
                                                    >
                                                        <p className="font-medium text-sm group-hover:underline line-clamp-2">
                                                            {session.title || "Untitled Session"}
                                                        </p>
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            <Badge variant="outline" className="text-[10px]">
                                                                {agentTypeLabel(session.agent_type)}
                                                            </Badge>
                                                            <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                                                <MessageSquare className="h-3 w-3" />
                                                                {session.message_count} messages
                                                            </span>
                                                            <span className="text-xs text-muted-foreground">
                                                                {session.execution_count} run{session.execution_count !== 1 ? "s" : ""}
                                                            </span>
                                                        </div>
                                                        <p className="text-xs text-muted-foreground">
                                                            {timeAgo(session.updated_at)}
                                                        </p>
                                                    </Link>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="shrink-0 text-muted-foreground hover:text-destructive"
                                                        disabled={deletingSessionId === session.id}
                                                        onClick={() => handleDeleteSession(session.id)}
                                                    >
                                                        {deletingSessionId === session.id ? (
                                                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                        ) : (
                                                            <Trash2 className="h-3.5 w-3.5" />
                                                        )}
                                                    </Button>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            )}

                            {sessionsTotalPages > 1 && (
                                <div className="flex items-center justify-center gap-2 mt-6">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={sessionsPage <= 1}
                                        onClick={() => fetchSessions(sessionsPage - 1)}
                                    >
                                        Previous
                                    </Button>
                                    <span className="text-sm text-muted-foreground">
                                        Page {sessionsPage} of {sessionsTotalPages}
                                    </span>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={sessionsPage >= sessionsTotalPages}
                                        onClick={() => fetchSessions(sessionsPage + 1)}
                                    >
                                        Next
                                    </Button>
                                </div>
                            )}
                        </>
                    )}

                    {/* ============== Executions Tab ============== */}
                    {activeTab === "executions" && !execLoading && (
                        <>
                            {executions.length === 0 ? (
                                <Card>
                                    <CardContent className="py-12 text-center">
                                        <p className="text-muted-foreground">
                                            No agent executions yet. Start a research or case
                                            prep agent to see history here.
                                        </p>
                                    </CardContent>
                                </Card>
                            ) : (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Executions</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="divide-y">
                                            {executions.map((exec) => (
                                                <div
                                                    key={exec.id}
                                                    className="flex items-center justify-between py-3 px-2"
                                                >
                                                    <div className="flex-1 min-w-0 space-y-1">
                                                        <div className="flex items-center gap-2">
                                                            <Badge
                                                                variant="outline"
                                                                className="text-[10px]"
                                                            >
                                                                {agentTypeLabel(
                                                                    exec.agent_type,
                                                                )}
                                                            </Badge>
                                                            <Badge
                                                                variant={statusBadgeVariant(
                                                                    exec.status,
                                                                )}
                                                                className={statusColor(
                                                                    exec.status,
                                                                )}
                                                            >
                                                                {exec.status.replace("_", " ")}
                                                            </Badge>
                                                        </div>
                                                        <p className="text-sm truncate">
                                                            {getInputSummary(exec)}
                                                        </p>
                                                        <p className="text-xs text-muted-foreground">
                                                            {new Date(
                                                                exec.created_at,
                                                            ).toLocaleString()}
                                                        </p>
                                                    </div>
                                                    <div className="flex items-center gap-1.5 shrink-0">
                                                        {(exec.status === "running" || exec.status === "waiting_input") && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                className="text-destructive hover:text-destructive"
                                                                disabled={cancellingId === exec.id}
                                                                onClick={() => handleCancel(exec.id)}
                                                            >
                                                                {cancellingId === exec.id ? (
                                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                                ) : (
                                                                    <Square className="h-3.5 w-3.5 mr-1" />
                                                                )}
                                                                Cancel
                                                            </Button>
                                                        )}
                                                        {exec.status === "completed" && exec.result_data && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => setViewingMemo(exec)}
                                                            >
                                                                View Results
                                                            </Button>
                                                        )}
                                                        {exec.status === "completed" && exec.agent_type === "research" && exec.result_data && (
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                disabled={exportingId === exec.id}
                                                                onClick={() => handleExport(exec.id, "docx")}
                                                            >
                                                                {exportingId === exec.id ? (
                                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                                ) : (
                                                                    <Download className="h-3.5 w-3.5 mr-1" />
                                                                )}
                                                                Export
                                                            </Button>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {execTotalPages > 1 && (
                                <div className="flex items-center justify-center gap-2 mt-6">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={execPage <= 1}
                                        onClick={() => fetchExecutions(execPage - 1)}
                                    >
                                        Previous
                                    </Button>
                                    <span className="text-sm text-muted-foreground">
                                        Page {execPage} of {execTotalPages}
                                    </span>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={execPage >= execTotalPages}
                                        onClick={() => fetchExecutions(execPage + 1)}
                                    >
                                        Next
                                    </Button>
                                </div>
                            )}
                        </>
                    )}

                    {/* Inline memo viewer dialog */}
                    {viewingMemo && memoContent && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                            <div role="dialog" aria-modal="true" aria-label="Memo viewer" className="bg-card rounded-lg shadow-lg max-w-3xl w-full mx-4 max-h-[80vh] overflow-y-auto">
                                <div className="flex items-center justify-between p-4 border-b">
                                    <div>
                                        <h3 className="font-semibold text-sm">
                                            {agentTypeLabel(viewingMemo.agent_type)}{" "}
                                            Agent Results
                                        </h3>
                                        <p className="text-xs text-muted-foreground">
                                            {new Date(
                                                viewingMemo.created_at,
                                            ).toLocaleString()}
                                        </p>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-7 w-7 p-0"
                                        onClick={() => setViewingMemo(null)}
                                    >
                                        <X className="h-4 w-4" />
                                    </Button>
                                </div>
                                <div className="p-4">
                                    <AgentMemoViewer content={memoContent} />
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
}
