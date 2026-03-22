"use client";

import type { ProcessEvent } from "@/lib/types";

interface ResearchProgressBarProps {
  events: ProcessEvent[];
  isRunning: boolean;
}

const STAGES = [
  { id: "understand", label: "Understand", weight: 0.10 },
  { id: "decompose", label: "Decompose", weight: 0.10 },
  { id: "investigate", label: "Investigate", weight: 0.50 },
  { id: "challenge", label: "Challenge", weight: 0.20 },
  { id: "synthesize", label: "Synthesize", weight: 0.10 },
] as const;

/** Cumulative weight thresholds for stage completion checks. */
const STAGE_CUMULATIVE: Record<string, number> = (() => {
  let cumulative = 0;
  const result: Record<string, number> = {};
  for (const stage of STAGES) {
    cumulative += stage.weight;
    result[stage.id] = cumulative;
  }
  return result;
})();

/** Compute overall progress (0-1) from events.
 *  Primary source: explicit "progress" events from the backend.
 *  Fallback: infer stage from event type keywords when no progress events exist.
 */
function computeProgress(events: ProcessEvent[]): { progress: number; currentStage: string; detail: string } {
  // Primary: find the latest explicit progress event
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.type === "progress" && typeof e.data?.progress === "number") {
      return {
        progress: e.data.progress as number,
        currentStage: (e.data.stage as string) || "",
        detail: (e.data.detail as string) || "",
      };
    }
  }

  // Fallback: infer from event types present in the event stream
  const types = new Set(events.map((e) => e.type ?? ""));

  const has = (keyword: string) =>
    [...types].some((t) => t.toLowerCase().includes(keyword));

  if (has("quality")) {
    return { progress: 0.95, currentStage: "synthesize", detail: "Quality check" };
  }
  if (has("verification")) {
    return { progress: 0.90, currentStage: "synthesize", detail: "Verifying memo" };
  }
  if (has("drafting")) {
    return { progress: 0.80, currentStage: "synthesize", detail: "Drafting memo" };
  }
  if (has("gap")) {
    return { progress: 0.65, currentStage: "challenge", detail: "Gap analysis" };
  }
  if (has("evaluating") || has("reflection")) {
    return { progress: 0.55, currentStage: "challenge", detail: "Evaluating sources" };
  }
  if (has("searching") || has("found")) {
    return { progress: 0.35, currentStage: "investigate", detail: "Searching case law" };
  }
  if (has("plan")) {
    return { progress: 0.15, currentStage: "decompose", detail: "Planning research" };
  }
  if (events.length > 0) {
    return { progress: 0.05, currentStage: "understand", detail: "Analysing query" };
  }

  return { progress: 0, currentStage: "", detail: "" };
}

export function ResearchProgressBar({ events, isRunning }: ResearchProgressBarProps) {
  const { progress, currentStage, detail } = computeProgress(events);

  if (!isRunning && progress === 0) return null;

  const pct = Math.round(progress * 100);

  return (
    <div className="space-y-1.5">
      {/* Stage labels */}
      <div className="flex justify-between text-xs text-muted-foreground">
        {STAGES.map((stage) => (
          <span
            key={stage.id}
            className={`${
              stage.id === currentStage
                ? "text-[var(--gold)] font-medium"
                : progress >= STAGE_CUMULATIVE[stage.id]
                  ? "text-foreground"
                  : ""
            }`}
          >
            {stage.label}
          </span>
        ))}
      </div>

      {/* Progress bar */}
      <div
        className="h-2.5 bg-muted rounded-full overflow-hidden relative"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Research progress"
      >
        <div
          className="h-full bg-[var(--gold)] rounded-full transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
        {/* Stage tick marks */}
        {[0.15, 0.35, 0.55, 0.70, 0.90].map((pos, i) => (
          <div
            key={i}
            className="absolute top-1/2 -translate-y-1/2 w-1 h-1 rounded-full bg-background/60"
            style={{ left: `${pos * 100}%` }}
          />
        ))}
      </div>

      {/* Detail text */}
      {isRunning && detail && (
        <p className="text-xs text-muted-foreground animate-pulse">
          {detail}...
        </p>
      )}
    </div>
  );
}
