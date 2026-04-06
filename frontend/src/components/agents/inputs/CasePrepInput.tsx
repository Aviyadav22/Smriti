"use client";

import { useEffect, useState } from "react";
import { getDocuments } from "@/lib/api";
import type { DocumentListItem } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, FileText } from "lucide-react";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CasePrepInputProps {
    onSubmit: (body: Record<string, unknown>) => void;
    disabled: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CasePrepInput({ onSubmit, disabled }: CasePrepInputProps) {
    const [documents, setDocuments] = useState<DocumentListItem[]>([]);
    const [documentsLoading, setDocumentsLoading] = useState(true);
    const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
    const [docSearch, setDocSearch] = useState("");
    const [loadError, setLoadError] = useState<string | null>(null);

    const filteredDocuments = documents.filter((d) =>
        d.filename.toLowerCase().includes(docSearch.toLowerCase()),
    );

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const data = await getDocuments(1, 100);
                if (!cancelled) {
                    setDocuments(data.documents.filter((d) => d.status === "completed"));
                }
            } catch {
                if (!cancelled) setLoadError("Failed to load documents. Please refresh the page.");
            } finally {
                if (!cancelled) setDocumentsLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const handleSubmit = () => {
        if (!selectedDocId || disabled) return;
        onSubmit({ document_id: selectedDocId });
    };

    return (
        <Card>
            <CardContent className="pt-6 space-y-4">
                {documentsLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" /> Loading documents...
                    </div>
                ) : loadError ? (
                    <div className="text-sm text-red-500" role="alert">{loadError}</div>
                ) : documents.length === 0 ? (
                    <div className="text-center py-6">
                        <FileText className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
                        <p className="text-sm text-muted-foreground mb-3">No analyzed documents found.</p>
                        <Button variant="outline" size="sm" asChild>
                            <Link href="/upload">Upload Document</Link>
                        </Button>
                    </div>
                ) : (
                    <>
                        <label htmlFor="doc-select" className="text-sm font-medium">Select a document</label>
                        <input
                            id="doc-search"
                            type="text"
                            placeholder="Search documents..."
                            value={docSearch}
                            onChange={(e) => setDocSearch(e.target.value)}
                            className="w-full px-3 py-2 text-sm border rounded-md mb-2 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                        />
                        <select
                            id="doc-select"
                            value={selectedDocId || ""}
                            onChange={(e) => setSelectedDocId(e.target.value || null)}
                            className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                        >
                            <option value="">Choose a document...</option>
                            {filteredDocuments.map((doc) => (
                                <option key={doc.id} value={doc.id}>
                                    {doc.filename} ({new Date(doc.created_at).toLocaleDateString()})
                                </option>
                            ))}
                        </select>
                        <Button onClick={handleSubmit} disabled={disabled || !selectedDocId}>
                            {disabled ? <Loader2 className="h-4 w-4 animate-spin" /> : "Start Case Prep"}
                        </Button>
                    </>
                )}
            </CardContent>
        </Card>
    );
}
