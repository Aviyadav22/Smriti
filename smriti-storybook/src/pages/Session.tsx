import { useParams, Navigate } from "react-router-dom";
import { useProgressStore } from "@/stores/progress";
import { SESSIONS } from "@/content/sessions";
import { SessionLock } from "@/components/layout/SessionLock";
import { ChapterShell } from "@/components/chapters/ChapterShell";
import { ScrollSection } from "@/components/chapters/ScrollSection";
import { QuizGate } from "@/components/quiz/QuizGate";
import { useAudio } from "@/hooks/useAudio";
import { lazy, Suspense, useEffect } from "react";
import { renderSection } from "@/content/chapters/renderer";
import { getChapterConfig } from "@/content/chapters";
import { ErrorBoundary } from "@/components/ErrorBoundary";

// Lazy 3D scenes
const heroScenes: Record<number, React.LazyExoticComponent<React.ComponentType>> = {
  1: lazy(() => import("@/components/three/JudgmentExplode")),
  2: lazy(() => import("@/components/three/VectorCloud")),
  3: lazy(() => import("@/components/three/CitationGraph3D")),
  4: lazy(() => import("@/components/three/ArchitectureMap")),
};

export function Session() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);
  const isSessionUnlocked = useProgressStore((s) => s.isSessionUnlocked);
  const { play } = useAudio();

  useEffect(() => {
    play("ambient");
  }, [play]);

  if (!SESSIONS[sessionId - 1]) return <Navigate to="/" />;

  const session = SESSIONS[sessionId - 1];

  if (!isSessionUnlocked(sessionId))
    return (
      <SessionLock
        sessionId={sessionId}
        sessionTitle={session.title}
        sessionDay={session.day}
      />
    );

  const HeroScene = heroScenes[sessionId];

  return (
    <div className="pt-14 pb-10">
      {/* 3D Hero */}
      <div className="h-[70vh] md:h-screen relative">
        <ErrorBoundary
          fallback={
            <div className="h-full flex items-center justify-center">
              <p className="text-[#666] text-sm">3D scene not available</p>
            </div>
          }
        >
          <Suspense
            fallback={
              <div className="h-full flex items-center justify-center">
                <p className="text-[#666] font-mono text-sm animate-pulse">Loading scene...</p>
              </div>
            }
          >
            {HeroScene && <HeroScene />}
          </Suspense>
        </ErrorBoundary>
        <div className="absolute bottom-10 inset-x-0 text-center">
          <p className="text-[0.625rem] font-mono text-[#C5A880] uppercase tracking-widest mb-2">
            {session.day}
          </p>
          <h1 className="text-3xl md:text-6xl font-serif text-[#E0E0E0]">
            {session.title}
          </h1>
          <p className="text-lg text-[#666] mt-2">{session.subtitle}</p>
          <p className="text-[0.6875rem] text-[#666]/50 mt-6 animate-bounce">{"\u2193"} Scroll to begin</p>
        </div>
      </div>

      {/* Chapters */}
      {session.chapters.map((chId) => {
        const config = getChapterConfig(chId);
        if (!config) return null;
        return (
          <ChapterShell key={chId} chapterId={chId} title={config.title} subtitle={config.subtitle}>
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
