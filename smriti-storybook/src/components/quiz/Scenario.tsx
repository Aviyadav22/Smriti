import { useState } from "react";
import { motion } from "framer-motion";

interface Props {
  question: string;
  options: string[];
  correctIndex: number;
  explanation: string;
  onAnswer: (correct: boolean) => void;
}

export function Scenario({ question, options, correctIndex, explanation, onAnswer }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const [revealed, setRevealed] = useState(false);

  const handleSelect = (index: number) => {
    if (revealed) return;
    setSelected(index);
    setRevealed(true);
    onAnswer(index === correctIndex);
  };

  return (
    <div className="max-w-lg mx-auto">
      <p className="text-base text-[#E8E8E8] mb-6 leading-relaxed">{question}</p>
      <div className="space-y-2 mb-6">
        {options.map((opt, i) => {
          let borderColor = "border-[#1E1E1E]/50";
          let textColor = "text-[#E8E8E8]";
          if (revealed) {
            if (i === correctIndex) { borderColor = "border-[#4ADE80]/60"; textColor = "text-[#4ADE80]"; }
            else if (i === selected) { borderColor = "border-[#EF4444]/60"; textColor = "text-[#EF4444]"; }
            else { borderColor = "border-[#1E1E1E]/20"; textColor = "text-[#6B6B6B]/50"; }
          }
          return (
            <button
              key={i}
              onClick={() => handleSelect(i)}
              disabled={revealed}
              className={`w-full text-left border ${borderColor} bg-[#111111]/50 px-4 py-3 text-sm ${textColor} transition-colors ${!revealed ? "hover:border-[#C5A880]/30 cursor-pointer" : "cursor-default"}`}
            >
              <span className="text-[#6B6B6B] mr-3 font-mono">{String.fromCharCode(65 + i)}.</span>
              {opt}
            </button>
          );
        })}
      </div>
      {revealed && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm text-[#6B6B6B] border-l-2 border-[#C5A880]/30 pl-4"
        >
          {explanation}
        </motion.div>
      )}
    </div>
  );
}
