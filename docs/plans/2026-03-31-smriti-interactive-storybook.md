# Smriti Interactive Storybook — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a cinematic, 3D-sprinkled interactive onboarding experience that tells the Smriti story across 4 sessions with scroll-driven animations, quiz gates, ambient audio, and progress tracking.

**Architecture:** Standalone React 19 + Vite app deployed to `onboarding.neetiq.in` (Netlify). GSAP ScrollTrigger drives chapter transitions, React Three Fiber renders 4 hero 3D scenes (one per session opener), Howler.js provides ambient audio. Quiz engine gates session progression. Zustand + localStorage persists progress. Content sourced from the existing `docs/storybook/` markdown chapters.

**Tech Stack:** React 19, Vite 6, TypeScript, TailwindCSS 4, GSAP + ScrollTrigger, Motion (Framer Motion), React Three Fiber + drei + postprocessing, Howler.js, @dnd-kit, Zustand, Lottie, Rough.js

---

## Session → Chapter Mapping

| Session | Title | Day | Chapters | 3D Hero | Quiz Format |
|---------|-------|-----|----------|---------|-------------|
| 1 | "The Origin Story" | Day 1 (~20 min) | Ch 0: The Spark, Ch 1: Laying the Foundation, Ch 2: Teaching Smriti to Read | Rotating 3D Supreme Court judgment PDF that cracks open, pages scatter into particles, then reassemble as structured data | Flashcards (3 true/false) |
| 2 | "The Intelligence" | Day 2 (~20 min) | Ch 3: Understanding What She Reads, Ch 4: The Memory Palace, Ch 5: The Art of Finding | A 3D embedding space — glowing dots (vectors) floating in a constellation. Camera flies through the vector cloud. Similar cases cluster together, visibly pulled by invisible forces | Drag-and-drop ("Order the 5 search pipeline steps") |
| 3 | "The Brain" | Day 3 (~20 min) | Ch 6: The Web of Citations, Ch 7: The Research Agent | 3D citation graph — nodes (cases) connected by glowing gold edges. Camera orbits. Hover a node and edges pulse. Overruled edges glow red. The web slowly rotates | Scenario-based ("A case cites IPC 302 from 2022. What temporal warning should Smriti show?") |
| 4 | "The Full Picture" | Day 4 (~15 min) | Ch 8: The Face of Smriti, Ch 9: Scaling the Mountain, Ch 10: The Road Ahead | Complete architecture as explorable 3D constellation — PostgreSQL, Pinecone, Neo4j, Gemini, Cloud Run nodes connected by pulsing data flows. Orbit controls enabled | Mixed final challenge (5 questions: 1 flashcard, 1 drag-drop, 2 scenario, 1 interactive "which vector type is this?") |

---

## Chapter Visual Moments (Key Animations Per Chapter)

### Session 1: "The Origin Story"

**Ch 0 — The Spark:**
- Avi's classroom scene: text typewriters "One fine day..." in Georgia serif
- Split animation: keyword search (gray, rigid boxes) vs semantic search (gold, flowing particles)
- Timeline draws itself: April 2024 → Oct 2024 → March 2026 with milestone markers
- The open-source wall: blocks stack up, then crack and crumble (representing limitations)

**Ch 1 — Laying the Foundation:**
- ADR cards flip in from the side: FastAPI, Next.js, PostgreSQL, Pinecone, Neo4j, Gemini
- Architecture diagram builds layer by layer: Interface → Provider → Route
- The "three databases" visualization: three geometric shapes (cube=PG, sphere=Pinecone, web=Neo4j) orbit each other

**Ch 2 — Teaching Smriti to Read:**
- PDF page extraction animation: pages peel off a document
- OCR fallback: page turns red (unreadable), then golden scanner sweeps across, text emerges
- Quality tiers: HIGH/MEDIUM/LOW bars fill with particles
- Text cleaning pipeline: garbage characters fly off, clean text remains

### Session 2: "The Intelligence"

**Ch 3 — Understanding What She Reads:**
- Two-brain diagram: LLM brain (creative, gold) + Regex brain (precise, silver) merge
- 16 metadata fields cascade in as cards
- Citation regex patterns light up as they match sample text
- Old→New code animation: "IPC 302" morphs into "BNS 103" with connecting arrow

**Ch 4 — The Memory Palace:**
- Embedding visualization: sentence turns into floating vector of 1,536 glowing dots
- Chunking animation: long text scroll gets sliced at section boundaries (FACTS, RATIO, ORDER)
- Seven vector types appear as colored orbs: chunk (blue), proposition (gold), ratio (amber), etc.
- Contextual prefix: lonely chunk gets wrapped with a golden context halo

**Ch 5 — The Art of Finding:**
- Three parallel search streams animate simultaneously (FTS, Vector, Citation)
- RRF fusion: three ranked lists merge into one (particles from each stream flow into a funnel)
- Reranker: Cohere badge stamps relevance scores onto each result
- Final results cascade in with scores

### Session 3: "The Brain"

**Ch 6 — The Web of Citations:**
- Citation network grows: nodes appear one by one, edges draw between them
- Community detection: clusters glow different colors, slowly orbit
- Precedent strength badges: BINDING (green), PERSUASIVE (blue), OVERRULED (red) label edges
- Overruling cascade: one red edge propagates, other nodes dim

**Ch 7 — The Research Agent:**
- V1→V2→V3 evolution timeline
- 5-stage pipeline: scroll scrubs a glowing orb through Understand → Decompose → Investigate → Challenge → Synthesize
- Worker fan-out: from the plan node, 7 worker beams fire outward in parallel
- Confidence meter fills segment by segment with breakdown labels
- SSE streaming: memo text typewriters in real-time

### Session 4: "The Full Picture"

**Ch 8 — The Face of Smriti:**
- UI mockup assembles itself: header slides in, search bar expands, results cascade
- Research workspace split-screen: left panel (progress) + right panel (memo)
- Footnote hover: card pops up with case metadata

**Ch 9 — Scaling the Mountain:**
- Counter animation: cases tick from 100 → 35,000
- AI Studio batch: PENDING spinner → red X (FAILED)
- Vertex AI batch: green checkmarks cascade through 4 phases
- Cost comparison: bars animate ($68 → $34, 50% savings)

**Ch 10 — The Road Ahead:**
- Timeline extends forward: Hindi, More Courts, Multi-Agent, Mobile — markers fade into golden mist
- The NeetiQ brand reveal: domain assembles, social icons float in
- Final message typewriters: "Welcome to NeetiQ. Your chapter starts now."
- Completion confetti in NeetiQ gold + certificate with name/date

---

## Project Structure

