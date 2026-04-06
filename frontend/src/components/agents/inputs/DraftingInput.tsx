"use client";

import { useEffect, useState } from "react";
import { getDraftingTemplates } from "@/lib/api";
import type { DocumentTemplate, TemplateCategory } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2 } from "lucide-react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatFieldName(name: string): string {
    return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DraftingInputProps {
    onSubmit: (body: Record<string, unknown>) => void;
    disabled: boolean;
    /** If coming from a research session, pre-fill this. */
    researchExecutionId?: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DraftingInput({ onSubmit, disabled, researchExecutionId }: DraftingInputProps) {
    const [templates, setTemplates] = useState<DocumentTemplate[]>([]);
    const [categories, setCategories] = useState<TemplateCategory[]>([]);
    const [templatesLoading, setTemplatesLoading] = useState(true);
    const [templateError, setTemplateError] = useState<string | null>(null);
    const [selectedDocType, setSelectedDocType] = useState("");
    const selectedTemplate = templates.find((t) => t.doc_type === selectedDocType);

    const [caseFacts, setCaseFacts] = useState("");
    const [targetCourt, setTargetCourt] = useState("");
    const [dynamicFields, setDynamicFields] = useState<Record<string, string>>({});

    // Fetch templates on mount
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await getDraftingTemplates();
                if (!cancelled) {
                    if (res.categories?.length) {
                        setCategories(res.categories);
                        setTemplates(res.categories.flatMap((c) => c.templates));
                    } else {
                        setTemplates(res.templates);
                    }
                }
            } catch (err) {
                if (!cancelled) setTemplateError(err instanceof Error ? err.message : "Failed to load templates");
            } finally {
                if (!cancelled) setTemplatesLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    // Reset dynamic fields when template changes
    useEffect(() => {
        if (selectedTemplate) {
            const fields: Record<string, string> = {};
            for (const field of selectedTemplate.required_fields) fields[field] = "";
            setDynamicFields(fields);
        } else {
            setDynamicFields({});
        }
    }, [selectedDocType, selectedTemplate]);

    const allDynamicFieldsFilled = !selectedTemplate || selectedTemplate.required_fields.every((field) => dynamicFields[field]?.trim());

    const handleSubmit = () => {
        if (!selectedDocType || disabled) return;
        if (!researchExecutionId && !caseFacts.trim()) return;

        const additionalContext: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(dynamicFields)) {
            if (value.trim()) additionalContext[key] = value.trim();
        }

        const body: Record<string, unknown> = {
            doc_type: selectedDocType,
            case_facts: caseFacts.trim(),
            target_court: targetCourt.trim() || "",
            relevant_precedents: [],
            additional_context: Object.keys(additionalContext).length > 0 ? additionalContext : undefined,
        };
        if (researchExecutionId) {
            body.research_execution_id = researchExecutionId;
        }

        onSubmit(body);
    };

    return (
        <>
            {researchExecutionId && (
                <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg text-sm text-green-800 dark:text-green-200">
                    Drafting from research session.
                </div>
            )}
            <Card>
                <CardContent className="pt-6 space-y-4">
                    <div>
                        {categories.length > 0 ? (
                            <select
                                id="drafting-template"
                                value={selectedDocType}
                                onChange={(e) => setSelectedDocType(e.target.value)}
                                disabled={templatesLoading}
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                                <option value="">{templatesLoading ? "Loading templates..." : "Select document type"}</option>
                                {categories.map((cat) => (
                                    <optgroup key={cat.id} label={cat.display_name}>
                                        {cat.templates.map((t) => (
                                            <option key={t.doc_type} value={t.doc_type}>{t.display_name}</option>
                                        ))}
                                    </optgroup>
                                ))}
                            </select>
                        ) : (
                            <Select value={selectedDocType} onValueChange={setSelectedDocType} disabled={templatesLoading}>
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder={templatesLoading ? "Loading templates..." : "Select document type"} />
                                </SelectTrigger>
                                <SelectContent>
                                    {templates.map((t) => (
                                        <SelectItem key={t.doc_type} value={t.doc_type}>{t.display_name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                        {templateError && <p className="text-xs text-red-500 mt-1" role="alert">{templateError}</p>}
                    </div>
                    <Textarea
                        id="drafting-case-facts"
                        placeholder="Describe the facts of your case..."
                        value={caseFacts}
                        onChange={(e) => setCaseFacts(e.target.value)}
                        className="min-h-[120px] text-sm"
                    />
                    <Input
                        id="drafting-target-court"
                        placeholder="e.g., High Court of Delhi"
                        value={targetCourt}
                        onChange={(e) => setTargetCourt(e.target.value)}
                    />
                    {selectedTemplate && selectedTemplate.required_fields.length > 0 && (
                        <div className="space-y-3 border-t pt-4">
                            <p className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                                Required fields for {selectedTemplate.display_name}
                            </p>
                            {selectedTemplate.required_fields.map((field) => (
                                <Input
                                    key={field}
                                    id={`drafting-field-${field}`}
                                    placeholder={formatFieldName(field)}
                                    value={dynamicFields[field] || ""}
                                    onChange={(e) => setDynamicFields((prev) => ({ ...prev, [field]: e.target.value }))}
                                />
                            ))}
                        </div>
                    )}
                    <Button
                        onClick={handleSubmit}
                        disabled={disabled || !selectedDocType || (!researchExecutionId && !caseFacts.trim()) || !allDynamicFieldsFilled}
                    >
                        {disabled ? <Loader2 className="h-4 w-4 animate-spin" /> : "Start Drafting"}
                    </Button>
                </CardContent>
            </Card>
        </>
    );
}
