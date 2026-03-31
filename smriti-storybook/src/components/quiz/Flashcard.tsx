import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Props {
  statement: string;
  isTrue: boolean;
  explanation: string;
  onAnswer: (correct: boolean) => void;
}

export function Flashcard({ statement, isTrue, explanation, onAnswer }: Props) {
  const [answered, setAnswered] = useState<boolean | null>(null);
  const [flipped, setFlipped] = useState(false);

  const handleAnswer = (answer: boolean) => {
    const correct = answer === isTrue;
    setAnswered(correct);
    setFlipped(true);
    onAnswer(correct);
  };

  return (
    <div className="border border-[#1E1E1E]/50 bg-[#111111]/50 p-6 max-w-lg mx-auto">
      <AnimatePresence mode="wait">
        {!flipped ? (
          <motion.div key="front" initial={{ opacity: 1 }} exit={{ opacity: 0, rotateY: 90 }} transition={{ duration: 0.3 }}>
            <p className="text-base text-[#E8E8E8] mb-6 leading-relaxed">{statement}</p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => handleAnswer(true)}
                className="px-6 py-2 border border-[#4ADE80]/40 text-[#4ADE80] text-sm font-mono uppercase tracking-wider hover:bg-[#4ADE80]/10 transition-colors"
              >
                True
              </button>
              <button
                onClick={() => handleAnswer(false)}
                className="px-6 py-2 border border-[#EF4444]/40 text-[#EF4444] text-sm font-mono uppercase tracking-wider hover:bg-[#EF4444]/10 transition-colors"
              >
                False
              </button>
            </div>
          </motion.div>
        ) : (
          <motion.div key="back" initial={{ opacity: 0, rotateY: -90 }} animate={{ opacity: 1, rotateY: 0 }} transition={{ duration: 0.3 }}>
            <div className={`text-center mb-4 text-lg font-mono ${answered ? "text-[#4ADE80]" : "text-[#EF4444]"}`}>
              {answered ? "✓ Correct!" : "✗ Not quite"}
            </div>
            <p className="text-sm text-[#6B6B6B] leading-relaxed">{explanation}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
