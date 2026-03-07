"use client";

import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";
import type { AgentStep } from "@/lib/types";

/** Map internal node names to human-readable labels for the step timeline. */
const STEP_LABELS: Record<string, string> = {
    // Research agent steps
    classify: "Understanding your question",
    decompose: "Breaking into sub-questions",
    checkpoint_plan: "Review research plan",
    search: "Searching case law",
    parallel_search: "Searching case law",
    gather: "Analyzing judgments",
    contradictions: "Checking for conflicts",
    checkpoint_findings: "Review findings",
    synthesize: "Drafting research memo",
    verify: "Verifying citations",
    checkpoint_memo: "Final review",
    // Case prep agent steps
    load_analysis: "Loading document analysis",
    prioritize: "Prioritizing legal issues",
    checkpoint_issues: "Review prioritized issues",
    deep_search: "Deep precedent search",
    deep_precedent_search: "Deep precedent search",
    argument_order: "Building argument order",
    build_argument_order: "Building argument order",
    checkpoint_strategy: "Review strategy",
    strategy_memo: "Generating strategy memo",
    generate_strategy_memo: "Generating strategy memo",
};

function getStepLabel(name: string): string {
    return STEP_LABELS[name] ?? name;
}

interface AgentStepTimelineProps {
    steps: AgentStep[];
}

export function AgentStepTimeline({ steps }: AgentStepTimelineProps) {
    return (
        <div className="space-y-3">
            {steps.map((step, i) => (
                <div key={i} className="flex items-start gap-3">
                    {step.status === "completed" && <CheckCircle2 className="h-4 w-4 mt-0.5 text-green-500 shrink-0" />}
                    {step.status === "active" && <Loader2 className="h-4 w-4 mt-0.5 text-[var(--gold)] animate-spin shrink-0" />}
                    {step.status === "pending" && <Circle className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />}
                    {step.status === "error" && <AlertCircle className="h-4 w-4 mt-0.5 text-red-500 shrink-0" />}
                    <div>
                        <p className={`text-sm font-medium ${step.status === "active" ? "text-foreground" : step.status === "completed" ? "text-muted-foreground" : "text-muted-foreground/60"}`}>
                            {getStepLabel(step.name)}
                        </p>
                        {step.message && (
                            <p className="text-xs text-muted-foreground mt-0.5">{step.message}</p>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