```
smriti-storybook/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.js
├── public/
│   ├── audio/
│   │   ├── ambient-loop.mp3          (~2 min loop, dark cinematic)
│   │   ├── transition-whoosh.mp3
│   │   ├── quiz-correct.mp3
│   │   ├── quiz-wrong.mp3
│   │   ├── chapter-unlock.mp3
│   │   └── completion-fanfare.mp3
│   ├── fonts/
│   │   ├── Inter-Variable.woff2
│   │   ├── Georgia (system)
│   │   └── JetBrainsMono-Variable.woff2
│   └── lottie/
│       ├── checkmark.json
│       ├── confetti.json
│       └── unlock.json
├── src/
│   ├── main.tsx                       # Entry point
│   ├── App.tsx                        # Router + layout shell
│   ├── index.css                      # Tailwind base + NeetiQ tokens
│   │
│   ├── stores/
│   │   └── progress.ts               # Zustand: session/chapter progress, quiz scores
│   │
│   ├── hooks/
│   │   ├── useScrollProgress.ts       # GSAP ScrollTrigger integration
│   │   ├── useAudio.ts                # Howler.js ambient + SFX
│   │   └── useQuizGate.ts             # Quiz state management
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── TopBar.tsx             # Logo, session label, mute toggle, user
│   │   │   ├── ProgressBar.tsx        # Bottom fixed progress indicator
│   │   │   └── SessionLock.tsx        # Locked session screen
│   │   │
│   │   ├── chapters/
│   │   │   ├── ChapterShell.tsx       # GSAP ScrollTrigger pinned wrapper
│   │   │   ├── ScrollSection.tsx      # Individual scroll-triggered section
│   │   │   ├── TypewriterText.tsx     # Text that types itself on scroll
│   │   │   ├── AnimatedDiagram.tsx    # SVG path draw-on-scroll
│   │   │   ├── CodeReveal.tsx         # Code block that types/highlights
│   │   │   ├── CounterAnimation.tsx   # Number counter (e.g., 100 → 35,000)
│   │   │   ├── ComparisonSlide.tsx    # Before/after or A-vs-B
│   │   │   ├── CardCascade.tsx        # Cards that fly in one by one
│   │   │   ├── TimelineDraw.tsx       # Timeline that draws itself
│   │   │   └── ParticleTransition.tsx # Chapter-to-chapter transition effect
│   │   │
│   │   ├── three/
│   │   │   ├── JudgmentExplode.tsx    # Session 1: PDF pages scatter → reassemble
│   │   │   ├── VectorCloud.tsx        # Session 2: Embedding constellation
│   │   │   ├── CitationGraph3D.tsx    # Session 3: Interactive citation network
│   │   │   └── ArchitectureMap.tsx    # Session 4: Full system constellation
│   │   │
│   │   ├── quiz/
│   │   │   ├── QuizGate.tsx           # Quiz container with session-lock logic
│   │   │   ├── Flashcard.tsx          # Flip card true/false
│   │   │   ├── DragOrder.tsx          # Drag items into correct order
│   │   │   ├── Scenario.tsx           # Multiple choice with explanation
│   │   │   └── InteractiveSpot.tsx    # "Click the right answer" on a diagram
│   │   │
│   │   └── fx/
│   │       ├── GoldConfetti.tsx       # Completion celebration
│   │       ├── NapkinSketch.tsx       # Rough.js hand-drawn moment (Ch 0)
│   │       └── Certificate.tsx        # Completion certificate with name/date
│   │
│   ├── content/
│   │   ├── sessions.ts               # Session metadata (titles, chapter IDs)
│   │   ├── chapters/
│   │   │   ├── ch00-the-spark.ts      # Scroll sections + animation configs
│   │   │   ├── ch01-foundation.ts
│   │   │   ├── ch02-reading.ts
│   │   │   ├── ch03-understanding.ts
│   │   │   ├── ch04-memory.ts
│   │   │   ├── ch05-finding.ts
│   │   │   ├── ch06-citations.ts
│   │   │   ├── ch07-agent.ts
│   │   │   ├── ch08-frontend.ts
│   │   │   ├── ch09-scaling.ts
│   │   │   └── ch10-road-ahead.ts
│   │   └── quizzes/
│   │       ├── session1-quiz.ts       # Flashcard questions
│   │       ├── session2-quiz.ts       # Drag-and-drop questions
│   │       ├── session3-quiz.ts       # Scenario questions
│   │       └── session4-quiz.ts       # Mixed format final challenge
│   │
│   └── pages/
│       ├── Landing.tsx                # Welcome screen with 4 session cards
│       ├── Session.tsx                # Session page (renders chapters + quiz gate)
│       └── Completion.tsx             # Final celebration + certificate
│
└── netlify.toml                       # Deploy config
```

---

## Design Tokens (Ported from NeetiQ)

```typescript
// tailwind.config.ts — NeetiQ design tokens
const config = {
  theme: {
    extend: {
      colors: {
        nq: {
          bg: "#0A0A0A",
          surface: "#111111",
          border: "#1E1E1E",
          text: "#E8E8E8",
          muted: "#6B6B6B",
          accent: "#C5A880",       // NeetiQ gold
          "accent-dim": "#C5A88040",
          success: "#4ADE80",
          error: "#EF4444",
        },
      },
      fontFamily: {
        heading: ["Georgia", "serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
    },
  },
};
```

---

## Tasks

### Task 1: Project Scaffold + Vite + Tailwind + Router

**Files:**
- Create: `smriti-storybook/package.json`
- Create: `smriti-storybook/vite.config.ts`
- Create: `smriti-storybook/tsconfig.json`
- Create: `smriti-storybook/tailwind.config.ts`
- Create: `smriti-storybook/postcss.config.js`
- Create: `smriti-storybook/index.html`
- Create: `smriti-storybook/src/main.tsx`
- Create: `smriti-storybook/src/App.tsx`
- Create: `smriti-storybook/src/index.css`
- Create: `smriti-storybook/netlify.toml`

**Step 1: Initialize project**

```bash
cd d:/Startup/Smriti
mkdir smriti-storybook && cd smriti-storybook
npm create vite@latest . -- --template react-ts
```

**Step 2: Install core dependencies**

```bash
npm install react-router-dom@7 zustand gsap @gsap/react framer-motion \
  @react-three/fiber @react-three/drei @react-three/postprocessing three \
  howler @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities \
  lottie-react roughjs
npm install -D tailwindcss @tailwindcss/vite @types/three @types/howler
```

**Step 3: Create config files**

`vite.config.ts`:
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": "/src" },
  },
});
```

`tailwind.config.ts`:
```typescript
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        nq: {
          bg: "#0A0A0A",
          surface: "#111111",
          border: "#1E1E1E",
          text: "#E8E8E8",
          muted: "#6B6B6B",
          accent: "#C5A880",
          "accent-dim": "rgba(197,168,128,0.25)",
          success: "#4ADE80",
          error: "#EF4444",
        },
      },
      fontFamily: {
        heading: ["Georgia", "serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      fontSize: {
        massive: ["clamp(3rem, 6vw, 4.5rem)", { lineHeight: "0.95", letterSpacing: "-0.025em" }],
        display: ["clamp(2rem, 4vw, 3rem)", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        title: ["1.75rem", { lineHeight: "1.2", letterSpacing: "-0.015em" }],
        subtitle: ["1.25rem", { lineHeight: "1.4" }],
      },
    },
  },
  plugins: [],
} satisfies Config;
```

`index.css`:
```css
@import "tailwindcss";

