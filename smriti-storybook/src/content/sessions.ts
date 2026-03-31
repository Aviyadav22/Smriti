export interface SessionMeta {
  id: number;
  title: string;
  subtitle: string;
  day: string;
  duration: string;
  chapters: string[];
  quizFormat: "flashcard" | "drag-order" | "scenario" | "mixed";
}

export const SESSIONS: SessionMeta[] = [
  {
    id: 1,
    title: "The Origin Story",
    subtitle: "How Avi's frustration became a platform",
    day: "Day 1",
    duration: "~20 min",
    chapters: ["ch00", "ch01", "ch02"],
    quizFormat: "flashcard",
  },
  {
    id: 2,
    title: "The Intelligence",
    subtitle: "How Smriti understands, remembers, and finds",
    day: "Day 2",
    duration: "~20 min",
    chapters: ["ch03", "ch04", "ch05"],
    quizFormat: "drag-order",
  },
  {
    id: 3,
    title: "The Brain",
    subtitle: "Citations, graphs, and the AI research agent",
    day: "Day 3",
    duration: "~20 min",
    chapters: ["ch06", "ch07"],
    quizFormat: "scenario",
  },
  {
    id: 4,
    title: "The Full Picture",
    subtitle: "The frontend, scaling, and what's next",
    day: "Day 4",
    duration: "~15 min",
    chapters: ["ch08", "ch09", "ch10"],
    quizFormat: "mixed",
  },
];
