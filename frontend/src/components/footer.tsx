"use client";

import Link from "next/link";
import { Scale } from "lucide-react";
import { useTranslations } from "next-intl";

export function Footer() {
    const t = useTranslations("footer");

    return (
        <footer className="border-t bg-card/50">
            <div className="mx-auto max-w-7xl px-4 py-6">
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                        <Scale className="h-3.5 w-3.5 text-[var(--gold)]" />
                        <span className="text-xs font-medium font-[family-name:var(--font-lora)]">Smriti</span>
                        <span className="text-[11px] text-muted-foreground">— {t("tagline")}</span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                        <span>{t("dataSource")}</span>
                        <span className="text-border">·</span>
                        <Link href="https://creativecommons.org/licenses/by/4.0/" className="hover:text-foreground" target="_blank" rel="noopener noreferrer">
                            CC-BY-4.0
                        </Link>
                        <span className="text-border">·</span>
                        <Link href="/privacy" className="hover:text-foreground">
                            Privacy
                        </Link>
                        <span className="text-border">·</span>
                        <Link href="/terms" className="hover:text-foreground">
                            Terms
                        </Link>
                        <span className="text-border">·</span>
                        <Link href="/about" className="hover:text-foreground">
                            About
                        </Link>
                    </div>
                </div>
                <p className="mt-3 text-center text-[10px] text-muted-foreground/60 leading-relaxed">
                    {t("disclaimer")}
                </p>
            </div>
        </footer>
    );
}
