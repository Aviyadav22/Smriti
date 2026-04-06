"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    getUserPreferences,
    updateUserPreferences,
    refreshUserPreferences,
} from "@/lib/api";

const SEARCH_MODES = ["semantic", "keyword", "hybrid"] as const;
const CITATION_FORMATS = ["standard", "oscola", "bluebook"] as const;
const RESULTS_OPTIONS = [10, 20, 50] as const;

export function PreferencesSection() {
    const t = useTranslations("settings.preferences");
    const [prefs, setPrefs] = useState<Record<string, unknown>>({});
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
    const [dirty, setDirty] = useState(false);

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
                search_mode: prefs.search_mode,
                citation_format: prefs.citation_format,
                results_per_page: prefs.results_per_page,
                preferred_jurisdictions: prefs.preferred_jurisdictions,
                preferred_courts: prefs.preferred_courts,
                common_case_types: prefs.common_case_types,
                frequent_acts: prefs.frequent_acts,
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

    const handleRefresh = useCallback(async () => {
        setRefreshing(true);
        try {
            const refreshed = await refreshUserPreferences();
            setPrefs(refreshed);
            setDirty(false);
            setMsg({ type: "success", text: t("refreshed") });
        } catch (err) {
            setMsg({ type: "error", text: err instanceof Error ? err.message : t("refreshFailed") });
        } finally {
            setRefreshing(false);
        }
    }, [t]);

    if (loading) {
        return <div className="space-y-4 animate-pulse"><div className="h-6 w-48 bg-muted rounded" /><div className="h-10 w-full bg-muted rounded" /><div className="h-10 w-full bg-muted rounded" /></div>;
    }

    const jurisdictions = (prefs.preferred_jurisdictions as string[]) ?? [];
    const courts = (prefs.preferred_courts as string[]) ?? [];
    const caseTypes = (prefs.common_case_types as string[]) ?? [];
    const acts = (prefs.frequent_acts as string[]) ?? [];

    return (
        <div className="space-y-8">
            <div className="flex items-start justify-between">
                <div>
                    <h2 className="text-lg font-semibold">{t("title")}</h2>
                    <p className="text-sm text-muted-foreground">{t("description")}</p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefresh}
                    disabled={refreshing}
                    className="gap-1.5"
                >
                    <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
                    {t("autoRefresh")}
                </Button>
            </div>

            {/* Search Mode */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("searchMode")}</label>
                <Select
                    value={(prefs.search_mode as string) ?? "hybrid"}
                    onValueChange={(v) => updateField("search_mode", v)}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {SEARCH_MODES.map((mode) => (
                            <SelectItem key={mode} value={mode}>
                                {t(`searchModes.${mode}`)}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Citation Format */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("citationFormat")}</label>
                <Select
                    value={(prefs.citation_format as string) ?? "standard"}
                    onValueChange={(v) => updateField("citation_format", v)}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {CITATION_FORMATS.map((fmt) => (
                            <SelectItem key={fmt} value={fmt}>
                                {t(`citationFormats.${fmt}`)}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Results Per Page */}
            <div className="space-y-2">
                <label className="text-sm font-medium">{t("resultsPerPage")}</label>
                <Select
                    value={String((prefs.results_per_page as number) ?? 20)}
                    onValueChange={(v) => updateField("results_per_page", Number(v))}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {RESULTS_OPTIONS.map((n) => (
                            <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Preferred Jurisdictions */}
            <TagField
                label={t("jurisdictions")}
                helpText={t("jurisdictionsHelp")}
                values={jurisdictions}
                onChange={(v) => updateField("preferred_jurisdictions", v)}
            />

            {/* Preferred Courts */}
            <TagField
                label={t("courts")}
                helpText={t("courtsHelp")}
                values={courts}
                onChange={(v) => updateField("preferred_courts", v)}
            />

            {/* Case Types */}
            <TagField
                label={t("caseTypes")}
                helpText={t("caseTypesHelp")}
                values={caseTypes}
                onChange={(v) => updateField("common_case_types", v)}
            />

            {/* Frequent Acts */}
            <TagField
                label={t("acts")}
                helpText={t("actsHelp")}
                values={acts}
                onChange={(v) => updateField("frequent_acts", v)}
            />

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

function TagField({
    label,
    helpText,
    values,
    onChange,
}: {
    label: string;
    helpText: string;
    values: string[];
    onChange: (v: string[]) => void;
}) {
    const [input, setInput] = useState("");

    const handleAdd = () => {
        const trimmed = input.trim();
        if (trimmed && !values.includes(trimmed)) {
            onChange([...values, trimmed]);
        }
        setInput("");
    };

    const handleRemove = (idx: number) => {
        onChange(values.filter((_, i) => i !== idx));
    };

    return (
        <div className="space-y-2">
            <label className="text-sm font-medium">{label}</label>
            <div className="flex gap-2">
                <Input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleAdd(); } }}
                    placeholder={helpText}
                    className="flex-1"
                />
                <Button variant="outline" size="sm" onClick={handleAdd} type="button">
                    Add
                </Button>
            </div>
            {values.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-1">
                    {values.map((v, i) => (
                        <span
                            key={i}
                            className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-xs font-medium"
                        >
                            {v}
                            <button
                                onClick={() => handleRemove(i)}
                                className="ml-0.5 text-muted-foreground hover:text-foreground"
                                type="button"
                            >
                                &times;
                            </button>
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}
