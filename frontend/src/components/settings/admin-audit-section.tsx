"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { getAdminAuditLogs } from "@/lib/api";
import type { AuditLogEntry } from "@/lib/types";

const ACTION_TYPES = [
    "login.success",
    "login.failure",
    "user.registered",
    "token.refresh",
    "password.changed",
    "password.change_failed",
    "profile.updated",
    "account.deleted",
    "admin.user_updated",
] as const;

export function AdminAuditSection() {
    const t = useTranslations("settings.adminAudit");
    const [logs, setLogs] = useState<AuditLogEntry[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);

    // Filters
    const [actionFilter, setActionFilter] = useState("");
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");

    const fetchLogs = useCallback(async (p: number) => {
        setLoading(true);
        try {
            const filters: Record<string, string> = {};
            if (actionFilter && actionFilter !== "all") filters.action = actionFilter;
            if (dateFrom) filters.date_from = dateFrom;
            if (dateTo) filters.date_to = dateTo;
            const res = await getAdminAuditLogs(p, 50, Object.keys(filters).length > 0 ? filters : undefined);
            setLogs(res.logs);
            setTotal(res.total);
        } catch {
            setLogs([]);
        } finally {
            setLoading(false);
        }
    }, [actionFilter, dateFrom, dateTo]);

    useEffect(() => {
        fetchLogs(page);
    }, [page, fetchLogs]);

    const handleFilter = () => {
        setPage(1);
        fetchLogs(1);
    };

    const totalPages = Math.ceil(total / 50);

    const actionColor = (action: string): "default" | "secondary" | "destructive" => {
        if (action.includes("failure") || action.includes("failed") || action.includes("deleted")) return "destructive";
        if (action.includes("success") || action.includes("registered")) return "default";
        return "secondary";
    };

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-semibold">{t("title")}</h2>
                <p className="text-sm text-muted-foreground">{t("description")}</p>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-2">
                <Select value={actionFilter || "all"} onValueChange={(v) => setActionFilter(v === "all" ? "" : v)}>
                    <SelectTrigger className="w-48">
                        <SelectValue placeholder={t("allActions")} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">{t("allActions")}</SelectItem>
                        {ACTION_TYPES.map((a) => (
                            <SelectItem key={a} value={a}>{a}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <Input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    className="w-40"
                    placeholder={t("from")}
                />
                <Input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    className="w-40"
                    placeholder={t("to")}
                />
                <Button variant="outline" size="sm" onClick={handleFilter}>
                    {t("filter")}
                </Button>
            </div>

            {/* Audit Log Table */}
            {loading ? (
                <div className="space-y-3 animate-pulse">
                    {[1, 2, 3, 4, 5].map((i) => <div key={i} className="h-12 bg-muted rounded" />)}
                </div>
            ) : (
                <div className="rounded-lg border">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b bg-muted/50">
                                    <th className="px-4 py-3 text-left font-medium">{t("timestamp")}</th>
                                    <th className="px-4 py-3 text-left font-medium">{t("action")}</th>
                                    <th className="px-4 py-3 text-left font-medium">{t("user")}</th>
                                    <th className="px-4 py-3 text-left font-medium">{t("resource")}</th>
                                    <th className="px-4 py-3 text-left font-medium">{t("details")}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {logs.map((log) => (
                                    <tr key={log.id} className="border-b last:border-b-0 hover:bg-muted/30">
                                        <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                                            {new Date(log.created_at).toLocaleString()}
                                        </td>
                                        <td className="px-4 py-3">
                                            <Badge variant={actionColor(log.action)} className="text-xs">
                                                {log.action}
                                            </Badge>
                                        </td>
                                        <td className="px-4 py-3 text-muted-foreground text-xs">
                                            {log.user_email ?? log.user_id?.slice(0, 8) ?? "—"}
                                        </td>
                                        <td className="px-4 py-3 text-xs">
                                            {log.resource_type && (
                                                <span className="text-muted-foreground">
                                                    {log.resource_type}
                                                    {log.resource_id && ` / ${log.resource_id.slice(0, 8)}...`}
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3 text-xs text-muted-foreground max-w-[200px] truncate">
                                            {log.metadata ? JSON.stringify(log.metadata) : "—"}
                                        </td>
                                    </tr>
                                ))}
                                {logs.length === 0 && (
                                    <tr>
                                        <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                                            {t("noLogs")}
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
                        {t("showing", { from: (page - 1) * 50 + 1, to: Math.min(page * 50, total), total })}
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