@font-face {
  font-family: "Inter";
  src: url("/fonts/Inter-Variable.woff2") format("woff2");
  font-weight: 100 900;
  font-display: swap;
}

@font-face {
  font-family: "JetBrains Mono";
  src: url("/fonts/JetBrainsMono-Variable.woff2") format("woff2");
  font-weight: 100 800;
  font-display: swap;
}

html {
  scroll-behavior: smooth;
}

body {
  background: #0A0A0A;
  color: #E8E8E8;
  font-family: "Inter", system-ui, sans-serif;
}

/* Subtle grain overlay */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: 9999;
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0A0A0A; }
::-webkit-scrollbar-thumb { background: #1E1E1E; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #C5A880; }
```

`src/App.tsx`:
```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Landing } from "@/pages/Landing";
import { Session } from "@/pages/Session";
import { Completion } from "@/pages/Completion";
import { TopBar } from "@/components/layout/TopBar";
import { ProgressBar } from "@/components/layout/ProgressBar";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-nq-bg text-nq-text">
        <TopBar />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/session/:id" element={<Session />} />
          <Route path="/complete" element={<Completion />} />
        </Routes>
        <ProgressBar />
      </div>
    </BrowserRouter>
  );
}
```

`netlify.toml`:
```toml
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

**Step 4: Run dev server to verify**

```bash
npm run dev
```

Expected: Vite dev server at localhost:5173, black background, no errors.

**Step 5: Commit**

```bash
git add smriti-storybook/
git commit -m "feat(storybook): scaffold React + Vite + Tailwind + Router"
```

---

### Task 2: Zustand Progress Store + Audio Hook

**Files:**
- Create: `src/stores/progress.ts`
- Create: `src/hooks/useAudio.ts`
- Create: `src/content/sessions.ts`

**Step 1: Define session metadata**

`src/content/sessions.ts`:
```typescript
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
```

**Step 2: Create Zustand store**

`src/stores/progress.ts`:
```typescript
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ChapterProgress {
  started: boolean;
  scrollPercent: number;
  completed: boolean;
}

interface QuizResult {
  sessionId: number;
  score: number;
  total: number;
  passed: boolean;
  completedAt: string;
}

interface ProgressState {
  userName: string;
  chapters: Record<string, ChapterProgress>;
  quizResults: Record<number, QuizResult>;
  currentSession: number;
  currentChapter: string;
  audioMuted: boolean;

  // Actions
  setUserName: (name: string) => void;
  updateChapterScroll: (chapterId: string, percent: number) => void;
  completeChapter: (chapterId: string) => void;
  submitQuiz: (result: QuizResult) => void;
  isSessionUnlocked: (sessionId: number) => boolean;
  getOverallProgress: () => number;
  setCurrentPosition: (session: number, chapter: string) => void;
  toggleMute: () => void;
  reset: () => void;
}

export const useProgressStore = create<ProgressState>()(
  persist(
    (set, get) => ({
      userName: "",
      chapters: {},
      quizResults: {},
      currentSession: 1,
      currentChapter: "ch00",
      audioMuted: false,

      setUserName: (name) => set({ userName: name }),

      updateChapterScroll: (chapterId, percent) =>
        set((state) => ({
          chapters: {
            ...state.chapters,
            [chapterId]: {
              ...state.chapters[chapterId],
              started: true,
              scrollPercent: Math.max(
                percent,
                state.chapters[chapterId]?.scrollPercent ?? 0
              ),
              completed: state.chapters[chapterId]?.completed ?? false,
            },
          },
        })),

      completeChapter: (chapterId) =>
        set((state) => ({
          chapters: {
            ...state.chapters,
            [chapterId]: {
              started: true,
              scrollPercent: 100,
              completed: true,
            },
          },
        })),

      submitQuiz: (result) =>
        set((state) => ({
          quizResults: { ...state.quizResults, [result.sessionId]: result },
        })),

      isSessionUnlocked: (sessionId) => {
        if (sessionId === 1) return true;
        const prevQuiz = get().quizResults[sessionId - 1];
        return prevQuiz?.passed ?? false;
      },

      getOverallProgress: () => {
        const chapters = get().chapters;
        const total = 11; // ch00-ch10
        const completed = Object.values(chapters).filter((c) => c.completed).length;
        return Math.round((completed / total) * 100);
      },

      setCurrentPosition: (session, chapter) =>
        set({ currentSession: session, currentChapter: chapter }),

      toggleMute: () => set((state) => ({ audioMuted: !state.audioMuted })),

      reset: () =>
        set({
          chapters: {},
          quizResults: {},
          currentSession: 1,
          currentChapter: "ch00",
        }),
    }),
    { name: "smriti-storybook-progress" }
  )
);
```

**Step 3: Create audio hook**

`src/hooks/useAudio.ts`:
```typescript
import { useEffect, useRef, useCallback } from "react";
import { Howl, Howler } from "howler";
import { useProgressStore } from "@/stores/progress";

const SOUNDS = {
  ambient: "/audio/ambient-loop.mp3",
  whoosh: "/audio/transition-whoosh.mp3",
  correct: "/audio/quiz-correct.mp3",
  wrong: "/audio/quiz-wrong.mp3",
  unlock: "/audio/chapter-unlock.mp3",
  fanfare: "/audio/completion-fanfare.mp3",
} as const;

type SoundKey = keyof typeof SOUNDS;

export function useAudio() {
  const muted = useProgressStore((s) => s.audioMuted);
  const toggleMute = useProgressStore((s) => s.toggleMute);
  const soundsRef = useRef<Partial<Record<SoundKey, Howl>>>({});

  useEffect(() => {
    Howler.mute(muted);
  }, [muted]);

  const play = useCallback((key: SoundKey) => {
    if (!soundsRef.current[key]) {
      soundsRef.current[key] = new Howl({
        src: [SOUNDS[key]],
        loop: key === "ambient",
        volume: key === "ambient" ? 0.15 : 0.4,
        preload: true,
      });
    }
    const sound = soundsRef.current[key]!;
    if (key === "ambient") {
      if (!sound.playing()) sound.play();
    } else {
      sound.play();
    }
  }, []);

  const stopAmbient = useCallback(() => {
    soundsRef.current.ambient?.stop();
  }, []);

  return { play, stopAmbient, muted, toggleMute };
}
```

**Step 4: Commit**

