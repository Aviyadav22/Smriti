"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ProcessingStatus } from "@/components/processing-status";
import { useAuth } from "@/lib/auth-context";
import { getDocument, deleteDocument, loadTokens } from "@/lib/api";
import type { DocumentDetail, DocumentIssue, DocumentCounterArgument } from "@/lib/types";
import { Loader2 } from "lucide-react";

function IssueCard({ issue, defaultOpen = false }: { issue: DocumentIssue; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Card>
      <CardHeader>
        <button
          type="button"
          className="flex items-center justify-between w-full text-left"
          onClick={() => setOpen(!open)}
        >
          <CardTitle className="text-base">{issue.title}</CardTitle>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`transition-transform ${open ? "rotate-180" : ""}`}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </CardHeader>
      {open && (
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{issue.description}</p>

          {issue.supporting_precedents.length > 0 && (
            <div>
              <h4 className="text-sm font-medium mb-2">Supporting Precedents</h4>
              <div className="space-y-1">
                {issue.supporting_precedents.map((p) => (
                  <Link
                    key={p.case_id}
                    href={`/case/${p.case_id}`}
                    className="block text-sm text-primary hover:underline"
                  >
                    {p.title || p.citation || p.case_id}
                    {p.citation && p.title ? ` — ${p.citation}` : ""}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {issue.statutes.length > 0 && (
            <div>
              <h4 className="text-sm font-medium mb-2">Statutes</h4>
              <div className="flex flex-wrap gap-1">
                {issue.statutes.map((s) => (
                  <Badge key={s} variant="outline" className="text-xs">
                    {s}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}

function CounterArgumentsSection({ args }: { args: DocumentCounterArgument[] }) {
  if (args.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold">Counter-Arguments</h3>
      {args.map((ca, i) => (
        <Card key={i}>
          <CardHeader>
            <CardTitle className="text-base">{ca.issue_title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div>
              <span className="text-xs font-medium text-muted-foreground uppercase">
                Argument
              </span>
              <p className="text-sm mt-1">{ca.argument}</p>
            </div>
            <div>
              <span className="text-xs font-medium text-muted-foreground uppercase">
                Response
              </span>
              <p className="text-sm mt-1">{ca.response}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ResearchMemoSection({ memo }: { memo: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(memo);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API unavailable (e.g. HTTP context)
    }
  }, [memo]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Research Memo</h3>
        <Button variant="outline" size="sm" onClick={handleCopy}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <Card>
        <CardContent className="prose prose-sm max-w-none whitespace-pre-wrap pt-4">
          {memo}
        </CardContent>
      </Card>
    </div>
  );
}

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const id = params.id as string;
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchDoc = useCallback(async () => {
    try {
      const data = await getDocument(id);
      setDoc(data);
      setLoading(false);

      // Stop polling if done
      if (data.status === "completed" || data.status === "failed") {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load document.";
      setError(message);
      setLoading(false);
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
  }, [id]);

  useEffect(() => {
    if (isAuthenticated) {
      loadTokens();
      fetchDoc();
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
    };
  }, [fetchDoc, isAuthenticated]);

  // Start polling when doc is in processing state
  useEffect(() => {
    if (
      doc &&
      doc.status !== "completed" &&
      doc.status !== "failed" &&
      !pollRef.current
    ) {
      pollRef.current = setInterval(fetchDoc, 3000);
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [doc, fetchDoc]);

  const handleDelete = useCallback(async () => {
    if (!confirm("Are you sure you want to delete this document?")) return;
    setDeleting(true);
    try {
      await deleteDocument(id);
      router.push("/documents");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to delete document.";
      setError(message);
      setDeleting(false);
    }
  }, [id, router]);

  if (authLoading || !isAuthenticated) return null;

  if (loading) {
    return (
      <div className="container mx-auto max-w-4xl py-10 px-4">
        <p className="text-muted-foreground">Loading document...</p>
      </div>
    );
  }

  if (error && !doc) {
    return (
      <div className="container mx-auto max-w-4xl py-10 px-4">
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  if (!doc) return null;

  const isProcessing =
    doc.status !== "completed" && doc.status !== "failed";

  return (
    <div className="container mx-auto max-w-4xl py-10 px-4 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{doc.filename}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Uploaded {new Date(doc.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push("/documents")}
          >
            Back
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleDelete}
            disabled={deleting}
          >
            {deleting ? "Deleting..." : "Delete"}
          </Button>
        </div>
      </div>

      {/* Processing status */}
      {isProcessing && (
        <Card>
          <CardHeader>
            <CardTitle>Processing</CardTitle>
            <CardDescription>
              Your document is being analyzed. This may take a few minutes.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ProcessingStatus
              status={doc.status}
              step={doc.processing_step}
            />
          </CardContent>
        </Card>
      )}

      {/* Failed status */}
      {doc.status === "failed" && (
        <Card>
          <CardContent className="pt-6">
            <ProcessingStatus
              status="failed"
              step={null}
              error={doc.error_message}
            />
          </CardContent>
        </Card>
      )}

      {/* Completed analysis */}
      {doc.status === "completed" && doc.analysis && (
        <>
          {/* Parties & Key Facts */}
          <Card>
            <CardHeader>
              <CardTitle>Case Overview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {doc.analysis.parties && (
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(doc.analysis.parties).map(([role, name]) => (
                    <div key={role}>
                      <span className="text-xs font-medium text-muted-foreground uppercase">
                        {role}
                      </span>
                      <p className="text-sm mt-1">{name || "N/A"}</p>
                    </div>
                  ))}
                </div>
              )}

              {doc.analysis.relief_sought && (
                <div>
                  <span className="text-xs font-medium text-muted-foreground uppercase">
                    Relief Sought
                  </span>
                  <p className="text-sm mt-1">{doc.analysis.relief_sought}</p>
                </div>
              )}

              {doc.analysis.key_facts && (
                <div>
                  <span className="text-xs font-medium text-muted-foreground uppercase">
                    Key Facts
                  </span>
                  <p className="text-sm mt-1 whitespace-pre-wrap">
                    {doc.analysis.key_facts}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Separator />

          {/* Issues */}
          {doc.analysis.issues.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-lg font-semibold">
                Legal Issues ({doc.analysis.issues.length})
              </h3>
              {doc.analysis.issues.map((issue, i) => (
                <IssueCard key={i} issue={issue} defaultOpen={i === 0} />
              ))}
            </div>
          )}

          <Separator />

          {/* Counter-arguments */}
          <CounterArgumentsSection args={doc.analysis.counter_arguments} />

          <Separator />

          {/* Research Memo */}
          <ResearchMemoSection memo={doc.analysis.research_memo} />
        </>
      )}
    </div>
  );
}
