import { useRef, useEffect, useState } from "react";
import { useInView } from "framer-motion";

interface Props {
  text: string;
  className?: string;
  speed?: number;
  as?: "p" | "h1" | "h2" | "h3" | "span" | "blockquote";
}

export function TypewriterText({ text, className = "", speed = 30, as: Tag = "p" }: Props) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });
  const [displayed, setDisplayed] = useState("");

  useEffect(() => {
    if (!inView) return;
    let i = 0;
    const interval = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
      } else {
        clearInterval(interval);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [inView, text, speed]);

  return (
    // @ts-expect-error dynamic tag
    <Tag ref={ref} className={className}>
      {displayed}
      {inView && displayed.length < text.length && (
        <span className="inline-block w-[2px] h-[1em] bg-[#C5A880] ml-0.5 animate-pulse" />
      )}
    </Tag>
  );
}
