import { useRef, type ReactNode } from "react";
import { motion, useInView } from "framer-motion";

interface Props {
  children: ReactNode;
  className?: string;
  delay?: number;
}

export function ScrollSection({ children, className = "", delay = 0 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <div ref={ref} className={`px-6 py-16 md:py-24 ${className}`}>
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.7, ease: "easeOut", delay }}
        className="max-w-4xl mx-auto"
      >
        {children}
      </motion.div>
    </div>
  );
}
