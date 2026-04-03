"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { getDocuments } from "@/lib/api";
import type { AgentStreamEvent, AgentStep, DocumentListItem } from "@/lib/types";
import { useAgentSession } from "@/hooks/useAgentSession";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { AgentSessionSidebar } from "@/components/agents/AgentSessionSidebar";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowLeft, RotateCcw, FileText, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Expected case prep agent steps for the timeline
// ---------------------------------------------------------------------------

const CASE_PREP_STEPS = [
    "load_analysis", "prioritize", "checkpoint_issues",
    "deep_search", "argument_order", "checkpoint_strategy",
    "strategy_memo", "verify", "checkpoint_memo",
];

// ---------------------------------------------------------------------------
// Case Prep Agent Workspace
// ---------------------------------------------------------------------------

export default function CasePrepAgentPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    // Session management (shared hook)
    const session = useAgentSession("case_prep");

    // Sidebar
    const [sidebarOpen, setSidebarOpen] = useState(true);

    // Document selection (unique to case-prep)
    const [documents, setDocuments] = useState<DocumentListItem[]>([]);
    const [documentsLoading, setDocumentsLoading] = useState(true);
    const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
    const [docSearch, setDocSearch] = useState("");

    // Step timeline
    const [steps, setSteps] = useState<AgentStep[]>([]);
    const [starting, setStarting] = useState(false);

    const filteredDocuments = documents.filter((d) =>
        d.filename.toLowerCase().includes(docSearch.toLowerCase()),
    );

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push("/login");
    }, [authLoading, isAuthenticated, router]);

    // Fetch documents
    useEffect(() => {
        if (!isAuthenticated) return;
        (async () => {
            try {
                const data = await getDocuments(1, 100);
                setDocuments(data.documents.filter((d) => d.status === "completed"));
            } catch {
                session.setError("Failed to load documents. Please refresh the page.");
            } finally {
                setDocumentsLoading(false);
            }
        })();
    }, [isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

    // Load sessions on mount
    useEffect(() => {
        if (isAuthenticated) session.refreshSessions();
    }, [isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

    // Handle ?session= query param
    useEffect(() => {
        const paramSessionId = searchParams.get("session");
        if (paramSessionId && isAuthenticated) session.loadSession(paramSessionId);
    }, [searchParams, isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

    // ---------------------------------------------------------------------------
    // Event handler
    // ---------------------------------------------------------------------------

    const handleEvent = useCallback((event: AgentStreamEvent) => {
        switch (event.type) {
            case "status":
                setSteps((prev) =>
                    prev.map((s) => ({
                        ...s,
                        status:
                            s.name === event.step ? "completed"
                                : CASE_PREP_STEPS.indexOf(s.name) === CASE_PREP_STEPS.indexOf(event.step!) + 1
                                    ? "active" : s.status,
                        message: s.name === event.step ? event.message || s.message : s.message,
                    })),
                );
                break;
            case "checkpoint":
                session.setCheckpoint({ question: event.question || "", context: event.context || {} });
                session.setIsRunning(false);
                break;
            case "memo":
                session.setMemo(event.content || "");
                if (event.data && typeof event.data === "object" && "confidence" in (event.data as Record<string, unknown>)) {
                    session.setConfidence((event.data as Record<string, unknown>).confidence as number);
                }
                break;
            case "done":
                session.setIsRunning(false);
                session.refreshSessions();
                setSteps((prev) => prev.map((s) => ({
                    ...s,
                    status: s.status === "active" || s.status === "pending" ? "completed" : s.status,
                })));
                break;
            case "error":
                session.setError(event.message || "Agent encountered an error");
                session.setIsRunning(false);
                break;
        }
    }, [session]);

    // ---------------------------------------------------------------------------
    // Submit
    // ---------------------------------------------------------------------------

    const handleStart = useCallback(() => {
        if (!selectedDocId || starting) return;
        setStarting(true);
        setSteps(CASE_PREP_STEPS.map((name, i) => ({
            name, status: i === 0 ? ("active" as const) : ("pending" as const),
        })));
        session.startSession({ document_id: selectedDocId }, handleEvent);
        setStarting(false);
    }, [selectedDocId, starting, handleEvent, session]);

    const handleReset = useCallback(() => {
        session.newSession();
        setSelectedDocId(null);
        setSteps([]);
    }, [session]);

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

    const selectedDoc = documents.find((d) => d.id === selectedDocId);
    const showSelector = !session.isRunning && !session.memo && !session.checkpoint && steps.length === 0 && !session.isFollowUp;
    const showWorkspace = session.isRunning || session.memo || session.checkpoint || steps.length > 0 || session.isFollowUp;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1 flex">
                {/* Session sidebar */}
                <div className={cn(
                    "hidden md:flex flex-col transition-all duration-200",
                    sidebarOpen ? "w-64 min-w-[16rem]" : "w-0 min-w-0 overflow-hidden",
                )}>
                    <AgentSessionSidebar
                        sessions={session.sessions}
                        activeSessionId={session.sessionId}
                        onSelectSession={session.loadSession}
                        onDeleteSession={session.deleteSession}
                        onNewSession={handleReset}
                        loading={session.sessionsLoading}
                    />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="mx-auto max-w-6xl px-4 py-8">
                        <div className="flex items-center gap-3 mb-6">
                            <Button variant="ghost" size="sm" asChild>
                                <Link href="/agents"><ArrowLeft className="h-3.5 w-3.5 mr-1" /> Agents</Link>
                            </Button>
                            <Button variant="ghost" size="sm" className="hidden md:flex" onClick={() => setSidebarOpen((p) => !p)}>
                                {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
                            </Button>
                        </div>

                        <h1 className="text-2xl font-semibold font-[family-name:var(--font-lora)] mb-1">Case Prep Agent</h1>
                        <p className="text-sm text-muted-foreground mb-6">
                            Select an analyzed document to generate a strategy memo with prioritized issues and precedent search.
                        </p>

                        {/* Document selector */}
                        {showSelector && (
                            <Card>
                                <CardContent className="pt-6 space-y-4">
                                    {documentsLoading ? (
                                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <Loader2 className="h-4 w-4 animate-spin" /> Loading documents...
                                        </div>
                                    ) : documents.length === 0 ? (
                                        <div className="text-center py-6">
                                            <FileText className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
                                            <p className="text-sm text-muted-foreground mb-3">No analyzed documents found.</p>
                                            <Button variant="outline" size="sm" asChild>
                                                <Link href="/upload">Upload Document</Link>
                                            </Button>
                                        </div>
                                    ) : (
                                        <>
                                            <label htmlFor="doc-select" className="text-sm font-medium">Select a document</label>
                                            <input id="doc-search" type="text" placeholder="Search documents..." value={docSearch}
                                                onChange={(e) => setDocSearch(e.target.value)}
                                                className="w-full px-3 py-2 text-sm border rounded-md mb-2 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                                            />
                                            <select id="doc-select" value={selectedDocId || ""} onChange={(e) => setSelectedDocId(e.target.value || null)}
                                                className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                                            >
                                                <option value="">Choose a document...</option>
                                                {filteredDocuments.map((doc) => (
                                                    <option key={doc.id} value={doc.id}>
                                                        {doc.filename} ({new Date(doc.created_at).toLocaleDateString()})
                                                    </option>
                                                ))}
                                            </select>
                                            <Button onClick={handleStart} disabled={starting || !selectedDocId}>
                                                {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Start Case Prep"}
                                            </Button>
                                        </>
                                    )}
                                </CardContent>
                            </Card>
                        )}

                        {/* Running or completed state */}
                        {showWorkspace && (
                            <div className="grid gap-6 md:grid-cols-[240px_1fr]">
                                <div className="hidden md:block">
                                    <div className="sticky top-20">
                                        <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-3">Progress</h3>
                                        <AgentStepTimeline steps={steps} />
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    {selectedDoc && (
                                        <Card><CardContent className="pt-4">
                                            <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">Document</p>
                                            <p className="text-sm font-medium">{selectedDoc.filename}</p>
                                        </CardContent></Card>
                                    )}

                                    <div className="md:hidden"><AgentStepTimeline steps={steps} /></div>

                                    {session.checkpoint && (
                                        <AgentCheckpointPrompt
                                            question={session.checkpoint.question}
                                            context={session.checkpoint.context}
                                            onSubmit={session.resume}
                                            disabled={session.isRunning}
                                            error={session.checkpointError}
                                            onClearError={() => session.setCheckpointError(null)}
                                        />
                                    )}

                                    {session.memo && (
                                        <Card><CardContent className="pt-6">
                                            <AgentMemoViewer content={session.memo} confidence={session.confidence} />
                                        </CardContent></Card>
                                    )}

                                    {/* Session loaded but no memo */}
                                    {session.isFollowUp && !session.isRunning && !session.memo && !session.checkpoint && !session.error && (
                                        <div className="rounded-lg border bg-card p-6 text-center space-y-3">
                                            <p className="text-sm text-muted-foreground">This session did not complete successfully.</p>
                                            <Button size="sm" onClick={handleReset}><RotateCcw className="h-3.5 w-3.5 mr-1.5" /> Start New Case Prep</Button>
                                        </div>
                                    )}

                                    {session.error && (
                                        <div className="text-sm text-red-500 p-3 rounded-md bg-red-50 dark:bg-red-950/20" role="alert">{session.error}</div>
                                    )}

                                    {session.isRunning && !session.checkpoint && (
                                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <Loader2 className="h-4 w-4 animate-spin" /> Agent is working...
                                        </div>
                                    )}

                                    {!session.isRunning && (session.memo || session.error) && (
                                        <>
                                            <LegalDisclaimer className="mt-2" />
                                            <Button variant="outline" size="sm" onClick={handleReset}>
                                                <RotateCcw className="h-3.5 w-3.5 mr-1.5" /> New Case Prep
                                            </Button>
                                        </>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>

            <Footer />
        </div>
    );
}
