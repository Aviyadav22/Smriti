"use client";

import { useCallback, useRef, useState } from "react";
import { AgentWorkspace } from "@/components/agents/AgentWorkspace";
import { ResearchInput } from "@/components/agents/inputs/ResearchInput";
import { ResearchExtras } from "@/components/agents/extras/ResearchExtras";
import { PlanReview } from "@/components/plan-review";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { reviseResearchSection } from "@/lib/api";
import type { ResearchAudit, ResearchFootnote } from "@/lib/types";

const FAST_PATH_INDICATORS = new Set(["fast_path_search", "fast_path_synthesis"]);

export default function ResearchPage() {
    const [researchAudit, setResearchAudit] = useState<ResearchAudit | null>(null);
    const [verificationBanner, setVerificationBanner] = useState<string | null>(null);
    const [citationsVerified, setCitationsVerified] = useState(0);
    const [citationsRemoved, setCitationsRemoved] = useState(0);
    const [confidenceBreakdown, setConfidenceBreakdown] = useState<{
        data_confidence?: number; legal_confidence?: number; consistency_confidence?: number;
    } | undefined>();
    const executionIdRef = useRef<string | null>(null);

    const handleReset = useCallback(() => {
        setResearchAudit(null);
        setVerificationBanner(null);
        setCitationsVerified(0);
        setCitationsRemoved(0);
        setConfidenceBreakdown(undefined);
    }, []);

    const handleReviseSection = useCallback(
        async (heading: string, feedback: string) =>
            reviseResearchSection(executionIdRef.current ?? "", heading, feedback),
        [],
    );

    return (
        <AgentWorkspace
            agentType="research"
            title="Research Agent"
            description="Legal research with verified citations"
            steps={[]}
            suppressDefaultMemo
            suppressDefaultProgress
            renderInput={(props) => <ResearchInput {...props} />}
            renderCheckpoint={({ checkpoint, onSubmit, disabled, error, onClearError }) => {
                const ctx = checkpoint.context;
                if (ctx.research_audit && ctx.research_audit !== researchAudit) {
                    const audit = ctx.research_audit as ResearchAudit;
                    queueMicrotask(() => {
                        setResearchAudit(audit);
                        if (audit.verification_banner) {
                            setVerificationBanner(audit.verification_banner);
                            setCitationsVerified(audit.citations_verified ?? 0);
                            setCitationsRemoved(audit.citations_removed ?? 0);
                        }
                    });
                }
                if (ctx.research_plan) {
                    return (
                        <PlanReview
                            question={checkpoint.question}
                            researchPlan={ctx.research_plan as Array<{task_type: string; nl_query: string; rationale: string; named_cases?: Array<{name?: string; citation?: string}>; priority?: number}>}
                            classification={ctx.classification as Record<string, unknown> | null}
                            statuteContext={ctx.statute_context as Array<{act: string; section: string; title?: string; repealed?: boolean}>}
                            legalElements={ctx.legal_elements as Array<{id: string; description: string; contested?: boolean}>}
                            includeAdversarial={ctx.include_adversarial as boolean | undefined}
                            onSubmit={onSubmit} disabled={disabled} error={error} onClearError={onClearError}
                        />
                    );
                }
                return (
                    <AgentCheckpointPrompt
                        question={checkpoint.question} context={checkpoint.context}
                        onSubmit={onSubmit} disabled={disabled} error={error} onClearError={onClearError}
                    />
                );
            }}
            renderResultExtras={({ memo, confidence, executionId, isRunning, session, processEvents, completedNodes, startTime, displayMemo, isStreaming }) => {
                executionIdRef.current = executionId;
                const isFastPath = [...completedNodes].some((n) => FAST_PATH_INDICATORS.has(n));
                const footnotes = session.footnotes;
                const footnoteVerification = footnotes.length > 0
                    ? Object.fromEntries(footnotes.map((f: ResearchFootnote) => [
                        f.number, f.verification_status as "verified_pg" | "verified_ik" | "verified_neo4j" | "unverified" | "removed" | "flagged",
                    ])) : undefined;
                return (
                    <ResearchExtras
                        memo={memo} confidence={confidence} executionId={executionId}
                        isRunning={isRunning} processEvents={processEvents}
                        completedNodes={completedNodes} startTime={startTime}
                        footnotes={footnotes} researchAudit={researchAudit}
                        verificationBanner={verificationBanner}
                        citationsVerified={citationsVerified} citationsRemoved={citationsRemoved}
                        confidenceBreakdown={confidenceBreakdown} isFastPath={isFastPath}
                        isStreaming={isStreaming} displayMemo={displayMemo}
                        onReviseSection={isStreaming ? undefined : (!isRunning ? handleReviseSection : undefined)}
                        footnoteVerification={footnoteVerification}
                    />
                );
            }}
            onReset={handleReset}
            newSessionLabel="New Research"
        />
    );
}
