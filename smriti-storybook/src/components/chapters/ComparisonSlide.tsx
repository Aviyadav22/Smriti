import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface Side {
  label: string;
  items: string[];
  rejected?: boolean;
  accepted?: boolean;
}

interface Props {
  left: Side;
  right: Side;
}

export function ComparisonSlide({ left, right }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });

  return (
    <div ref={ref} className="grid md:grid-cols-2 gap-6">
      <motion.div
        initial={{ opacity: 0, x: -40 }}
        animate={inView ? { opacity: left.rejected ? 0.4 : 1, x: 0 } : {}}
        transition={{ duration: 0.6 }}
        className={`border p-6 ${left.rejected ? "border-[#EF4444]/30 bg-[#EF4444]/5" : "border-[#1E1E1E]/30 bg-[#111111]/30"}`}
      >
        <p className="text-[0.625rem] font-mono uppercase tracking-widest mb-4 text-[#6B6B6B]">{left.label}</p>
        <ul className="space-y-2">
          {left.items.map((item) => (
            <li key={item} className="text-sm text-[#6B6B6B] flex items-start gap-2">
              <span className={left.rejected ? "text-[#EF4444]" : "text-[#6B6B6B]"}>{left.rejected ? "\u2717" : "\u2014"}</span>
              {item}
            </li>
          ))}
        </ul>
      </motion.div>
      <motion.div
        initial={{ opacity: 0, x: 40 }}
        animate={inView ? { opacity: 1, x: 0 } : {}}
        transition={{ duration: 0.6, delay: 0.2 }}
        className={`border p-6 ${right.accepted ? "border-[#C5A880]/30 bg-[#C5A880]/5" : "border-[#1E1E1E]/30 bg-[#111111]/30"}`}
      >
        <p className="text-[0.625rem] font-mono uppercase tracking-widest mb-4 text-[#C5A880]">{right.label}</p>
        <ul className="space-y-2">
          {right.items.map((item) => (
            <li key={item} className="text-sm text-[#E8E8E8] flex items-start gap-2">
              <span className="text-[#C5A880]">{"\u2713"}</span>
              {item}
            </li>
          ))}
        </ul>
      </motion.div>
    </div>
  );
}
