import { motion } from "framer-motion";
import { useProgressStore } from "@/stores/progress";
import { SESSIONS } from "@/content/sessions";
import { useLocation } from "react-router-dom";

export function ProgressBar() {
  const location = useLocation();
  const chapters = useProgressStore((s) => s.chapters);
  const quizResults = useProgressStore((s) => s.quizResults);

  // Only show on session pages
  const sessionMatch = location.pathname.match(/^\/session\/(\d+)$/);
  if (!sessionMatch) return null;

  const sessionId = Number(sessionMatch[1]);
  const session = SESSIONS[sessionId - 1];
  if (!session) return null;

  const sessionChapters = session.chapters;
  const completedCount = sessionChapters.filter(
    (ch) => chapters[ch]?.completed
  ).length;
  const quizPassed = quizResults[sessionId]?.passed === true;
  const totalSteps = sessionChapters.length + 1; // chapters + quiz
  const doneSteps = completedCount + (quizPassed ? 1 : 0);
  const percent = Math.round((doneSteps / totalSteps) * 100);

  return (
    <footer className="fixed bottom-0 inset-x-0 z-50 h-10 bg-[#0A0A0A]/90 backdrop-blur-md border-t border-[#1E1E1E]/30">
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center gap-4">
        <div className="flex-1 flex gap-1 h-1.5">
          {sessionChapters.map((ch) => {
            const progress = chapters[ch];
            const pct = progress?.completed ? 100 : (progress?.scrollPercent ?? 0);
            return (
              <div key={ch} className="flex-1 bg-[#1E1E1E]/40 overflow-hidden">
                <motion.div
                  className="h-full bg-[#C5A880]"
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                />
              </div>
            );
          })}
          {/* Quiz segment */}
          <div className="flex-1 bg-[#1E1E1E]/40 overflow-hidden">
            <motion.div
              className="h-full bg-[#4ADE80]"
              initial={{ width: 0 }}
              animate={{ width: quizPassed ? "100%" : "0%" }}
              transition={{ duration: 0.3, ease: "easeOut" }}
            />
          </div>
        </div>
        <span className="text-[0.625rem] font-mono text-[#666] whitespace-nowrap">
          {session.day}
        </span>
        <span className="text-[0.625rem] font-mono text-[#C5A880] w-10 text-right">
          {percent}%
        </span>
      </div>
    </footer>
  );
}
