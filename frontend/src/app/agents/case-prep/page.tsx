"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
    getDocuments,
    runCasePrepAgent,
    resumeAgentExecution,
} from "@/lib/api";
import type {
    AgentStreamEvent,
    AgentStep,
    DocumentListItem,
} from "@/lib/types";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowLeft, RotateCcw, FileText } from "lucide-react";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Expected case prep agent steps for the timeline
// ---------------------------------------------------------------------------

const CASE_PREP_STEPS = [
    "load_analysis",
    "prioritize",
    "checkpoint_issues",
    "deep_search",
    "argument_order",
    "checkpoint_strategy",
    "strategy_memo",
    "verify",
    "checkpoint_memo",
];

// ---------------------------------------------------------------------------
// Case Prep Agent Workspace
// ---------------------------------------------------------------------------

export default function CasePrepAgentPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();

    // Document selection
    const [documents, setDocuments] = useState<DocumentListItem[]>([]);
    const [documentsLoading, setDocumentsLoading] = useState(true);
    const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
    const [docSearch, setDocSearch] = useState("");

    // Filtered documents for search
    const filteredDocuments = documents.filter((d) =>
        d.filename.toLowerCase().includes(docSearch.toLowerCase()),
    );

    // Agent state
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

    // Fetch completed documents
    useEffect(() => {
        if (!isAuthenticated) return;
        (async () => {
            try {
                const data = await getDocuments(1, 100);
                setDocuments(
                    data.documents.filter((d) => d.status === "completed"),
                );
            } catch {
                // silently fail
            } finally {
                setDocumentsLoading(false);
            }
        })();
    }, [isAuthenticated]);

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
                                : CASE_PREP_STEPS.indexOf(s.name) ===
                                    CASE_PREP_STEPS.indexOf(event.step!) + 1
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

    const handleStart = useCallback(() => {
        if (!selectedDocId || starting) return;
        setStarting(true);
        setIsRunning(true);
        setError(null);
        setMemo("");
        setConfidence(undefined);
        setCheckpoint(null);
        setExecutionId(null);
        setSteps(
            CASE_PREP_STEPS.map((name, i) => ({
                name,
                status: i === 0 ? ("active" as const) : ("pending" as const),
            })),
        );
        try {
            abortRef.current = runCasePrepAgent(
                selectedDocId,
                handleEvent,
                (err) => {
                    setError(err.message);
                    setIsRunning(false);
                },
            );
        } finally {
            setStarting(false);
        }
    }, [selectedDocId, starting, handleEvent]);

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
        setSelectedDocId(null);
        setIsRunning(false);
        setExecutionId(null);
        setSteps([]);
        setCheckpoint(null);
        setMemo("");
        setConfidence(undefined);
        setError(null);
    }, []);

    if (authLoading || !isAuthenticated) return null;

    const selectedDoc = documents.find((d) => d.id === selectedDocId);
    const showSelector = !isRunning && !memo && !checkpoint && steps.length === 0;
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
                Case Prep Agent
            </h1>
            <p className="text-sm text-muted-foreground mb-6">
                Select an analyzed document to generate a strategy memo with
                prioritized issues, deep precedent search, and recommended
                argument ordering.
            </p>

            {/* Document selector (shown when not running) */}
            {showSelector && (
                <Card>
                    <CardContent className="pt-6 space-y-4">
                        {documentsLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />{" "}
                                Loading documents...
                            </div>
                        ) : documents.length === 0 ? (
                            <div className="text-center py-6">
                                <FileText className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
                                <p className="text-sm text-muted-foreground mb-3">
                                    No analyzed documents found. Upload and
                                    analyze a document first.
                                </p>
                                <Button variant="outline" size="sm" asChild>
                                    <Link href="/upload">Upload Document</Link>
                                </Button>
                            </div>
                        ) : (
                            <>
                                <label
                                    htmlFor="doc-select"
                                    className="text-sm font-medium"
                                >
                                    Select a document
                                </label>
                                <label htmlFor="doc-search" className="sr-only">Search documents</label>
                                <input
                                    id="doc-search"
                                    type="text"
                                    placeholder="Search documents..."
                                    value={docSearch}
                                    onChange={(e) =>
                                        setDocSearch(e.target.value)
                                    }
                                    className="w-full px-3 py-2 text-sm border rounded-md mb-2 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                                />
                                <select
                                    id="doc-select"
                                    value={selectedDocId || ""}
                                    onChange={(e) =>
                                        setSelectedDocId(
                                            e.target.value || null,
                                        )
                                    }
                                    className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                                >
                                    <option value="">
                                        Choose a document...
                                    </option>
                                    {filteredDocuments.map((doc) => (
                                        <option key={doc.id} value={doc.id}>
                                            {doc.filename} (
                                            {new Date(
                                                doc.created_at,
                                            ).toLocaleDateString()}
                                            )
                                        </option>
                                    ))}
                                </select>
                                <Button
                                    onClick={handleStart}
                                    disabled={starting || !selectedDocId}
                                >
                                    {starting ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        "Start Case Prep"
                                    )}
                                </Button>
                            </>
                        )}
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
                        {/* Selected document info */}
                        {selectedDoc && (
                            <Card>
                                <CardContent className="pt-4">
                                    <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">
                                        Document
                                    </p>
                                    <p className="text-sm font-medium">
                                        {selectedDoc.filename}
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                        Uploaded{" "}
                                        {new Date(
                                            selectedDoc.created_at,
                                        ).toLocaleDateString()}
                                    </p>
                                </CardContent>
                            </Card>
                        )}

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

                        {/* New Case Prep button after completion */}
                        {!isRunning && (memo || error) && (
                            <>
                                <LegalDisclaimer className="mt-2" />
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleReset}
                                >
                                    <RotateCcw className="h-3.5 w-3.5 mr-1.5" />{" "}
                                    New Case Prep
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
