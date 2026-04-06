"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
    getUserProfile,
    updateUserProfile,
    changePassword,
} from "@/lib/api";
import type { UserProfile } from "@/lib/types";

export function ProfileSection() {
    const t = useTranslations("settings.profile");
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [loading, setLoading] = useState(true);

    // Name editing
    const [name, setName] = useState("");
    const [nameSaving, setNameSaving] = useState(false);
    const [nameMsg, setNameMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

    // Password change
    const [currentPw, setCurrentPw] = useState("");
    const [newPw, setNewPw] = useState("");
    const [confirmPw, setConfirmPw] = useState("");
    const [pwSaving, setPwSaving] = useState(false);
    const [pwMsg, setPwMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

    // Delete account
    const [deleteConfirm, setDeleteConfirm] = useState("");
    const [deleting, setDeleting] = useState(false);

    useEffect(() => {
        getUserProfile()
            .then((p) => {
                setProfile(p);
                setName(p.name ?? "");
            })
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    const handleNameSave = useCallback(async () => {
        if (!name.trim()) return;
        setNameSaving(true);
        setNameMsg(null);
        try {
            const updated = await updateUserProfile({ name: name.trim() });
            setProfile(updated);
            setNameMsg({ type: "success", text: t("nameSaved") });
        } catch (err) {
            setNameMsg({ type: "error", text: err instanceof Error ? err.message : t("saveFailed") });
        } finally {
            setNameSaving(false);
        }
    }, [name, t]);

    const handlePasswordChange = useCallback(async () => {
        setPwMsg(null);
        if (newPw !== confirmPw) {
            setPwMsg({ type: "error", text: t("passwordMismatch") });
            return;
        }
        if (newPw.length < 8) {
            setPwMsg({ type: "error", text: t("passwordTooShort") });
            return;
        }
        setPwSaving(true);
        try {
            await changePassword({ current_password: currentPw, new_password: newPw });
            setPwMsg({ type: "success", text: t("passwordChanged") });
            setCurrentPw("");
            setNewPw("");
            setConfirmPw("");
        } catch (err) {
            setPwMsg({ type: "error", text: err instanceof Error ? err.message : t("saveFailed") });
        } finally {
            setPwSaving(false);
        }
    }, [currentPw, newPw, confirmPw, t]);

    const handleDeleteAccount = useCallback(async () => {
        if (deleteConfirm !== "DELETE") return;
        setDeleting(true);
        try {
            const { deleteAccount } = await import("@/lib/api");
            await deleteAccount();
            window.location.href = "/login";
        } catch {
            setDeleting(false);
        }
    }, [deleteConfirm]);

    if (loading) {
        return <ProfileSkeleton />;
    }

    const nameIsDirty = name.trim() !== (profile?.name ?? "");

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-lg font-semibold">{t("title")}</h2>
                <p className="text-sm text-muted-foreground">{t("description")}</p>
            </div>

            {/* Name */}
            <div className="space-y-3">
                <label className="text-sm font-medium">{t("displayName")}</label>
                <Input
                    value={name}
                    onChange={(e) => { setName(e.target.value); setNameMsg(null); }}
                    placeholder={t("namePlaceholder")}
                    maxLength={255}
                />
                {nameMsg && (
                    <p className={`text-sm ${nameMsg.type === "success" ? "text-green-600" : "text-destructive"}`}>
                        {nameMsg.text}
                    </p>
                )}
                {nameIsDirty && (
                    <Button onClick={handleNameSave} disabled={nameSaving} size="sm">
                        {nameSaving ? t("saving") : t("saveChanges")}
                    </Button>
                )}
            </div>

            {/* Email (read-only) */}
            <div className="space-y-3">
                <label className="text-sm font-medium">{t("email")}</label>
                <Input value={profile?.email ?? ""} disabled className="bg-muted" />
                <p className="text-xs text-muted-foreground">{t("emailReadOnly")}</p>
            </div>

            {/* Role */}
            <div className="space-y-3">
                <label className="text-sm font-medium">{t("role")}</label>
                <Input value={profile?.role ?? ""} disabled className="bg-muted capitalize" />
            </div>

            <Separator />

            {/* Password Change */}
            <div className="space-y-4">
                <h3 className="text-base font-semibold">{t("changePassword")}</h3>
                <div className="space-y-3">
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">{t("currentPassword")}</label>
                        <Input
                            type="password"
                            value={currentPw}
                            onChange={(e) => { setCurrentPw(e.target.value); setPwMsg(null); }}
                        />
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">{t("newPassword")}</label>
                        <Input
                            type="password"
                            value={newPw}
                            onChange={(e) => { setNewPw(e.target.value); setPwMsg(null); }}
                        />
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">{t("confirmPassword")}</label>
                        <Input
                            type="password"
                            value={confirmPw}
                            onChange={(e) => { setConfirmPw(e.target.value); setPwMsg(null); }}
                        />
                    </div>
                </div>
                {pwMsg && (
                    <p className={`text-sm ${pwMsg.type === "success" ? "text-green-600" : "text-destructive"}`}>
                        {pwMsg.text}
                    </p>
                )}
                <Button
                    onClick={handlePasswordChange}
                    disabled={pwSaving || !currentPw || !newPw || !confirmPw}
                    size="sm"
                >
                    {pwSaving ? t("saving") : t("updatePassword")}
                </Button>
            </div>

            <Separator />

            {/* Danger Zone */}
            <div className="space-y-4 rounded-lg border border-destructive/30 p-4">
                <h3 className="text-base font-semibold text-destructive">{t("dangerZone")}</h3>
                <p className="text-sm text-muted-foreground">{t("deleteWarning")}</p>
                <div className="space-y-2">
                    <label className="text-sm font-medium">{t("typeDelete")}</label>
                    <Input
                        value={deleteConfirm}
                        onChange={(e) => setDeleteConfirm(e.target.value)}
                        placeholder="DELETE"
                        className="max-w-xs"
                    />
                </div>
                <Button
                    variant="destructive"
                    onClick={handleDeleteAccount}
                    disabled={deleteConfirm !== "DELETE" || deleting}
                    size="sm"
                >
                    {deleting ? t("deleting") : t("deleteAccount")}
                </Button>
            </div>
        </div>
    );
}

function ProfileSkeleton() {
    return (
        <div className="space-y-6 animate-pulse">
            <div className="h-6 w-48 bg-muted rounded" />
            <div className="h-4 w-72 bg-muted rounded" />
            <div className="h-10 w-full bg-muted rounded" />
            <div className="h-10 w-full bg-muted rounded" />
            <div className="h-10 w-full bg-muted rounded" />
        </div>
    );
}
