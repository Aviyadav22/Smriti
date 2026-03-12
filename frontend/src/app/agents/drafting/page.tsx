"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
    runDraftingAgent,
    getDraftingTemplates,
    exportDraft,
    resumeAgentExecution,
} from "@/lib/api";
import type { AgentStreamEvent, AgentStep, DocumentTemplate } from "@/lib/types";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { DraftSectionViewer } from "@/components/draft-section-viewer";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Loader2, ArrowLeft, RotateCcw } from "lucide-react";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Expected drafting agent steps for the timeline
// ---------------------------------------------------------------------------

const DRAFTING_STEPS = [
    "resolve_template",
    "gather_provisions",
    "verify_precedents",
    "checkpoint_sources",
    "draft_sections",
    "assemble",
    "checkpoint_draft",
    "verify_final",
    "checkpoint_final",
];

// ---------------------------------------------------------------------------
// Drafting Agent Workspace
// ---------------------------------------------------------------------------

export default function DraftingAgentPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();

    // Template state
    const [templates, setTemplates] = useState<DocumentTemplate[]>([]);
    const [templatesLoading, setTemplatesLoading] = useState(true);
    const [selectedDocType, setSelectedDocType] = useState("");
    const selectedTemplate = templates.find((t) => t.doc_type === selectedDocType);

    // Form inputs
    const [caseFacts, setCaseFacts] = useState("");
    const [targetCourt, setTargetCourt] = useState("");
    const [dynamicFields, setDynamicFields] = useState<Record<string, string>>({});

    // Template error state
    const [templateError, setTemplateError] = useState<string | null>(null);

    // Agent execution state
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
    const [sectionDrafts, setSectionDrafts] = useState<Record<string, string> | null>(null);
    const [error, setError] = useState<string | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push("/login");
    }, [authLoading, isAuthenticated, router]);

    // Fetch templates on mount
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await getDraftingTemplates();
                if (!cancelled) {
                    setTemplates(res.templates);
                }
            } catch (err) {
                if (!cancelled) {
                    setTemplateError(
                        err instanceof Error ? err.message : "Failed to load templates",
                    );
                }
            } finally {
                if (!cancelled) setTemplatesLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            abortRef.current?.abort();
        };
    }, []);

    // Reset dynamic fields when template changes
    useEffect(() => {
        if (selectedTemplate) {
            const fields: Record<string, string> = {};
            for (const field of selectedTemplate.required_fields) {
                fields[field] = "";
            }
            setDynamicFields(fields);
        } else {
            setDynamicFields({});
        }
    }, [selectedDocType, selectedTemplate]);

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
                                : DRAFTING_STEPS.indexOf(s.name) ===
                                    DRAFTING_STEPS.indexOf(event.step!) + 1
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
                // If the checkpoint context has section_drafts, store them
                if (
                    event.context &&
                    typeof event.context === "object" &&
                    "section_drafts" in event.context
                ) {
                    setSectionDrafts(
                        event.context.section_drafts as Record<string, string>,
                    );
                }
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
                // Try to parse section drafts from final data
                if (
                    event.data &&
                    typeof event.data === "object" &&
                    "section_drafts" in (event.data as Record<string, unknown>)
                ) {
                    setSectionDrafts(
                        (event.data as Record<string, unknown>)
                            .section_drafts as Record<string, string>,
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

    const handleSubmit = useCallback(() => {
        if (!selectedDocType || !caseFacts.trim() || starting) return;
        setStarting(true);
        setIsRunning(true);
        setError(null);
        setMemo("");
        setConfidence(undefined);
        setCheckpoint(null);
        setExecutionId(null);
        setSectionDrafts(null);
        setSteps(
            DRAFTING_STEPS.map((name, i) => ({
                name,
                status: i === 0 ? ("active" as const) : ("pending" as const),
            })),
        );

        // Build additional context from dynamic fields
        const additionalContext: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(dynamicFields)) {
            if (value.trim()) {
                additionalContext[key] = value.trim();
            }
        }

        try {
            abortRef.current = runDraftingAgent(
                selectedDocType,
                caseFacts.trim(),
                handleEvent,
                (err) => {
                    setError(err.message);
                    setIsRunning(false);
                },
                targetCourt.trim() || undefined,
                [],
                Object.keys(additionalContext).length > 0
                    ? additionalContext
                    : undefined,
            );
        } finally {
            setStarting(false);
        }
    }, [selectedDocType, caseFacts, targetCourt, dynamicFields, starting, handleEvent]);

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

    const handleRevise = (sectionName: string, feedback: string) => {
        if (!executionId) return;
        // Resume with revision feedback in format "section_name: feedback"
        handleResume(`${sectionName}: ${feedback}`);
    };

    const handleExport = async (format: "docx" | "pdf") => {
        if (!executionId) return;
        try {
            const blob = await exportDraft(executionId, format);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `draft.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Export failed");
        }
    };

    const handleReset = useCallback(() => {
        abortRef.current?.abort();
        setSelectedDocType("");
        setCaseFacts("");
        setTargetCourt("");
        setDynamicFields({});
        setIsRunning(false);
        setExecutionId(null);
        setSteps([]);
        setCheckpoint(null);
        setMemo("");
        setConfidence(undefined);
        setSectionDrafts(null);
        setError(null);
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

    // Check if all required dynamic fields are filled
    const allDynamicFieldsFilled =
        !selectedTemplate ||
        selectedTemplate.required_fields.every(
            (field) => dynamicFields[field]?.trim(),
        );

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
                Drafting Agent
            </h1>
            <p className="text-sm text-muted-foreground mb-6">
                Select a document type and provide case details. The agent will
                draft a legal document grounded in precedents and statutes.
            </p>

            {/* Input form (shown when not running and no memo) */}
            {showInputForm && (
                <Card>
                    <CardContent className="pt-6 space-y-4">
                        {/* Template selector */}
                        <div>
                            <label htmlFor="drafting-template" className="sr-only">
                                Document type
                            </label>
                            <Select
                                value={selectedDocType}
                                onValueChange={setSelectedDocType}
                                disabled={templatesLoading}
                            >
                                <SelectTrigger id="drafting-template" className="w-full">
                                    <SelectValue
                                        placeholder={
                                            templatesLoading
                                                ? "Loading templates..."
                                                : "Select document type"
                                        }
                                    />
                                </SelectTrigger>
                                <SelectContent>
                                    {templates.map((t) => (
                                        <SelectItem key={t.doc_type} value={t.doc_type}>
                                            {t.display_name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            {templateError && (
                                <p className="text-xs text-red-500 mt-1" role="alert">
                                    {templateError}
                                </p>
                            )}
                        </div>

                        {/* Case facts */}
                        <div>
                            <label htmlFor="drafting-case-facts" className="sr-only">
                                Case facts
                            </label>
                            <Textarea
                                id="drafting-case-facts"
                                placeholder="Describe the facts of your case..."
                                value={caseFacts}
                                onChange={(e) => setCaseFacts(e.target.value)}
                                className="min-h-[120px] text-sm"
                            />
                        </div>

                        {/* Target court */}
                        <div>
                            <label htmlFor="drafting-target-court" className="sr-only">
                                Target court
                            </label>
                            <Input
                                id="drafting-target-court"
                                placeholder="e.g., High Court of Delhi"
                                value={targetCourt}
                                onChange={(e) => setTargetCourt(e.target.value)}
                            />
                        </div>

                        {/* Dynamic required fields based on selected template */}
                        {selectedTemplate &&
                            selectedTemplate.required_fields.length > 0 && (
                                <div className="space-y-3 border-t pt-4">
                                    <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                                        Required fields for {selectedTemplate.display_name}
                                    </p>
                                    {selectedTemplate.required_fields.map((field) => (
                                        <div key={field}>
                                            <label
                                                htmlFor={`drafting-field-${field}`}
                                                className="sr-only"
                                            >
                                                {formatFieldName(field)}
                                            </label>
                                            <Input
                                                id={`drafting-field-${field}`}
                                                placeholder={formatFieldName(field)}
                                                value={dynamicFields[field] || ""}
                                                onChange={(e) =>
                                                    setDynamicFields((prev) => ({
                                                        ...prev,
                                                        [field]: e.target.value,
                                                    }))
                                                }
                                            />
                                        </div>
                                    ))}
                                </div>
                            )}

                        <Button
                            onClick={handleSubmit}
                            disabled={
                                starting ||
                                !selectedDocType ||
                                !caseFacts.trim() ||
                                !allDynamicFieldsFilled
                            }
                        >
                            {starting ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                "Start Drafting"
                            )}
                        </Button>
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
                        {/* Input summary display */}
                        <Card>
                            <CardContent className="pt-4">
                                <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">
                                    Document Type
                                </p>
                                <p className="text-sm mb-3">
                                    {selectedTemplate?.display_name || selectedDocType}
                                </p>
                                <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">
                                    Case Facts
                                </p>
                                <p className="text-sm">{caseFacts}</p>
                            </CardContent>
                        </Card>

                        {/* Mobile step timeline */}
                        <div className="md:hidden">
                            <AgentStepTimeline steps={steps} />
                        </div>

                        {/* Checkpoint prompt */}
                        {checkpoint && !sectionDrafts && (
                            <AgentCheckpointPrompt
                                question={checkpoint.question}
                                context={checkpoint.context}
                                onSubmit={handleResume}
                                disabled={isRunning}
                                error={checkpointError}
                                onClearError={() => setCheckpointError(null)}
                            />
                        )}

                        {/* Draft section viewer at checkpoint (when section_drafts available) */}
                        {checkpoint && sectionDrafts && (
                            <div className="space-y-4">
                                <div className="text-sm font-medium">
                                    {checkpoint.question || "Review the drafted sections below. You can revise individual sections or approve to continue."}
                                </div>
                                <DraftSectionViewer
                                    sections={sectionDrafts}
                                    onRevise={handleRevise}
                                    disabled={isRunning}
                                />
                                <Button
                                    onClick={() => handleResume("approve")}
                                    disabled={isRunning}
                                >
                                    Approve and Continue
                                </Button>
                            </div>
                        )}

                        {/* Final draft section viewer (after completion) */}
                        {!isRunning && !checkpoint && sectionDrafts && (
                            <DraftSectionViewer
                                sections={sectionDrafts}
                                onExport={executionId ? handleExport : undefined}
                                disabled={isRunning}
                            />
                        )}

                        {/* Memo result (shown if no section drafts available) */}
                        {memo && !sectionDrafts && (
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

                        {/* New Draft button after completion */}
                        {!isRunning && (memo || sectionDrafts || error) && !checkpoint && (
                            <>
                                <LegalDisclaimer className="mt-2" />
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleReset}
                                >
                                    <RotateCcw className="h-3.5 w-3.5 mr-1.5" />{" "}
                                    New Draft
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatFieldName(name: string): string {
    return name
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
}
