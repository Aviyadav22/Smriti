"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { getCase, getCaseCitations, getCaseCitedBy, getCaseSimilar, getCasePdfUrl } from "@/lib/api";
import type { CaseDetail, CitationItem, SimilarCase } from "@/lib/types";
import { ArrowLeft, FileText, BookOpen, Link2, Scale, ExternalLink, Loader2 } from "lucide-react";

export default function CaseDetailPage() {
    const params = useParams();
    const router = useRouter();
    const caseId = params.id as string;

    const [caseData, setCaseData] = useState<CaseDetail | null>(null);
    const [citations, setCitations] = useState<CitationItem[]>([]);
    const [citedBy, setCitedBy] = useState<CitationItem[]>([]);
    const [similar, setSimilar] = useState<SimilarCase[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function load() {
            setLoading(true);
            try {
                const [c, cit, cb, sim] = await Promise.allSettled([
                    getCase(caseId),
                    getCaseCitations(caseId),
                    getCaseCitedBy(caseId),
                    getCaseSimilar(caseId),
                ]);
                if (c.status === "fulfilled") setCaseData(c.value);
                else throw new Error("Case not found");
                if (cit.status === "fulfilled") setCitations(cit.value.citations);
                if (cb.status === "fulfilled") setCitedBy(cb.value.cited_by);
                if (sim.status === "fulfilled") setSimilar(sim.value.similar);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load case");
            } finally {
                setLoading(false);
            }
        }
        load();
    }, [caseId]);

    if (loading) return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <div className="flex-1 flex items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
        </div>
    );

    if (error || !caseData) return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                    <p className="text-sm text-destructive">{error || "Case not found"}</p>
                    <Button variant="outline" size="sm" className="mt-3 text-xs" onClick={() => router.back()}>Go Back</Button>
                </div>
            </div>
        </div>
    );

    const sectionKeys = Object.keys(caseData.sections || {});

    return (
        <div className="min-h-screen flex flex-col">
            <Header />

            <main className="flex-1">
                {/* Back + Case header */}
                <div className="border-b bg-card/50">
                    <div className="mx-auto max-w-5xl px-4 py-5">
                        <button onClick={() => router.back()} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-4">
                            <ArrowLeft className="h-3 w-3" /> Back to results
                        </button>

                        <h1 className="text-xl sm:text-2xl font-semibold leading-snug tracking-tight mb-3">
                            {caseData.title}
                        </h1>

                        <div className="flex flex-wrap items-center gap-2">
                            {caseData.citation && (
                                <Badge variant="outline" className="text-[11px] font-normal">{caseData.citation}</Badge>
                            )}
                            {caseData.court && (
                                <Badge variant="secondary" className="text-[11px] font-normal">{caseData.court}</Badge>
                            )}
                            {caseData.year && (
                                <Badge variant="secondary" className="text-[11px] font-normal">{caseData.year}</Badge>
                            )}
                            {caseData.case_type && (
                                <Badge variant="secondary" className="text-[11px] font-normal">{caseData.case_type}</Badge>
                            )}
                            {caseData.bench_type && (
                                <Badge variant="secondary" className="text-[11px] font-normal capitalize">{caseData.bench_type} bench</Badge>
                            )}
                        </div>
                    </div>
                </div>

                <div className="mx-auto max-w-5xl px-4 py-6">
                    <div className="grid lg:grid-cols-[1fr_280px] gap-6">
                        {/* Main content */}
                        <div>
                            <Tabs defaultValue={sectionKeys[0] || "info"}>
                                <TabsList className="h-8 bg-muted/50 rounded-md mb-4">
                                    {sectionKeys.length > 0 ? (
                                        sectionKeys.map((key) => (
                                            <TabsTrigger key={key} value={key} className="text-[11px] uppercase tracking-wider h-7 px-3 rounded-md">
                                                {key.replace(/_/g, " ")}
                                            </TabsTrigger>
                                        ))
                                    ) : (
                                        <TabsTrigger value="info" className="text-[11px] uppercase tracking-wider h-7 px-3">Info</TabsTrigger>
                                    )}
                                    {caseData.pdf_storage_path && (
                                        <TabsTrigger value="pdf" className="text-[11px] uppercase tracking-wider h-7 px-3 rounded-md">PDF</TabsTrigger>
                                    )}
                                    <TabsTrigger value="citations" className="text-[11px] uppercase tracking-wider h-7 px-3 rounded-md">
                                        Citations
                                    </TabsTrigger>
                                </TabsList>

                                {/* Section content tabs */}
                                {sectionKeys.map((key) => (
                                    <TabsContent key={key} value={key}>
                                        <Card className="p-6 rounded-md">
                                            <div className="prose prose-sm max-w-none dark:prose-invert font-[family-name:var(--font-lora)] leading-[1.7] text-[15px]">
                                                <p className="whitespace-pre-wrap">{caseData.sections[key]}</p>
                                            </div>
                                        </Card>
                                    </TabsContent>
                                ))}

                                {sectionKeys.length === 0 && (
                                    <TabsContent value="info">
                                        <Card className="p-6 rounded-md">
                                            <p className="text-sm text-muted-foreground">
                                                {caseData.description || caseData.ratio_decidendi || "No section content available."}
                                            </p>
                                        </Card>
                                    </TabsContent>
                                )}

                                {/* PDF tab */}
                                {caseData.pdf_storage_path && (
                                    <TabsContent value="pdf">
                                        <Card className="p-6 rounded-md text-center">
                                            <FileText className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
                                            <p className="text-sm text-muted-foreground mb-3">View the original judgment PDF</p>
                                            <Button asChild variant="outline" size="sm" className="text-xs rounded-md">
                                                <a href={getCasePdfUrl(caseId)} target="_blank" rel="noopener">
                                                    Open PDF <ExternalLink className="h-3 w-3 ml-1.5" />
                                                </a>
                                            </Button>
                                        </Card>
                                    </TabsContent>
                                )}

                                {/* Citations tab */}
                                <TabsContent value="citations">
                                    <div className="space-y-4">
                                        {/* Cases cited */}
                                        <Card className="p-5 rounded-md">
                                            <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-3 flex items-center gap-1.5">
                                                <Link2 className="h-3 w-3" /> Cases Cited ({citations.length})
                                            </h3>
                                            {citations.length > 0 ? (
                                                <div className="space-y-2">
                                                    {citations.map((c, i) => (
                                                        <div
                                                            key={i}
                                                            className="text-sm hover:bg-muted/50 p-2 rounded cursor-pointer border"
                                                            onClick={() => c.case_id && router.push(`/case/${c.case_id}`)}
                                                        >
                                                            <span className="font-medium font-[family-name:var(--font-lora)]">{c.title || "Unknown"}</span>
                                                            {c.citation && <span className="text-muted-foreground ml-2 text-xs">{c.citation}</span>}
                                                            <div className="text-xs text-muted-foreground mt-0.5">
                                                                {[c.court, c.year].filter(Boolean).join(" · ")}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <p className="text-xs text-muted-foreground">No citation data available.</p>
                                            )}
                                        </Card>

                                        {/* Cited by */}
                                        <Card className="p-5 rounded-md">
                                            <h3 className="text-xs uppercase tracking-wider font-medium text-muted-foreground mb-3 flex items-center gap-1.5">
                                                <BookOpen className="h-3 w-3" /> Cited By ({citedBy.length})
                                            </h3>
                                            {citedBy.length > 0 ? (
                                                <div className="space-y-2">
                                                    {citedBy.map((c, i) => (
                                                        <div
                                                            key={i}
                                                            className="text-sm hover:bg-muted/50 p-2 rounded cursor-pointer border"
                                                            onClick={() => c.case_id && router.push(`/case/${c.case_id}`)}
                                                        >
                                                            <span className="font-medium font-[family-name:var(--font-lora)]">{c.title || "Unknown"}</span>
                                                            {c.citation && <span className="text-muted-foreground ml-2 text-xs">{c.citation}</span>}
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <p className="text-xs text-muted-foreground">No citing cases found.</p>
                                            )}
                                        </Card>
                                    </div>
                                </TabsContent>
                            </Tabs>
                        </div>

                        {/* Metadata sidebar */}
                        <aside className="space-y-4">
                            {/* Parties */}
                            {(caseData.petitioner || caseData.respondent) && (
                                <Card className="p-4 rounded-md">
                                    <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground mb-2">Parties</h4>
                                    {caseData.petitioner && (
                                        <p className="text-sm"><span className="text-muted-foreground text-xs">Petitioner:</span> {caseData.petitioner}</p>
                                    )}
                                    {caseData.respondent && (
                                        <p className="text-sm mt-1"><span className="text-muted-foreground text-xs">Respondent:</span> {caseData.respondent}</p>
                                    )}
                                </Card>
                            )}

                            {/* Judges */}
                            {caseData.judge && (
                                <Card className="p-4 rounded-md">
                                    <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground mb-2">Bench</h4>
                                    <p className="text-sm">{caseData.judge}</p>
                                    {caseData.author_judge && (
                                        <p className="text-xs text-muted-foreground mt-1">Author: {caseData.author_judge}</p>
                                    )}
                                </Card>
                            )}

                            {/* Ratio decidendi */}
                            {caseData.ratio_decidendi && (
                                <Card className="p-4 rounded-md border-l-2 border-l-[var(--gold)]">
                                    <h4 className="text-[11px] uppercase tracking-wider font-medium text-[var(--gold)] mb-2">Ratio Decidendi</h4>
                                    <p className="text-sm leading-relaxed font-[family-name:var(--font-lora)]">
                                        {caseData.ratio_decidendi}
                                    </p>
                                </Card>
                            )}

                            {/* Keywords */}
                            {caseData.keywords && caseData.keywords.length > 0 && (
                                <Card className="p-4 rounded-md">
                                    <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground mb-2">Keywords</h4>
                                    <div className="flex flex-wrap gap-1">
                                        {caseData.keywords.map((kw) => (
                                            <Badge key={kw} variant="secondary" className="text-[10px]">{kw}</Badge>
                                        ))}
                                    </div>
                                </Card>
                            )}

                            {/* Acts cited */}
                            {caseData.acts_cited && caseData.acts_cited.length > 0 && (
                                <Card className="p-4 rounded-md">
                                    <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground mb-2">Acts Cited</h4>
                                    <div className="space-y-1">
                                        {caseData.acts_cited.map((act) => (
                                            <p key={act} className="text-xs text-muted-foreground">{act}</p>
                                        ))}
                                    </div>
                                </Card>
                            )}

                            {/* Similar cases */}
                            {similar.length > 0 && (
                                <Card className="p-4 rounded-md">
                                    <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
                                        <Scale className="h-3 w-3" /> Similar Cases
                                    </h4>
                                    <div className="space-y-2">
                                        {similar.map((s) => (
                                            <div
                                                key={s.case_id}
                                                className="text-xs hover:bg-muted/50 p-2 rounded cursor-pointer border"
                                                onClick={() => router.push(`/case/${s.case_id}`)}
                                            >
                                                <span className="font-medium">{s.title || "Untitled"}</span>
                                                <span className="text-muted-foreground ml-1">{s.year}</span>
                                                <div className="text-[10px] text-muted-foreground/60 mt-0.5">
                                                    Similarity: {(s.similarity_score * 100).toFixed(0)}%
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </Card>
                            )}

                            {/* Meta */}
                            <Card className="p-4 rounded-md">
                                <h4 className="text-[11px] uppercase tracking-wider font-medium text-muted-foreground mb-2">Details</h4>
                                <div className="space-y-1.5 text-xs text-muted-foreground">
                                    {caseData.disposal_nature && <div>Disposal: <span className="text-foreground">{caseData.disposal_nature}</span></div>}
                                    {caseData.jurisdiction && <div>Jurisdiction: <span className="text-foreground capitalize">{caseData.jurisdiction}</span></div>}
                                    {caseData.decision_date && <div>Decision: <span className="text-foreground">{caseData.decision_date}</span></div>}
                                    {caseData.source && <div>Source: <span className="text-foreground">{caseData.source}</span></div>}
                                    {caseData.chunk_count !== null && <div>Chunks: <span className="text-foreground">{caseData.chunk_count}</span></div>}
                                </div>
                            </Card>
                        </aside>
                    </div>
                </div>
            </main>

            <Footer />
        </div>
    );
}
