"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Search, FileText, AlertTriangle, CheckCircle2, Loader2, BrainCircuit, Lightbulb } from "lucide-react";
import type { ProcessEvent } from "@/lib/types";

interface ResearchProcessPanelProps {
    events: ProcessEvent[];
    isRunning: boolean;
}

const EVENT_CONFIG: Record<string, { icon: React.ElementType; label: string; color: string }> = {
    plan: { icon: BrainCircuit, label: "Research Plan", color: "text-blue-500" },
    searching: { icon: Search, label: "Searching", color: "text-yellow-500" },
    found: { icon: FileText, label: "Results Found", color: "text-green-500" },
    evaluating: { icon: CheckCircle2, label: "Evaluating", color: "text-purple-500" },
    reflection: { icon: Lightbulb, label: "Reflection", color: "text-amber-500" },
    gap: { icon: AlertTriangle, label: "Gap Analysis", color: "text-orange-500" },
    drafting: { icon: FileText, label: "Drafting", color: "text-indigo-500" },
    verification: { icon: CheckCircle2, label: "Verification", color: "text-green-600" },
    quality: { icon: CheckCircle2, label: "Quality Check", color: "text-emerald-500" },
};

function formatEventData(event: ProcessEvent): string {
    const d = event.data;
    switch (event.type) {
        case "plan":
            return `${d.total_workers} research tasks planned`;
        case "found":
            return `${d.worker}: ${d.count} results${d.top_case ? ` — ${d.top_case}` : ""}`;
        case "evaluating":
            return `${d.correct} relevant, ${d.ambiguous} ambiguous, ${d.filtered} filtered${d.deep_read ? `, ${d.deep_read} deep reads` : ""}`;
        case "reflection":
            return d.pivot ? `Strategy pivot — ${d.insights}` : `${d.insights}`;
        case "gap":
            return Array.isArray(d.gaps) && d.gaps.length > 0
                ? `${d.gaps.length} gap(s): ${(d.gaps as string[])[0]}`
                : "No gaps identified";
        case "drafting":
            return `${d.strategy} — ${d.status}`;
        case "verification":
            return `${d.citations_verified} verified, ${d.citations_removed} removed`;
        case "quality":
            return `Score: ${typeof d.overall_score === "number" ? Math.round(d.overall_score * 100) : "?"}% — ${d.pass_threshold ? "Passed" : "Review needed"}`;
        default:
            return JSON.stringify(d).slice(0, 100);
    }
}

export function ResearchProcessPanel({ events, isRunning }: ResearchProcessPanelProps) {
    const [isOpen, setIsOpen] = useState(true);

    if (events.length === 0 && !isRunning) return null;

    return (
        <div className="border rounded-lg bg-card">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium text-left hover:bg-muted/50 transition-colors"
            >
                {isOpen ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                Research Process
                {isRunning && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground ml-auto" />}
                {!isRunning && events.length > 0 && (
                    <span className="ml-auto text-xs text-muted-foreground">{events.length} events</span>
                )}
            </button>

            {isOpen && (
                <div className="px-4 pb-3 space-y-1.5 max-h-[300px] overflow-y-auto">
                    {events.map((event, i) => {
                        const config = EVENT_CONFIG[event.type] || { icon: FileText, label: event.type, color: "text-muted-foreground" };
                        const Icon = config.icon;
                        return (
                            <div key={i} className="flex items-start gap-2 text-xs">
                                <Icon className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${config.color}`} />
                                <span className="text-muted-foreground leading-relaxed">
                                    <span className="font-medium text-foreground">{config.label}:</span>{" "}
                                    {formatEventData(event)}
                                </span>
                            </div>
                        );
                    })}
                    {isRunning && events.length === 0 && (
                        <div className="text-xs text-muted-foreground">Waiting for events...</div>
                    )}
                </div>
            )}
        </div>
    );
}
