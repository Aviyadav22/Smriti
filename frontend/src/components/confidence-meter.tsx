"use client";

import { cn } from "@/lib/utils";

interface ConfidenceMeterProps {
  score: number;
  className?: string;
}

export function ConfidenceMeter({ score, className }: ConfidenceMeterProps) {
  const percentage = Math.round(score * 100);
  const color =
    percentage >= 60 ? "bg-green-500" :
    percentage >= 40 ? "bg-yellow-500" :
    percentage >= 20 ? "bg-orange-500" :
    "bg-red-500";

  const label =
    percentage >= 60 ? "Strong match" :
    percentage >= 40 ? "Good match" :
    percentage >= 20 ? "Partial match" :
    "Weak match";

  return (
    <div
      className={cn("flex items-center gap-2", className)}
      title={`${label} — Based on semantic similarity and keyword matching. Higher scores indicate stronger matches to your query.`}
    >
      <div className="h-2 w-24 rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}
