import { cn } from "@/lib/utils";

const BENCH_LABELS: Record<string, string> = {
  single: "Single Judge",
  division: "Division Bench",
  full: "Full Bench",
  constitutional: "Constitution Bench",
};

interface BenchStrengthProps {
  benchType: string | null;
  judgeCount?: number;
  className?: string;
}

export function BenchStrength({ benchType, judgeCount, className }: BenchStrengthProps) {
  if (!benchType) return null;
  const label = BENCH_LABELS[benchType] || benchType;
  const countStr = judgeCount ? ` (${judgeCount}J)` : "";
  return (
    <span className={cn("text-xs text-muted-foreground", className)}>
      {label}{countStr}
    </span>
  );
}
