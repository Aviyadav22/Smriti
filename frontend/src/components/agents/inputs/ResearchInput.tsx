"use client";

import { useState } from "react";
import { ArrowUp, Loader2, Route, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

const PROMPT_STARTERS = [
    "Anticipatory bail — S.438 CrPC",
    "FIR quashing after settlement",
    "Article 21 against private entities",
    "Specific performance vs damages",
    "Corporate veil lifting",
    "S.125 CrPC maintenance",
] as const;

interface ResearchInputProps {
    onSubmit: (body: Record<string, unknown>) => void;
    disabled: boolean;
}

export function ResearchInput({ onSubmit, disabled }: ResearchInputProps) {
    const [query, setQuery] = useState("");
    const [steerResearch, setSteerResearch] = useState(false);
    const [verifyCitations, setVerifyCitations] = useState(false);

    const handleSubmit = () => {
        if (!query.trim() || disabled) return;
        onSubmit({
            query: query.trim(),
            steer_research: steerResearch,
            auto_approve: !steerResearch,
            skip_verification: !verifyCitations,
        });
    };

    const canSubmit = query.trim().length > 0 && !disabled;

    return (
        <div className="max-w-2xl mx-auto w-full">
            {/* Input container — compact, ChatGPT-style */}
            <div className="rounded-2xl border border-border bg-card shadow-sm focus-within:ring-2 focus-within:ring-ring/20 focus-within:border-ring/40 transition-all">
                <textarea
                    placeholder="Ask a legal research question..."
                    value={query}
                    onChange={(e) => {
                        if (e.target.value.length <= 2000) setQuery(e.target.value);
                        e.target.style.height = "auto";
                        e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px";
                    }}
                    onKeyDown={(e) => {
                        if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && canSubmit) {
                            e.preventDefault();
                            handleSubmit();
                        }
                    }}
                    rows={2}
                    className="w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none"
                    maxLength={2000}
                />

                {/* Bottom bar */}
                <div className="flex items-center justify-between px-3 pb-2.5">
                    <div className="flex items-center gap-1">
                        <TogglePill
                            active={steerResearch}
                            onClick={() => setSteerResearch(!steerResearch)}
                            icon={<Route className="h-3 w-3" />}
                            label="Steer"
                            tooltip="Pause at checkpoints to review and steer the research plan"
                        />
                        <TogglePill
                            active={verifyCitations}
                            onClick={() => setVerifyCitations(!verifyCitations)}
                            icon={<ShieldCheck className="h-3 w-3" />}
                            label="Verify"
                            tooltip="Re-verify every citation against primary sources (+30-60s)"
                        />
                    </div>

                    <button
                        onClick={handleSubmit}
                        disabled={!canSubmit}
                        className={cn(
                            "rounded-full p-2 transition-all",
                            canSubmit
                                ? "bg-foreground text-background hover:opacity-90"
                                : "bg-muted text-muted-foreground/40 cursor-not-allowed",
                        )}
                        aria-label="Start legal research"
                    >
                        {disabled ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <ArrowUp className="h-4 w-4" />
                        )}
                    </button>
                </div>
            </div>

            {/* Prompt starters */}
            {!query && (
                <div className="mt-3 flex flex-wrap items-center gap-1.5 justify-center">
                    <span className="text-[11px] text-muted-foreground mr-0.5">Try</span>
                    {PROMPT_STARTERS.map((prompt) => (
                        <button
                            key={prompt}
                            type="button"
                            onClick={() => setQuery(prompt)}
                            className="text-[12px] text-muted-foreground hover:text-foreground hover:bg-accent/50 px-2.5 py-1 rounded-full border border-border/50 hover:border-border transition-all cursor-pointer"
                        >
                            {prompt}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

function TogglePill({
    active,
    onClick,
    icon,
    label,
    tooltip,
}: {
    active: boolean;
    onClick: () => void;
    icon: React.ReactNode;
    label: string;
    tooltip: string;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            title={tooltip}
            className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all select-none",
                active
                    ? "bg-foreground/10 text-foreground border border-foreground/20"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-transparent",
            )}
        >
            {icon}
            {label}
        </button>
    );
}
