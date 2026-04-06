"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import { getDocuments, uploadDocument, deleteDocument, loadTokens } from "@/lib/api";
import type { DocumentListItem } from "@/lib/types";
import {
    Loader2,
    Upload,
    FileText,
    Search,
    ChevronLeft,
    ChevronRight,
    Vault,
    X,
    Trash2,
    ArrowUpDown,
    Clock,
    CheckCircle2,
    AlertCircle,
    RefreshCw,
    Plus,
} from "lucide-react";

// ── Status helpers ──────────────────────────────────────────────

function statusConfig(status: string) {
    switch (status) {
        case "completed":
            return {
                label: "Ready",
                icon: CheckCircle2,
                color: "text-emerald-600 dark:text-emerald-400",
                bg: "bg-emerald-500/10",
                border: "border-emerald-200 dark:border-emerald-800",
            };
        case "failed":
            return {
                label: "Failed",
                icon: AlertCircle,
                color: "text-red-600 dark:text-red-400",
                bg: "bg-red-500/10",
                border: "border-red-200 dark:border-red-800",
            };
        case "pending":
            return {
                label: "Processing",
                icon: RefreshCw,
                color: "text-amber-600 dark:text-amber-400",
                bg: "bg-amber-500/10",
                border: "border-amber-200 dark:border-amber-800",
            };
        default:
            return {
                label: status,
                icon: Clock,
                color: "text-blue-600 dark:text-blue-400",
                bg: "bg-blue-500/10",
                border: "border-blue-200 dark:border-blue-800",
            };
    }
}

