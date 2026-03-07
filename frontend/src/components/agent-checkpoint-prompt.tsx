"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { MessageSquare } from "lucide-react";

interface AgentCheckpointPromptProps {
    question: string;
    context?: Record<string, unknown>;
    onSubmit: (input: string) => void;
    disabled?: boolean;
}

export function AgentCheckpointPrompt({ question, context, onSubmit, disabled }: AgentCheckpointPromptProps) {
    const [input, setInput] = useState("");

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (input.trim()) {
            onSubmit(input.trim());
            setInput("");
        }
    }

    return (
        <Card className="border-[var(--gold)]/30">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                    <MessageSquare className="h-4 w-4 text-[var(--gold)]" />
                    Agent needs your input
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <p className="text-sm text-foreground">{question}</p>

                {context && Object.keys(context).length > 0 && (
                    <div className="rounded-md bg-muted/50 p-3 space-y-2">
                        {Object.entries(context).map(([key, value]) => (
                            <div key={key}>
                                <p className="text-xs font-medium text-muted-foreground capitalize">
                                    {key.replace(/_/g, " ")}
                                </p>
                                {Array.isArray(value) ? (
                                    <ul className="text-xs text-foreground mt-1 space-y-0.5">
                                        {value.map((item, i) => (
                                            <li key={i} className="list-disc ml-4">{String(item)}</li>
                                        ))}
                                    </ul>
                                ) : (
                                    <p className="text-xs text-foreground mt-0.5">{String(value)}</p>
                                )}
                            </div>
                        ))}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-3">
                    {/* Quick suggestion chips */}
                    <div className="flex flex-wrap gap-2">
                        {[
                            "Looks good, proceed",
                            "Focus more on constitutional aspects",
                            "Add cases from the last 5 years",
                        ].map((suggestion) => (
                            <button
                                key={suggestion}
                                type="button"
                                disabled={disabled}
                                onClick={() => setInput(suggestion)}
                                className="rounded-full border border-border bg-muted/50 px-3 py-1 text-xs text-foreground hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {suggestion}
                            </button>
                        ))}
                    </div>
                    <label htmlFor="checkpoint-response" className="sr-only">Type your response</label>
                    <Textarea
                        id="checkpoint-response"
                        placeholder="Type your response..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        disabled={disabled}
                        className="min-h-[80px] text-sm"
                    />
                    <Button
                        type="submit"
                        size="sm"
                        disabled={disabled || !input.trim()}
                    >
                        Submit
                    </Button>
                </form>
            </CardContent>
        </Card>
    );
}
