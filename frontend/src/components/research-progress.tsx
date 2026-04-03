"use client";

import { useEffect, useRef, useState } from "react";
import type { ProcessEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Search, BookOpen, Scale, Shield, FileText, CheckCircle2, Loader2,
  BrainCircuit, Lightbulb, AlertTriangle, Eye,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Stage definitions — maps the 5 conceptual research stages
// ---------------------------------------------------------------------------

interface Stage {
  id: string;
  label: string;
  icon: React.ElementType;
  nodes: Set<string>;
}

const STAGES: Stage[] = [
  {
    id: "understand",
    label: "Understand",
    icon: BookOpen,
    nodes: new Set(["rewrite_query", "classify", "statute_lookup", "element_decomposition"]),
  },
  {
    id: "decompose",
    label: "Plan",
    icon: BrainCircuit,
    nodes: new Set(["plan_research", "checkpoint_plan", "pre_warm_embeddings"]),
  },
  {
    id: "investigate",
    label: "Investigate",
    icon: Search,
    nodes: new Set([
      "dispatch_workers", "case_law_worker", "named_case_worker", "statute_worker",
      "ik_search_worker", "web_search_worker", "graph_worker", "graph_community_worker",
      "gather_results", "batch_cot_with_reflection", "evaluate_and_extract",
      "gap_analysis", "checkpoint_findings",
    ]),
  },
  {
    id: "challenge",
    label: "Challenge",
    icon: Shield,
    nodes: new Set(["adversarial_search", "temporal_validation"]),
  },
  {
    id: "synthesize",
    label: "Synthesize",
    icon: FileText,
    nodes: new Set(["speculative_synthesis", "format_footnotes", "verify_v2", "quality_check", "checkpoint_memo"]),
  },
];

// Fast path: collapse to 3 stages
const FAST_STAGES: Stage[] = [
  STAGES[0], // Understand
  { id: "search", label: "Search", icon: Search, nodes: new Set(["fast_path_search"]) },
  { id: "synthesize", label: "Synthesize", icon: FileText, nodes: new Set(["fast_path_synthesis", "format_footnotes", "verify_v2", "quality_check", "checkpoint_memo"]) },
];

// ---------------------------------------------------------------------------
// Helpers to map backend events to human-readable activity lines
// ---------------------------------------------------------------------------

interface ActivityItem {
  icon: React.ElementType;
  text: string;
  color: string;
  timestamp: number;
}

/** Map node names to user-friendly labels for the activity feed.
 *  Worker nodes are excluded — they emit richer "found" events instead. */
const STATUS_STEP_LABELS: Record<string, string> = {
  rewrite_query: "Rewriting query",
  classify: "Classifying query",
  statute_lookup: "Looking up relevant statutes",
  element_decomposition: "Decomposing into legal elements",
  plan_research: "Planning research strategy",
  pre_warm_embeddings: "Preparing search embeddings",
  gather_results: "Collecting search results",
  batch_cot_with_reflection: "Analyzing and reflecting on results",
  evaluate_and_extract: "Evaluating source relevance",
  gap_analysis: "Checking for evidence gaps",
  adversarial_search: "Searching for counter-arguments",
  temporal_validation: "Checking for outdated precedents",
  speculative_synthesis: "Synthesizing research memo",
  format_footnotes: "Building footnotes",
  verify_v2: "Verifying citations",
  quality_check: "Running legal quality check",
  fast_path_search: "Quick search",
  fast_path_synthesis: "Quick synthesis",
  // Worker nodes intentionally excluded — they emit "found" events with result counts
  // dispatch_workers excluded — emits its own "progress" event
};

function eventToActivity(event: ProcessEvent): ActivityItem | null {
  const d = event.data;
  const ts = event.timestamp ?? Date.now();

  switch (event.type) {
    case "plan":
      return { icon: BrainCircuit, text: `Research plan created with ${d.total_workers} tasks`, color: "text-blue-500", timestamp: ts };
    case "found":
      return {
        icon: CheckCircle2,
        text: `${workerLabel(d.worker as string)}: found ${d.count} result${(d.count as number) !== 1 ? "s" : ""}${d.top_case ? ` — ${d.top_case}` : ""}`,
        color: "text-green-600",
        timestamp: ts,
      };
    case "searching":
      return { icon: Search, text: `Searching ${workerLabel(d.worker as string)}...`, color: "text-amber-500", timestamp: ts };
    case "evaluating":
      return {
        icon: Eye,
        text: `Evaluated ${d.total} sources — ${d.correct} relevant, ${d.filtered} filtered`,
        color: "text-purple-500",
        timestamp: ts,
      };
    case "reflection":
      return {
        icon: Lightbulb,
        text: d.pivot ? `Strategy pivot: ${d.insights}` : `Reflection: ${d.insights}`,
        color: d.pivot ? "text-orange-500" : "text-amber-500",
        timestamp: ts,
      };
    case "gap":
      return {
        icon: AlertTriangle,
        text: Array.isArray(d.gaps) && d.gaps.length > 0
          ? `${d.gaps.length} evidence gap${(d.gaps as string[]).length !== 1 ? "s" : ""} identified`
          : "No evidence gaps found",
        color: "text-orange-500",
        timestamp: ts,
      };
    case "drafting":
      return {
        icon: FileText,
        text: d.status === "generating"
          ? `Drafting memo (${d.strategy} strategy)...`
          : `Draft complete (${d.strategy} strategy)`,
        color: "text-indigo-500",
        timestamp: ts,
      };
    case "verification":
      return {
        icon: CheckCircle2,
        text: `${d.citations_verified} citation${(d.citations_verified as number) !== 1 ? "s" : ""} verified${(d.citations_removed as number) > 0 ? `, ${d.citations_removed} removed` : ""}`,
        color: "text-green-600",
        timestamp: ts,
      };
    case "quality":
      return {
        icon: Scale,
        text: `Quality score: ${typeof d.overall_score === "number" ? Math.round(d.overall_score * 100) : "?"}% — ${d.pass_threshold ? "Passed" : "Needs review"}`,
        color: d.pass_threshold ? "text-green-600" : "text-amber-500",
        timestamp: ts,
      };
    case "progress": {
      const detail = d.detail as string;
      if (!detail) return null;
      // "Starting: ..." events from astream_events — map to human-readable labels
      if (detail.startsWith("Starting: ")) {
        const nodeName = detail.slice("Starting: ".length).trim();
        const label = STATUS_STEP_LABELS[nodeName.replace(/ /g, "_")] || nodeName;
        return { icon: Loader2, text: `${label}...`, color: "text-[var(--gold)]", timestamp: ts };
      }
      return { icon: Loader2, text: detail, color: "text-muted-foreground", timestamp: ts };
    }
    case "status": {
      const step = d.step as string;
      if (!step) return null;
      const label = STATUS_STEP_LABELS[step];
      if (!label) return null; // Skip internal/uninteresting steps
      return { icon: CheckCircle2, text: label, color: "text-muted-foreground", timestamp: ts };
    }
    default:
      return null;
  }
}

function workerLabel(worker: string): string {
  const labels: Record<string, string> = {
    // Old-style node names (backward compat)
    case_law_worker: "Case law search",
    named_case_worker: "Named case lookup",
    statute_worker: "Statute search",
    ik_search_worker: "Indian Kanoon",
    web_search_worker: "Web search",
    graph_worker: "Citation graph",
    graph_community_worker: "Graph community",
    // New-style task types
    case_law: "Case law search",
    named_case: "Named case lookup",
    statute: "Statute search",
    ik_search: "Indian Kanoon",
    web: "Web search",
    graph: "Citation graph",
    graph_community: "Graph community",
  };
  return labels[worker] || worker?.replace(/_/g, " ") || "Search";
}

// ---------------------------------------------------------------------------
// Determine current stage from completed nodes
// ---------------------------------------------------------------------------

function getCurrentStageIndex(completedNodes: Set<string>, stages: Stage[]): number {
  // Find the highest stage that has at least one completed node
  let current = 0;
  for (let i = 0; i < stages.length; i++) {
    for (const node of stages[i].nodes) {
      if (completedNodes.has(node)) {
        current = i;
        break;
      }
    }
  }
  return current;
}

// Stage completion is determined by index comparison in the main component

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ResearchProgressProps {
  events: ProcessEvent[];
  completedNodes: Set<string>;
  isRunning: boolean;
  isFastPath?: boolean;
  startTime?: number;
}

export function ResearchProgress({
  events,
  completedNodes,
  isRunning,
  isFastPath,
  startTime,
}: ResearchProgressProps) {
  const stages = isFastPath ? FAST_STAGES : STAGES;
  const currentStageIdx = getCurrentStageIndex(completedNodes, stages);
  const activityRef = useRef<HTMLDivElement>(null);
  const [elapsed, setElapsed] = useState(0);

  // Elapsed time — compute from startTime rather than tracking in state during cleanup
  useEffect(() => {
    if (!isRunning || !startTime) return;
    const tick = () => setElapsed(Math.floor((Date.now() - startTime) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [isRunning, startTime]);

  // Derive elapsed display: 0 when not running/no startTime
  const displayElapsed = isRunning && startTime ? elapsed : 0;

  // Convert events to activity items, deduplicating consecutive identical texts
  const activities: ActivityItem[] = [];
  for (const ev of events) {
    const item = eventToActivity(ev);
    if (!item) continue;
    // Skip if identical to previous item
    const prev = activities[activities.length - 1];
    if (prev && prev.text === item.text) continue;
    activities.push(item);
  }

  // Auto-scroll activity feed
  useEffect(() => {
    if (activityRef.current) {
      activityRef.current.scrollTop = activityRef.current.scrollHeight;
    }
  }, [activities.length]);

  if (!isRunning && completedNodes.size === 0 && events.length === 0) return null;

  // Determine stage states
  const stageStates = stages.map((stage, i) => {
    const hasCompletedNode = [...stage.nodes].some((n) => completedNodes.has(n));
    if (i < currentStageIdx || (!isRunning && hasCompletedNode && i <= currentStageIdx)) {
      return "completed" as const;
    }
    if (i === currentStageIdx && (isRunning || hasCompletedNode)) {
      return "active" as const;
    }
    return "pending" as const;
  });

  // If done (not running), mark all stages with completed nodes as completed
  if (!isRunning && completedNodes.size > 0) {
    for (let i = 0; i < stages.length; i++) {
      const hasNode = [...stages[i].nodes].some((n) => completedNodes.has(n));
      if (hasNode) stageStates[i] = "completed";
    }
  }

  const formatElapsed = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  return (
    <div className="space-y-4">
      {/* Stage stepper */}
      <div className="relative">
        {/* Connecting line */}
        <div className="absolute top-5 left-0 right-0 h-0.5 bg-border" aria-hidden />
        <div
          className="absolute top-5 left-0 h-0.5 bg-[var(--gold)] transition-all duration-700 ease-out"
          style={{
            width: `${Math.min(
              ((stageStates.lastIndexOf("completed") + (stageStates.includes("active") ? 0.5 : 0)) /
                Math.max(stages.length - 1, 1)) *
                100,
              100,
            )}%`,
          }}
          aria-hidden
        />

        <div className="relative flex justify-between">
          {stages.map((stage, i) => {
            const state = stageStates[i];
            const Icon = stage.icon;

            return (
              <div key={stage.id} className="flex flex-col items-center" style={{ width: `${100 / stages.length}%` }}>
                {/* Circle */}
                <div
                  className={cn(
                    "relative z-10 flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all duration-500",
                    state === "completed" && "bg-[var(--gold)] border-[var(--gold)] text-white",
                    state === "active" && "bg-background border-[var(--gold)] text-[var(--gold)] shadow-[0_0_0_4px_rgba(var(--gold-rgb,180,140,60),0.15)]",
                    state === "pending" && "bg-muted border-border text-muted-foreground",
                  )}
                >
                  {state === "completed" ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : state === "active" ? (
                    <div className="relative">
                      <Icon className="h-5 w-5" />
                      <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-[var(--gold)] rounded-full animate-pulse" />
                    </div>
                  ) : (
                    <Icon className="h-5 w-5" />
                  )}
                </div>

                {/* Label */}
                <span
                  className={cn(
                    "mt-2 text-xs font-medium transition-colors",
                    state === "completed" && "text-foreground",
                    state === "active" && "text-[var(--gold)]",
                    state === "pending" && "text-muted-foreground",
                  )}
                >
                  {stage.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Live activity feed */}
      {(isRunning || activities.length > 0) && (
        <div className="rounded-lg border bg-card overflow-hidden">
          {/* Header with elapsed time */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b bg-muted/30">
            <div className="flex items-center gap-2">
              {isRunning && <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--gold)]" />}
              <span className="text-xs font-medium text-muted-foreground">
                {isRunning ? "Researching..." : "Research complete"}
              </span>
            </div>
            {displayElapsed > 0 && (
              <span className="text-xs tabular-nums text-muted-foreground">
                {formatElapsed(displayElapsed)}
              </span>
            )}
          </div>

          {/* Activity items */}
          <div
            ref={activityRef}
            className={cn(
              "overflow-y-auto transition-all",
              activities.length > 5 ? "max-h-[160px]" : "max-h-[300px]",
            )}
          >
            {activities.length === 0 && isRunning && (
              <div className="px-4 py-3 text-xs text-muted-foreground animate-pulse">
                Analyzing your research question...
              </div>
            )}
            {activities.map((item, i) => {
              const Icon = item.icon;
              return (
                <div
                  key={i}
                  className={cn(
                    "flex items-start gap-2.5 px-4 py-2 text-xs border-b border-border/50 last:border-0",
                    i === activities.length - 1 && isRunning && "bg-muted/20",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-3.5 w-3.5 mt-0.5 shrink-0",
                      item.color,
                      i === activities.length - 1 && isRunning && item.icon === Loader2 && "animate-spin",
                    )}
                  />
                  <span className="text-foreground/80 leading-relaxed">{item.text}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
