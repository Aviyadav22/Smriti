import { useRef, useEffect, useState } from "react";
import { motion, useInView } from "framer-motion";

interface Props {
  from: number;
  to: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
}

export function CounterAnimation({ from, to, duration = 2000, prefix = "", suffix = "", className = "" }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const [value, setValue] = useState(from);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const step = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(from + (to - from) * eased));
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        setDone(true);
      }
    };
    requestAnimationFrame(step);
  }, [inView, from, to, duration]);

  return (
    <span ref={ref} className={`relative inline-block ${className}`}>
      {/* Pulsing glow behind number when counter reaches target */}
      {done && (
        <motion.span
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: [0, 0.4, 0], scale: [0.8, 1.2, 0.8] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          className="absolute inset-0 rounded-full bg-[#C5A880]/20 blur-xl pointer-events-none"
          aria-hidden
        />
      )}
      <span className="relative">
        {prefix}{value.toLocaleString()}{suffix}
      </span>
    </span>
  );
}
