"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { getAgentExecutions, cancelExecution, exportResearchMemo } from "@/lib/api";
import type { AgentExecution } from "@/lib/types";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Download, Loader2, Square, X } from "lucide-react";
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

// ---------------------------------------------------------------------------
// Execution History Page
// ---------------------------------------------------------------------------

export default function AgentHistoryPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();

    const [executions, setExecutions] = useState<AgentExecution[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [error, setError] = useState<string | null>(null);
    const [viewingMemo, setViewingMemo] = useState<AgentExecution | null>(null);
    const [cancellingId, setCancellingId] = useState<string | null>(null);
    const [exportingId, setExportingId] = useState<string | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push("/login");
    }, [authLoading, isAuthenticated, router]);

    const fetchExecutions = useCallback(async (p: number) => {
        setLoading(true);
        setError(null);
        try {
            const data = await getAgentExecutions(p);
            setExecutions(data.executions);
            setTotalPages(
                Math.max(1, Math.ceil(data.total / data.page_size)),
            );
            setPage(data.page);
        } catch (err: unknown) {
            const message =
                err instanceof Error
                    ? err.message
                    : "Failed to load executions.";
            setError(message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (isAuthenticated) {
            fetchExecutions(1);
        }
    }, [isAuthenticated, fetchExecutions]);

    // WIRED_BY_REFACTOR: Cancel and export were disconnected backend endpoints.
    // Wired here so lawyers can cancel running agents and export completed memos.
    const handleCancel = useCallback(async (executionId: string) => {
        setCancellingId(executionId);
        try {
            await cancelExecution(executionId);
            // Refresh the list to show updated status
            await fetchExecutions(page);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to cancel execution.";
            setError(message);
        } finally {
            setCancellingId(null);
        }
    }, [fetchExecutions, page]);

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

            {loading && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading
                    executions...
                </div>
            )}

            {error && (
                <p className="text-sm text-destructive font-medium">{error}</p>
            )}

            {!loading && !error && executions.length === 0 && (
                <Card>
                    <CardContent className="py-12 text-center">
                        <p className="text-muted-foreground">
                            No agent executions yet. Start a research or case
                            prep agent to see history here.
                        </p>
                    </CardContent>
                </Card>
            )}

            {!loading && executions.length > 0 && (
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
                                        {/* Cancel button for running/waiting executions */}
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
                                        {/* View results for completed executions */}
                                        {exec.status === "completed" && exec.result_data && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => setViewingMemo(exec)}
                                            >
                                                View Results
                                            </Button>
                                        )}
                                        {/* Export for completed research executions */}
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

            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-6">
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={page <= 1}
                        onClick={() => fetchExecutions(page - 1)}
                    >
                        Previous
                    </Button>
                    <span className="text-sm text-muted-foreground">
                        Page {page} of {totalPages}
                    </span>
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={page >= totalPages}
                        onClick={() => fetchExecutions(page + 1)}
                    >
                        Next
                    </Button>
                </div>
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
