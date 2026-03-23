"use client";

/**
 * @deprecated SUPERSEDED by inline pill/tab UI in search/page.tsx (SECTION_TABS).
 *
 * This dropdown-based section filter was the original approach but was replaced
 * by always-visible pill buttons in the search page. The pill UI is superior:
 * - All options visible at once (no click to expand)
 * - Immediate visual feedback via highlighted active state
 * - Toggle behavior (click active pill to deselect)
 * - Proper ARIA roles (role="tab", aria-selected)
 *
 * The search page's inline SECTION_TABS uses the same JudgmentSection type
 * and identical section values (FACTS, ISSUES, ARGUMENTS, HOLDINGS, REASONING, ORDER).
 *
 * Kept for potential reuse in contexts where a compact dropdown is preferred
 * (e.g., mobile views, filter sidebars, case detail page section navigation).
 *
 * DEPRECATED_BY_REFACTOR: search/page.tsx inline pill tabs (lines 198-229)
 */

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

/** @deprecated Use inline pill tabs in search/page.tsx instead. */
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
