"use client";

import { useState } from "react";
import { getJudgePrediction } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Loader2, TrendingUp } from "lucide-react";

const CASE_TYPES = [
    "Criminal Appeal",
    "Civil Appeal",
    "Writ Petition",
    "SLP",
    "Bail Application",
    "Review Petition",
];

type Prediction = {
    predicted_outcome: string;
    outcome_probabilities: Record<string, number>;
    confidence: number;
    sample_size: number;
    factors: { name: string; impact: string; detail: string }[];
    caveats: string[];
};

interface JudgePredictionCardProps {
    judgeName: string;
}

function outcomeColor(outcome: string): string {
    const lower = outcome.toLowerCase();
    if (lower.includes("allowed") && !lower.includes("partly")) return "text-green-600 dark:text-green-400";
    if (lower.includes("dismissed")) return "text-red-600 dark:text-red-400";
    return "text-amber-600 dark:text-amber-400";
}

function outcomeBgColor(outcome: string): string {
    const lower = outcome.toLowerCase();
    if (lower.includes("allowed") && !lower.includes("partly")) return "bg-green-500";
    if (lower.includes("dismissed")) return "bg-red-500";
    return "bg-amber-500";
}

function confidenceColor(confidence: number): string {
    if (confidence > 0.7) return "bg-green-500";
    if (confidence >= 0.4) return "bg-amber-500";
    return "bg-red-500";
}

function impactVariant(impact: string): "destructive" | "secondary" | "outline" {
    const lower = impact.toLowerCase();
    if (lower === "strong") return "destructive";
    if (lower === "moderate") return "secondary";
    return "outline";
}

export function JudgePredictionCard({ judgeName }: JudgePredictionCardProps) {
    const [caseType, setCaseType] = useState("");
    const [acts, setActs] = useState("");
    const [loading, setLoading] = useState(false);
    const [prediction, setPrediction] = useState<Prediction | null>(null);
    const [queried, setQueried] = useState(false);

    async function handlePredict() {
        if (!caseType) return;
        setLoading(true);
        setPrediction(null);
        setQueried(true);
        try {
            const result = await getJudgePrediction({
                judges: judgeName,
                case_type: caseType,
                acts: acts || undefined,
            });
            setPrediction(result);
        } finally {
            setLoading(false);
        }
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <TrendingUp className="h-4 w-4" />
                    Outcome Prediction
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Input area */}
                <div className="flex flex-col sm:flex-row gap-3">
                    <Select value={caseType} onValueChange={setCaseType}>
                        <SelectTrigger className="sm:w-[200px]">
                            <SelectValue placeholder="Case type" />
                        </SelectTrigger>
                        <SelectContent>
                            {CASE_TYPES.map((t) => (
                                <SelectItem key={t} value={t}>
                                    {t}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Input
                        placeholder="Acts (optional, e.g. IPC, CrPC)"
                        value={acts}
                        onChange={(e) => setActs(e.target.value)}
                        className="sm:w-[240px]"
                    />
                    <Button onClick={handlePredict} disabled={!caseType || loading}>
                        {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                        Predict
                    </Button>
                </div>

                {/* Loading state */}
                {loading && (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    </div>
                )}

                {/* Empty state */}
                {queried && !loading && !prediction && (
                    <p className="text-sm text-muted-foreground text-center py-6">
                        Insufficient data for prediction.
                    </p>
                )}

                {/* Results */}
                {prediction && !loading && (
                    <div className="space-y-5">
                        {/* Predicted outcome */}
                        <div>
                            <p className="text-xs text-muted-foreground mb-1">Predicted Outcome</p>
                            <p className={`text-xl font-semibold ${outcomeColor(prediction.predicted_outcome)}`}>
                                {prediction.predicted_outcome}
                            </p>
                        </div>

                        {/* Outcome probability bars */}
                        <div>
                            <p className="text-xs text-muted-foreground mb-2">Outcome Probabilities</p>
                            <div className="space-y-2">
                                {Object.entries(prediction.outcome_probabilities)
                                    .sort(([, a], [, b]) => b - a)
                                    .map(([outcome, prob]) => (
                                        <div key={outcome}>
                                            <div className="flex justify-between text-xs mb-0.5">
                                                <span>{outcome}</span>
                                                <span className="text-muted-foreground">
                                                    {(prob * 100).toFixed(1)}%
                                                </span>
                                            </div>
                                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full rounded-full transition-all ${outcomeBgColor(outcome)}`}
                                                    style={{ width: `${prob * 100}%` }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                            </div>
                        </div>

                        {/* Confidence indicator */}
                        <div>
                            <div className="flex justify-between text-xs mb-1">
                                <span className="text-muted-foreground">Confidence</span>
                                <span>{(prediction.confidence * 100).toFixed(0)}%</span>
                            </div>
                            <div className="h-2.5 bg-muted rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all ${confidenceColor(prediction.confidence)}`}
                                    style={{ width: `${prediction.confidence * 100}%` }}
                                />
                            </div>
                        </div>

                        {/* Sample size */}
                        <p className="text-xs text-muted-foreground">
                            Based on {prediction.sample_size} cases
                        </p>

                        {/* Factors */}
                        {prediction.factors.length > 0 && (
                            <div>
                                <p className="text-xs text-muted-foreground mb-2">Key Factors</p>
                                <div className="space-y-2">
                                    {prediction.factors.map((f, i) => (
                                        <div key={i} className="flex items-start gap-2">
                                            <Badge variant={impactVariant(f.impact)} className="shrink-0 text-[10px] mt-0.5">
                                                {f.impact}
                                            </Badge>
                                            <div className="min-w-0">
                                                <p className="text-sm font-medium">{f.name}</p>
                                                <p className="text-xs text-muted-foreground">{f.detail}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Caveats */}
                        {prediction.caveats.length > 0 && (
                            <div className="bg-muted/50 rounded-md p-3 space-y-1">
                                {prediction.caveats.map((c, i) => (
                                    <p key={i} className="text-xs text-muted-foreground">{c}</p>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
