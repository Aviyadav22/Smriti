"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { getDocuments, loadTokens } from "@/lib/api";
import type { DocumentListItem } from "@/lib/types";
import { Loader2 } from "lucide-react";

function statusBadgeVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "completed":
      return "default";
    case "failed":
      return "destructive";
    case "pending":
      return "outline";
    default:
      return "secondary";
  }
}

function statusColor(status: string): string {
  switch (status) {
    case "completed":
      return "bg-green-500/10 text-green-700 border-green-200";
    case "failed":
      return "bg-red-500/10 text-red-700 border-red-200";
    case "pending":
      return "bg-gray-500/10 text-gray-600 border-gray-200";
    default:
      return "bg-blue-500/10 text-blue-700 border-blue-200";
  }
}

export default function DocumentsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDocuments(p);
      setDocuments(data.documents);
      setTotalPages(data.total_pages);
      setPage(data.page);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load documents.";
      setError(message);
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

  if (authLoading || !isAuthenticated) return null;

  return (
    <div className="container mx-auto max-w-4xl py-10 px-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">My Documents</h1>
        <Button onClick={() => router.push("/upload")}>Upload New</Button>
      </div>

      {loading && (
        <p className="text-muted-foreground text-sm">Loading documents...</p>
      )}

      {error && (
        <p className="text-sm text-destructive font-medium">{error}</p>
      )}

      {!loading && !error && documents.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No documents yet. Upload a PDF to get started.
            </p>
          </CardContent>
        </Card>
      )}

      {!loading && documents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Documents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {documents.map((doc) => (
                <button
                  key={doc.id}
                  type="button"
                  className="w-full flex items-center justify-between py-3 px-2 hover:bg-muted/50 rounded-md transition-colors text-left"
                  onClick={() => router.push(`/documents/${doc.id}`)}
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{doc.filename}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Badge
                    variant={statusBadgeVariant(doc.status)}
                    className={statusColor(doc.status)}
                  >
                    {doc.status}
                  </Badge>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => fetchDocuments(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => fetchDocuments(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
