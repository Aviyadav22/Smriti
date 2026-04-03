"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { getDraftingTemplates, exportDraft } from "@/lib/api";
import type { AgentStreamEvent, AgentStep, DocumentTemplate, TemplateCategory } from "@/lib/types";
import { useAgentSession } from "@/hooks/useAgentSession";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { DraftSectionViewer } from "@/components/draft-section-viewer";
import { AgentSessionSidebar } from "@/components/agents/AgentSessionSidebar";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, ArrowLeft, RotateCcw, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

const DRAFTING_STEPS = [
    "resolve_template", "gather_provisions", "verify_precedents",
    "checkpoint_sources", "draft_sections", "assemble",
    "checkpoint_draft", "verify_final", "checkpoint_final",
];

function formatFieldName(name: string): string {
    return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DraftingAgentPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const researchExecutionId = searchParams.get("research_execution_id");

    const session = useAgentSession("drafting");
    const [sidebarOpen, setSidebarOpen] = useState(true);

    // Template state
    const [templates, setTemplates] = useState<DocumentTemplate[]>([]);
    const [categories, setCategories] = useState<TemplateCategory[]>([]);
    const [templatesLoading, setTemplatesLoading] = useState(true);
    const [selectedDocType, setSelectedDocType] = useState("");
    const selectedTemplate = templates.find((t) => t.doc_type === selectedDocType);
    const [templateError, setTemplateError] = useState<string | null>(null);

    // Form inputs
    const [caseFacts, setCaseFacts] = useState("");
    const [targetCourt, setTargetCourt] = useState("");
    const [dynamicFields, setDynamicFields] = useState<Record<string, string>>({});

    // Drafting-specific state
    const [starting, setStarting] = useState(false);
    const [steps, setSteps] = useState<AgentStep[]>([]);
    const [sectionDrafts, setSectionDrafts] = useState<Record<string, string> | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push("/login");
    }, [authLoading, isAuthenticated, router]);

    // Fetch templates
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await getDraftingTemplates();
                if (!cancelled) {
                    if (res.categories?.length) {
                        setCategories(res.categories);
                        setTemplates(res.categories.flatMap((c) => c.templates));
                    } else {
                        setTemplates(res.templates);
                    }
                }
            } catch (err) {
                if (!cancelled) setTemplateError(err instanceof Error ? err.message : "Failed to load templates");
            } finally {
                if (!cancelled) setTemplatesLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    // Load sessions
    useEffect(() => {
        if (isAuthenticated) session.refreshSessions();
    }, [isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

    // Handle ?session= query param
    useEffect(() => {
        const paramSessionId = searchParams.get("session");
        if (paramSessionId && isAuthenticated) session.loadSession(paramSessionId);
    }, [searchParams, isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

    // Reset dynamic fields when template changes
    useEffect(() => {
        if (selectedTemplate) {
            const fields: Record<string, string> = {};
            for (const field of selectedTemplate.required_fields) fields[field] = "";
            setDynamicFields(fields);
        } else {
            setDynamicFields({});
        }
    }, [selectedDocType, selectedTemplate]);

    // ---------------------------------------------------------------------------
    // Event handler
    // ---------------------------------------------------------------------------

    const handleEvent = useCallback((event: AgentStreamEvent) => {
        switch (event.type) {
            case "status":
                setSteps((prev) =>
                    prev.map((s) => ({
                        ...s,
                        status: s.name === event.step ? "completed"
                            : DRAFTING_STEPS.indexOf(s.name) === DRAFTING_STEPS.indexOf(event.step!) + 1
                                ? "active" : s.status,
                        message: s.name === event.step ? event.message || s.message : s.message,
                    })),
                );
                break;
            case "checkpoint":
                if (event.context && typeof event.context === "object" && "section_drafts" in event.context) {
                    setSectionDrafts(event.context.section_drafts as Record<string, string>);
                }
                session.setCheckpoint({ question: event.question || "", context: event.context || {} });
                session.setIsRunning(false);
                break;
            case "memo":
                session.setMemo(event.content || "");
                if (event.data && typeof event.data === "object") {
                    const d = event.data as Record<string, unknown>;
                    if ("confidence" in d) session.setConfidence(d.confidence as number);
                    if ("section_drafts" in d) setSectionDrafts(d.section_drafts as Record<string, string>);
                }
                break;
            case "done":
                session.setIsRunning(false);
                session.refreshSessions();
                setSteps((prev) => prev.map((s) => ({
                    ...s, status: s.status === "active" || s.status === "pending" ? "completed" : s.status,
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

    const handleSubmit = useCallback(() => {
        if (!selectedDocType || starting) return;
        if (!researchExecutionId && !caseFacts.trim()) return;
        setStarting(true);
        setSectionDrafts(null);
        setSteps(DRAFTING_STEPS.map((name, i) => ({
            name, status: i === 0 ? ("active" as const) : ("pending" as const),
        })));

        const additionalContext: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(dynamicFields)) {
            if (value.trim()) additionalContext[key] = value.trim();
        }

        const body: Record<string, unknown> = {
            doc_type: selectedDocType,
            case_facts: caseFacts.trim(),
            target_court: targetCourt.trim() || "",
            relevant_precedents: [],
            additional_context: Object.keys(additionalContext).length > 0 ? additionalContext : undefined,
        };
        if (researchExecutionId) {
            body.research_execution_id = researchExecutionId;
        }

        session.startSession(body, handleEvent);
        setStarting(false);
    }, [selectedDocType, caseFacts, targetCourt, dynamicFields, starting, handleEvent, researchExecutionId, session]);

    const handleRevise = (sectionName: string, feedback: string) => {
        if (!session.executionId) return;
        session.resume(`${sectionName}: ${feedback}`);
    };

    const handleExport = async (format: "docx" | "pdf") => {
        if (!session.executionId) return;
        try {
            const blob = await exportDraft(session.executionId, format);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `draft.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err) {
            session.setError(err instanceof Error ? err.message : "Export failed");
        }
    };

    const handleReset = useCallback(() => {
        session.newSession();
        setSelectedDocType("");
        setCaseFacts("");
        setTargetCourt("");
        setDynamicFields({});
        setSteps([]);
        setSectionDrafts(null);
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

    const showInputForm = !session.isRunning && !session.memo && !session.checkpoint && steps.length === 0 && !session.isFollowUp;
    const showWorkspace = session.isRunning || session.memo || session.checkpoint || steps.length > 0 || session.isFollowUp;
    const allDynamicFieldsFilled = !selectedTemplate || selectedTemplate.required_fields.every((field) => dynamicFields[field]?.trim());

    return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1 flex">
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

                        <h1 className="text-2xl font-semibold font-[family-name:var(--font-lora)] mb-1">Drafting Agent</h1>
                        <p className="text-sm text-muted-foreground mb-6">
                            Select a document type and provide case details. The agent drafts legal documents grounded in precedents.
                        </p>

                        {researchExecutionId && (
                            <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg text-sm text-green-800 dark:text-green-200">
                                Drafting from research session.
                            </div>
                        )}

                        {showInputForm && (
                            <Card>
                                <CardContent className="pt-6 space-y-4">
                                    <div>
                                        {categories.length > 0 ? (
                                            <select id="drafting-template" value={selectedDocType} onChange={(e) => setSelectedDocType(e.target.value)} disabled={templatesLoading}
                                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                                                <option value="">{templatesLoading ? "Loading templates..." : "Select document type"}</option>
                                                {categories.map((cat) => (
                                                    <optgroup key={cat.id} label={cat.display_name}>
                                                        {cat.templates.map((t) => (
                                                            <option key={t.doc_type} value={t.doc_type}>{t.display_name}</option>
                                                        ))}
                                                    </optgroup>
                                                ))}
                                            </select>
                                        ) : (
                                            <Select value={selectedDocType} onValueChange={setSelectedDocType} disabled={templatesLoading}>
                                                <SelectTrigger className="w-full">
                                                    <SelectValue placeholder={templatesLoading ? "Loading templates..." : "Select document type"} />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {templates.map((t) => (
                                                        <SelectItem key={t.doc_type} value={t.doc_type}>{t.display_name}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        )}
                                        {templateError && <p className="text-xs text-red-500 mt-1" role="alert">{templateError}</p>}
                                    </div>
                                    <Textarea id="drafting-case-facts" placeholder="Describe the facts of your case..." value={caseFacts} onChange={(e) => setCaseFacts(e.target.value)} className="min-h-[120px] text-sm" />
                                    <Input id="drafting-target-court" placeholder="e.g., High Court of Delhi" value={targetCourt} onChange={(e) => setTargetCourt(e.target.value)} />
                                    {selectedTemplate && selectedTemplate.required_fields.length > 0 && (
                                        <div className="space-y-3 border-t pt-4">
                                            <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground">Required fields for {selectedTemplate.display_name}</p>
                                            {selectedTemplate.required_fields.map((field) => (
                                                <Input key={field} id={`drafting-field-${field}`} placeholder={formatFieldName(field)}
                                                    value={dynamicFields[field] || ""} onChange={(e) => setDynamicFields((prev) => ({ ...prev, [field]: e.target.value }))} />
                                            ))}
                                        </div>
                                    )}
                                    <Button onClick={handleSubmit} disabled={starting || !selectedDocType || (!researchExecutionId && !caseFacts.trim()) || !allDynamicFieldsFilled}>
                                        {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Start Drafting"}
                                    </Button>
                                </CardContent>
                            </Card>
                        )}

                        {showWorkspace && (
                            <div className="grid gap-6 md:grid-cols-[240px_1fr]">
                                <div className="hidden md:block">
                                    <div className="sticky top-20">
                                        <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-3">Progress</h3>
                                        <AgentStepTimeline steps={steps} />
                                    </div>
                                </div>
                                <div className="space-y-4">
                                    {caseFacts && (
                                        <Card><CardContent className="pt-4">
                                            <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">Document Type</p>
                                            <p className="text-sm mb-3">{selectedTemplate?.display_name || selectedDocType}</p>
                                            <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">Case Facts</p>
                                            <p className="text-sm">{caseFacts}</p>
                                        </CardContent></Card>
                                    )}
                                    <div className="md:hidden"><AgentStepTimeline steps={steps} /></div>

                                    {session.checkpoint?.context?.suggested_precedents != null && Array.isArray(session.checkpoint.context.suggested_precedents) && (session.checkpoint.context.suggested_precedents as Array<Record<string, string>>).length > 0 ? (
                                        <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                                            <p className="text-sm font-medium text-blue-800 dark:text-blue-200 mb-2">Related cases from citation graph:</p>
                                            <ul className="text-sm space-y-1">
                                                {(session.checkpoint.context.suggested_precedents as Array<Record<string, string>>).map((p, i) => (
                                                    <li key={i} className="text-blue-700 dark:text-blue-300">{p.title || p.citation}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    ) : null}

                                    {session.checkpoint && !sectionDrafts && (
                                        <AgentCheckpointPrompt question={session.checkpoint.question} context={session.checkpoint.context}
                                            onSubmit={session.resume} disabled={session.isRunning}
                                            error={session.checkpointError} onClearError={() => session.setCheckpointError(null)} />
                                    )}

                                    {session.checkpoint && sectionDrafts && (
                                        <div className="space-y-4">
                                            <div className="text-sm font-medium">{session.checkpoint.question || "Review the drafted sections below."}</div>
                                            <DraftSectionViewer sections={sectionDrafts} onRevise={handleRevise} disabled={session.isRunning} />
                                            <Button onClick={() => session.resume("approve")} disabled={session.isRunning}>Approve and Continue</Button>
                                        </div>
                                    )}

                                    {!session.isRunning && !session.checkpoint && sectionDrafts && (
                                        <DraftSectionViewer sections={sectionDrafts} onExport={session.executionId ? handleExport : undefined} disabled={session.isRunning} />
                                    )}

                                    {session.checkpoint?.context?.affidavit_draft != null ? (
                                        <details className="border rounded-lg p-4">
                                            <summary className="font-semibold cursor-pointer">Companion Affidavit (auto-generated)</summary>
                                            <div className="mt-2 prose prose-sm max-w-none whitespace-pre-wrap">{String(session.checkpoint.context.affidavit_draft)}</div>
                                        </details>
                                    ) : null}

                                    {session.memo && !sectionDrafts && (
                                        <Card><CardContent className="pt-6">
                                            <AgentMemoViewer content={session.memo} confidence={session.confidence} />
                                        </CardContent></Card>
                                    )}

                                    {session.isFollowUp && !session.isRunning && !session.memo && !session.checkpoint && !sectionDrafts && !session.error && (
                                        <div className="rounded-lg border bg-card p-6 text-center space-y-3">
                                            <p className="text-sm text-muted-foreground">This session did not complete successfully.</p>
                                            <Button size="sm" onClick={handleReset}><RotateCcw className="h-3.5 w-3.5 mr-1.5" /> New Draft</Button>
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

                                    {!session.isRunning && (session.memo || sectionDrafts || session.error) && !session.checkpoint && (
                                        <>
                                            <LegalDisclaimer className="mt-2" />
                                            <Button variant="outline" size="sm" onClick={handleReset}>
                                                <RotateCcw className="h-3.5 w-3.5 mr-1.5" /> New Draft
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
