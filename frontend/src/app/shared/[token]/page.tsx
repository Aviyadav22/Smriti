"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { getSharedMemo } from "@/lib/api";
import { Loader2 } from "lucide-react";
import type { ResearchFootnote } from "@/lib/types";

interface SharedMemoData {
    title: string;
    memo: string;
    footnotes: unknown[];
    confidence: number | null;
    agent_type: string;
}

export default function SharedMemoPage() {
    const params = useParams();
    const token = params.token as string;

    const [data, setData] = useState<SharedMemoData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        if (!token) return;
        setLoading(true);
        getSharedMemo(token)
            .then((result) => {
                setData(result);
                setError(false);
            })
            .catch(() => {
                setError(true);
            })
            .finally(() => {
                setLoading(false);
            });
    }, [token]);

    return (
        <div className="min-h-screen bg-background flex flex-col">
            <header className="border-b border-border bg-card px-6 py-4">
                <h1 className="text-lg font-semibold text-foreground">
                    NeetiQ — Shared Research Memo
                </h1>
            </header>

            <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8">
                {loading && (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                )}

                {error && !loading && (
                    <Card className="max-w-md mx-auto mt-16">
                        <CardContent className="pt-6 text-center space-y-2">
                            <h2 className="text-lg font-semibold text-foreground">
                                Memo Not Found
                            </h2>
                            <p className="text-sm text-muted-foreground">
                                This memo may have been revoked, expired, or the link is invalid.
                            </p>
                        </CardContent>
                    </Card>
                )}

                {data && !loading && !error && (
                    <div className="space-y-4">
                        {data.title && (
                            <h2 className="text-xl font-bold text-foreground">
                                {data.title}
                            </h2>
                        )}
                        <AgentMemoViewer
                            content={data.memo}
                            confidence={data.confidence ?? undefined}
                            maxFootnote={
                                Array.isArray(data.footnotes) ? data.footnotes.length : undefined
                            }
                            footnotes={data.footnotes as ResearchFootnote[]}
                        />
                    </div>
                )}
            </main>

            <footer className="border-t border-border bg-card px-6 py-4 text-center">
                <p className="text-xs text-muted-foreground">
                    Powered by NeetiQ — AI Legal Research for India
                </p>
            </footer>
        </div>
    );
}
