"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronDown, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { AgentSessionMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

interface AgentFollowUpThreadProps {
    messages: AgentSessionMessage[];
    isStreaming: boolean;
    streamingContent: string;
}

function StreamingDots() {
    return (
        <span className="inline-flex items-center gap-0.5">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:0ms]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:300ms]" />
        </span>
    );
}

function SourceBadges({ sources }: { sources: AgentSessionMessage["sources"] }) {
    if (!sources || sources.length === 0) return null;
    return (
        <div className="mt-1.5 flex flex-wrap gap-1">
            {sources.map((src) => (
                <Badge
                    key={src.number}
                    variant="outline"
                    className="text-[10px] font-normal"
                >
                    [{src.number}] {src.citation}
                </Badge>
            ))}
        </div>
    );
}

function MemoMessage({ content }: { content: string }) {
    const [expanded, setExpanded] = useState(false);
    return (
        <div className="w-full">
            <button
                type="button"
                onClick={() => setExpanded((prev) => !prev)}
                className="mb-1 flex items-center gap-1 text-xs font-semibold text-muted-foreground hover:text-foreground"
            >
                {expanded ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                )}
                Research Memo
            </button>
            {expanded && (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {content}
                    </ReactMarkdown>
                </div>
            )}
        </div>
    );
}

export function AgentFollowUpThread({
    messages,
    isStreaming,
    streamingContent,
}: AgentFollowUpThreadProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom on new messages or streaming content
    useEffect(() => {
        const el = scrollRef.current;
        if (el) {
            el.scrollTop = el.scrollHeight;
        }
    }, [messages.length, streamingContent]);

    return (
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg) => {
                const isUser = msg.role === "user";
                const isQuery = msg.message_type === "query";
                const isMemo = msg.message_type === "memo";

                return (
                    <div
                        key={msg.id}
                        className={cn(
                            "flex flex-col gap-1",
                            isUser ? "items-end" : "items-start",
                        )}
                    >
                        {/* Label for special message types */}
                        {isQuery && (
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                Initial Query
                            </span>
                        )}

                        {/* Message bubble */}
                        <div
                            className={cn(
                                "max-w-[85%] rounded-lg px-3.5 py-2.5 text-sm",
                                isUser
                                    ? "bg-primary text-primary-foreground"
                                    : "bg-muted",
                            )}
                        >
                            {isMemo ? (
                                <MemoMessage content={msg.content} />
                            ) : isUser ? (
                                <p className="whitespace-pre-wrap">{msg.content}</p>
                            ) : (
                                <div className="prose prose-sm dark:prose-invert max-w-none">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {msg.content}
                                    </ReactMarkdown>
                                </div>
                            )}
                        </div>

                        {/* Sources for assistant messages */}
                        {!isUser && <SourceBadges sources={msg.sources} />}
                    </div>
                );
            })}

            {/* Streaming message */}
            {isStreaming && (
                <div className="flex flex-col items-start gap-1">
                    <div className="max-w-[85%] rounded-lg bg-muted px-3.5 py-2.5 text-sm">
                        {streamingContent ? (
                            <div className="prose prose-sm dark:prose-invert max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {streamingContent}
                                </ReactMarkdown>
                            </div>
                        ) : (
                            <StreamingDots />
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
