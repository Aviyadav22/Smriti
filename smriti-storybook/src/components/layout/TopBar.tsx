import { Link, useLocation } from "react-router-dom";
import { useProgressStore } from "@/stores/progress";
import { SESSIONS } from "@/content/sessions";

export function TopBar() {
  const location = useLocation();
  const muted = useProgressStore((s) => s.audioMuted);
  const toggleMute = useProgressStore((s) => s.toggleMute);
  const isHome = location.pathname === "/";

  const sessionMatch = location.pathname.match(/^\/session\/(\d+)$/);
  const sessionId = sessionMatch ? Number(sessionMatch[1]) : null;
  const session = sessionId ? SESSIONS[sessionId - 1] : null;

  return (
    <header className="fixed top-0 inset-x-0 z-50 h-14 bg-[#0A0A0A]/90 backdrop-blur-md border-b border-[#1E1E1E]/30">
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3">
          <span className="text-sm font-[Georgia] text-[#C5A880] tracking-wide">
            NeetiQ
          </span>
          <span className="hidden md:inline text-[0.6rem] font-mono text-[#555] uppercase tracking-widest">
            Onboarding
          </span>
        </Link>

        {session && (
          <div className="text-[0.6875rem] font-mono text-[#555]">
            {session.day} — {session.title}
          </div>
        )}

        <div className="flex items-center gap-4">
          {!isHome && (
            <Link
              to="/"
              className="text-[0.625rem] font-mono text-[#555] hover:text-[#C5A880] transition-colors uppercase tracking-wider hidden sm:inline"
            >
              Sessions
            </Link>
          )}
          <button
            onClick={toggleMute}
            className="text-[#555] hover:text-[#C5A880] transition-colors text-sm"
            aria-label={muted ? "Unmute" : "Mute"}
          >
            {muted ? "🔇" : "🔊"}
          </button>
        </div>
      </div>
    </header>
  );
}
