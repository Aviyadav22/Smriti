interface CertificateProps {
  userName: string;
  completedAt: string;
  scores: { session: number; score: number; total: number }[];
}

export function Certificate({ userName, completedAt, scores }: CertificateProps) {
  const formattedDate = new Date(completedAt).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div
      className="relative mx-auto max-w-xl rounded-lg p-[2px]"
      style={{
        background: "linear-gradient(135deg, #C5A880, #E8D5B5, #B89A6C, #C5A880)",
      }}
    >
      <div className="rounded-lg bg-[#1A1A1A] px-8 py-10 sm:px-12 sm:py-14">
        {/* Header */}
        <p
          className="text-center text-sm font-semibold tracking-[0.3em] uppercase"
          style={{ color: "#C5A880" }}
        >
          NeetiQ
        </p>

        <div className="my-6 h-px bg-[#2A2A2A]" />

        {/* Title */}
        <h2
          className="text-center font-[Georgia] text-2xl sm:text-3xl"
          style={{ color: "#C5A880" }}
        >
          Certificate of Completion
        </h2>

        <div className="my-6 h-px bg-[#2A2A2A]" />

        {/* Body */}
        <p className="text-center text-[#E0E0E0] leading-relaxed">
          This certifies that{" "}
          <span className="font-semibold" style={{ color: "#C5A880" }}>
            {userName}
          </span>{" "}
          has completed the Smriti Platform Tour
        </p>

        <p className="mt-2 text-center text-sm text-[#666666]">{formattedDate}</p>

        {/* Scores */}
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {scores.map((s) => (
            <div
              key={s.session}
              className="rounded-md border border-[#2A2A2A] bg-[#0A0A0A] px-3 py-3 text-center"
            >
              <p className="text-xs text-[#666666]">Session {s.session}</p>
              <p className="mt-1 text-lg font-semibold" style={{ color: "#C5A880" }}>
                {s.score}/{s.total}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-8 h-px bg-[#2A2A2A]" />

        {/* Footer */}
        <p className="mt-4 text-center text-xs text-[#666666]">
          Powered by NeetiQ
        </p>
      </div>
    </div>
  );
}
