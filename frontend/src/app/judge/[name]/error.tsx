"use client";

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    return (
        <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-8">
            <h2 className="text-xl font-semibold text-destructive">Failed to load judge profile</h2>
            <p className="text-muted-foreground text-sm">{error.message || "An unexpected error occurred."}</p>
            <button
                onClick={reset}
                className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
            >
                Try again
            </button>
        </div>
    );
}
