"use client";

import { useTranslations } from "next-intl";
import { AgentHubCard } from "@/components/agent-hub-card";
import { Search, FileText, History, Scale, PenTool } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function AgentsPage() {
    const t = useTranslations("agents");

    return (
        <div className="mx-auto max-w-4xl px-4 py-8">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-semibold font-[family-name:var(--font-lora)]">
                        {t("title")}
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {t("subtitle")}
                    </p>
                </div>
                <Button variant="outline" size="sm" asChild>
                    <Link href="/agents/history">
                        <History className="h-3.5 w-3.5 mr-1.5" /> {t("history")}
                    </Link>
                </Button>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                <AgentHubCard
                    title={t("research.title")}
                    description={t("research.description")}
                    icon={<Search className="h-6 w-6" />}
                    href="/agents/research"
                />
                <AgentHubCard
                    title={t("casePrep.title")}
                    description={t("casePrep.description")}
                    icon={<FileText className="h-6 w-6" />}
                    href="/agents/case-prep"
                    badge={t("requiresDocument")}
                />
                <AgentHubCard
                    title={t("strategy.title")}
                    description={t("strategy.description")}
                    icon={<Scale className="h-6 w-6" />}
                    href="/agents/strategy"
                />
                <AgentHubCard
                    title={t("drafting.title")}
                    description={t("drafting.description")}
                    icon={<PenTool className="h-6 w-6" />}
                    href="/agents/drafting"
                />
            </div>
        </div>
    );
}
