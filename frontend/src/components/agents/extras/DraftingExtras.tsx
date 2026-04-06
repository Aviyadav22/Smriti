"use client";

import { useCallback } from "react";
import { DraftSectionViewer } from "@/components/draft-section-viewer";
import { exportDraft } from "@/lib/api";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface DraftingExtrasProps {
    sectionDrafts: Record<string, string> | null;
    executionId: string | null;
    isRunning: boolean;
    /** Whether a checkpoint is active (sections being reviewed). */
    checkpointActive: boolean;
    /** Callback to revise a section through the agent. */
    onRevise?: (sectionName: string, feedback: string) => void;
    /** Report an error to the parent workspace. */
    onError?: (msg: string) => void;
    disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DraftingExtras({
    sectionDrafts,
    executionId,
    isRunning,
    checkpointActive,
    onRevise,
    onError,
    disabled,
}: DraftingExtrasProps) {
    const handleExport = useCallback(async (format: "docx" | "pdf") => {
        if (!executionId) return;
        try {
            const blob = await exportDraft(executionId, format);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `draft.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err) {
            onError?.(err instanceof Error ? err.message : "Export failed");
        }
    }, [executionId, onError]);

    if (!sectionDrafts) return null;

    // During checkpoint: show sections with revise capability
    if (checkpointActive) {
        return (
            <DraftSectionViewer
                sections={sectionDrafts}
                onRevise={onRevise}
                disabled={disabled ?? isRunning}
            />
        );
    }

    // After completion: show sections with export
    return (
        <DraftSectionViewer
            sections={sectionDrafts}
            onExport={executionId ? handleExport : undefined}
            disabled={isRunning}
        />
    );
}
