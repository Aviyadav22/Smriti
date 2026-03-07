"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { JudgmentSection } from "@/lib/types";

const SECTIONS: { value: JudgmentSection; label: string }[] = [
  { value: "FACTS", label: "Facts" },
  { value: "ISSUES", label: "Issues" },
  { value: "ARGUMENTS", label: "Arguments" },
  { value: "HOLDINGS", label: "Holdings" },
  { value: "REASONING", label: "Reasoning" },
  { value: "ORDER", label: "Order" },
];

interface SectionFilterProps {
  value: JudgmentSection | null;
  onChange: (value: JudgmentSection | null) => void;
}

export function SectionFilter({ value, onChange }: SectionFilterProps) {
  return (
    <Select
      value={value || "all"}
      onValueChange={(v) => onChange(v === "all" ? null : (v as JudgmentSection))}
    >
      <SelectTrigger className="w-[180px]">
        <SelectValue placeholder="All sections" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All sections</SelectItem>
        {SECTIONS.map((s) => (
          <SelectItem key={s.value} value={s.value}>
            {s.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
