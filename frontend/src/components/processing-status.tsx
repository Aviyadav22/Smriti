"use client";

import { Badge } from "@/components/ui/badge";

interface ProcessingStatusProps {
  status: string;
  step: string | null;
  error?: string | null;
}

const PROCESSING_STEPS = [
  { key: "extracting", label: "Extracting text" },
  { key: "analyzing", label: "Analyzing document" },
  { key: "searching", label: "Searching precedents" },
  { key: "generating", label: "Generating memo" },
  { key: "completed", label: "Completed" },
] as const;

function getStepIndex(status: string): number {
  return PROCESSING_STEPS.findIndex((s) => s.key === status);
}

export function ProcessingStatus({ status, step, error }: ProcessingStatusProps) {
  if (status === "failed") {
    return (
      <div className="space-y-3">
        <Badge variant="destructive">Failed</Badge>
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
      </div>
    );
  }

  const currentIndex = getStepIndex(status);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">Processing</span>
        {step && (
          <span className="text-sm text-muted-foreground">— {step}</span>
        )}
      </div>
      <div className="space-y-2">
        {PROCESSING_STEPS.map((s, i) => {
          let variant: "default" | "secondary" | "outline" = "outline";
          let label = s.label;

          if (i < currentIndex) {
            variant = "secondary";
            label = `${s.label}`;
          } else if (i === currentIndex) {
            variant = "default";
          }

          return (
            <div key={s.key} className="flex items-center gap-3">
              <div
                className={`h-2 w-2 rounded-full ${
                  i < currentIndex
                    ? "bg-green-500"
                    : i === currentIndex
                      ? "bg-blue-500 animate-pulse"
                      : "bg-muted-foreground/30"
                }`}
              />
              <Badge variant={variant} className="text-xs">
                {label}
              </Badge>
              {i < currentIndex && (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-green-500"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
