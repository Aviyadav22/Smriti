import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useProgressStore } from "@/stores/progress";
import { GoldConfetti } from "@/components/fx/GoldConfetti";
import { Certificate } from "@/components/fx/Certificate";

export function Completion() {
  const navigate = useNavigate();
  const { userName, quizResults, reset } = useProgressStore();

  const allCompleted =
    [1, 2, 3, 4].every((id) => quizResults[id]?.passed === true);

  useEffect(() => {
    if (!allCompleted) {
      navigate("/", { replace: true });
    }
  }, [allCompleted, navigate]);

  if (!allCompleted) return null;

  const latestCompletion =
    Object.values(quizResults)
      .map((r) => r.completedAt)
      .sort()
      .pop() ?? new Date().toISOString();

  const scores = [1, 2, 3, 4].map((id) => ({
    session: id,
    score: quizResults[id].score,
    total: quizResults[id].total,
  }));

  const handleReset = () => {
    reset();
    navigate("/");
  };

  return (
    <div className="min-h-screen px-4 py-16 sm:py-24">
      <GoldConfetti />

      <motion.div
        className="mx-auto max-w-2xl"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      >
        {/* Heading */}
        <h1
          className="mb-2 text-center font-[Georgia] text-3xl sm:text-5xl font-bold"
          style={{ color: "#C5A880" }}
        >
          Congratulations, {userName}!
        </h1>

        <p className="mb-12 text-center text-[#666666]">
          You have completed 100% of the Smriti Platform Tour.
        </p>

        {/* Certificate */}
        <Certificate
          userName={userName}
          completedAt={latestCompletion}
          scores={scores}
        />

        {/* Actions */}
        <div className="mt-12 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <button
            onClick={handleReset}
            className="rounded-md border border-[#2A2A2A] bg-[#1A1A1A] px-6 py-3 text-sm font-medium text-[#E0E0E0] transition-colors hover:border-[#C5A880] hover:text-[#C5A880]"
          >
            Start Over
          </button>

          <a
            href="https://neetiq.in"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md px-6 py-3 text-sm font-medium text-[#0A0A0A] transition-opacity hover:opacity-90"
            style={{ background: "linear-gradient(135deg, #C5A880, #D4B896)" }}
          >
            Visit NeetiQ
          </a>
        </div>
      </motion.div>
    </div>
  );
}