function formatFileSize(bytes: number | null): string {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

// ── Sort options ────────────────────────────────────────────────

type SortKey = "newest" | "oldest" | "name" | "size";
const SORT_LABELS: Record<SortKey, string> = {
    newest: "Newest first",
    oldest: "Oldest first",
    name: "A → Z",
    size: "Largest first",
};

function sortDocuments(docs: DocumentListItem[], key: SortKey): DocumentListItem[] {
    const sorted = [...docs];
    switch (key) {
        case "newest":
            return sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        case "oldest":
            return sorted.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
        case "name":
            return sorted.sort((a, b) => a.filename.localeCompare(b.filename));
        case "size":
            return sorted.sort((a, b) => (b.file_size ?? 0) - (a.file_size ?? 0));
    }
}

// ── Upload queue item ───────────────────────────────────────────

interface UploadItem {
    id: string;
    file: File;
    status: "uploading" | "done" | "error";
    error?: string;
    progress: number;
}

// ── Main component ──────────────────────────────────────────────

export default function VaultPage() {
    const router = useRouter();
    const { isAuthenticated, isLoading: authLoading } = useAuth();
    const [documents, setDocuments] = useState<DocumentListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalDocs, setTotalDocs] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [sortKey, setSortKey] = useState<SortKey>("newest");
    const [isDragOver, setIsDragOver] = useState(false);
    const [uploads, setUploads] = useState<UploadItem[]>([]);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [deleting, setDeleting] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // ── Fetch ───────────────────────────────────────────────────

    const fetchDocuments = useCallback(async (p: number) => {
        setLoading(true);
        setError(null);
        try {
            const data = await getDocuments(p);
            setDocuments(data.documents);
            setTotalPages(data.total_pages);
            setTotalDocs(data.total);
            setPage(data.page);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to load documents.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (isAuthenticated) {
            loadTokens();
            fetchDocuments(1);
        }
    }, [fetchDocuments, isAuthenticated]);

    // Poll for processing status updates
    useEffect(() => {
        const hasPending = documents.some((d) => d.status === "pending" || d.status === "processing");
        if (!hasPending) return;
        const interval = setInterval(() => fetchDocuments(page), 8000);
        return () => clearInterval(interval);
    }, [documents, fetchDocuments, page]);

    // ── Upload ──────────────────────────────────────────────────

    const handleUploadFiles = useCallback(async (files: FileList | File[]) => {
        const fileArray = Array.from(files).filter((f) => f.type === "application/pdf");
        if (fileArray.length === 0) return;

        const newItems: UploadItem[] = fileArray.map((f) => ({
            id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
            file: f,
            status: "uploading" as const,
            progress: 0,
        }));

        setUploads((prev) => [...newItems, ...prev]);

        // Upload sequentially to avoid overwhelming the server
        for (const item of newItems) {
            try {
                await uploadDocument(item.file);
                setUploads((prev) =>
                    prev.map((u) => (u.id === item.id ? { ...u, status: "done" as const, progress: 100 } : u)),
                );
            } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : "Upload failed";
                setUploads((prev) =>
                    prev.map((u) => (u.id === item.id ? { ...u, status: "error" as const, error: msg } : u)),
                );
            }
        }

        // Refresh document list after all uploads
        await fetchDocuments(1);

        // Clear completed uploads after 3s
        setTimeout(() => {
            setUploads((prev) => prev.filter((u) => u.status !== "done"));
        }, 3000);
    }, [fetchDocuments]);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        if (e.dataTransfer.files.length > 0) {
            handleUploadFiles(e.dataTransfer.files);
        }
    }, [handleUploadFiles]);

    // ── Selection & Delete ──────────────────────────────────────

    const toggleSelect = useCallback((id: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }, []);

    const toggleSelectAll = useCallback(() => {
        if (selectedIds.size === documents.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(documents.map((d) => d.id)));
        }
    }, [selectedIds, documents]);

    const handleBulkDelete = useCallback(async () => {
        if (selectedIds.size === 0) return;
        setDeleting(true);
        try {
            await Promise.all(Array.from(selectedIds).map((id) => deleteDocument(id)));
            setSelectedIds(new Set());
            await fetchDocuments(page);
        } catch {
            // Individual failures are acceptable
        } finally {
            setDeleting(false);
        }
    }, [selectedIds, fetchDocuments, page]);

    // ── Derived state ───────────────────────────────────────────

    const filteredDocs = useMemo(() => {
        const filtered = documents.filter((doc) =>
            doc.filename.toLowerCase().includes(searchQuery.toLowerCase()),
        );
        return sortDocuments(filtered, sortKey);
    }, [documents, searchQuery, sortKey]);

    const statusCounts = useMemo(() => {
        const counts = { ready: 0, processing: 0, failed: 0 };
        documents.forEach((d) => {
            if (d.status === "completed") counts.ready++;
            else if (d.status === "failed") counts.failed++;
            else counts.processing++;
        });
        return counts;
    }, [documents]);

    const activeUploads = uploads.filter((u) => u.status === "uploading");

    if (authLoading || !isAuthenticated) return null;

    // ── Render ──────────────────────────────────────────────────

    return (
        <div
            className="mx-auto max-w-4xl px-4 py-8"
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={(e) => {
                // Only set false if we're leaving the container
                if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                    setIsDragOver(false);
                }
            }}
            onDrop={handleDrop}
        >
            {/* Drag overlay */}
            {isDragOver && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
                    <div className="flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-[var(--gold)] bg-[var(--gold)]/5 px-16 py-12">
                        <Upload className="h-10 w-10 text-[var(--gold)]" />
                        <p className="text-lg font-medium">Drop PDF files here</p>
                        <p className="text-sm text-muted-foreground">Multiple files supported</p>
                    </div>
                </div>
            )}

            {/* ── Header ─────────────────────────────────────── */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--gold)]/10">
                        <Vault className="h-5 w-5 text-[var(--gold)]" />
                    </div>
                    <div>
                        <h1 className="text-xl font-semibold font-[family-name:var(--font-lora)]">
                            Vault
                        </h1>
                        <p className="text-xs text-muted-foreground">
                            {totalDocs > 0 ? `${totalDocs} document${totalDocs !== 1 ? "s" : ""}` : "Your private document library"}
                        </p>
                    </div>
                </div>

                <Button
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={activeUploads.length > 0}
                >
                    {activeUploads.length > 0 ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                    ) : (
                        <Plus className="h-3.5 w-3.5 mr-1.5" />
                    )}
                    {activeUploads.length > 0 ? `Uploading ${activeUploads.length}...` : "Upload"}
                </Button>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    multiple
                    className="hidden"
                    onChange={(e) => {
                        if (e.target.files && e.target.files.length > 0) {
                            handleUploadFiles(e.target.files);
                        }
                        e.target.value = "";
                    }}
                />
            </div>

            {/* ── Upload progress bar ────────────────────────── */}
            {uploads.length > 0 && (
                <div className="mb-4 space-y-1.5">
                    {uploads.map((item) => (
                        <div
                            key={item.id}
                            className={`flex items-center gap-3 rounded-md border px-3 py-2 text-sm ${
                                item.status === "error"
                                    ? "border-red-200 dark:border-red-800 bg-red-500/5"
                                    : item.status === "done"
                                        ? "border-emerald-200 dark:border-emerald-800 bg-emerald-500/5"
                                        : "border-border bg-muted/30"
                            }`}
                        >
                            {item.status === "uploading" && <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--gold)] shrink-0" />}
                            {item.status === "done" && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />}
                            {item.status === "error" && <AlertCircle className="h-3.5 w-3.5 text-red-600 dark:text-red-400 shrink-0" />}
                            <span className="truncate flex-1">{item.file.name}</span>
                            <span className="text-xs text-muted-foreground shrink-0">
                                {formatFileSize(item.file.size)}
                            </span>
                            {item.status === "error" && (
                                <span className="text-xs text-red-600 dark:text-red-400 shrink-0">{item.error}</span>
                            )}
                            <button
                                onClick={() => setUploads((prev) => prev.filter((u) => u.id !== item.id))}
                                className="text-muted-foreground hover:text-foreground shrink-0"
                            >
                                <X className="h-3 w-3" />
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* ── Status summary pills ───────────────────────── */}
            {!loading && documents.length > 0 && (
                <div className="flex items-center gap-4 mb-4">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                        <span>{statusCounts.ready} ready</span>
                    </div>
                    {statusCounts.processing > 0 && (
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <RefreshCw className="h-3 w-3 text-amber-600 dark:text-amber-400 animate-spin" />
                            <span>{statusCounts.processing} processing</span>
                        </div>
                    )}
                    {statusCounts.failed > 0 && (
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <AlertCircle className="h-3 w-3 text-red-600 dark:text-red-400" />
                            <span>{statusCounts.failed} failed</span>
                        </div>
                    )}
                </div>
            )}

            {/* ── Search + Sort bar ──────────────────────────── */}
            {documents.length > 0 && (
                <div className="flex items-center gap-2 mb-4">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            placeholder="Search documents..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-9 h-9 text-sm"
                        />
                        {searchQuery && (
                            <button
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                onClick={() => setSearchQuery("")}
                            >
                                <X className="h-3 w-3" />
                            </button>
                        )}
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-9 text-xs gap-1.5 shrink-0"
                        onClick={() => {
                            const keys: SortKey[] = ["newest", "oldest", "name", "size"];
                            const idx = keys.indexOf(sortKey);
                            setSortKey(keys[(idx + 1) % keys.length]);
                        }}
                    >
                        <ArrowUpDown className="h-3 w-3" />
                        {SORT_LABELS[sortKey]}
                    </Button>
                </div>
            )}

            {/* ── Bulk actions bar ───────────────────────────── */}
            {selectedIds.size > 0 && (
                <div className="flex items-center gap-3 mb-4 rounded-md border border-border bg-muted/30 px-3 py-2">
                    <span className="text-xs text-muted-foreground">
                        {selectedIds.size} selected
                    </span>
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs text-destructive hover:text-destructive"
                        onClick={handleBulkDelete}
                        disabled={deleting}
                    >
                        {deleting ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Trash2 className="h-3 w-3 mr-1" />}
                        Delete
                    </Button>
                    <button
                        className="ml-auto text-xs text-muted-foreground hover:text-foreground"
                        onClick={() => setSelectedIds(new Set())}
                    >
                        Clear
                    </button>
                </div>
            )}

            {/* ── Loading state ──────────────────────────────── */}
            {loading && (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
            )}

            {/* ── Error state ────────────────────────────────── */}
            {error && !loading && (
                <Card>
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-destructive">{error}</p>
                        <Button variant="outline" size="sm" className="mt-3" onClick={() => fetchDocuments(1)}>
                            Retry
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* ── Empty state ────────────────────────────────── */}
            {!loading && !error && documents.length === 0 && (
                <Card className="border-dashed border-2 border-muted-foreground/20 hover:border-[var(--gold)]/30 transition-colors">
                    <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[var(--gold)]/10 mb-5">
                            <Vault className="h-7 w-7 text-[var(--gold)]" />
                        </div>
                        <h3 className="font-semibold mb-1">Your vault is empty</h3>
                        <p className="text-sm text-muted-foreground mb-5 max-w-sm">
                            Upload legal briefs, petitions, or contracts. Smriti will extract issues, find precedents, and prepare them for agent analysis.
                        </p>
                        <Button
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <Upload className="h-4 w-4 mr-2" />
                            Upload your first document
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* ── Document list ──────────────────────────────── */}
            {!loading && !error && filteredDocs.length > 0 && (
                <div className="rounded-lg border border-border overflow-hidden">
                    {/* Table header */}
                    <div className="flex items-center gap-3 px-4 py-2 bg-muted/30 border-b border-border text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                        <input
                            type="checkbox"
                            checked={selectedIds.size === documents.length && documents.length > 0}
                            onChange={toggleSelectAll}
                            className="h-3.5 w-3.5 rounded border-border accent-[var(--gold)]"
                        />
                        <span className="flex-1">Document</span>
                        <span className="w-16 text-right hidden sm:block">Size</span>
                        <span className="w-20 text-right hidden sm:block">Added</span>
                        <span className="w-24 text-right">Status</span>
                    </div>

                    {/* Rows */}
                    <div className="divide-y divide-border">
                        {filteredDocs.map((doc) => {
                            const sc = statusConfig(doc.status);
                            const StatusIcon = sc.icon;
                            const isSelected = selectedIds.has(doc.id);
                            return (
                                <div
                                    key={doc.id}
                                    className={`flex items-center gap-3 px-4 py-2.5 transition-colors cursor-pointer group ${
                                        isSelected ? "bg-[var(--gold)]/5" : "hover:bg-muted/40"
                                    }`}
                                >
                                    <input
                                        type="checkbox"
                                        checked={isSelected}
                                        onChange={() => toggleSelect(doc.id)}
                                        onClick={(e) => e.stopPropagation()}
                                        className="h-3.5 w-3.5 rounded border-border accent-[var(--gold)]"
                                    />
                                    <button
                                        type="button"
                                        className="flex items-center gap-3 flex-1 min-w-0 text-left"
                                        onClick={() => router.push(`/documents/${doc.id}`)}
                                    >
                                        <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium truncate group-hover:text-[var(--gold)] transition-colors">
                                                {doc.filename.replace(/\.pdf$/i, "")}
                                            </p>
                                            {doc.processing_step && doc.status !== "completed" && (
                                                <p className="text-[10px] text-muted-foreground mt-0.5">
                                                    {doc.processing_step}...
                                                </p>
                                            )}
                                        </div>
                                    </button>
                                    <span className="text-xs text-muted-foreground w-16 text-right hidden sm:block">
                                        {formatFileSize(doc.file_size)}
                                    </span>
                                    <span className="text-xs text-muted-foreground w-20 text-right hidden sm:block">
                                        {formatDate(doc.created_at)}
                                    </span>
                                    <div className="w-24 flex justify-end">
                                        <Badge
                                            variant="outline"
                                            className={`text-[10px] gap-1 ${sc.color} ${sc.bg} ${sc.border}`}
                                        >
                                            <StatusIcon className={`h-2.5 w-2.5 ${doc.status === "pending" ? "animate-spin" : ""}`} />
                                            {sc.label}
                                        </Badge>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* ── No search results ──────────────────────────── */}
            {!loading && !error && documents.length > 0 && filteredDocs.length === 0 && (
                <div className="py-12 text-center">
                    <Search className="h-5 w-5 text-muted-foreground mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">
                        No documents matching &ldquo;{searchQuery}&rdquo;
                    </p>
                </div>
            )}

            {/* ── Pagination ─────────────────────────────────── */}
            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-6">
                    <Button
                        variant="outline"
                        size="icon"
                        className="h-8 w-8"
                        disabled={page <= 1}
                        onClick={() => fetchDocuments(page - 1)}
                    >
                        <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-xs text-muted-foreground px-2">
                        {page} / {totalPages}
                    </span>
                    <Button
                        variant="outline"
                        size="icon"
                        className="h-8 w-8"
                        disabled={page >= totalPages}
                        onClick={() => fetchDocuments(page + 1)}
                    >
                        <ChevronRight className="h-4 w-4" />
                    </Button>
                </div>
            )}
        </div>
    );
}
