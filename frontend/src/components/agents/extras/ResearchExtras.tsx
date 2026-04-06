"use client";

import { useState } from "react";
import type { ProcessEvent, ResearchFootnote, ResearchAudit } from "@/lib/types";
import { ResearchProgress } from "@/components/research-progress";
import { FootnotesPanel } from "@/components/footnotes-panel";
import { VerificationBanner } from "@/components/verification-banner";
import { ResearchAuditTrail } from "@/components/research-audit-trail";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { FileText, PanelRightOpen } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ResearchExtrasProps {
    memo: string;
    confidence: number | undefined;
    executionId: string | null;
    isRunning: boolean;
    processEvents: ProcessEvent[];
    completedNodes: Set<string>;
    startTime: number | null;
    footnotes: ResearchFootnote[];
    researchAudit: ResearchAudit | null;
    verificationBanner: string | null;
    citationsVerified: number;
    citationsRemoved: number;
    confidenceBreakdown?: {
        data_confidence?: number;
        legal_confidence?: number;
        consistency_confidence?: number;
    };
    /** Whether fast path was detected. */
    isFastPath: boolean;
    /** Whether memo is still streaming (typewriter). */
    isStreaming: boolean;
    /** The display memo (may include streaming content). */
    displayMemo: string;
    /** Callback to revise a section. */
    onReviseSection?: (heading: string, feedback: string) => Promise<string | null>;
    /** Footnote verification map. */
    footnoteVerification?: Record<number, "verified_pg" | "verified_ik" | "verified_neo4j" | "unverified" | "removed" | "flagged">;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResearchExtras({
    memo,
    confidence,
    executionId,
    isRunning,
    processEvents,
    completedNodes,
    startTime,
    footnotes,
    researchAudit,
    verificationBanner,
    citationsVerified,
    citationsRemoved,
    confidenceBreakdown,
    isFastPath,
    isStreaming,
    displayMemo,
    onReviseSection,
    footnoteVerification,
}: ResearchExtrasProps) {
    const [footnotesPanelOpen, setFootnotesPanelOpen] = useState(false);
    const [selectedFootnoteNum, setSelectedFootnoteNum] = useState<number | null>(null);

    return (
        <>
            {/* Wrapper that shifts content when footnotes panel is open */}
            <div className={cn(
                "transition-[margin] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
                footnotesPanelOpen ? "lg:mr-[400px]" : "",
            )}>
                {/* Research progress (5-stage stepper + activity feed) */}
                <ResearchProgress
                    events={processEvents}
                    completedNodes={completedNodes}
                    isRunning={isRunning}
                    isFastPath={isFastPath}
                    startTime={startTime ?? undefined}
                />

                {/* Verification Banner */}
                {verificationBanner && !isRunning && (
                    <VerificationBanner
                        banner={verificationBanner}
                        citationsVerified={citationsVerified}
                        citationsRemoved={citationsRemoved}
                    />
                )}

                {/* Enhanced memo viewer with footnotes + revision */}
                {displayMemo && (
                    <Card>
                        <CardContent className="pt-6">
                            <AgentMemoViewer
                                content={displayMemo}
                                confidence={isStreaming ? 0 : confidence}
                                maxFootnote={footnotes.length}
                                onFootnoteClick={(num) => {
                                    setSelectedFootnoteNum(num);
                                    setFootnotesPanelOpen(true);
                                }}
                                confidenceBreakdown={isStreaming ? undefined : confidenceBreakdown}
                                footnoteVerification={footnoteVerification}
                                executionId={executionId ?? undefined}
                                onReviseSection={isStreaming ? undefined : (!isRunning ? onReviseSection : undefined)}
                                footnotes={footnotes}
                            />
                            {isStreaming && (
                                <span className="inline-block w-1.5 h-5 bg-[var(--gold)] animate-pulse ml-0.5 align-text-bottom" />
                            )}
                        </CardContent>
                    </Card>
                )}

                {/* Mobile: Footnotes Sheet */}
                {footnotes.length > 0 && (
                    <div className="lg:hidden">
                        <Sheet>
                            <SheetTrigger asChild>
                                <Button variant="outline" size="sm" className="w-full">
                                    <FileText className="h-4 w-4 mr-2" />
                                    Footnotes & Sources ({footnotes.filter((f) => f.is_used).length})
                                </Button>
                            </SheetTrigger>
                            <SheetContent side="bottom" className="h-[80vh] p-0">
                                <SheetTitle className="sr-only">Footnotes & Sources</SheetTitle>
                                <FootnotesPanel
                                    footnotes={footnotes}
                                    selectedFootnoteNumber={selectedFootnoteNum}
                                    onFootnoteSelect={setSelectedFootnoteNum}
                                    isOpen={true}
                                    onToggle={() => {}}
                                />
                            </SheetContent>
                        </Sheet>
                    </div>
                )}

                {/* Research Audit Trail */}
                {researchAudit && !isRunning && (
                    <ResearchAuditTrail audit={researchAudit} />
                )}
            </div>

            {/* Desktop slide-out footnotes panel */}
            <div
                className={cn(
                    "hidden lg:block fixed right-0 top-20 h-[calc(100vh-5rem)] w-[400px] z-40",
                    "border-l bg-background shadow-xl",
                    "transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
                    footnotesPanelOpen ? "translate-x-0" : "translate-x-full",
                )}
            >
                <FootnotesPanel
                    footnotes={footnotes}
                    selectedFootnoteNumber={selectedFootnoteNum}
                    onFootnoteSelect={setSelectedFootnoteNum}
                    isOpen={true}
                    onToggle={() => setFootnotesPanelOpen(false)}
                />
            </div>

            {/* Floating reopen tab */}
            {footnotes.length > 0 && !footnotesPanelOpen && (
                <button
                    onClick={() => setFootnotesPanelOpen(true)}
                    className="hidden lg:flex fixed right-0 top-1/2 -translate-y-1/2 z-30 items-center gap-1.5 bg-background/95 border border-r-0 rounded-l-lg shadow-md px-2 py-3 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors backdrop-blur-sm"
                    style={{ writingMode: "vertical-rl" }}
                >
                    <PanelRightOpen className="h-3.5 w-3.5" />
                    Sources ({footnotes.filter((f) => f.is_used).length})
                </button>
            )}
        </>
    );
}