```bash
git add src/stores/ src/hooks/ src/content/sessions.ts
git commit -m "feat(storybook): add Zustand progress store + audio hook"
```

---

### Task 3: Layout Shell (TopBar + ProgressBar + SessionLock)

**Files:**
- Create: `src/components/layout/TopBar.tsx`
- Create: `src/components/layout/ProgressBar.tsx`
- Create: `src/components/layout/SessionLock.tsx`

**Step 1: TopBar**

`src/components/layout/TopBar.tsx`:
```tsx
import { Link } from "react-router-dom";
import { useProgressStore } from "@/stores/progress";
import { useAudio } from "@/hooks/useAudio";
import { SESSIONS } from "@/content/sessions";

export function TopBar() {
  const currentSession = useProgressStore((s) => s.currentSession);
  const { muted, toggleMute } = useAudio();
  const session = SESSIONS[currentSession - 1];

  return (
    <header className="fixed top-0 inset-x-0 z-50 h-14 bg-nq-bg/80 backdrop-blur-md border-b border-nq-border/30">
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3">
          <span className="text-sm font-heading text-nq-accent tracking-wide">
            NeetiQ
          </span>
          <span className="text-[0.6rem] font-mono text-nq-muted uppercase tracking-widest">
            Onboarding
          </span>
        </Link>

        {/* Session indicator */}
        <div className="text-[0.6875rem] font-mono text-nq-muted/70">
          {session && `Session ${currentSession} of 4 — ${session.title}`}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4">
          <button
            onClick={toggleMute}
            className="text-nq-muted hover:text-nq-accent transition-colors text-sm"
            aria-label={muted ? "Unmute" : "Mute"}
          >
            {muted ? "🔇" : "🔊"}
          </button>
        </div>
      </div>
    </header>
  );
}
```

**Step 2: ProgressBar**

`src/components/layout/ProgressBar.tsx`:
```tsx
import { useProgressStore } from "@/stores/progress";
import { SESSIONS } from "@/content/sessions";
import { motion } from "framer-motion";

export function ProgressBar() {
  const currentSession = useProgressStore((s) => s.currentSession);
  const currentChapter = useProgressStore((s) => s.currentChapter);
  const chapters = useProgressStore((s) => s.chapters);
  const session = SESSIONS[currentSession - 1];
  if (!session) return null;

  const chapterIndex = session.chapters.indexOf(currentChapter);
  const chapterProgress = chapters[currentChapter]?.scrollPercent ?? 0;
  const sessionPercent =
    ((chapterIndex + chapterProgress / 100) / session.chapters.length) * 100;

  return (
    <footer className="fixed bottom-0 inset-x-0 z-50 h-10 bg-nq-bg/80 backdrop-blur-md border-t border-nq-border/30">
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center gap-4">
        {/* Segmented bar */}
        <div className="flex-1 flex gap-1 h-1.5">
          {session.chapters.map((ch, i) => (
            <div key={ch} className="flex-1 bg-nq-border/30 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-nq-accent rounded-full"
                initial={{ width: 0 }}
                animate={{
                  width:
                    i < chapterIndex
                      ? "100%"
                      : i === chapterIndex
                        ? `${chapterProgress}%`
                        : "0%",
                }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              />
            </div>
          ))}
        </div>

        {/* Chapter label */}
        <span className="text-[0.625rem] font-mono text-nq-muted whitespace-nowrap">
          Ch {chapterIndex + 1} of {session.chapters.length}
        </span>

        {/* Percentage */}
        <span className="text-[0.625rem] font-mono text-nq-accent w-8 text-right">
          {Math.round(sessionPercent)}%
        </span>
      </div>
    </footer>
  );
}
```

**Step 3: SessionLock**

`src/components/layout/SessionLock.tsx`:
```tsx
import { Link } from "react-router-dom";
import { SESSIONS } from "@/content/sessions";

interface Props {
  sessionId: number;
}

export function SessionLock({ sessionId }: Props) {
  const session = SESSIONS[sessionId - 1];

  return (
    <div className="min-h-screen flex items-center justify-center pt-14 pb-10">
      <div className="text-center max-w-md px-6">
        <div className="text-6xl mb-6 opacity-30">🔒</div>
        <p className="text-[0.625rem] font-mono text-nq-muted uppercase tracking-widest mb-2">
          {session.day}
        </p>
        <h1 className="text-display font-heading text-nq-text mb-4">
          Session {sessionId}: {session.title}
        </h1>
        <p className="text-nq-muted mb-8">
          Complete Session {sessionId - 1} quiz to unlock this session.
        </p>
        <Link
          to={`/session/${sessionId - 1}`}
          className="inline-block border border-nq-accent/40 text-nq-accent px-6 py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-nq-accent/10 transition-colors"
        >
          ← Back to Session {sessionId - 1}
        </Link>
      </div>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add src/components/layout/
git commit -m "feat(storybook): add TopBar, ProgressBar, SessionLock layout"
```

---

### Task 4: Landing Page (Session Selector)

**Files:**
- Create: `src/pages/Landing.tsx`

**Step 1: Build landing page**

