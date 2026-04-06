"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Languages } from "lucide-react";

interface LanguageToggleProps {
    /** When true, show only the Globe icon (for collapsed sidebar). Default false. */
    compact?: boolean;
}

export function LanguageToggle({ compact = false }: LanguageToggleProps) {
    const [locale, setLocaleState] = useState(() => {
        if (typeof document !== "undefined") {
            const match = document.cookie.match(/(?:^|; )locale=([^;]*)/);
            return match ? match[1] : "en";
        }
        return "en";
    });

    const toggleLocale = () => {
        const newLocale = locale === "en" ? "hi" : "en";
        document.cookie = `locale=${newLocale}; path=/; max-age=${60 * 60 * 24 * 365}`;
        setLocaleState(newLocale);
        window.location.reload();
    };

    const label = locale === "en" ? "Switch to Hindi" : "Switch to English";
    const shortLabel = locale === "en" ? "HI" : "EN";

    if (compact) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent"
                        onClick={toggleLocale}
                        aria-label={label}
                    >
                        <Languages className="h-4.5 w-4.5" />
                    </Button>
                </TooltipTrigger>
                <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
        );
    }

    return (
        <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start h-9 px-3 gap-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent"
            onClick={toggleLocale}
            title={label}
        >
            <Globe className="h-4 w-4 shrink-0" />
            <span>{shortLabel} - {locale === "en" ? "English" : "हिन्दी"}</span>
        </Button>
    );
}
