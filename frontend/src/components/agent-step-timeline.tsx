"use client";

import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";
import type { AgentStep } from "@/lib/types";

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
                            {step.name}
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
