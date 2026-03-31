export interface ChapterConfig {
  id: string;
  title: string;
  subtitle: string;
  sections: Section[];
}

export type Section =
  | { type: "typewriter"; text: string; className?: string; speed?: number }
  | { type: "prose"; content: string }
  | { type: "comparison"; left: ComparisonSide; right: ComparisonSide }
  | { type: "timeline"; milestones: Milestone[] }
  | { type: "cards"; cards: Card[]; columns?: 2 | 3 | 4 }
  | { type: "code"; code: string; language?: string }
  | {
      type: "counter";
      from: number;
      to: number;
      prefix?: string;
      suffix?: string;
      label: string;
    }
  | { type: "heading"; text: string; level?: 2 | 3 }
  | { type: "quote"; text: string; attribution?: string }
  | { type: "spacer"; height?: string }
  | { type: "stats"; items: StatItem[] }
  | { type: "highlight-box"; icon: string; title: string; description: string; accent?: string }
  | { type: "flow"; steps: string[] };

export interface StatItem {
  value: string;
  label: string;
  icon?: string;
}

export interface ComparisonSide {
  label: string;
  items: string[];
  rejected?: boolean;
  accepted?: boolean;
}

export interface Milestone {
  date: string;
  label: string;
  detail?: string;
  highlight?: boolean;
}

export interface Card {
  title: string;
  description: string;
  icon?: string;
}
