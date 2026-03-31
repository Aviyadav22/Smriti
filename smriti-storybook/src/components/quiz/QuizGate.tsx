import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Flashcard } from "./Flashcard";
import { DragOrder } from "./DragOrder";
import { Scenario } from "./Scenario";
import { useProgressStore } from "@/stores/progress";
import { getQuizForSession } from "@/content/quizzes";

interface Props {
  sessionId: number;
}

export function QuizGate({ sessionId }: Props) {
  const navigate = useNavigate();
  const submitQuiz = useProgressStore((s) => s.submitQuiz);
  const existingResult = useProgressStore((s) => s.quizResults[sessionId]);
  const questions = getQuizForSession(sessionId);
  const [currentQ, setCurrentQ] = useState(0);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);
  const total = questions.length;
  const passThreshold = Math.ceil(total * 0.6);

  if (existingResult?.passed) {
    return (
      <div className="py-20 text-center">
        <p className="text-[#4ADE80] font-mono text-sm mb-2">✓ Quiz Passed</p>
        <p className="text-[#6B6B6B] text-sm">Score: {existingResult.score}/{existingResult.total}</p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center mt-6">
          <button
            onClick={() => navigate("/")}
            className="border border-[#2A2A2A] text-[#6B6B6B] px-6 py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-[#1A1A1A] transition-colors"
          >
            ← All Sessions
          </button>
          {sessionId < 4 && (
            <button
              onClick={() => navigate(`/session/${sessionId + 1}`)}
              className="border border-[#C5A880]/40 text-[#C5A880] px-6 py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-[#C5A880]/10 transition-colors"
            >
              Session {sessionId + 1} →
            </button>
          )}
          {sessionId === 4 && (
            <button
              onClick={() => navigate("/complete")}
              className="bg-[#C5A880] text-[#0A0A0A] px-6 py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-[#C5A880]/90 transition-colors"
            >
              Complete Onboarding →
            </button>
          )}
        </div>
      </div>
    );
  }

  const handleAnswer = (correct: boolean) => {
    if (correct) setScore((s) => s + 1);
    setTimeout(() => {
      if (currentQ + 1 >= total) {
        const finalScore = correct ? score + 1 : score;
        const passed = finalScore >= passThreshold;
        submitQuiz({ sessionId, score: finalScore, total, passed, completedAt: new Date().toISOString() });
        setFinished(true);
      } else {
        setCurrentQ((q) => q + 1);
      }
    }, 1500);
  };

  if (finished) {
    const finalScore = score;
    const passed = finalScore >= passThreshold;
    return (
      <div className="py-20 text-center">
        <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}>
          <p className={`text-2xl font-mono mb-4 ${passed ? "text-[#4ADE80]" : "text-[#EF4444]"}`}>
            {passed ? "🎉 Quiz Passed!" : "Not quite — try again"}
          </p>
          <p className="text-[#6B6B6B] mb-8">
            Score: {finalScore}/{total} (need {passThreshold} to pass)
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => navigate("/")}
              className="border border-[#2A2A2A] text-[#6B6B6B] px-6 py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-[#1A1A1A] transition-colors"
            >
              ← All Sessions
            </button>
            {passed && sessionId < 4 && (
              <button onClick={() => navigate(`/session/${sessionId + 1}`)} className="border border-[#C5A880]/40 text-[#C5A880] px-6 py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-[#C5A880]/10 transition-colors">
                Session {sessionId + 1} →
              </button>
            )}
            {passed && sessionId === 4 && (
              <button onClick={() => navigate("/complete")} className="bg-[#C5A880] text-[#0A0A0A] px-6 py-2.5 text-sm font-mono uppercase tracking-wider">
                Complete Onboarding →
              </button>
            )}
            {!passed && (
              <button onClick={() => { setCurrentQ(0); setScore(0); setFinished(false); }} className="border border-[#EF4444]/40 text-[#EF4444] px-6 py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-[#EF4444]/10 transition-colors">
                Try Again
              </button>
            )}
          </div>
        </motion.div>
      </div>
    );
  }

  const q = questions[currentQ];
  return (
    <div className="py-20">
      <div className="text-center mb-10">
        <p className="text-[0.625rem] font-mono text-[#C5A880] uppercase tracking-widest mb-2">Quiz Gate</p>
        <p className="text-[#6B6B6B] text-sm">Question {currentQ + 1} of {total}</p>
      </div>
      {q.type === "flashcard" && (
        <Flashcard key={currentQ} statement={q.statement!} isTrue={q.isTrue!} explanation={q.explanation!} onAnswer={handleAnswer} />
      )}
      {q.type === "drag-order" && (
        <DragOrder key={currentQ} question={q.question!} items={q.items!} onComplete={handleAnswer} />
      )}
      {q.type === "scenario" && (
        <Scenario key={currentQ} question={q.question!} options={q.options!} correctIndex={q.correctIndex!} explanation={q.explanation!} onAnswer={handleAnswer} />
      )}
    </div>
  );
}
