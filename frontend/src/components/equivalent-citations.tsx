"use client";

import { cn } from "@/lib/utils";

interface EquivalentCitationsProps {
  citations: string[];
  primaryCitation?: string | null;
  className?: string;
}

export function EquivalentCitations({ citations, primaryCitation, className }: EquivalentCitationsProps) {
  const allCitations = primaryCitation
    ? [primaryCitation, ...citations.filter(c => c !== primaryCitation)]
    : citations;

  if (allCitations.length === 0) return null;

  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {allCitations.map((citation, i) => (
        <span key={i}>
          <span className="text-xs text-muted-foreground">{citation}</span>
          {i < allCitations.length - 1 && (
            <span className="text-xs text-muted-foreground mx-1">|</span>
          )}
        </span>
      ))}
    </div>
  );
}
