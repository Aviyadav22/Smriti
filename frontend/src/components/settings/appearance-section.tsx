"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { getUserPreferences, updateUserPreferences } from "@/lib/api";

const FONT_SIZES = ["small", "medium", "large"] as const;

const THEME_OPTIONS = [
    { value: "light", icon: Sun },
    { value: "dark", icon: Moon },
    { value: "system", icon: Monitor },
] as const;

export function AppearanceSection() {
    const t = useTranslations("settings.appearance");
    const { theme, setTheme } = useTheme();
    const [fontSize, setFontSize] = useState("medium");
    const [language, setLanguage] = useState("en");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

    useEffect(() => {
        getUserPreferences()
            .then((prefs) => {
                if (prefs.font_size) setFontSize(prefs.font_size as string);
                if (prefs.language) setLanguage(prefs.language as string);
            })
            .catch(() => {})
            .finally(() => setLoading(false));

        // Read current locale from cookie
        const match = document.cookie.match(/(?:^|;\s*)locale=([^;]*)/);
        if (match) setLanguage(match[1]);
    }, []);

    const handleThemeChange = useCallback((value: string) => {
        setTheme(value);
        // Also persist to backend preferences
        updateUserPreferences({ theme: value }).catch(() => {});
    }, [setTheme]);

    const handleFontSizeChange = useCallback(async (value: string) => {
        setFontSize(value);
        // Apply CSS variable immediately
        const sizes = { small: "14px", medium: "16px", large: "18px" };
        document.documentElement.style.setProperty(
            "--app-font-size",
            sizes[value as keyof typeof sizes] ?? "16px",
        );
        try {
            await updateUserPreferences({ font_size: value });
        } catch {
            // Ignore — applied locally regardless
        }
    }, []);

    const handleLanguageChange = useCallback(async (value: string) => {
        setSaving(true);
        setMsg(null);
        try {
            await updateUserPreferences({ language: value });
            // Set cookie and reload (same mechanism as LanguageToggle)
            document.cookie = `locale=${value};path=/;max-age=31536000`;
            window.location.reload();
        } catch (err) {
            setMsg({ type: "error", text: err instanceof Error ? err.message : t("saveFailed") });
            setSaving(false);
        }
    }, [t]);

    if (loading) {
        return <div className="space-y-4 animate-pulse"><div className="h-6 w-48 bg-muted rounded" /><div className="h-10 w-full bg-muted rounded" /></div>;
    }

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-lg font-semibold">{t("title")}</h2>
                <p className="text-sm text-muted-foreground">{t("description")}</p>
            </div>

            {/* Theme */}
            <div className="space-y-3">
                <label className="text-sm font-medium">{t("theme")}</label>
                <div className="flex gap-2">
                    {THEME_OPTIONS.map(({ value, icon: Icon }) => (
                        <button
                            key={value}
                            onClick={() => handleThemeChange(value)}
                            className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm transition-colors ${
                                theme === value
                                    ? "border-primary bg-primary/5 text-foreground"
                                    : "border-border text-muted-foreground hover:border-primary/50"
                            }`}
                        >
                            <Icon className="h-4 w-4" />
                            {t(`themes.${value}`)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Language */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("language")}</label>
                <Select value={language} onValueChange={handleLanguageChange} disabled={saving}>
                    <SelectTrigger className="w-full">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="en">English</SelectItem>
                        <SelectItem value="hi">हिन्दी (Hindi)</SelectItem>
                    </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{t("languageNote")}</p>
            </div>

            {/* Font Size */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("fontSize")}</label>
                <Select value={fontSize} onValueChange={handleFontSizeChange}>
                    <SelectTrigger className="w-full">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {FONT_SIZES.map((size) => (
                            <SelectItem key={size} value={size}>
                                {t(`fontSizes.${size}`)}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {msg && (
                <p className={`text-sm ${msg.type === "success" ? "text-green-600" : "text-destructive"}`}>
                    {msg.text}
                </p>
            )}
        </div>
    );
}
