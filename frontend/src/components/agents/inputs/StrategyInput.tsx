"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2 } from "lucide-react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StrategyInputProps {
    onSubmit: (body: Record<string, unknown>) => void;
    disabled: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StrategyInput({ onSubmit, disabled }: StrategyInputProps) {
    const [caseFacts, setCaseFacts] = useState("");
    const [desiredRelief, setDesiredRelief] = useState("");
    const [targetJudge, setTargetJudge] = useState("");
    const [targetBench, setTargetBench] = useState("");
    const [steerConversation, setSteerConversation] = useState(false);

    const handleSubmit = () => {
        if (!caseFacts.trim() || !desiredRelief.trim() || disabled) return;
        onSubmit({
            case_facts: caseFacts.trim(),
            desired_relief: desiredRelief.trim(),
            target_judge: targetJudge.trim() || "",
            target_bench: targetBench || "",
            skip_checkpoints: !steerConversation,
        });
    };

    return (
        <Card>
            <CardContent className="pt-6 space-y-4">
                <Textarea
                    id="strategy-case-facts"
                    placeholder="Describe the facts of your case..."
                    value={caseFacts}
                    onChange={(e) => setCaseFacts(e.target.value)}
                    className="min-h-[120px] text-sm"
                />
                <Input
                    id="strategy-desired-relief"
                    placeholder="What relief are you seeking?"
                    value={desiredRelief}
                    onChange={(e) => setDesiredRelief(e.target.value)}
                />
                <div className="grid gap-4 sm:grid-cols-2">
                    <Input
                        id="strategy-target-judge"
                        placeholder="Target judge name (optional)"
                        value={targetJudge}
                        onChange={(e) => setTargetJudge(e.target.value)}
                    />
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
                <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer select-none">
                        <input
                            type="checkbox"
                            checked={steerConversation}
                            onChange={(e) => setSteerConversation(e.target.checked)}
                            className="h-4 w-4 rounded border-gray-300 text-[var(--gold)] focus:ring-[var(--gold)]"
                        />
                        <span className="text-xs text-muted-foreground">
                            Steer conversation (review at each step)
                        </span>
                    </label>
                    <Button onClick={handleSubmit} disabled={disabled || !caseFacts.trim() || !desiredRelief.trim()}>
                        {disabled ? <Loader2 className="h-4 w-4 animate-spin" /> : "Build Arguments"}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
