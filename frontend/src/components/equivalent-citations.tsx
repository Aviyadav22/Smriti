"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

interface EquivalentCitationsProps {
  citations: string[];
  primaryCitation?: string | null;
  className?: string;
}

export function EquivalentCitations({ citations, primaryCitation, className }: EquivalentCitationsProps) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const allCitations = primaryCitation
    ? [primaryCitation, ...citations.filter(c => c !== primaryCitation)]
    : citations;

  if (allCitations.length === 0) return null;

  function handleCopy(citation: string, idx: number) {
    navigator.clipboard.writeText(citation).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    });
  }

  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {allCitations.map((citation, i) => (
        <span key={i}>
          <button
            className={cn(
              "text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer",
              copiedIdx === i && "text-green-600"
            )}
            onClick={() => handleCopy(citation, i)}
            title="Click to copy citation"
          >
            {copiedIdx === i ? "Copied!" : citation}
          </button>
          {i < allCitations.length - 1 && (
            <span className="text-xs text-muted-foreground mx-1">|</span>
          )}
        </span>
      ))}
    </div>
  );
}
