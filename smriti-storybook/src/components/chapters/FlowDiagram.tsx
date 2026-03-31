import { useRef } from "react";
import { motion, useInView } from "framer-motion";

interface Props {
  steps: string[];
}

export function FlowDiagram({ steps }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });

  return (
    <div ref={ref} className="overflow-x-auto py-4">
      <div className="flex items-center gap-0 min-w-max mx-auto justify-center">
        {steps.map((step, i) => (
          <motion.div
            key={step}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={inView ? { opacity: 1, scale: 1 } : {}}
            transition={{ delay: i * 0.2, duration: 0.5 }}
            className="flex items-center"
          >
            <div className="border border-[#C5A880]/30 bg-[#0A0A0A] px-4 py-3 text-center min-w-[120px]">
              <span className="text-[0.6rem] font-mono text-[#C5A880]/60 block mb-1">STEP {i + 1}</span>
              <span className="text-xs text-[#E0E0E0]">{step}</span>
            </div>
            {i < steps.length - 1 && (
              <motion.div
                initial={{ scaleX: 0 }}
                animate={inView ? { scaleX: 1 } : {}}
                transition={{ delay: i * 0.2 + 0.3, duration: 0.3 }}
                className="w-8 h-px bg-gradient-to-r from-[#C5A880]/60 to-[#C5A880]/20 origin-left"
              />
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
