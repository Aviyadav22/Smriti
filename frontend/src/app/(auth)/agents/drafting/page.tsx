"use client";

import { useCallback, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AgentWorkspace } from "@/components/agents/AgentWorkspace";
import { DraftingInput } from "@/components/agents/inputs/DraftingInput";
import { DraftingExtras } from "@/components/agents/extras/DraftingExtras";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { Button } from "@/components/ui/button";

const STEPS = [
    "resolve_template", "gather_provisions", "verify_precedents",
    "checkpoint_sources", "draft_sections", "assemble",
    "checkpoint_draft", "verify_final", "checkpoint_final",
];

export default function DraftingPage() {
    const searchParams = useSearchParams();
    const researchExecutionId = searchParams.get("research_execution_id");

    // Track section drafts across checkpoint/completion boundary
    const [sectionDrafts, setSectionDrafts] = useState<Record<string, string> | null>(null);
    const resumeRef = useRef<((input: string) => void) | null>(null);

    const handleReset = useCallback(() => {
        setSectionDrafts(null);
    }, []);

    return (
        <AgentWorkspace
            agentType="drafting"
            title="Drafting Agent"
            description="Select a document type and provide case details. The agent drafts legal documents grounded in precedents."
            steps={STEPS}
            renderInput={(props) => (
                <DraftingInput {...props} researchExecutionId={researchExecutionId} />
            )}
            renderCheckpoint={({ checkpoint, onSubmit, disabled, error, onClearError }) => {
                // Capture section_drafts from checkpoint context
                const sections = checkpoint.context?.section_drafts as Record<string, string> | undefined;
                if (sections && sections !== sectionDrafts) {
                    // Schedule state update (not during render)
                    queueMicrotask(() => setSectionDrafts(sections));
                }
                // Store resume fn for revise flow
                resumeRef.current = onSubmit;

                if (sections) {
                    return (
                        <div className="space-y-4">
                            <div className="text-sm font-medium">
                                {checkpoint.question || "Review the drafted sections below."}
                            </div>
                            <DraftingExtras
                                sectionDrafts={sections}
                                executionId={null}
                                isRunning={disabled}
                                checkpointActive={true}
                                onRevise={(sectionName, feedback) => onSubmit(`${sectionName}: ${feedback}`)}
                                disabled={disabled}
                            />
                            <Button onClick={() => onSubmit("approve")} disabled={disabled}>
                                Approve and Continue
                            </Button>
                            {error && (
                                <div className="text-sm text-red-500 p-2 rounded bg-red-50 dark:bg-red-950/20 cursor-pointer" onClick={onClearError}>
                                    {error}
                                </div>
                            )}
                        </div>
                    );
                }

                return (
                    <AgentCheckpointPrompt
                        question={checkpoint.question}
                        context={checkpoint.context}
                        onSubmit={onSubmit}
                        disabled={disabled}
                        error={error}
                        onClearError={onClearError}
                    />
                );
            }}
            renderResultExtras={({ executionId, isRunning, session }) => {
                // Show section viewer after completion (if we captured sections)
                if (!sectionDrafts || session.checkpoint) return null;
                return (
                    <DraftingExtras
                        sectionDrafts={sectionDrafts}
                        executionId={executionId}
                        isRunning={isRunning}
                        checkpointActive={false}
                        onError={(msg) => session.setError(msg)}
                    />
                );
            }}
            onReset={handleReset}
            newSessionLabel="New Draft"
        />
    );
}
