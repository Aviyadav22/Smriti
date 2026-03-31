import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface Props {
  children: string;
  highlight?: boolean;
}

export function ProseBlock({ children, highlight }: Props) {
  const ref = useRef<HTMLParagraphElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });

  return (
    <motion.p
      ref={ref}
      initial={{ opacity: 0 }}
      animate={inView ? { opacity: 1 } : {}}
      transition={{ duration: 0.6 }}
      className={`text-base leading-relaxed max-w-3xl ${highlight ? "text-[#E8E8E8] border-l-2 border-[#C5A880]/40 pl-4" : "text-[#6B6B6B]"}`}
    >
      {children}
    </motion.p>
  );
}
