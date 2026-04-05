"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Card } from "@/components/ui/card";
import { Search, FileText, Scale, PenTool, ArrowRight, History } from "lucide-react";
import { Button } from "@/components/ui/button";

function getGreeting(): string {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return "Good morning";
    if (hour >= 12 && hour < 17) return "Good afternoon";
    if (hour >= 17 && hour < 21) return "Good evening";
    return "Still at it";
}

const TAGLINES = [
    "What case are you building today?",
    "Ready to strengthen your arguments?",
    "Let's find that precedent.",
    "Your research companion awaits.",
    "Time to build your case.",
];

const AGENTS = [
    {
        key: "research" as const,
        href: "/agents/research",
        icon: Search,
        color: "text-blue-600 dark:text-blue-400",
        bgColor: "bg-blue-50 dark:bg-blue-950/30",
    },
    {
        key: "casePrep" as const,
        href: "/agents/case-prep",
        icon: FileText,
        color: "text-emerald-600 dark:text-emerald-400",
        bgColor: "bg-emerald-50 dark:bg-emerald-950/30",
    },
    {
        key: "strategy" as const,
        href: "/agents/strategy",
        icon: Scale,
        color: "text-amber-600 dark:text-amber-400",
        bgColor: "bg-amber-50 dark:bg-amber-950/30",
    },
    {
        key: "drafting" as const,
        href: "/agents/drafting",
        icon: PenTool,
        color: "text-purple-600 dark:text-purple-400",
        bgColor: "bg-purple-50 dark:bg-purple-950/30",
    },
];

export default function DashboardPage() {
    const t = useTranslations("agents");
    const [greeting, setGreeting] = useState("Welcome");
    const tagline = useMemo(() => TAGLINES[Math.floor(Math.random() * TAGLINES.length)], []);

    useEffect(() => {
        setGreeting(getGreeting());
    }, []);

    return (
        <div className="flex flex-col items-center justify-center min-h-full px-4 py-12">
            {/* Greeting */}
            <div className="text-center mb-10 max-w-2xl">
                <h1 className="text-3xl md:text-4xl font-semibold font-[family-name:var(--font-lora)] tracking-tight">
                    {greeting}, <span className="text-[var(--gold)]">Counsellor</span>
                </h1>
                <p className="text-muted-foreground mt-3 text-base">
                    {tagline}
                </p>
            </div>

            {/* Agent Cards — 2x2 grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-2xl">
                {AGENTS.map((agent) => {
                    const Icon = agent.icon;
                    return (
                        <Link key={agent.key} href={agent.href}>
                            <Card className="group relative flex items-center gap-4 p-5 border border-border/60 hover:border-[var(--gold)]/40 hover:shadow-sm transition-all duration-200 cursor-pointer">
                                <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${agent.bgColor}`}>
                                    <Icon className={`h-5 w-5 ${agent.color}`} />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <h3 className="text-sm font-semibold">{t(`${agent.key}.title`)}</h3>
                                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                                        {t(`${agent.key}.description`)}
                                    </p>
                                </div>
                                <ArrowRight className="h-4 w-4 text-muted-foreground/50 group-hover:text-[var(--gold)] transition-colors shrink-0" />
                            </Card>
                        </Link>
                    );
                })}
            </div>

            {/* Quick links */}
            <div className="flex items-center gap-3 mt-8">
                <Button variant="ghost" size="sm" className="text-xs text-muted-foreground" asChild>
                    <Link href="/agents/history">
                        <History className="h-3.5 w-3.5 mr-1.5" />
                        View session history
                    </Link>
                </Button>
            </div>
        </div>
    );
}
