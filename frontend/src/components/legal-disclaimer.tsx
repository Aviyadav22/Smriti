import { Scale } from "lucide-react";
import { cn } from "@/lib/utils";

interface LegalDisclaimerProps {
  className?: string;
}

export function LegalDisclaimer({ className }: LegalDisclaimerProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-3 py-2 text-xs text-amber-800 dark:text-amber-200",
        "sm:relative sm:bottom-auto fixed bottom-0 left-0 right-0 z-30 sm:z-auto sm:rounded-md rounded-none",
        className
      )}
    >
      <Scale className="h-4 w-4 shrink-0" />
      <span>
        AI-assisted legal research — not legal advice. Verify all citations and reasoning independently.
      </span>
    </div>
  );
}
