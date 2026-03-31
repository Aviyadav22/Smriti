import { Link } from "react-router-dom";

interface Props {
  sessionId: number;
  sessionTitle: string;
  sessionDay: string;
}

export function SessionLock({ sessionId, sessionTitle, sessionDay }: Props) {
  return (
    <div className="min-h-screen flex items-center justify-center pt-14 pb-10">
      <div className="text-center max-w-md px-6">
        <div className="text-6xl mb-6 opacity-30">{"\uD83D\uDD12"}</div>
        <p className="text-[0.625rem] font-mono text-[#6B6B6B] uppercase tracking-widest mb-2">
          {sessionDay}
        </p>
        <h1 className="text-3xl font-[Georgia] text-[#E8E8E8] mb-4">
          Session {sessionId}: {sessionTitle}
        </h1>
        <p className="text-[#6B6B6B] mb-8">
          Complete Session {sessionId - 1} quiz to unlock this session.
        </p>
        <Link
          to={`/session/${sessionId - 1}`}
          className="inline-block border border-[#C5A880]/40 text-[#C5A880] px-6 py-2.5 text-sm font-mono uppercase tracking-wider hover:bg-[#C5A880]/10 transition-colors"
        >
          {"\u2190"} Back to Session {sessionId - 1}
        </Link>
      </div>
    </div>
  );
}
