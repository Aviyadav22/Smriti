"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Globe } from "lucide-react";

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
                        size="sm"
                        className="w-full justify-center h-9 px-2"
                        onClick={toggleLocale}
                        aria-label={label}
                    >
                        <Globe className="h-4 w-4" />
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
