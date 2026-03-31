import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useProgressStore } from "@/stores/progress";

gsap.registerPlugin(ScrollTrigger);

export function useScrollProgress(chapterId: string) {
  const containerRef = useRef<HTMLDivElement>(null);
  const updateScroll = useProgressStore((s) => s.updateChapterScroll);
  const completeChapter = useProgressStore((s) => s.completeChapter);

  useEffect(() => {
    if (!containerRef.current) return;

    const trigger = ScrollTrigger.create({
      trigger: containerRef.current,
      start: "top top",
      end: "bottom bottom",
      onUpdate: (self) => {
        const percent = Math.round(self.progress * 100);
        updateScroll(chapterId, percent);
        if (percent >= 95) completeChapter(chapterId);
      },
    });

    return () => {
      trigger.kill();
    };
  }, [chapterId, updateScroll, completeChapter]);

  return containerRef;
}
