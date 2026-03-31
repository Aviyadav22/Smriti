import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface StatItem {
  value: string;
  label: string;
  icon?: string;
}

interface Props {
  items: StatItem[];
}

export function StatBlock({ items }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });

  return (
    <div ref={ref} className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {items.map((item, i) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, y: 20, scale: 0.9 }}
          animate={inView ? { opacity: 1, y: 0, scale: 1 } : {}}
          transition={{ delay: i * 0.15, duration: 0.6, ease: "easeOut" }}
          className="relative border border-[#C5A880]/20 bg-gradient-to-b from-[#C5A880]/5 to-transparent p-6 text-center group hover:border-[#C5A880]/40 transition-all duration-300"
        >
          {/* Glow effect on hover */}
          <div className="absolute inset-0 bg-[#C5A880]/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          {item.icon && <span className="text-2xl mb-2 block">{item.icon}</span>}
          <p className="text-3xl md:text-4xl font-[Georgia] text-[#C5A880] mb-1 relative">{item.value}</p>
          <p className="text-xs text-[#666] uppercase tracking-wider relative">{item.label}</p>
        </motion.div>
      ))}
    </div>
  );
}