`src/pages/Landing.tsx`:
```tsx
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useProgressStore } from "@/stores/progress";
import { SESSIONS } from "@/content/sessions";
import { useState } from "react";

export function Landing() {
  const { userName, setUserName, isSessionUnlocked, quizResults } =
    useProgressStore();
  const [nameInput, setNameInput] = useState(userName);
  const [nameSet, setNameSet] = useState(!!userName);

  if (!nameSet) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center max-w-lg px-6"
        >
          <p className="text-[0.625rem] font-mono text-nq-accent uppercase tracking-widest mb-4">
            NeetiQ Onboarding
          </p>
          <h1 className="text-massive font-heading text-nq-text mb-6">
            The Smriti Story
          </h1>
          <p className="text-nq-muted mb-10">
            How a law student's frustration became an AI-powered legal research
            platform. Enter your name to begin.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (nameInput.trim()) {
                setUserName(nameInput.trim());
                setNameSet(true);
              }
            }}
            className="flex gap-3 max-w-sm mx-auto"
          >
            <input
              type="text"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              placeholder="Your name"
              className="flex-1 bg-nq-surface border border-nq-border px-4 py-2.5 text-sm text-nq-text placeholder:text-nq-muted/50 focus:border-nq-accent/50 focus:outline-none transition-colors"
              autoFocus
            />
            <button
              type="submit"
              className="bg-nq-accent text-nq-bg px-6 py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-nq-accent/90 transition-colors"
            >
              Begin
            </button>
          </form>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-14 pb-10">
      <div className="max-w-4xl mx-auto px-6 py-20">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-16"
        >
          <p className="text-[0.625rem] font-mono text-nq-accent uppercase tracking-widest mb-4">
            Welcome, {userName}
          </p>
          <h1 className="text-massive font-heading text-nq-text mb-4">
            The Smriti Story
          </h1>
          <p className="text-subtitle text-nq-muted max-w-2xl mx-auto">
            Four sessions across your first week. Each one builds on the last.
            Complete the quiz at the end of each session to unlock the next.
          </p>
        </motion.div>

        {/* Session cards */}
        <div className="grid gap-4">
          {SESSIONS.map((session, i) => {
            const unlocked = isSessionUnlocked(session.id);
            const quiz = quizResults[session.id];
            const completed = quiz?.passed;

            return (
              <motion.div
                key={session.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
              >
                {unlocked ? (
                  <Link
                    to={`/session/${session.id}`}
                    className="block group border border-nq-border/50 hover:border-nq-accent/30 bg-nq-surface/30 hover:bg-nq-surface/60 p-6 transition-all"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-3 mb-2">
                          <span className="text-[0.625rem] font-mono text-nq-accent uppercase tracking-widest">
                            {session.day}
                          </span>
                          {completed && (
                            <span className="text-[0.625rem] font-mono text-nq-success uppercase tracking-widest">
                              ✓ Complete
                            </span>
                          )}
                        </div>
                        <h2 className="text-title font-heading text-nq-text group-hover:text-nq-accent transition-colors">
                          Session {session.id}: {session.title}
                        </h2>
                        <p className="text-sm text-nq-muted mt-1">
                          {session.subtitle}
                        </p>
                      </div>
                      <span className="text-[0.6875rem] font-mono text-nq-muted/50">
                        {session.duration}
                      </span>
                    </div>
                  </Link>
                ) : (
                  <div className="border border-nq-border/20 bg-nq-surface/10 p-6 opacity-50">
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="text-[0.625rem] font-mono text-nq-muted/50 uppercase tracking-widest">
                          {session.day}
                        </span>
                        <h2 className="text-title font-heading text-nq-muted/50 mt-2">
                          🔒 Session {session.id}: {session.title}
                        </h2>
                      </div>
                    </div>
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add src/pages/Landing.tsx
git commit -m "feat(storybook): add landing page with session selector"
```

---

### Task 5: Scroll Engine (ChapterShell + ScrollSection + GSAP)

**Files:**
- Create: `src/hooks/useScrollProgress.ts`
- Create: `src/components/chapters/ChapterShell.tsx`
- Create: `src/components/chapters/ScrollSection.tsx`

**Step 1: GSAP scroll hook**

`src/hooks/useScrollProgress.ts`:
```typescript
import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useProgressStore } from "@/stores/progress";

gsap.registerPlugin(ScrollTrigger);

export function useScrollProgress(chapterId: string) {
  const containerRef = useRef<HTMLDivElement>(null);
  const updateScroll = useProgressStore((s) => s.updateChapterScroll);
  const completeChapter = useProgressStore((s) => s.completeChapter);

  useEffect(() => {
    if (!containerRef.current) return;

    const trigger = ScrollTrigger.create({
      trigger: containerRef.current,
      start: "top top",
      end: "bottom bottom",
      onUpdate: (self) => {
        const percent = Math.round(self.progress * 100);
        updateScroll(chapterId, percent);
        if (percent >= 95) completeChapter(chapterId);
      },
    });

    return () => trigger.kill();
  }, [chapterId, updateScroll, completeChapter]);

  return containerRef;
}
```

**Step 2: ChapterShell**

`src/components/chapters/ChapterShell.tsx`:
```tsx
import { type ReactNode } from "react";
import { useScrollProgress } from "@/hooks/useScrollProgress";
import { motion } from "framer-motion";

interface Props {
  chapterId: string;
  title: string;
  subtitle: string;
  children: ReactNode;
}

export function ChapterShell({ chapterId, title, subtitle, children }: Props) {
  const containerRef = useScrollProgress(chapterId);

  return (
    <div ref={containerRef} className="relative">
      {/* Chapter header */}
      <div className="min-h-[60vh] flex items-center justify-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="text-center max-w-3xl"
        >
          <p className="text-[0.625rem] font-mono text-nq-accent uppercase tracking-widest mb-4">
            {chapterId.replace("ch", "Chapter ")}
          </p>
          <h2 className="text-massive font-heading text-nq-text mb-4">
            {title}
          </h2>
          <p className="text-subtitle text-nq-muted">{subtitle}</p>
        </motion.div>
      </div>

      {/* Chapter content sections */}
      {children}

      {/* Chapter divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-nq-accent/20 to-transparent my-20" />
    </div>
  );
}
```

**Step 3: ScrollSection**

`src/components/chapters/ScrollSection.tsx`:
```tsx
import { useRef, type ReactNode } from "react";
import { motion, useInView } from "framer-motion";

interface Props {
  children: ReactNode;
  className?: string;
  delay?: number;
}

export function ScrollSection({ children, className = "", delay = 0 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <div ref={ref} className={`px-6 py-16 md:py-24 ${className}`}>
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.7, ease: "easeOut", delay }}
        className="max-w-4xl mx-auto"
      >
        {children}
      </motion.div>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add src/hooks/useScrollProgress.ts src/components/chapters/
git commit -m "feat(storybook): add scroll engine with GSAP + chapter shell"
```

---

### Task 6: Reusable Animation Components

**Files:**
- Create: `src/components/chapters/TypewriterText.tsx`
- Create: `src/components/chapters/AnimatedDiagram.tsx`
- Create: `src/components/chapters/CodeReveal.tsx`
- Create: `src/components/chapters/CounterAnimation.tsx`
- Create: `src/components/chapters/CardCascade.tsx`
- Create: `src/components/chapters/TimelineDraw.tsx`
- Create: `src/components/chapters/ComparisonSlide.tsx`
- Create: `src/components/chapters/ParticleTransition.tsx`

These are the building blocks. Each chapter will compose these to create its unique visual experience.

**Step 1: TypewriterText** — Text that types itself when scrolled into view

```tsx
// src/components/chapters/TypewriterText.tsx
import { useRef, useEffect, useState } from "react";
import { useInView } from "framer-motion";

interface Props {
  text: string;
  className?: string;
  speed?: number; // ms per character
  as?: "p" | "h1" | "h2" | "h3" | "span" | "blockquote";
}

export function TypewriterText({
  text,
  className = "",
  speed = 30,
  as: Tag = "p",
}: Props) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });
  const [displayed, setDisplayed] = useState("");

  useEffect(() => {
    if (!inView) return;
    let i = 0;
    const interval = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
      } else {
        clearInterval(interval);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [inView, text, speed]);

  return (
    <Tag ref={ref as any} className={className}>
      {displayed}
      {inView && displayed.length < text.length && (
        <span className="inline-block w-[2px] h-[1em] bg-nq-accent ml-0.5 animate-pulse" />
      )}
    </Tag>
  );
}
```

**Step 2: CounterAnimation** — Numbers that count up

