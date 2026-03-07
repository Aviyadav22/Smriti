"use client";

import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AgentHubCard } from "@/components/agent-hub-card";
import { Search, FileText, History } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function AgentsPage() {
    const { isAuthenticated } = useAuth();
    const router = useRouter();

    useEffect(() => {
        if (!isAuthenticated) router.push("/login");
    }, [isAuthenticated, router]);

    if (!isAuthenticated) return null;

    return (
        <div className="mx-auto max-w-4xl px-4 py-8">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-semibold font-[family-name:var(--font-lora)]">
                        AI Agents
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Autonomous legal research and case preparation assistants
                    </p>
                </div>
                <Button variant="outline" size="sm" asChild>
                    <Link href="/agents/history">
                        <History className="h-3.5 w-3.5 mr-1.5" /> History
                    </Link>
                </Button>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
                <AgentHubCard
                    title="Research Agent"
                    description="Ask a legal question. The agent decomposes it into sub-queries, searches across case law in parallel, detects contradictions between holdings, and generates a structured research memo with citations."
                    icon={<Search className="h-6 w-6" />}
                    href="/agents/research"
                />
                <AgentHubCard
                    title="Case Prep Agent"
                    description="Select a previously analyzed document. The agent prioritizes issues by legal strength, performs deeper precedent searches through citation graphs, and generates a strategy memo with recommended argument ordering."
                    icon={<FileText className="h-6 w-6" />}
                    href="/agents/case-prep"
                    badge="Requires uploaded document"
                />
            </div>
        </div>
    );
}
