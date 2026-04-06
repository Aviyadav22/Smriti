"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
    const { theme, setTheme } = useTheme();
    const [mounted, setMounted] = useState(false);

    useEffect(() => setMounted(true), []);

    if (!mounted) {
        return (
            <Button variant="ghost" size="icon" className="h-9 w-9" disabled>
                <Sun className="h-4.5 w-4.5" />
            </Button>
        );
    }

    const isDark = theme === "dark";

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent"
                    onClick={() => setTheme(isDark ? "light" : "dark")}
                    aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
                >
                    {isDark ? (
                        <Sun className="h-4.5 w-4.5" />
                    ) : (
                        <Moon className="h-4.5 w-4.5" />
                    )}
                </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
                {isDark ? "Light mode" : "Dark mode"}
            </TooltipContent>
        </Tooltip>
    );
}
