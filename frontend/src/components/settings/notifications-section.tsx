"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { getUserPreferences, updateUserPreferences } from "@/lib/api";

const VERBOSITY_OPTIONS = ["concise", "detailed", "comprehensive"] as const;
const VOICE_OPTIONS = ["male", "female"] as const;
const LANGUAGE_OPTIONS = [
    { value: "en", label: "English" },
    { value: "hi", label: "हिन्दी (Hindi)" },
] as const;

export function NotificationsSection() {
    const t = useTranslations("settings.notifications");
    const [prefs, setPrefs] = useState<Record<string, unknown>>({});
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [dirty, setDirty] = useState(false);
    const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

    useEffect(() => {
        getUserPreferences()
            .then(setPrefs)
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    const updateField = useCallback((key: string, value: unknown) => {
        setPrefs((prev) => ({ ...prev, [key]: value }));
        setDirty(true);
        setMsg(null);
    }, []);

    const handleSave = useCallback(async () => {
        setSaving(true);
        setMsg(null);
        try {
            const updated = await updateUserPreferences({
                email_alerts: prefs.email_alerts,
                agent_verbosity: prefs.agent_verbosity,
                tts_voice: prefs.tts_voice,
                tts_language: prefs.tts_language,
                response_language: prefs.response_language,
            });
            setPrefs(updated);
            setDirty(false);
            setMsg({ type: "success", text: t("saved") });
        } catch (err) {
            setMsg({ type: "error", text: err instanceof Error ? err.message : t("saveFailed") });
        } finally {
            setSaving(false);
        }
    }, [prefs, t]);

    if (loading) {
        return <div className="space-y-4 animate-pulse"><div className="h-6 w-48 bg-muted rounded" /><div className="h-10 w-full bg-muted rounded" /></div>;
    }

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-lg font-semibold">{t("title")}</h2>
                <p className="text-sm text-muted-foreground">{t("description")}</p>
            </div>

            {/* Email Alerts */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("emailAlerts")}</label>
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => updateField("email_alerts", !(prefs.email_alerts as boolean))}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                            prefs.email_alerts ? "bg-primary" : "bg-muted"
                        }`}
                        role="switch"
                        aria-checked={!!prefs.email_alerts}
                    >
                        <span
                            className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                                prefs.email_alerts ? "translate-x-6" : "translate-x-1"
                            }`}
                        />
                    </button>
                    <span className="text-sm text-muted-foreground">
                        {prefs.email_alerts ? t("enabled") : t("disabled")}
                    </span>
                </div>
                <p className="text-xs text-muted-foreground">{t("emailAlertsHelp")}</p>
            </div>

            {/* Agent Verbosity */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("agentVerbosity")}</label>
                <Select
                    value={(prefs.agent_verbosity as string) ?? "detailed"}
                    onValueChange={(v) => updateField("agent_verbosity", v)}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {VERBOSITY_OPTIONS.map((opt) => (
                            <SelectItem key={opt} value={opt}>
                                {t(`verbosity.${opt}`)}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{t("verbosityHelp")}</p>
            </div>

            {/* TTS Voice */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("ttsVoice")}</label>
                <Select
                    value={(prefs.tts_voice as string) ?? "female"}
                    onValueChange={(v) => updateField("tts_voice", v)}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {VOICE_OPTIONS.map((opt) => (
                            <SelectItem key={opt} value={opt}>
                                {t(`voices.${opt}`)}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* TTS Language */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("ttsLanguage")}</label>
                <Select
                    value={(prefs.tts_language as string) ?? "en"}
                    onValueChange={(v) => updateField("tts_language", v)}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {LANGUAGE_OPTIONS.map(({ value, label }) => (
                            <SelectItem key={value} value={value}>{label}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Response Language */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("responseLanguage")}</label>
                <Select
                    value={(prefs.response_language as string) ?? "en"}
                    onValueChange={(v) => updateField("response_language", v)}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {LANGUAGE_OPTIONS.map(({ value, label }) => (
                            <SelectItem key={value} value={value}>{label}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{t("responseLanguageHelp")}</p>
            </div>

            {msg && (
                <p className={`text-sm ${msg.type === "success" ? "text-green-600" : "text-destructive"}`}>
                    {msg.text}
                </p>
            )}

            {dirty && (
                <Button onClick={handleSave} disabled={saving} size="sm">
                    {saving ? t("saving") : t("saveChanges")}
                </Button>
            )}
        </div>
    );
}
