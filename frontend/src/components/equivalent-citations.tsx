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
    // Use Clipboard API with fallback for older browsers / insecure contexts
    const onSuccess = () => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    };

    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(citation).then(onSuccess).catch(() => {
        // Fallback: use legacy execCommand for browsers without Clipboard API support
        fallbackCopyText(citation, onSuccess);
      });
    } else {
      fallbackCopyText(citation, onSuccess);
    }
  }

  function fallbackCopyText(text: string, onSuccess: () => void) {
    try {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      onSuccess();
    } catch {
      // Copy failed silently — no user-facing error for a copy action
    }
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
