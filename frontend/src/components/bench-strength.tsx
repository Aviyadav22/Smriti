import { cn } from "@/lib/utils";

const BENCH_CONFIG: Record<string, { label: string; style: string }> = {
  single: { label: "Single Judge", style: "text-muted-foreground" },
  division: { label: "Division Bench", style: "text-foreground" },
  full: { label: "Full Bench", style: "text-foreground font-semibold" },
  constitutional: { label: "Constitution Bench", style: "text-blue-700 dark:text-blue-400 font-bold" },
};

interface BenchStrengthProps {
  benchType: string | null;
  judgeCount?: number;
  className?: string;
}

export function BenchStrength({ benchType, judgeCount, className }: BenchStrengthProps) {
  if (!benchType) return null;
  const config = BENCH_CONFIG[benchType] || { label: benchType, style: "text-muted-foreground" };
  const countStr = judgeCount ? ` (${judgeCount}J)` : "";

  // Constitutional bench gets a colored badge
  if (benchType === "constitutional") {
    return (
      <span className={cn("inline-flex items-center rounded-full bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 px-2 py-0.5 text-xs", config.style, className)}>
        {config.label}{countStr}
      </span>
    );
  }

  return (
    <span className={cn("text-xs", config.style, className)}>
      {config.label}{countStr}
    </span>
  );
}
