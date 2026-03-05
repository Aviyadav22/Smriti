import Link from "next/link";
import { Scale } from "lucide-react";

export function Footer() {
    return (
        <footer className="border-t bg-card/50">
            <div className="mx-auto max-w-7xl px-4 py-6">
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                        <Scale className="h-3.5 w-3.5 text-[var(--gold)]" />
                        <span className="text-xs font-medium font-[family-name:var(--font-lora)]">Smriti</span>
                        <span className="text-[11px] text-muted-foreground">— AI Legal Research</span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                        <span>Judgment data from public records</span>
                        <span className="text-border">·</span>
                        <Link href="https://creativecommons.org/licenses/by/4.0/" className="hover:text-foreground" target="_blank" rel="noopener">
                            CC-BY-4.0
                        </Link>
                    </div>
                </div>
                <p className="mt-3 text-center text-[10px] text-muted-foreground/60 leading-relaxed">
                    AI-assisted legal research — not legal advice. Verify all citations and consult a qualified advocate.
                </p>
            </div>
        </footer>
    );
}
