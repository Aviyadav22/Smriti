"use client";

import { CheckCircle2, AlertTriangle } from "lucide-react";

interface VerificationBannerProps {
    banner: string;
    citationsVerified: number;
    citationsRemoved: number;
}

export function VerificationBanner({ banner, citationsVerified, citationsRemoved }: VerificationBannerProps) {
    const isClean = citationsRemoved === 0;

    return (
        <div
            className={`flex items-start gap-2 px-4 py-3 rounded-lg text-sm ${
                isClean
                    ? "bg-green-50 dark:bg-green-950/20 text-green-800 dark:text-green-300"
                    : "bg-amber-50 dark:bg-amber-950/20 text-amber-800 dark:text-amber-300"
            }`}
        >
            {isClean ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
            ) : (
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            )}
            <div>
                <p>{banner}</p>
                <p className="text-xs mt-1 opacity-75">
                    {citationsVerified} citation{citationsVerified !== 1 ? "s" : ""} verified
                    {citationsRemoved > 0 && ` | ${citationsRemoved} removed`}
                </p>
            </div>
        </div>
    );
}
