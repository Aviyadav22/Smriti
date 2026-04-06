export default function PublicLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-background px-4">
            <div className="w-full max-w-sm">
                {children}
            </div>
            <p className="text-[10px] text-muted-foreground mt-8 text-center max-w-md">
                AI-assisted legal research — not legal advice. Verify all citations and consult a qualified advocate.
            </p>
        </div>
    );
}
