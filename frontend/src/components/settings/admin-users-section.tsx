"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { getAdminUsers, updateAdminUser } from "@/lib/api";
import type { AdminUserSummary } from "@/lib/types";

const ROLES = ["admin", "researcher", "viewer"] as const;

export function AdminUsersSection() {
    const t = useTranslations("settings.adminUsers");
    const [users, setUsers] = useState<AdminUserSummary[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [roleFilter, setRoleFilter] = useState<string>("");
    const [loading, setLoading] = useState(true);
    const [updatingId, setUpdatingId] = useState<string | null>(null);
    const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

    const fetchUsers = useCallback(async (p: number, s: string, r: string) => {
        setLoading(true);
        try {
            const res = await getAdminUsers(p, 20, s || undefined, r || undefined);
            setUsers(res.users);
            setTotal(res.total);
        } catch {
            setUsers([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchUsers(page, search, roleFilter);
    }, [page, fetchUsers]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleSearch = () => {
        setPage(1);
        fetchUsers(1, search, roleFilter);
    };

    const handleRoleChange = async (userId: string, newRole: string) => {
        setUpdatingId(userId);
        setMsg(null);
        try {
            const updated = await updateAdminUser(userId, { role: newRole });
            setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
            setMsg({ type: "success", text: t("roleUpdated") });
        } catch (err) {
            setMsg({ type: "error", text: err instanceof Error ? err.message : t("updateFailed") });
        } finally {
            setUpdatingId(null);
        }
    };

    const handleToggleActive = async (userId: string, currentlyActive: boolean) => {
        setUpdatingId(userId);
        setMsg(null);
        try {
            const updated = await updateAdminUser(userId, { is_active: !currentlyActive });
            setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
            setMsg({ type: "success", text: currentlyActive ? t("userDeactivated") : t("userActivated") });
        } catch (err) {
            setMsg({ type: "error", text: err instanceof Error ? err.message : t("updateFailed") });
        } finally {
            setUpdatingId(null);
        }
    };

    const totalPages = Math.ceil(total / 20);

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-semibold">{t("title")}</h2>
                <p className="text-sm text-muted-foreground">{t("description")}</p>
            </div>

            {/* Search & Filters */}
            <div className="flex gap-2">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                        placeholder={t("searchPlaceholder")}
                        className="pl-9"
                    />
                </div>
                <Select value={roleFilter} onValueChange={(v) => { setRoleFilter(v === "all" ? "" : v); setPage(1); fetchUsers(1, search, v === "all" ? "" : v); }}>
                    <SelectTrigger className="w-36">
                        <SelectValue placeholder={t("allRoles")} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">{t("allRoles")}</SelectItem>
                        {ROLES.map((r) => (
                            <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <Button variant="outline" size="sm" onClick={handleSearch}>
                    {t("search")}
                </Button>
            </div>

            {msg && (
                <p className={`text-sm ${msg.type === "success" ? "text-green-600" : "text-destructive"}`}>
                    {msg.text}
                </p>
            )}

            {/* User Table */}
            {loading ? (
                <div className="space-y-3 animate-pulse">
                    {[1, 2, 3].map((i) => <div key={i} className="h-14 bg-muted rounded" />)}
                </div>
            ) : (
                <div className="rounded-lg border">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b bg-muted/50">
                                    <th className="px-4 py-3 text-left font-medium">{t("name")}</th>
                                    <th className="px-4 py-3 text-left font-medium">{t("email")}</th>
                                    <th className="px-4 py-3 text-left font-medium">{t("role")}</th>
                                    <th className="px-4 py-3 text-left font-medium">{t("status")}</th>
                                    <th className="px-4 py-3 text-left font-medium">{t("lastLogin")}</th>
                                    <th className="px-4 py-3 text-left font-medium">{t("actions")}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((u) => (
                                    <tr key={u.id} className="border-b last:border-b-0 hover:bg-muted/30">
                                        <td className="px-4 py-3">{u.name ?? "—"}</td>
                                        <td className="px-4 py-3 text-muted-foreground">{u.email}</td>
                                        <td className="px-4 py-3">
                                            <Select
                                                value={u.role}
                                                onValueChange={(v) => handleRoleChange(u.id, v)}
                                                disabled={updatingId === u.id}
                                            >
                                                <SelectTrigger className="w-28 h-8 text-xs">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {ROLES.map((r) => (
                                                        <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </td>
                                        <td className="px-4 py-3">
                                            <Badge variant={u.is_active ? "default" : "secondary"}>
                                                {u.is_active ? t("active") : t("inactive")}
                                            </Badge>
                                        </td>
                                        <td className="px-4 py-3 text-muted-foreground text-xs">
                                            {u.last_login_at
                                                ? new Date(u.last_login_at).toLocaleDateString()
                                                : "—"}
                                        </td>
                                        <td className="px-4 py-3">
                                            <Button
                                                variant={u.is_active ? "destructive" : "outline"}
                                                size="sm"
                                                className="text-xs h-7"
                                                onClick={() => handleToggleActive(u.id, u.is_active)}
                                                disabled={updatingId === u.id}
                                            >
                                                {u.is_active ? t("deactivate") : t("activate")}
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                                {users.length === 0 && (
                                    <tr>
                                        <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                                            {t("noUsers")}
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                        {t("showing", { from: (page - 1) * 20 + 1, to: Math.min(page * 20, total), total })}
                    </span>
                    <div className="flex gap-1">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1}
                        >
                            {t("previous")}
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                        >
                            {t("next")}
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
