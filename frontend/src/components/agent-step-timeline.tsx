"use client";

import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";
import type { AgentStep } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Map internal node names to human-readable labels for the step timeline. */
const STEP_LABELS: Record<string, string> = {
    // Research agent V1 steps (backward compat)
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
    // Research agent V2 steps
    rewrite_query: "Refining your question",
    plan_research: "Planning research strategy",
    dispatch_workers: "Dispatching search workers",
    gather_results: "Collecting search results",
    batch_cot_with_reflection: "Analyzing & reflecting",
    evaluate_and_extract: "Evaluating relevance",
    gap_analysis: "Identifying evidence gaps",
    speculative_synthesis: "Synthesizing research memo",
    format_footnotes: "Building footnotes",
    verify_v2: "Verifying citations",
    quality_check: "Legal quality check",
    // Fast path
    fast_path_search: "Quick search",
    fast_path_synthesis: "Quick synthesis",
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
    completedCount?: number;
    totalCount?: number;
}

export function AgentStepTimeline({ steps, completedCount, totalCount }: AgentStepTimelineProps) {
    const derivedCompleted = completedCount ?? steps.filter((s) => s.status === "completed").length;
    const derivedTotal = totalCount ?? steps.length;

    return (
        <div>
            <div role="list" className="relative">
                {steps.map((step, i) => (
                    <div key={i} role="listitem" className="relative flex items-start gap-3 pb-3 last:pb-0">
                        {i < steps.length - 1 && (
                            <div className={cn(
                                "absolute left-[7px] top-5 bottom-0 w-0.5",
                                step.status === "completed" ? "bg-green-500/30" : "bg-border",
                            )} />
                        )}
                        <div className={cn(
                            "relative z-10 shrink-0 mt-0.5",
                            step.status === "active" && "ring-2 ring-[var(--gold)]/30 ring-offset-2 ring-offset-background rounded-full",
                        )}>
                            {step.status === "completed" && <CheckCircle2 aria-label="Completed" className="h-4 w-4 text-green-500" />}
                            {step.status === "active" && <Loader2 aria-label="In progress" className="h-4 w-4 text-[var(--gold)] animate-spin" />}
                            {step.status === "pending" && <Circle aria-label="Pending" className="h-4 w-4 text-muted-foreground" />}
                            {step.status === "error" && <AlertCircle aria-label="Error" className="h-4 w-4 text-red-500" />}
                        </div>
                        <div className="min-w-0">
                            <p className={cn(
                                "text-sm font-medium truncate",
                                step.status === "active" ? "text-foreground" : step.status === "completed" ? "text-muted-foreground" : "text-muted-foreground/50",
                            )}>
                                {getStepLabel(step.name)}
                            </p>
                            {step.message && (
                                <p className="text-xs text-muted-foreground mt-0.5 truncate">{step.message}</p>
                            )}
                        </div>
                    </div>
                ))}
            </div>
            {derivedTotal > 0 && (
                <p className="text-xs text-muted-foreground mt-2">
                    Step {derivedCompleted} of {derivedTotal}
                </p>
            )}
        </div>
    );
}
