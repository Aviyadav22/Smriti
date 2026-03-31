import { useRef, useEffect, useState } from "react";
import { useInView } from "framer-motion";

interface Props {
  code: string;
  language?: string;
  speed?: number;
}

export function CodeReveal({ code, speed = 80 }: Props) {
  const ref = useRef<HTMLPreElement>(null);
  const inView = useInView(ref, { once: true });
  const lines = code.split("\n");
  const [visibleLines, setVisibleLines] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let i = 0;
    const interval = setInterval(() => {
      if (i < lines.length) { setVisibleLines(++i); } else { clearInterval(interval); }
    }, speed);
    return () => clearInterval(interval);
  }, [inView, lines.length, speed]);

  return (
    <pre ref={ref} className="bg-[#111111] border border-[#1E1E1E]/30 p-5 overflow-x-auto text-[0.8125rem] font-mono text-[#E8E8E8]/80 leading-relaxed">
      <code>
        {lines.slice(0, visibleLines).map((line, i) => (
          <span key={i} className="block">
            <span className="text-[#6B6B6B]/30 select-none mr-4 inline-block w-6 text-right">{i + 1}</span>
            {line}
          </span>
        ))}
        {visibleLines < lines.length && inView && (
          <span className="inline-block w-2 h-4 bg-[#C5A880]/50 animate-pulse" />
        )}
      </code>
    </pre>
  );
}
