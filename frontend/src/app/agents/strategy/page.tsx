"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import type { AgentStreamEvent, AgentStep } from "@/lib/types";
import { useAgentSession } from "@/hooks/useAgentSession";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { AgentSessionSidebar } from "@/components/agents/AgentSessionSidebar";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, ArrowLeft, RotateCcw, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import Link from "next/link";

const STRATEGY_STEPS = [
    "analyze_facts", "element_decomposition", "fetch_judge",
    "checkpoint_analysis", "search_precedents", "assess_strength",
    "generate_arguments_irac", "checkpoint_arguments",
    "adversarial_search", "counter_and_judge", "argument_ordering",
    "synthesize_strategy", "verify", "checkpoint_memo",
];

export default function StrategyAgentPage() {
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();

    const session = useAgentSession("strategy");
    const [sidebarOpen, setSidebarOpen] = useState(true);

    // Form inputs
    const [caseFacts, setCaseFacts] = useState("");
    const [desiredRelief, setDesiredRelief] = useState("");
    const [targetJudge, setTargetJudge] = useState("");
    const [targetBench, setTargetBench] = useState("");
    const [starting, setStarting] = useState(false);
    const [steps, setSteps] = useState<AgentStep[]>([]);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push("/login");
    }, [authLoading, isAuthenticated, router]);

    useEffect(() => {
        if (isAuthenticated) session.refreshSessions();
    }, [isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        const paramSessionId = searchParams.get("session");
        if (paramSessionId && isAuthenticated) session.loadSession(paramSessionId);
    }, [searchParams, isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleEvent = useCallback((event: AgentStreamEvent) => {
        switch (event.type) {
            case "status":
                setSteps((prev) =>
                    prev.map((s) => ({
                        ...s,
                        status: s.name === event.step ? "completed"
                            : STRATEGY_STEPS.indexOf(s.name) === STRATEGY_STEPS.indexOf(event.step!) + 1
                                ? "active" : s.status,
                        message: s.name === event.step ? event.message || s.message : s.message,
                    })),
                );
                break;
            case "checkpoint":
                session.setCheckpoint({ question: event.question || "", context: event.context || {} });
                session.setIsRunning(false);
                break;
            case "memo":
                session.setMemo(event.content || "");
                if (event.data && typeof event.data === "object" && "confidence" in (event.data as Record<string, unknown>)) {
                    session.setConfidence((event.data as Record<string, unknown>).confidence as number);
                }
                break;
            case "done":
                session.setIsRunning(false);
                session.refreshSessions();
                setSteps((prev) => prev.map((s) => ({
                    ...s, status: s.status === "active" || s.status === "pending" ? "completed" : s.status,
                })));
                break;
            case "error":
                session.setError(event.message || "Agent encountered an error");
                session.setIsRunning(false);
                break;
        }
    }, [session]);

    const handleSubmit = useCallback(() => {
        if (!caseFacts.trim() || !desiredRelief.trim() || starting) return;
        setStarting(true);
        setSteps(STRATEGY_STEPS.map((name, i) => ({
            name, status: i === 0 ? ("active" as const) : ("pending" as const),
        })));
        session.startSession({
            case_facts: caseFacts.trim(),
            desired_relief: desiredRelief.trim(),
            target_judge: targetJudge.trim() || "",
            target_bench: targetBench || "",
        }, handleEvent);
        setStarting(false);
    }, [caseFacts, desiredRelief, targetJudge, targetBench, starting, handleEvent, session]);

    const handleReset = useCallback(() => {
        session.newSession();
        setCaseFacts("");
        setDesiredRelief("");
        setTargetJudge("");
        setTargetBench("");
        setSteps([]);
    }, [session]);

    if (authLoading || !isAuthenticated) {
        return (
            <div className="min-h-screen flex flex-col">
                <Header />
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
            </div>
        );
    }

    const showInputForm = !session.isRunning && !session.memo && !session.checkpoint && steps.length === 0 && !session.isFollowUp;
    const showWorkspace = session.isRunning || session.memo || session.checkpoint || steps.length > 0 || session.isFollowUp;

    return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1 flex">
                <div className={cn(
                    "hidden md:flex flex-col transition-all duration-200",
                    sidebarOpen ? "w-64 min-w-[16rem]" : "w-0 min-w-0 overflow-hidden",
                )}>
                    <AgentSessionSidebar
                        sessions={session.sessions}
                        activeSessionId={session.sessionId}
                        onSelectSession={session.loadSession}
                        onDeleteSession={session.deleteSession}
                        onNewSession={handleReset}
                        loading={session.sessionsLoading}
                    />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="mx-auto max-w-6xl px-4 py-8">
                        <div className="flex items-center gap-3 mb-6">
                            <Button variant="ghost" size="sm" asChild>
                                <Link href="/agents"><ArrowLeft className="h-3.5 w-3.5 mr-1" /> Agents</Link>
                            </Button>
                            <Button variant="ghost" size="sm" className="hidden md:flex" onClick={() => setSidebarOpen((p) => !p)}>
                                {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
                            </Button>
                        </div>

                        <h1 className="text-2xl font-semibold font-[family-name:var(--font-lora)] mb-1">Argument Builder</h1>
                        <p className="text-sm text-muted-foreground mb-6">
                            Enter case facts and desired relief. The agent generates IRAC arguments with verified precedents.
                        </p>

                        {showInputForm && (
                            <Card>
                                <CardContent className="pt-6 space-y-4">
                                    <Textarea id="strategy-case-facts" placeholder="Describe the facts of your case..."
                                        value={caseFacts} onChange={(e) => setCaseFacts(e.target.value)} className="min-h-[120px] text-sm" />
                                    <Input id="strategy-desired-relief" placeholder="What relief are you seeking?"
                                        value={desiredRelief} onChange={(e) => setDesiredRelief(e.target.value)} />
                                    <div className="grid gap-4 sm:grid-cols-2">
                                        <Input id="strategy-target-judge" placeholder="Target judge name (optional)"
                                            value={targetJudge} onChange={(e) => setTargetJudge(e.target.value)} />
                                        <Select value={targetBench} onValueChange={setTargetBench}>
                                            <SelectTrigger id="strategy-target-bench" className="w-full">
                                                <SelectValue placeholder="Bench type (optional)" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="single">Single Bench</SelectItem>
                                                <SelectItem value="division">Division Bench</SelectItem>
                                                <SelectItem value="full">Full Bench</SelectItem>
                                                <SelectItem value="constitutional">Constitutional Bench</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <Button onClick={handleSubmit} disabled={starting || !caseFacts.trim() || !desiredRelief.trim()}>
                                        {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Build Arguments"}
                                    </Button>
                                </CardContent>
                            </Card>
                        )}

                        {showWorkspace && (
                            <div className="grid gap-6 md:grid-cols-[240px_1fr]">
                                <div className="hidden md:block">
                                    <div className="sticky top-20">
                                        <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-3">Progress</h3>
                                        <AgentStepTimeline steps={steps} />
                                    </div>
                                </div>
                                <div className="space-y-4">
                                    {caseFacts && (
                                        <Card><CardContent className="pt-4">
                                            <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">Case Facts</p>
                                            <p className="text-sm mb-3">{caseFacts}</p>
                                            <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-1">Desired Relief</p>
                                            <p className="text-sm">{desiredRelief}</p>
                                        </CardContent></Card>
                                    )}
                                    <div className="md:hidden"><AgentStepTimeline steps={steps} /></div>

                                    {session.checkpoint && (
                                        <AgentCheckpointPrompt question={session.checkpoint.question} context={session.checkpoint.context}
                                            onSubmit={session.resume} disabled={session.isRunning}
                                            error={session.checkpointError} onClearError={() => session.setCheckpointError(null)} />
                                    )}

                                    {session.memo && (
                                        <Card><CardContent className="pt-6">
                                            <AgentMemoViewer content={session.memo} confidence={session.confidence} />
                                        </CardContent></Card>
                                    )}

                                    {session.isFollowUp && !session.isRunning && !session.memo && !session.checkpoint && !session.error && (
                                        <div className="rounded-lg border bg-card p-6 text-center space-y-3">
                                            <p className="text-sm text-muted-foreground">This session did not complete successfully.</p>
                                            <Button size="sm" onClick={handleReset}><RotateCcw className="h-3.5 w-3.5 mr-1.5" /> New Argument Brief</Button>
                                        </div>
                                    )}

                                    {session.error && (
                                        <div className="text-sm text-red-500 p-3 rounded-md bg-red-50 dark:bg-red-950/20" role="alert">{session.error}</div>
                                    )}

                                    {session.isRunning && !session.checkpoint && (
                                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <Loader2 className="h-4 w-4 animate-spin" /> Agent is working...
                                        </div>
                                    )}

                                    {!session.isRunning && (session.memo || session.error) && (
                                        <>
                                            <LegalDisclaimer className="mt-2" />
                                            <Button variant="outline" size="sm" onClick={handleReset}>
                                                <RotateCcw className="h-3.5 w-3.5 mr-1.5" /> New Argument Brief
                                            </Button>
                                        </>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>
            <Footer />
        </div>
    );
}
