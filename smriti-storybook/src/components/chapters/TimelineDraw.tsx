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
      <motion.div
        className="absolute left-3 top-0 bottom-0 w-px bg-[#C5A880]/30"
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
          <div className={`absolute -left-5 top-1 w-2.5 h-2.5 rounded-full border-2 ${m.highlight ? "bg-[#C5A880] border-[#C5A880]" : "bg-[#0A0A0A] border-[#C5A880]/40"}`} />
          <p className="text-[0.625rem] font-mono text-[#C5A880] uppercase tracking-widest mb-1">{m.date}</p>
          <p className="text-sm text-[#E8E8E8] font-medium">{m.label}</p>
          {m.detail && <p className="text-[0.8125rem] text-[#6B6B6B] mt-1">{m.detail}</p>}
        </motion.div>
      ))}
    </div>
  );
}
