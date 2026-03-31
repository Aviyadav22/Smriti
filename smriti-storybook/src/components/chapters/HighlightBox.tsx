import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface Props {
  icon: string;
  title: string;
  description: string;
  accent?: string;
}

export function HighlightBox({ icon, title, description, accent = "#C5A880" }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, x: -30 }}
      animate={inView ? { opacity: 1, x: 0 } : {}}
      transition={{ duration: 0.6 }}
      className="relative border-l-2 bg-gradient-to-r from-[#1A1A1A] to-transparent p-6 md:p-8"
      style={{ borderColor: accent }}
    >
      <div className="absolute top-0 left-0 w-24 h-full opacity-10" style={{ background: `linear-gradient(90deg, ${accent}, transparent)` }} />
      <span className="text-3xl mb-3 block">{icon}</span>
      <h3 className="text-lg font-[Georgia] text-[#E0E0E0] mb-2">{title}</h3>
      <p className="text-sm text-[#888] leading-relaxed">{description}</p>
    </motion.div>
  );
}
