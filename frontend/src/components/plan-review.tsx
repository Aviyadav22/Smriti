"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
// No Switch component — using Button toggle instead
import { Badge } from "@/components/ui/badge";
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  Scale,
  Search,
  Shield,
  Trash2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ResearchTaskPreview {
  task_type: string;
  nl_query: string;
  rationale: string;
  named_cases?: Array<{ name?: string; citation?: string }>;
  priority?: number;
}

interface StatutePreview {
  act: string;
  section: string;
  title?: string;
  repealed?: boolean;
}

interface ElementPreview {
  id: string;
  description: string;
  contested?: boolean;
}

interface PlanReviewProps {
  question: string;
  researchPlan: ResearchTaskPreview[];
  classification?: Record<string, unknown> | null;
  statuteContext?: StatutePreview[];
  legalElements?: ElementPreview[];
  includeAdversarial?: boolean;
  onSubmit: (input: string) => void;
  disabled?: boolean;
  error?: string | null;
  onClearError?: () => void;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const TASK_TYPE_LABELS: Record<string, string> = {
  case_law: "Case Law",
  named_case: "Named Case",
  statute: "Statute",
  constitution: "Constitution",
  ik_search: "Indian Kanoon",
  web: "Web Search",
  graph: "Citation Graph",
  graph_community: "Graph Community",
  llm_direct: "LLM Knowledge",
};

const TASK_TYPE_COLORS: Record<string, string> = {
  case_law: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  named_case: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  statute: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  constitution: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  ik_search: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  web: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300",
  graph: "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300",
  graph_community: "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300",
};

function TaskCard({
  task,
  index,
  onRemove,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}: {
  task: ResearchTaskPreview;
  index: number;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="group flex items-start gap-2 rounded-md border border-border p-2 hover:bg-muted/30 transition-colors">
      <div className="flex flex-col items-center gap-0.5 pt-1">
        <button
          type="button"
          onClick={onMoveUp}
          disabled={isFirst}
          className="p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30 focus-visible:ring-2 focus-visible:ring-ring rounded"
          aria-label="Move up"
        >
          <ChevronUp className="h-3 w-3" />
        </button>
        <button
          type="button"
          onClick={onMoveDown}
          disabled={isLast}
          className="p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30 focus-visible:ring-2 focus-visible:ring-ring rounded"
          aria-label="Move down"
        >
          <ChevronDown className="h-3 w-3" />
        </button>
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-mono text-muted-foreground">
            #{index + 1}
          </span>
          <Badge
            variant="secondary"
            className={`text-[10px] px-1.5 py-0 ${TASK_TYPE_COLORS[task.task_type] || ""}`}
          >
            {TASK_TYPE_LABELS[task.task_type] || task.task_type}
          </Badge>
          {task.priority === 1 && (
            <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
              High
            </Badge>
          )}
        </div>
        <p className="text-sm mt-1 leading-snug">{task.nl_query}</p>

        {expanded && (
          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
            <p>
              <span className="font-medium">Rationale:</span> {task.rationale}
            </p>
            {task.named_cases && task.named_cases.length > 0 && (
              <div>
                <span className="font-medium">Named cases:</span>
                <ul className="ml-3 mt-0.5">
                  {task.named_cases.map((c, i) => (
                    <li key={i} className="list-disc">
                      {c.name || c.citation || "Unknown"}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="text-xs py-0.5 px-1 text-muted-foreground hover:text-foreground mt-1"
        >
          {expanded ? "Less" : "More"}
        </button>
      </div>

      <button
        type="button"
        onClick={onRemove}
        className="p-1 text-muted-foreground hover:text-red-500 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-ring transition-opacity rounded"
        aria-label="Remove task"
      >
        <Trash2 className="h-3 w-3" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function PlanReview({
  question,
  researchPlan,
  classification,
  statuteContext,
  legalElements,
  includeAdversarial: initialAdversarial = false,
  onSubmit,
  disabled,
  error,
  onClearError,
}: PlanReviewProps) {
  const [tasks, setTasks] = useState<ResearchTaskPreview[]>(researchPlan);
  const [adversarial, setAdversarial] = useState(initialAdversarial);
  const [submitting, setSubmitting] = useState(false);
  const [customFeedback, setCustomFeedback] = useState("");

  // Sync tasks when researchPlan prop updates (e.g. from SSE stream)
  useEffect(() => {
    if (researchPlan.length > 0) {
      setTasks(researchPlan);
    }
  }, [researchPlan]);

  // Reset submitting state when an error restores the checkpoint
  useEffect(() => {
    if (error && submitting) {
      setSubmitting(false);
    }
  }, [error, submitting]);

  function moveTask(from: number, to: number) {
    const next = [...tasks];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    setTasks(next);
  }

  function removeTask(index: number) {
    setTasks(tasks.filter((_, i) => i !== index));
  }

  function handleApprove() {
    if (submitting || disabled) return;
    setSubmitting(true);
    const removedCount = researchPlan.length - tasks.length;
    const payload: Record<string, unknown> = {
      action: "approve",
      include_adversarial: adversarial,
      tasks: tasks.map((t) => t.nl_query),
      removed_count: removedCount,
    };
    if (customFeedback.trim()) {
      payload.custom_feedback = customFeedback.trim();
    }
    const response = JSON.stringify(payload);
    onSubmit(response);
  }

  function handleRequestChanges(suggestion: string) {
    if (submitting || disabled) return;
    setSubmitting(true);
    // onSubmit triggers async resume — error resets submitting via useEffect on error prop
    onSubmit(suggestion);
    // Safety: reset submitting after timeout in case error prop never arrives
    setTimeout(() => setSubmitting(false), 30_000);
  }

  return (
    <Card className="border-[var(--gold)]/30">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Scale className="h-4 w-4 text-[var(--gold)]" />
          Research Plan Review
        </CardTitle>
        <p className="text-xs text-muted-foreground">{question}</p>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Classification summary */}
        {classification && (
          <div className="flex flex-wrap gap-2">
            {!!classification.topic && (
              <Badge variant="outline" className="text-xs capitalize">
                {String(classification.topic).replace(/_/g, " ")}
              </Badge>
            )}
            {!!classification.complexity && (
              <Badge
                variant="outline"
                className={`text-xs ${
                  classification.complexity === "complex"
                    ? "border-red-300 text-red-700 dark:border-red-700 dark:text-red-400"
                    : classification.complexity === "moderate"
                      ? "border-amber-300 text-amber-700 dark:border-amber-700 dark:text-amber-400"
                      : "border-green-300 text-green-700 dark:border-green-700 dark:text-green-400"
                }`}
              >
                {String(classification.complexity)}
              </Badge>
            )}
            {!!classification.procedural_context && (
              <Badge variant="outline" className="text-xs capitalize">
                {String(classification.procedural_context).replace(/_/g, " ")}
              </Badge>
            )}
          </div>
        )}

        {/* Statute context */}
        {statuteContext && statuteContext.length > 0 && (
          <div className="rounded-md bg-muted/50 p-3">
            <h4 className="text-xs font-medium flex items-center gap-1.5 mb-2">
              <BookOpen className="h-3.5 w-3.5" />
              Statute Context ({statuteContext.length} provisions found)
            </h4>
            <div className="space-y-1">
              {statuteContext.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <Badge
                    variant="secondary"
                    className="text-[10px] px-1.5 py-0 font-mono"
                  >
                    {s.act} {s.section}
                  </Badge>
                  {s.title && (
                    <span className="text-muted-foreground truncate">
                      {s.title}
                    </span>
                  )}
                  {s.repealed && (
                    <Badge
                      variant="destructive"
                      className="text-[10px] px-1.5 py-0"
                    >
                      Repealed
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Legal elements */}
        {legalElements && legalElements.length > 0 && (
          <div className="rounded-md bg-muted/50 p-3">
            <h4 className="text-xs font-medium flex items-center gap-1.5 mb-2">
              <Search className="h-3.5 w-3.5" />
              Legal Elements ({legalElements.length})
            </h4>
            <div className="space-y-1.5">
              {legalElements.map((e, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <Badge
                    variant={e.contested ? "destructive" : "secondary"}
                    className="text-[10px] px-1.5 py-0 mt-0.5 shrink-0"
                  >
                    {e.contested ? "Contested" : "Element"}
                  </Badge>
                  <span>{e.description}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Research tasks */}
        <div>
          <h4 className="text-xs font-medium mb-2">
            Research Tasks ({tasks.length})
          </h4>
          <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
            {tasks.map((task, i) => (
              <TaskCard
                key={`${task.task_type}-${i}`}
                task={task}
                index={i}
                onRemove={() => removeTask(i)}
                onMoveUp={() => i > 0 && moveTask(i, i - 1)}
                onMoveDown={() => i < tasks.length - 1 && moveTask(i, i + 1)}
                isFirst={i === 0}
                isLast={i === tasks.length - 1}
              />
            ))}
          </div>
        </div>

        {/* Adversarial toggle */}
        <div className="flex items-center justify-between rounded-md border border-border p-3">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-xs font-medium">Adversarial Analysis</p>
              <p className="text-[10px] text-muted-foreground">
                Search for counter-arguments and opposing precedents
              </p>
            </div>
          </div>
          <Button
            size="sm"
            variant={adversarial ? "default" : "outline"}
            onClick={() => setAdversarial(!adversarial)}
            disabled={disabled || submitting}
            aria-label="Toggle adversarial analysis"
            className="text-xs"
          >
            {adversarial ? "On" : "Off"}
          </Button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="rounded-md border border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/20 p-3 flex items-center justify-between">
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
            {onClearError && (
              <button
                type="button"
                onClick={onClearError}
                className="text-red-500 hover:text-red-700 text-xs font-medium ml-2 shrink-0"
              >
                Dismiss
              </button>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleRequestChanges("Focus more on constitutional aspects")}
              disabled={disabled || submitting}
            >
              Focus: Constitutional
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleRequestChanges("Add cases from the last 5 years")}
              disabled={disabled || submitting}
            >
              Recent Cases
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleRequestChanges("Add more statute-focused tasks")}
              disabled={disabled || submitting}
            >
              More Statutes
            </Button>
          </div>
          <Textarea
            placeholder="Additional instructions or modifications..."
            value={customFeedback}
            onChange={(e) => setCustomFeedback(e.target.value)}
            className="text-sm min-h-[60px]"
            disabled={disabled || submitting}
          />
          <Button
            size="sm"
            onClick={handleApprove}
            disabled={disabled || submitting}
          >
            {submitting ? "Submitting..." : "Approve Plan"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