```tsx
// src/components/chapters/CounterAnimation.tsx
import { useRef, useEffect, useState } from "react";
import { useInView } from "framer-motion";

interface Props {
  from: number;
  to: number;
  duration?: number; // ms
  prefix?: string;
  suffix?: string;
  className?: string;
}

export function CounterAnimation({
  from,
  to,
  duration = 2000,
  prefix = "",
  suffix = "",
  className = "",
}: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const [value, setValue] = useState(from);

  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const step = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setValue(Math.round(from + (to - from) * eased));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [inView, from, to, duration]);

  return (
    <span ref={ref} className={className}>
      {prefix}
      {value.toLocaleString()}
      {suffix}
    </span>
  );
}
```

**Step 3: CardCascade** — Cards that fly in one by one

```tsx
// src/components/chapters/CardCascade.tsx
import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface Card {
  title: string;
  description: string;
  icon?: string;
}

interface Props {
  cards: Card[];
  columns?: 2 | 3 | 4;
}

export function CardCascade({ cards, columns = 3 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });

  const gridCols = {
    2: "grid-cols-1 md:grid-cols-2",
    3: "grid-cols-1 md:grid-cols-3",
    4: "grid-cols-2 md:grid-cols-4",
  };

  return (
    <div ref={ref} className={`grid ${gridCols[columns]} gap-4`}>
      {cards.map((card, i) => (
        <motion.div
          key={card.title}
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={inView ? { opacity: 1, y: 0, scale: 1 } : {}}
          transition={{ delay: i * 0.12, duration: 0.5, ease: "easeOut" }}
          className="border border-nq-border/30 bg-nq-surface/30 p-5 hover:border-nq-accent/20 transition-colors"
        >
          {card.icon && <span className="text-2xl mb-3 block">{card.icon}</span>}
          <h3 className="text-sm font-heading text-nq-accent mb-2">
            {card.title}
          </h3>
          <p className="text-[0.8125rem] text-nq-muted leading-relaxed">
            {card.description}
          </p>
        </motion.div>
      ))}
    </div>
  );
}
```

**Step 4: TimelineDraw** — Timeline that draws itself

```tsx
// src/components/chapters/TimelineDraw.tsx
import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface Milestone {
  date: string;
  label: string;
  detail?: string;
  highlight?: boolean;
}

interface Props {
  milestones: Milestone[];
}

export function TimelineDraw({ milestones }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });

  return (
    <div ref={ref} className="relative pl-8">
      {/* Vertical line */}
      <motion.div
        className="absolute left-3 top-0 bottom-0 w-px bg-nq-accent/30"
        initial={{ scaleY: 0 }}
        animate={inView ? { scaleY: 1 } : {}}
        transition={{ duration: 1.5, ease: "easeOut" }}
        style={{ transformOrigin: "top" }}
      />

      {milestones.map((m, i) => (
        <motion.div
          key={m.date}
          initial={{ opacity: 0, x: -20 }}
          animate={inView ? { opacity: 1, x: 0 } : {}}
          transition={{ delay: 0.3 + i * 0.2, duration: 0.5 }}
          className="relative mb-8 last:mb-0"
        >
          {/* Dot */}
          <div
            className={`absolute -left-5 top-1 w-2.5 h-2.5 rounded-full border-2 ${
              m.highlight
                ? "bg-nq-accent border-nq-accent"
                : "bg-nq-bg border-nq-accent/40"
            }`}
          />
          <p className="text-[0.625rem] font-mono text-nq-accent uppercase tracking-widest mb-1">
            {m.date}
          </p>
          <p className="text-sm text-nq-text font-medium">{m.label}</p>
          {m.detail && (
            <p className="text-[0.8125rem] text-nq-muted mt-1">{m.detail}</p>
          )}
        </motion.div>
      ))}
    </div>
  );
}
```

**Step 5: CodeReveal** — Code block that types line by line

```tsx
// src/components/chapters/CodeReveal.tsx
import { useRef, useEffect, useState } from "react";
import { useInView } from "framer-motion";

interface Props {
  code: string;
  language?: string;
  speed?: number; // ms per line
}

export function CodeReveal({ code, language = "python", speed = 80 }: Props) {
  const ref = useRef<HTMLPreElement>(null);
  const inView = useInView(ref, { once: true });
  const lines = code.split("\n");
  const [visibleLines, setVisibleLines] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let i = 0;
    const interval = setInterval(() => {
      if (i < lines.length) {
        setVisibleLines(++i);
      } else {
        clearInterval(interval);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [inView, lines.length, speed]);

  return (
    <pre
      ref={ref}
      className="bg-nq-surface border border-nq-border/30 p-5 overflow-x-auto text-[0.8125rem] font-mono text-nq-text/80 leading-relaxed"
    >
      <code>
        {lines.slice(0, visibleLines).map((line, i) => (
          <span key={i} className="block">
            <span className="text-nq-muted/30 select-none mr-4 inline-block w-6 text-right">
              {i + 1}
            </span>
            {line}
          </span>
        ))}
        {visibleLines < lines.length && inView && (
          <span className="inline-block w-2 h-4 bg-nq-accent/50 animate-pulse" />
        )}
      </code>
    </pre>
  );
}
```

**Step 6: ComparisonSlide** — Side-by-side before/after

```tsx
// src/components/chapters/ComparisonSlide.tsx
import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface Props {
  left: { label: string; items: string[]; rejected?: boolean };
  right: { label: string; items: string[]; accepted?: boolean };
}

export function ComparisonSlide({ left, right }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });

  return (
    <div ref={ref} className="grid md:grid-cols-2 gap-6">
      <motion.div
        initial={{ opacity: 0, x: -40 }}
        animate={inView ? { opacity: left.rejected ? 0.4 : 1, x: 0 } : {}}
        transition={{ duration: 0.6 }}
        className={`border p-6 ${
          left.rejected
            ? "border-nq-error/30 bg-nq-error/5"
            : "border-nq-border/30 bg-nq-surface/30"
        }`}
      >
        <p className="text-[0.625rem] font-mono uppercase tracking-widest mb-4 text-nq-muted">
          {left.label}
        </p>
        <ul className="space-y-2">
          {left.items.map((item) => (
            <li key={item} className="text-sm text-nq-muted flex items-start gap-2">
              <span className={left.rejected ? "text-nq-error" : "text-nq-muted"}>
                {left.rejected ? "✗" : "—"}
              </span>
              {item}
            </li>
          ))}
        </ul>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, x: 40 }}
        animate={inView ? { opacity: 1, x: 0 } : {}}
        transition={{ duration: 0.6, delay: 0.2 }}
        className={`border p-6 ${
          right.accepted
            ? "border-nq-accent/30 bg-nq-accent/5"
            : "border-nq-border/30 bg-nq-surface/30"
        }`}
      >
        <p className="text-[0.625rem] font-mono uppercase tracking-widest mb-4 text-nq-accent">
          {right.label}
        </p>
        <ul className="space-y-2">
          {right.items.map((item) => (
            <li key={item} className="text-sm text-nq-text flex items-start gap-2">
              <span className="text-nq-accent">✓</span>
              {item}
            </li>
          ))}
        </ul>
      </motion.div>
    </div>
  );
}
```

