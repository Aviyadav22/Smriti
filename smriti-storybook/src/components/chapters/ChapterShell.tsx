import { type ReactNode } from "react";
import { useScrollProgress } from "@/hooks/useScrollProgress";
import { motion } from "framer-motion";

interface Props {
  chapterId: string;
  title: string;
  subtitle: string;
  children: ReactNode;
}

export function ChapterShell({ chapterId, title, subtitle, children }: Props) {
  const containerRef = useScrollProgress(chapterId);

  return (
    <div ref={containerRef} className="relative">
      {/* Chapter header */}
      <div className="min-h-[60vh] flex items-center justify-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="text-center max-w-3xl"
        >
          <p className="text-[0.625rem] font-mono text-[#C5A880] uppercase tracking-widest mb-4">
            {chapterId.replace("ch0", "Chapter ").replace("ch", "Chapter ")}
          </p>
          <h2 className="text-[clamp(2.5rem,5vw,4rem)] font-[Georgia] text-[#E8E8E8] mb-4 leading-tight">
            {title}
          </h2>
          <p className="text-xl text-[#6B6B6B]">{subtitle}</p>
        </motion.div>
      </div>

      {/* Chapter content sections */}
      {children}

      {/* Chapter divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-[#C5A880]/20 to-transparent my-20" />
    </div>
  );
}
