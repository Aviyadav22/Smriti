import { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  width: number;
  height: number;
  rotation: number;
  rotationSpeed: number;
  color: string;
  opacity: number;
}

const GOLD_SHADES = ["#C5A880", "#D4B896", "#B89A6C", "#E8D5B5"];
const PARTICLE_COUNT = 100;
const DURATION_MS = 5000;
const FADE_START_MS = 4000;

export function GoldConfetti() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId: number;
    const startTime = performance.now();

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const particles: Particle[] = Array.from({ length: PARTICLE_COUNT }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * -canvas.height * 0.5,
      vx: (Math.random() - 0.5) * 2,
      vy: Math.random() * 3 + 2,
      width: Math.random() * 6 + 3,
      height: Math.random() * 4 + 2,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * 0.15,
      color: GOLD_SHADES[Math.floor(Math.random() * GOLD_SHADES.length)],
      opacity: 1,
    }));

    const animate = (now: number) => {
      const elapsed = now - startTime;
      if (elapsed > DURATION_MS) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        window.removeEventListener("resize", resize);
        return;
      }

      const globalOpacity =
        elapsed > FADE_START_MS
          ? 1 - (elapsed - FADE_START_MS) / (DURATION_MS - FADE_START_MS)
          : 1;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        p.rotation += p.rotationSpeed;
        p.vx += (Math.random() - 0.5) * 0.1;

        if (p.y > canvas.height + 20) {
          p.y = -10;
          p.x = Math.random() * canvas.width;
        }

        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rotation);
        ctx.globalAlpha = globalOpacity;
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.width / 2, -p.height / 2, p.width, p.height);
        ctx.restore();
      }

      animationId = requestAnimationFrame(animate);
    };

    animationId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{ zIndex: 50 }}
    />
  );
}
