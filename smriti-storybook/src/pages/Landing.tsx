import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useProgressStore } from "@/stores/progress";
import { SESSIONS } from "@/content/sessions";

function NameEntry({ onSubmit }: { onSubmit: (name: string) => void }) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (trimmed) onSubmit(trimmed);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className="min-h-screen flex items-center justify-center px-4"
    >
      <div className="text-center max-w-xl">
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.2 }}
        >
          <p className="text-[#C5A880] font-mono text-sm uppercase tracking-widest mb-4">
            NeetiQ Onboarding
          </p>
          <h1 className="text-5xl md:text-7xl font-[Georgia] text-[#E8E8E8] mb-3">
            The Smriti Story
          </h1>
          <div className="w-16 h-px bg-[#C5A880]/40 mx-auto mb-6" />
          <p className="text-[#6B6B6B] text-lg mb-10 leading-relaxed">
            How a law student&apos;s frustration became India&apos;s AI-powered
            legal research platform.
          </p>
        </motion.div>

        <motion.form
          onSubmit={handleSubmit}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.5 }}
          className="flex flex-col sm:flex-row gap-3 justify-center items-center"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter your name to begin"
            autoFocus
            className="bg-[#111111] border border-[#2A2A2A] text-[#E8E8E8] px-5 py-3.5 text-base focus:outline-none focus:border-[#C5A880]/60 transition-colors w-full sm:w-72 placeholder:text-[#555]"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="bg-[#C5A880] text-[#0A0A0A] font-semibold px-8 py-3.5 hover:bg-[#D4BA94] transition-all disabled:opacity-30 disabled:cursor-not-allowed w-full sm:w-auto"
          >
            Begin →
          </button>
        </motion.form>
      </div>
    </motion.div>
  );
}

function SessionCard({
  session,
  index,
  unlocked,
  completed,
}: {
  session: (typeof SESSIONS)[0];
  index: number;
  unlocked: boolean;
  completed: boolean;
}) {
  const inner = (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 + index * 0.12, ease: "easeOut" }}
      className={`border px-6 py-5 flex items-center justify-between transition-all duration-300 group ${
        completed
          ? "border-[#4ADE80]/30 bg-[#4ADE80]/5"
          : unlocked
          ? "border-[#2A2A2A] hover:border-[#C5A880]/40 hover:bg-[#C5A880]/5 cursor-pointer"
          : "border-[#1A1A1A] opacity-40"
      }`}
    >
      <div className="flex items-center gap-4">
        <div className={`w-10 h-10 flex items-center justify-center border text-sm font-mono ${
          completed ? "border-[#4ADE80]/40 text-[#4ADE80]" : unlocked ? "border-[#C5A880]/30 text-[#C5A880]" : "border-[#333] text-[#444]"
        }`}>
          {completed ? "✓" : index + 1}
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[#C5A880] font-mono text-[0.625rem] uppercase tracking-widest">
            {session.day} · {session.duration}
          </span>
          <span className="text-[#E8E8E8] font-[Georgia] text-lg group-hover:text-[#C5A880] transition-colors">
            {session.title}
          </span>
          <span className="text-[#555] text-sm">{session.subtitle}</span>
        </div>
      </div>
      <div className="shrink-0 ml-4">
        {!unlocked && <span className="text-lg opacity-50">🔒</span>}
        {unlocked && !completed && (
          <motion.span
            animate={{ x: [0, 4, 0] }}
            transition={{ repeat: Infinity, duration: 1.5 }}
            className="text-[#C5A880] text-lg"
          >
            →
          </motion.span>
        )}
      </div>
    </motion.div>
  );

  if (unlocked) {
    return <Link to={`/session/${session.id}`}>{inner}</Link>;
  }

  return inner;
}

function SessionSelector({ name }: { name: string }) {
  const isSessionUnlocked = useProgressStore((s) => s.isSessionUnlocked);
  const quizResults = useProgressStore((s) => s.quizResults);

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-2xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="text-center mb-10"
        >
          <p className="text-[#C5A880] font-mono text-sm uppercase tracking-widest mb-3">
            Welcome back, {name}
          </p>
          <h1 className="text-4xl md:text-6xl font-[Georgia] text-[#E8E8E8] mb-3">
            Your Journey
          </h1>
          <div className="w-16 h-px bg-[#C5A880]/40 mx-auto mb-4" />
          <p className="text-[#555] text-base">
            4 sessions across your first week. Each unlocks after passing the quiz.
          </p>
        </motion.div>

        <div className="flex flex-col gap-3">
          {SESSIONS.map((session, i) => (
            <SessionCard
              key={session.id}
              session={session}
              index={i}
              unlocked={isSessionUnlocked(session.id)}
              completed={quizResults[session.id]?.passed === true}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export function Landing() {
  const storedName = useProgressStore((s) => s.userName);
  const setUserName = useProgressStore((s) => s.setUserName);

  const handleNameSubmit = (name: string) => {
    setUserName(name);
  };

  if (!storedName) {
    return <NameEntry onSubmit={handleNameSubmit} />;
  }

  return <SessionSelector name={storedName} />;
}
