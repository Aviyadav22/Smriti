"use client";

import { cn } from "@/lib/utils";

interface ConfidenceMeterProps {
  score: number;
  className?: string;
}

export function ConfidenceMeter({ score, className }: ConfidenceMeterProps) {
  const percentage = Math.round(score * 100);
  const color =
    percentage >= 80 ? "bg-green-500" :
    percentage >= 60 ? "bg-yellow-500" :
    percentage >= 40 ? "bg-orange-500" :
    "bg-red-500";

  const label =
    percentage >= 80 ? "High confidence" :
    percentage >= 60 ? "Moderate confidence" :
    percentage >= 40 ? "Low confidence" :
    "Very low confidence";

  return (
    <div
      className={cn("flex items-center gap-2", className)}
      title={`${label} — based on relevance scores, source authority, coverage, and consistency`}
    >
      <div className="h-2 w-24 rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground">{percentage}%</span>
    </div>
  );
}
