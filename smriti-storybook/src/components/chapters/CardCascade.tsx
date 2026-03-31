import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface Card {
  title: string;
  description: string;
  icon?: string;
}

interface Props {
  cards: Card[];
  columns?: 2 | 3 | 4;
}

export function CardCascade({ cards, columns = 3 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });

  const gridCols = { 2: "md:grid-cols-2", 3: "md:grid-cols-3", 4: "grid-cols-2 md:grid-cols-4" };

  return (
    <div ref={ref} className={`grid grid-cols-1 ${gridCols[columns]} gap-4`}>
      {cards.map((card, i) => (
        <motion.div
          key={card.title}
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={inView ? { opacity: 1, y: 0, scale: 1 } : {}}
          transition={{ delay: i * 0.12, duration: 0.5, ease: "easeOut" }}
          whileHover={{ scale: 1.03 }}
          className="relative border border-[#1E1E1E]/30 border-t-[#C5A880]/30 bg-[#111111]/30 p-5 hover:border-[#C5A880]/20 transition-colors"
        >
          {/* Index badge */}
          <span className="absolute top-2 right-3 text-[0.6rem] font-mono text-[#C5A880]/30">
            {String(i + 1).padStart(2, "0")}
          </span>
          {card.icon && <span className="text-3xl mb-3 block text-[#C5A880]">{card.icon}</span>}
          <h3 className="text-sm font-[Georgia] text-[#C5A880] mb-2">{card.title}</h3>
          <p className="text-[0.8125rem] text-[#6B6B6B] leading-relaxed">{card.description}</p>
        </motion.div>
      ))}
    </div>
  );
}
