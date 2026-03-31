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

const TOTAL_CHAPTERS = 11;

export const useProgressStore = create<ProgressState>()(
  persist(
    (set, get) => ({
      userName: "",
      chapters: {},
      quizResults: {},
      currentSession: 1,
      currentChapter: "ch00",
      audioMuted: false,

      setUserName: (name: string) => set({ userName: name }),

      updateChapterScroll: (chapterId: string, percent: number) =>
        set((state) => {
          const existing = state.chapters[chapterId];
          return {
            chapters: {
              ...state.chapters,
              [chapterId]: {
                started: true,
                scrollPercent: Math.max(
                  existing?.scrollPercent ?? 0,
                  percent
                ),
                completed: existing?.completed ?? false,
              },
            },
          };
        }),

      completeChapter: (chapterId: string) =>
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

      submitQuiz: (result: QuizResult) =>
        set((state) => ({
          quizResults: {
            ...state.quizResults,
            [result.sessionId]: result,
          },
          currentSession: result.passed
            ? Math.max(state.currentSession, result.sessionId + 1)
            : state.currentSession,
        })),

      isSessionUnlocked: (sessionId: number): boolean => {
        if (sessionId <= 1) return true;
        const prevQuiz = get().quizResults[sessionId - 1];
        return prevQuiz?.passed === true;
      },

      getOverallProgress: (): number => {
        const { chapters } = get();
        const completedCount = Object.values(chapters).filter(
          (ch) => ch.completed
        ).length;
        return (completedCount / TOTAL_CHAPTERS) * 100;
      },

      setCurrentPosition: (session: number, chapter: string) =>
        set({ currentSession: session, currentChapter: chapter }),

      toggleMute: () => set((state) => ({ audioMuted: !state.audioMuted })),

      reset: () =>
        set((state) => ({
          userName: state.userName,
          chapters: {},
          quizResults: {},
          currentSession: 1,
          currentChapter: "ch00",
          audioMuted: state.audioMuted,
        })),
    }),
    {
      name: "smriti-storybook-progress",
      version: 2,
      migrate: () => ({
        userName: "",
        chapters: {},
        quizResults: {},
        currentSession: 1,
        currentChapter: "ch00",
        audioMuted: false,
      }),
    }
  )
);
