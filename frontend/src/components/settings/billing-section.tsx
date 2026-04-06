"use client";

import { useTranslations } from "next-intl";
import { CreditCard, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function BillingSection() {
    const t = useTranslations("settings.billing");

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-lg font-semibold">{t("title")}</h2>
                <p className="text-sm text-muted-foreground">{t("description")}</p>
            </div>

            {/* Current Plan */}
            <div className="rounded-lg border p-6 space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                            <CreditCard className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                            <h3 className="font-semibold">{t("freePlan")}</h3>
                            <p className="text-sm text-muted-foreground">{t("freePlanDescription")}</p>
                        </div>
                    </div>
                    <Badge variant="secondary">{t("currentPlan")}</Badge>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                    <UsageStat label={t("searches")} value="--" limit={t("unlimited")} />
                    <UsageStat label={t("agentRuns")} value="--" limit={t("unlimited")} />
                    <UsageStat label={t("documents")} value="--" limit={t("unlimited")} />
                </div>
            </div>

            {/* Upgrade CTA */}
            <div className="rounded-lg border border-primary/20 bg-primary/5 p-6 space-y-3">
                <h3 className="font-semibold">{t("upgradeTitle")}</h3>
                <p className="text-sm text-muted-foreground">{t("upgradeDescription")}</p>
                <Button className="gap-2" disabled>
                    {t("contactUs")}
                    <ExternalLink className="h-3.5 w-3.5" />
                </Button>
                <p className="text-xs text-muted-foreground">{t("comingSoon")}</p>
            </div>
        </div>
    );
}

function UsageStat({ label, value, limit }: { label: string; value: string; limit: string }) {
    return (
        <div className="space-y-1">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-xl font-semibold">{value}</p>
            <p className="text-xs text-muted-foreground">{limit}</p>
        </div>
    );
}