**Step 7: Commit**

```bash
git add src/components/chapters/
git commit -m "feat(storybook): add reusable animation components"
```

---

### Task 7: Quiz Engine (4 Formats)

**Files:**
- Create: `src/components/quiz/QuizGate.tsx`
- Create: `src/components/quiz/Flashcard.tsx`
- Create: `src/components/quiz/DragOrder.tsx`
- Create: `src/components/quiz/Scenario.tsx`
- Create: `src/components/quiz/InteractiveSpot.tsx`
- Create: `src/content/quizzes/session1-quiz.ts`
- Create: `src/content/quizzes/session2-quiz.ts`
- Create: `src/content/quizzes/session3-quiz.ts`
- Create: `src/content/quizzes/session4-quiz.ts`

This task builds all 4 quiz formats and the quiz content for each session. Each quiz requires 60% to pass (e.g., 2/3 flashcards, 3/5 mixed).

**Quiz content is derived from the storybook chapters:**

Session 1 flashcards:
1. "Smriti started as a basic RAG model coded from scratch in April 2024" — True
2. "Smriti uses MySQL as its primary database" — False (PostgreSQL)
3. "The project uses a single Pinecone index for all 7 vector types" — True

Session 2 drag-order:
"Order the search pipeline steps": Query Understanding → Parallel Search (FTS + Vector) → RRF Fusion → Cohere Reranking → Post-Processing

Session 3 scenarios:
1. "A judgment from 2022 cites Section 302 IPC. In 2024, IPC was replaced by BNS. What should Smriti's temporal validation node warn?" → "This case cites IPC 302, now replaced by BNS 103"
2. "The research agent found 15 cases supporting bail under NDPS, but 0 opposing cases. What stage addresses this?" → "Stage 4: Challenge (adversarial_search_node)"
3. "A case is cited by 500 other cases and decided by a 5-judge Constitution Bench. What precedent strength?" → "BINDING (same or higher court, large bench)"

Session 4 mixed:
1. Flashcard: "The frontend uses Jest for testing" — False (Vitest)
2. Drag-order: "Order the batch ingestion phases": Text Extraction → Batch Metadata → Online Processing → Quality Check
3. Scenario: "AI Studio batch API failed because..." → "No responseSchema support in JSONL"
4. Scenario: "Smriti has how many backend tests?" → "~2,185"
5. Interactive: "Which vector type gets a 1.5x RRF boost in agent search?" → proposition/ratio/headnote

Full component implementations follow the same pattern as Tasks above. Each quiz component receives questions via props, manages local state, and calls `submitQuiz` from the progress store on completion.

**Step N: Commit**

```bash
git add src/components/quiz/ src/content/quizzes/
git commit -m "feat(storybook): add quiz engine with 4 formats + content"
```

---

### Task 8: 3D Hero Scenes (React Three Fiber)

**Files:**
- Create: `src/components/three/JudgmentExplode.tsx` — Session 1
- Create: `src/components/three/VectorCloud.tsx` — Session 2
- Create: `src/components/three/CitationGraph3D.tsx` — Session 3
- Create: `src/components/three/ArchitectureMap.tsx` — Session 4

Each 3D scene renders inside a `<Canvas>` from React Three Fiber, wrapped in a full-viewport container. Scroll progress (from GSAP) drives animation progress via `useScroll` or manual interpolation.

**Session 1 — JudgmentExplode:** Instanced mesh of ~50 white rectangles (pages) arranged as a stack. On scroll: pages scatter outward with spring physics, rotate, then reassemble into a structured grid (representing structured data). Gold bloom postprocessing.

**Session 2 — VectorCloud:** 1,536 small glowing spheres randomly positioned in 3D space. On scroll: spheres cluster into 7 groups (representing 7 vector types), each group a different shade of gold. Camera slowly orbits. `@react-three/postprocessing` Bloom for glow.

