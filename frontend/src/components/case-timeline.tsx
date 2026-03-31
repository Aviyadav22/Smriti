"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowRight, ArrowLeft } from "lucide-react";
import { getCaseTimeline, getCitationEvolution } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TimelineEvent {
    date: string;
    type: string;
    court: string;
    detail: string;
}

interface EvolutionEntry {
    case_id: string;
    title: string;
    year: number;
    citation: string;
    court: string;
    treatment: string;
    ratio_snippet: string;
}

interface CaseTimelineProps {
    caseId: string;
}

// ---------------------------------------------------------------------------
// Badge color helpers
// ---------------------------------------------------------------------------

function eventTypeBadge(type: string) {
    const t = type.toLowerCase();
    if (t === "filing")
        return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 text-[10px]">{type}</Badge>;
    if (t === "judgment")
        return <Badge className="bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 text-[10px]">{type}</Badge>;
    if (t === "interim_order")
        return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 text-[10px]">{type.replace(/_/g, " ")}</Badge>;
    if (t === "appeal_filed")
        return <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300 text-[10px]">{type.replace(/_/g, " ")}</Badge>;
    return <Badge variant="secondary" className="text-[10px]">{type.replace(/_/g, " ")}</Badge>;
}

function treatmentBadge(treatment: string) {
    const t = treatment.toLowerCase();
    if (t === "followed")
        return <Badge className="bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 text-[10px]">{treatment}</Badge>;
    if (t === "distinguished")
        return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 text-[10px]">{treatment}</Badge>;
    if (t === "overruled")
        return <Badge className="bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 text-[10px]">{treatment}</Badge>;
    return <Badge variant="secondary" className="text-[10px]">{treatment}</Badge>;
}

// ---------------------------------------------------------------------------
// Dot on the timeline line
// ---------------------------------------------------------------------------

function TimelineDot({ color }: { color: string }) {
    return (
        <div className="flex flex-col items-center">
            <div className={`w-3 h-3 rounded-full border-2 border-background ${color}`} />
        </div>
    );
}

function dotColor(type: string): string {
    const t = type.toLowerCase();
    if (t === "filing") return "bg-blue-500";
    if (t === "judgment") return "bg-green-500";
    if (t === "interim_order") return "bg-amber-500";
    if (t === "appeal_filed") return "bg-purple-500";
    return "bg-muted-foreground";
}

function treatmentDotColor(treatment: string): string {
    const t = treatment.toLowerCase();
    if (t === "followed") return "bg-green-500";
    if (t === "distinguished") return "bg-amber-500";
    if (t === "overruled") return "bg-red-500";
    return "bg-muted-foreground";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CaseTimeline({ caseId }: CaseTimelineProps) {
    const [events, setEvents] = useState<TimelineEvent[]>([]);
    const [evolution, setEvolution] = useState<EvolutionEntry[]>([]);
    const [direction, setDirection] = useState<"forward" | "backward">("forward");
    const [loading, setLoading] = useState(true);
    const [evoLoading, setEvoLoading] = useState(false);

    // Initial fetch
    useEffect(() => {
        let cancelled = false;
        async function load() {
            setLoading(true);
            const [timelineRes, evoRes] = await Promise.allSettled([
                getCaseTimeline(caseId),
                getCitationEvolution(caseId, "forward"),
            ]);
            if (cancelled) return;
            if (timelineRes.status === "fulfilled") setEvents(timelineRes.value.events);
            if (evoRes.status === "fulfilled") setEvolution(evoRes.value.evolution);
            setLoading(false);
        }
        load();
        return () => { cancelled = true; };
    }, [caseId]);

    // Direction toggle refetch
    const toggleDirection = useCallback(async () => {
        const newDir = direction === "forward" ? "backward" : "forward";
        setDirection(newDir);
        setEvoLoading(true);
        try {
            const res = await getCitationEvolution(caseId, newDir);
            setEvolution(res.evolution);
        } catch {
            // keep previous data on error
        } finally {
            setEvoLoading(false);
        }
    }, [caseId, direction]);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {/* Procedural History */}
            <section>
                <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-4">
                    Procedural History
                </h3>
                {events.length === 0 ? (
                    <Card className="p-6 rounded-md">
                        <p className="text-sm text-muted-foreground text-center">No procedural history available.</p>
                    </Card>
                ) : (
                    <div className="relative pl-6">
                        {/* Vertical line */}
                        <div className="absolute left-[5px] top-1.5 bottom-1.5 w-px bg-border" />

                        <div className="space-y-4">
                            {events.map((evt, i) => (
                                <div key={i} className="relative flex gap-3">
                                    <div className="absolute -left-6 top-1">
                                        <TimelineDot color={dotColor(evt.type)} />
                                    </div>
                                    <Card className="flex-1 p-4 rounded-md">
                                        <div className="flex items-center gap-2 mb-1.5">
                                            <span className="text-xs text-muted-foreground font-mono">{evt.date}</span>
                                            {eventTypeBadge(evt.type)}
                                        </div>
                                        <p className="text-sm">{evt.detail}</p>
                                        <p className="text-[11px] text-muted-foreground mt-1">{evt.court}</p>
                                    </Card>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </section>

            {/* Citation Evolution */}
            <section>
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                        Citation Evolution
                    </h3>
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-[11px] gap-1.5 rounded-md"
                        onClick={toggleDirection}
                        disabled={evoLoading}
                    >
                        {evoLoading ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                        ) : direction === "forward" ? (
                            <ArrowRight className="h-3 w-3" />
                        ) : (
                            <ArrowLeft className="h-3 w-3" />
                        )}
                        {direction === "forward" ? "Forward (citing cases)" : "Backward (cited cases)"}
                    </Button>
                </div>

                {evolution.length === 0 ? (
                    <Card className="p-6 rounded-md">
                        <p className="text-sm text-muted-foreground text-center">No citing cases found.</p>
                    </Card>
                ) : (
                    <div className="relative pl-6">
                        {/* Vertical line */}
                        <div className="absolute left-[5px] top-1.5 bottom-1.5 w-px bg-border" />

                        <div className="space-y-4">
                            {evolution.map((entry, i) => (
                                <div key={i} className="relative flex gap-3">
                                    <div className="absolute -left-6 top-1">
                                        <TimelineDot color={treatmentDotColor(entry.treatment)} />
                                    </div>
                                    <Card className="flex-1 p-4 rounded-md">
                                        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                                            <span className="text-xs text-muted-foreground font-mono">{entry.year}</span>
                                            {treatmentBadge(entry.treatment)}
                                            <span className="text-[11px] text-muted-foreground">{entry.court}</span>
                                        </div>
                                        <Link
                                            href={`/case/${entry.case_id}`}
                                            className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline font-[family-name:var(--font-lora)] italic"
                                        >
                                            {entry.title}
                                        </Link>
                                        {entry.citation && (
                                            <span className="text-xs text-muted-foreground ml-2">{entry.citation}</span>
                                        )}
                                        {entry.ratio_snippet && (
                                            <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed line-clamp-2">
                                                {entry.ratio_snippet}
                                            </p>
                                        )}
                                    </Card>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </section>
        </div>
    );
}
