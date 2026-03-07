"use client";

import { cn } from "@/lib/utils";
import type { PrecedentStrengthLevel } from "@/lib/types";

const BADGE_CONFIG: Record<PrecedentStrengthLevel, { label: string; className: string; tooltip: string }> = {
  BINDING: {
    label: "Binding",
    className: "bg-green-100 text-green-800 border-green-300",
    tooltip: "This precedent is legally binding on the target court (higher court or same court with equal/larger bench)",
  },
  PERSUASIVE: {
    label: "Persuasive",
    className: "bg-yellow-100 text-yellow-800 border-yellow-300",
    tooltip: "This precedent is persuasive but not binding (different High Court, smaller bench, or lower court)",
  },
  DISTINGUISHABLE: {
    label: "Distinguishable",
    className: "bg-orange-100 text-orange-800 border-orange-300",
    tooltip: "This precedent may be distinguished on its facts or legal context",
  },
  OVERRULED: {
    label: "Overruled",
    className: "bg-red-100 text-red-800 border-red-300 line-through",
    tooltip: "This precedent has been overruled and is no longer good law",
  },
};

interface PrecedentBadgeProps {
  strength: PrecedentStrengthLevel;
  className?: string;
}

export function PrecedentBadge({ strength, className }: PrecedentBadgeProps) {
  const config = BADGE_CONFIG[strength];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium cursor-help",
        config.className,
        className
      )}
      title={config.tooltip}
    >
      {config.label}
    </span>
  );
}