**Session 3 — CitationGraph3D:** Force-directed graph with ~30 nodes (spheres) and ~60 edges (lines). Nodes float, edges pulse gold. On hover (drei's `Html` overlay): node label appears. OrbitControls enabled so user can explore. Overruled edges glow red.

**Session 4 — ArchitectureMap:** 6 labeled nodes (PostgreSQL, Pinecone, Neo4j, Gemini, Cloud Run, Redis) arranged in 3D space. Pulsing connection lines between them with particle effects flowing along the edges. Camera auto-orbits slowly. Clicking a node shows a tooltip with the service role.

Each scene is lazy-loaded with `React.lazy()` and `<Suspense>` to avoid blocking initial paint.

**Step N: Commit**

```bash
git add src/components/three/
git commit -m "feat(storybook): add 4 React Three Fiber hero scenes"
```

---

### Task 9: Chapter Content (All 11 Chapters)

**Files:**
- Create: `src/content/chapters/ch00-the-spark.ts` through `ch10-road-ahead.ts`

Each chapter file exports a configuration object used by the Session page to render scroll sections:

```typescript
// Example: src/content/chapters/ch00-the-spark.ts
import type { ChapterConfig } from "./types";

export const ch00: ChapterConfig = {
  id: "ch00",
  title: "The Spark",
  subtitle: "How Avi stumbled on the problem and saw the opportunity",
  sections: [
    {
      type: "typewriter",
      text: "One fine day, Avi was sitting in a classroom at UPES, half-listening to a lecture on Natural Language Processing...",
      className: "text-display font-heading text-nq-text italic",
    },
    {
      type: "prose",
      content: "The professor was explaining how machines could understand the *meaning* of text...",
    },
    {
      type: "comparison",
      left: {
        label: "Keyword Search (Before)",
        items: ["Type exact words", "Miss synonyms", "No concept matching", "Hope for the best"],
        rejected: true,
      },
      right: {
        label: "Semantic Search (Smriti)",
        items: ["Understand meaning", "Find concepts", "Match intent", "Indian law-aware"],
        accepted: true,
      },
    },
    {
      type: "timeline",
      milestones: [
        { date: "April 2024", label: "Basic RAG model coded from scratch", detail: "Proof of concept — extract PDF, embed, search" },
        { date: "October 2024", label: "Adopted open-source framework", detail: "Better foundation, but hit architectural ceiling" },
        { date: "March 2026", label: "Built from scratch", detail: "Purpose-built for Indian legal research", highlight: true },
      ],
    },
    // ... more sections
  ],
};
```

**Types:**
```typescript
// src/content/chapters/types.ts
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
  | { type: "counter"; from: number; to: number; prefix?: string; suffix?: string; label: string }
  | { type: "diagram"; svg: string } // SVG path for AnimatedDiagram
  | { type: "heading"; text: string; level?: 2 | 3 }
  | { type: "quote"; text: string; attribution?: string }
  | { type: "spacer"; height?: string };
```

Content is distilled from the storybook markdown files — same story, same facts, condensed for a scroll experience (shorter paragraphs, more visual moments, less wall-of-text).

**Step N: Commit**

```bash
git add src/content/chapters/
git commit -m "feat(storybook): add all 11 chapter content configs"
```

---

### Task 10: Session Page (Renders Chapters + Quiz Gate)

**Files:**
- Create: `src/pages/Session.tsx`

The Session page reads the session ID from the URL, checks if it's unlocked, renders each chapter's scroll sections using `ChapterShell` + `ScrollSection` + animation components, and ends with the `QuizGate`.

```tsx
// src/pages/Session.tsx
import { useParams, Navigate } from "react-router-dom";
import { useProgressStore } from "@/stores/progress";
import { SESSIONS } from "@/content/sessions";
import { SessionLock } from "@/components/layout/SessionLock";
import { ChapterShell } from "@/components/chapters/ChapterShell";
import { ScrollSection } from "@/components/chapters/ScrollSection";
import { QuizGate } from "@/components/quiz/QuizGate";
import { useAudio } from "@/hooks/useAudio";
import { lazy, Suspense, useEffect } from "react";
// Dynamic chapter imports
import { renderSection } from "@/content/chapters/renderer";
import { getChapterConfig } from "@/content/chapters";

// Lazy 3D scenes
const heroScenes = {
  1: lazy(() => import("@/components/three/JudgmentExplode")),
  2: lazy(() => import("@/components/three/VectorCloud")),
  3: lazy(() => import("@/components/three/CitationGraph3D")),
  4: lazy(() => import("@/components/three/ArchitectureMap")),
};

export function Session() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);
  const { isSessionUnlocked, setCurrentPosition } = useProgressStore();
  const { play } = useAudio();

  useEffect(() => {
    play("ambient");
  }, [play]);

  if (!SESSIONS[sessionId - 1]) return <Navigate to="/" />;
  if (!isSessionUnlocked(sessionId)) return <SessionLock sessionId={sessionId} />;

  const session = SESSIONS[sessionId - 1];
  const HeroScene = heroScenes[sessionId as keyof typeof heroScenes];

  return (
    <div className="pt-14 pb-10">
      {/* 3D Hero */}
      <div className="h-screen relative">
        <Suspense
          fallback={
            <div className="h-full flex items-center justify-center">
              <p className="text-nq-muted font-mono text-sm animate-pulse">
                Loading...
              </p>
            </div>
          }
        >
          <HeroScene />
        </Suspense>
        <div className="absolute bottom-10 inset-x-0 text-center">
          <p className="text-[0.625rem] font-mono text-nq-accent uppercase tracking-widest mb-2">
            {session.day}
          </p>
          <h1 className="text-massive font-heading text-nq-text">
            {session.title}
          </h1>
          <p className="text-subtitle text-nq-muted mt-2">{session.subtitle}</p>
          <p className="text-[0.6875rem] text-nq-muted/50 mt-6 animate-bounce">
            ↓ Scroll to begin
          </p>
        </div>
      </div>

      {/* Chapters */}
      {session.chapters.map((chId) => {
        const config = getChapterConfig(chId);
        if (!config) return null;
        return (
          <ChapterShell
            key={chId}
            chapterId={chId}
            title={config.title}
            subtitle={config.subtitle}
          >
            {config.sections.map((section, i) => (
              <ScrollSection key={i} delay={i * 0.05}>
                {renderSection(section)}
              </ScrollSection>
            ))}
          </ChapterShell>
        );
      })}

      {/* Quiz Gate */}
      <QuizGate sessionId={sessionId} />
    </div>
  );
}
```

**Step N: Commit**

```bash
git add src/pages/Session.tsx src/content/chapters/renderer.tsx src/content/chapters/index.ts
git commit -m "feat(storybook): add Session page with chapter rendering + quiz gate"
```

---

### Task 11: Completion Page + Certificate

**Files:**
- Create: `src/pages/Completion.tsx`
- Create: `src/components/fx/GoldConfetti.tsx`
- Create: `src/components/fx/Certificate.tsx`

The Completion page shows when all 4 sessions are passed. It renders gold confetti (Lottie or canvas particles), a personalized certificate with the user's name and completion date, and a "Return to NeetiQ" link.

**Step N: Commit**

```bash
git add src/pages/Completion.tsx src/components/fx/
git commit -m "feat(storybook): add completion page with confetti + certificate"
```

---

### Task 12: Audio Assets + Lottie + Fonts

**Files:**
- Create: `public/audio/` placeholder files
- Create: `public/fonts/` placeholder files
- Create: `public/lottie/` placeholder files

Audio: Generate or source royalty-free ambient loop (~2 min, dark cinematic), plus SFX (whoosh, chime, correct/wrong buzzer, fanfare). Can use Pixabay or Freesound.org.

Fonts: Download Inter Variable and JetBrains Mono Variable woff2 files from Google Fonts / JetBrains.

Lottie: Source from LottieFiles — checkmark, confetti, and unlock animations.

**Step N: Commit**

```bash
git add public/
git commit -m "feat(storybook): add audio, font, and Lottie assets"
```

---

### Task 13: Final Polish + Responsive + Deploy

**Files:**
- Modify: Various components for mobile responsiveness
- Create: `smriti-storybook/README.md` (brief setup instructions)

**Steps:**
1. Test all sessions end-to-end
2. Verify quiz gates lock/unlock correctly
3. Test on mobile viewport (3D scenes should gracefully degrade)
4. Add `<meta>` tags for SEO/sharing (og:image, title, description)
5. Deploy to Netlify (connect repo, set subdomain)
6. Verify at onboarding.neetiq.in

**Step N: Commit**

```bash
git add .
git commit -m "feat(storybook): responsive polish + deploy config"
```

---

## Summary

| Task | What | Effort |
|------|------|--------|
| 1 | Project scaffold | Small |
| 2 | Zustand + Audio hook | Small |
| 3 | Layout shell (TopBar, Progress, Lock) | Small |
| 4 | Landing page | Small |
| 5 | Scroll engine (GSAP + ChapterShell) | Medium |
| 6 | 8 reusable animation components | Medium |
| 7 | Quiz engine (4 formats + content) | Medium-Large |
| 8 | 4 React Three Fiber 3D scenes | Large |
| 9 | 11 chapter content configs | Large (content) |
| 10 | Session page (wires everything) | Medium |
| 11 | Completion page + certificate | Small |
| 12 | Audio/font/Lottie assets | Small |
| 13 | Polish + responsive + deploy | Medium |

**Total: 13 tasks. Estimated build: ~4-5 focused sessions.**
