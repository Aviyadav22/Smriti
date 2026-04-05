"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import {
    createChatSession,
    sendChatMessage,
    getChatSessions,
    getChatHistory,
    deleteChatSession,
} from "@/lib/api";
import type { ChatMessage, ChatSession, ChatSource, StreamEvent } from "@/lib/types";
import {
    MessageSquare,
    Plus,
    Trash2,
    Send,
    Square,
    Loader2,
    Scale,
    ExternalLink,
    Menu,
    X,
    Copy,
    Check,
    Download,
} from "lucide-react";
import { LegalDisclaimer } from "@/components/legal-disclaimer";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DisplayMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources: ChatSource[];
    created_at: string;
    isStreaming?: boolean;
    disclaimer?: string;
}

// ---------------------------------------------------------------------------
// Example queries shown when no session is active
// ---------------------------------------------------------------------------

const EXAMPLE_QUERIES = [
    "What are the landmark cases on right to privacy in India?",
    "Explain the doctrine of basic structure",
    "Cases where Section 498A IPC was discussed by Constitution Bench",
    "What is the legal position on anticipatory bail?",
];

// ---------------------------------------------------------------------------
// Chat Page
// ---------------------------------------------------------------------------

export default function ChatPage() {
    return (
        <Suspense
            fallback={
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
            }
        >
            <ChatPageInner />
        </Suspense>
    );
}

function ChatPageInner() {
    const router = useRouter();
    const { isAuthenticated, isLoading: authLoading } = useAuth();

    // Session state
    const [sessions, setSessions] = useState<ChatSession[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [sessionsLoading, setSessionsLoading] = useState(false);

    // Message state
    const [messages, setMessages] = useState<DisplayMessage[]>([]);
    const [messagesLoading, setMessagesLoading] = useState(false);

    // Input state
    const [input, setInput] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);
    const abortRef = useRef<AbortController | null>(null);

    // Streaming content accumulator (reduces re-renders from per-chunk to ~10/sec)
    const streamingContentRef = useRef("");
    const streamingFlushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const stopFlushTimer = () => {
        if (streamingFlushTimerRef.current) {
            clearInterval(streamingFlushTimerRef.current);
            streamingFlushTimerRef.current = null;
        }
    };

    // Cleanup flush timer on unmount
    useEffect(() => {
        return () => stopFlushTimer();
    }, []);

    // Error state
    const [networkError, setNetworkError] = useState<string | null>(null);

    // Query params (for "Open in Chat" from case detail page)
    const searchParams = useSearchParams();

    // UI state
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // Load sessions on mount
    useEffect(() => {
        if (isAuthenticated) {
            loadSessions();
        }
    }, [isAuthenticated]);

    // Auto-scroll on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // Auto-resize textarea
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = "auto";
            inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 150) + "px";
        }
    }, [input]);

    // Auto-send query from URL params (e.g., "Open in Chat" from case detail page)
    const autoSendDone = useRef(false);
    useEffect(() => {
        const initialQuery = searchParams.get("q");
        if (initialQuery && messages.length === 0 && !isStreaming && !autoSendDone.current) {
            autoSendDone.current = true;
            setInput(initialQuery);
            handleSend(initialQuery);
        }
    }, [searchParams, messages.length, isStreaming]); // eslint-disable-line react-hooks/exhaustive-deps

    async function loadSessions() {
        setSessionsLoading(true);
        try {
            const data = await getChatSessions();
            setSessions(data);
        } catch (err) {
            console.error("Failed to load sessions:", err);
            setNetworkError("Failed to load conversations. Please refresh the page.");
        } finally {
            setSessionsLoading(false);
        }
    }

    async function loadHistory(sessionId: string) {
        setMessagesLoading(true);
        try {
            const history = await getChatHistory(sessionId);
            setMessages(
                history.map((m: ChatMessage) => ({
                    id: m.id,
                    role: m.role,
                    content: m.content,
                    sources: m.sources,
                    created_at: m.created_at,
                })),
            );
        } catch (err) {
            console.error("Failed to load history:", err);
            // Don't clear messages — keep existing data visible while showing error
            setNetworkError("Failed to load chat history. Please try again.");
        } finally {
            setMessagesLoading(false);
        }
    }

    function selectSession(sessionId: string) {
        if (sessionId === activeSessionId) return;
        // Cancel any in-progress stream
        abortRef.current?.abort();
        setActiveSessionId(sessionId);
        loadHistory(sessionId);
        setSidebarOpen(false);
    }

    function startNewChat() {
        abortRef.current?.abort();
        setActiveSessionId(null);
        setMessages([]);
        setInput("");
        setSidebarOpen(false);
        inputRef.current?.focus();
    }

    async function handleDeleteSession(e: React.MouseEvent, sessionId: string) {
        e.stopPropagation();
        if (!confirm("Delete this conversation? This cannot be undone.")) return;
        try {
            await deleteChatSession(sessionId);
            setSessions((prev) => prev.filter((s) => s.id !== sessionId));
            if (activeSessionId === sessionId) {
                startNewChat();
            }
        } catch (err) {
            console.error("Failed to delete session:", err);
            setNetworkError("Failed to delete conversation. Please try again.");
        }
    }

    const handleSend = useCallback(
        (messageText?: string) => {
            const text = (messageText || input).trim();
            if (!text || isStreaming) return;

            setInput("");
            setNetworkError(null);

            // Add user message to display
            const userMsg: DisplayMessage = {
                id: `temp-user-${Date.now()}`,
                role: "user",
                content: text,
                sources: [],
                created_at: new Date().toISOString(),
            };

            // Add placeholder assistant message for streaming
            const assistantMsg: DisplayMessage = {
                id: `temp-assistant-${Date.now()}`,
                role: "assistant",
                content: "",
                sources: [],
                created_at: new Date().toISOString(),
                isStreaming: true,
            };

            setMessages((prev) => [...prev, userMsg, assistantMsg]);
            streamingContentRef.current = "";
            stopFlushTimer();
            setIsStreaming(true);

            let currentSessionId = activeSessionId;
            const sources: ChatSource[] = [];

            const onEvent = (event: StreamEvent) => {
                switch (event.type) {
                    case "session":
                        if (event.session_id) {
                            currentSessionId = event.session_id;
                            setActiveSessionId(event.session_id);
                            // Add to sessions list
                            setSessions((prev) => [
                                {
                                    id: event.session_id!,
                                    title: event.title || "New Chat",
                                    created_at: new Date().toISOString(),
                                    updated_at: new Date().toISOString(),
                                    message_count: 0,
                                },
                                ...prev,
                            ]);
                        }
                        break;

                    case "chunk":
                        if (event.content) {
                            streamingContentRef.current += event.content;
                            // Start flush interval on first chunk
                            if (!streamingFlushTimerRef.current) {
                                streamingFlushTimerRef.current = setInterval(() => {
                                    const content = streamingContentRef.current;
                                    setMessages((prev) => {
                                        const updated = [...prev];
                                        const last = updated[updated.length - 1];
                                        if (last && last.role === "assistant") {
                                            updated[updated.length - 1] = {
                                                ...last,
                                                content,
                                            };
                                        }
                                        return updated;
                                    });
                                }, 100);
                            }
                        }
                        break;

                    case "source":
                        if (event.case_id) {
                            sources.push({
                                case_id: event.case_id,
                                title: event.title || null,
                                citation: event.citation || null,
                                court: event.court || null,
                                year: event.year || null,
                                score: event.score || 0,
                            });
                        }
                        break;

                    case "disclaimer":
                        // Append disclaimer text to the assistant message
                        if (event.message) {
                            setMessages((prev) => {
                                const updated = [...prev];
                                const last = updated[updated.length - 1];
                                if (last && last.role === "assistant") {
                                    updated[updated.length - 1] = {
                                        ...last,
                                        disclaimer: event.message,
                                    };
                                }
                                return updated;
                            });
                        }
                        break;

                    case "done":
                        // Final flush of accumulated streaming content
                        stopFlushTimer();
                        setMessages((prev) => {
                            const updated = [...prev];
                            const last = updated[updated.length - 1];
                            if (last && last.role === "assistant") {
                                updated[updated.length - 1] = {
                                    ...last,
                                    content: streamingContentRef.current || last.content,
                                    sources: [...sources],
                                    isStreaming: false,
                                };
                            }
                            return updated;
                        });
                        streamingContentRef.current = "";
                        setIsStreaming(false);
                        // Refresh session list to update message counts
                        loadSessions();
                        break;
                }
            };

            const onError = (err: Error) => {
                stopFlushTimer();
                streamingContentRef.current = "";
                setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    if (last && last.role === "assistant") {
                        updated[updated.length - 1] = {
                            ...last,
                            content: last.content || `Error: ${err.message}`,
                            isStreaming: false,
                        };
                    }
                    return updated;
                });
                setIsStreaming(false);
                setNetworkError("Connection error. Please check your network and try again.");
            };

            if (currentSessionId) {
                abortRef.current = sendChatMessage(currentSessionId, text, onEvent, onError);
            } else {
                abortRef.current = createChatSession(text, onEvent, onError);
            }
        },
        [input, isStreaming, activeSessionId],
    );

    function exportSession() {
        if (messages.length === 0) return;

        const md = messages
            .map((m) => {
                const prefix = m.role === "user" ? "**You:**" : "**Smriti:**";
                let text = `${prefix} ${m.content}\n`;
                if (m.sources && m.sources.length > 0) {
                    text += "\n**Sources:**\n";
                    m.sources.forEach((s, i) => {
                        text += `- [${i + 1}] ${s.citation || s.title} (${s.court}, ${s.year})\n`;
                    });
                }
                return text;
            })
            .join("\n---\n\n");

        const blob = new Blob([md], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `smriti-chat-${new Date().toISOString().slice(0, 10)}.md`;
        a.click();
        URL.revokeObjectURL(url);
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    if (authLoading || !isAuthenticated) return null;

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 flex overflow-hidden">
                {/* Mobile sidebar overlay */}
                {sidebarOpen && (
                    <div
                        className="fixed inset-0 z-40 bg-black/40 lg:hidden"
                        onClick={() => setSidebarOpen(false)}
                    />
                )}

                {/* Sidebar */}
                <aside
                    className={`
                        fixed lg:relative z-50 lg:z-auto
                        top-0 left-0 h-full lg:h-auto
                        w-72 lg:w-64 xl:w-72
                        bg-card border-r
                        flex flex-col
                        transition-transform duration-200
                        ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
                    `}
                >
                    {/* Sidebar header */}
                    <div className="flex items-center justify-between p-3 border-b">
                        <h2 className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                            Sessions
                        </h2>
                        <div className="flex items-center gap-1">
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 p-0"
                                onClick={startNewChat}
                                title="New chat"
                                aria-label="New chat"
                            >
                                <Plus className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 p-0 lg:hidden"
                                onClick={() => setSidebarOpen(false)}
                                aria-label="Close sidebar"
                            >
                                <X className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    </div>

                    {/* Session list */}
                    <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
                        {sessionsLoading ? (
                            <div className="flex justify-center py-8">
                                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                            </div>
                        ) : sessions.length === 0 ? (
                            <p className="text-xs text-muted-foreground text-center py-8">
                                No conversations yet
                            </p>
                        ) : (
                            sessions.map((session) => (
                                <div
                                    key={session.id}
                                    className={`
                                        group flex items-center gap-2 px-2.5 py-2 rounded-md cursor-pointer text-sm
                                        hover:bg-muted/50 transition-colors
                                        ${activeSessionId === session.id ? "bg-muted" : ""}
                                    `}
                                    onClick={() => selectSession(session.id)}
                                >
                                    <MessageSquare className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                    <span className="truncate flex-1 text-xs" title={session.title}>
                                        {session.title}
                                    </span>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 shrink-0"
                                        onClick={(e) => handleDeleteSession(e, session.id)}
                                        aria-label="Delete session"
                                    >
                                        <Trash2 className="h-3 w-3 text-muted-foreground" />
                                    </Button>
                                </div>
                            ))
                        )}
                    </div>
                </aside>

                {/* Main chat area */}
                <div className="flex-1 flex flex-col min-w-0">
                    {/* Mobile sidebar toggle */}
                    <div className="lg:hidden border-b px-3 py-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2"
                            onClick={() => setSidebarOpen(true)}
                        >
                            <Menu className="h-4 w-4 mr-1.5" />
                            <span className="text-xs">Sessions</span>
                        </Button>
                    </div>

                    {/* Messages area */}
                    <div className="flex-1 overflow-y-auto">
                        {messages.length === 0 && !messagesLoading ? (
                            /* Empty state with example queries */
                            <div className="h-full flex items-center justify-center p-6">
                                <div className="max-w-lg text-center">
                                    <Scale className="h-8 w-8 mx-auto text-[var(--gold)] mb-4" />
                                    <h2 className="text-lg font-semibold font-[family-name:var(--font-lora)] mb-2">
                                        Legal Research Assistant
                                    </h2>
                                    <p className="text-sm text-muted-foreground mb-6">
                                        Ask questions about Indian law. Answers are grounded in
                                        Supreme Court judgments with cited sources.
                                    </p>
                                    <div className="grid gap-2 sm:grid-cols-2">
                                        {EXAMPLE_QUERIES.map((q) => (
                                            <button
                                                key={q}
                                                className="text-left text-xs p-3 rounded-md border hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground"
                                                onClick={() => handleSend(q)}
                                            >
                                                &ldquo;{q}&rdquo;
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ) : messagesLoading ? (
                            <div className="flex justify-center py-12">
                                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                            </div>
                        ) : (
                            <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
                                {messages.map((msg) => (
                                    <MessageBubble key={msg.id} message={msg} />
                                ))}
                                <div ref={messagesEndRef} />
                            </div>
                        )}
                    </div>

                    {/* Network error banner */}
                    {networkError && (
                        <div className="mx-4 p-3 rounded-md bg-red-50 border border-red-200 text-red-800 dark:bg-red-950/20 dark:border-red-800 dark:text-red-200 text-sm flex items-center justify-between">
                            <span>{networkError}</span>
                            <button onClick={() => setNetworkError(null)} className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200 ml-2 shrink-0">
                                Dismiss
                            </button>
                        </div>
                    )}

                    {/* Input area */}
                    <div className="border-t bg-card/50">
                        <div className="max-w-3xl mx-auto px-4 py-3">
                            <div className="flex items-end gap-2">
                                <label htmlFor="chat-input" className="sr-only">Ask a legal question</label>
                                <textarea
                                    id="chat-input"
                                    ref={inputRef}
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    placeholder="Ask a legal question..."
                                    rows={1}
                                    maxLength={5000}
                                    className="flex-1 resize-none bg-background border rounded-md px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground/60"
                                    disabled={isStreaming}
                                />
                                {messages.length > 0 && !isStreaming && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="h-10 w-10 p-0 shrink-0 rounded-md"
                                        onClick={exportSession}
                                        title="Export conversation as Markdown"
                                        aria-label="Export conversation"
                                    >
                                        <Download className="h-4 w-4" />
                                    </Button>
                                )}
                                {isStreaming ? (
                                    <Button
                                        variant="destructive"
                                        size="sm"
                                        className="h-10 px-3 shrink-0 rounded-md gap-1.5"
                                        onClick={() => abortRef.current?.abort()}
                                        aria-label="Stop generating"
                                    >
                                        <Square className="h-3.5 w-3.5" />
                                        <span className="text-xs">Stop</span>
                                    </Button>
                                ) : (
                                    <Button
                                        size="sm"
                                        className="h-10 w-10 p-0 shrink-0 rounded-md"
                                        onClick={() => handleSend()}
                                        disabled={!input.trim()}
                                        aria-label="Send message"
                                    >
                                        <Send className="h-4 w-4" />
                                    </Button>
                                )}
                            </div>
                            <LegalDisclaimer className="mt-2" />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Message Bubble
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: DisplayMessage }) {
    const router = useRouter();
    const [copied, setCopied] = useState(false);

    const handleCopy = useCallback(() => {
        navigator.clipboard.writeText(message.content).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }).catch((err) => {
            console.error("Failed to copy to clipboard:", err);
        });
    }, [message.content]);

    if (message.role === "user") {
        return (
            <div className="flex justify-end">
                <div className="max-w-[85%] bg-primary text-primary-foreground rounded-2xl rounded-br-sm px-4 py-2.5">
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex justify-start group/msg">
            <div className="max-w-[85%] space-y-3">
                {/* Assistant text */}
                <div className="bg-muted/50 rounded-2xl rounded-bl-sm px-4 py-3 relative">
                    {message.content ? (
                        <div className="text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none prose-headings:text-base prose-headings:font-semibold prose-p:my-1.5 prose-li:my-0.5 prose-ul:my-1 prose-ol:my-1">
                            <MarkdownWithCitations
                                content={message.content}
                                sources={message.sources}
                                messageId={message.id}
                            />
                        </div>
                    ) : message.isStreaming ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            Researching...
                        </div>
                    ) : null}

                    {message.isStreaming && message.content && (
                        <span className="inline-block w-1.5 h-4 bg-foreground/60 animate-pulse ml-0.5 -mb-0.5" />
                    )}

                    {/* Copy button */}
                    {message.content && !message.isStreaming && (
                        <button
                            onClick={handleCopy}
                            className="absolute top-2 right-2 opacity-0 group-hover/msg:opacity-100 transition-opacity p-1 rounded hover:bg-muted"
                            title="Copy to clipboard"
                            aria-label="Copy to clipboard"
                        >
                            {copied ? (
                                <Check className="h-3.5 w-3.5 text-green-500" />
                            ) : (
                                <Copy className="h-3.5 w-3.5 text-muted-foreground" />
                            )}
                        </button>
                    )}
                </div>

                {/* Sources */}
                {message.sources.length > 0 && (
                    <div className="space-y-1.5">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium px-1">
                            Sources
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                            {message.sources.map((source, i) => (
                                <Badge
                                    key={source.case_id}
                                    variant="outline"
                                    className="text-[10px] cursor-pointer hover:bg-muted/50 transition-colors gap-1"
                                    onClick={() => router.push(`/case/${source.case_id}`)}
                                    id={`source-${message.id}-${i + 1}`}
                                >
                                    <span className="text-[var(--gold)] font-semibold">[{i + 1}]</span>
                                    <span className="truncate max-w-[180px]" title={source.citation || source.title || "Case"}>
                                        {source.citation || source.title || "Case"}
                                    </span>
                                    {source.court && (
                                        <span className="text-muted-foreground">
                                            {source.court.replace("Supreme Court of India", "SC").replace("High Court", "HC")}
                                        </span>
                                    )}
                                    {source.year && (
                                        <span className="text-muted-foreground">{source.year}</span>
                                    )}
                                    <ExternalLink className="h-2.5 w-2.5 text-muted-foreground" />
                                </Badge>
                            ))}
                        </div>
                    </div>
                )}

                {/* Legal Disclaimer */}
                {message.disclaimer && !message.isStreaming && (
                    <p className="text-[10px] text-muted-foreground/70 italic mt-2 px-1">
                        {message.disclaimer}
                    </p>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Markdown with inline citation links
// ---------------------------------------------------------------------------

function MarkdownWithCitations({
    content,
    sources,
    messageId,
}: {
    content: string;
    sources: ChatSource[];
    messageId: string;
}) {
    // Replace [N] patterns with clickable links that scroll to the source badge
    const processedContent = content.replace(
        /\[(\d+)\]/g,
        (match, num) => {
            const idx = parseInt(num, 10);
            if (idx >= 1 && idx <= sources.length) {
                return `[${match}](#source-${messageId}-${idx})`;
            }
            return match;
        },
    );

    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeSanitize]}
            components={{
                a: ({ href, children, ...props }) => {
                    // Handle internal citation anchor links
                    if (href?.startsWith("#source-")) {
                        const sourceId = href.replace("#", "");
                        return (
                            <a
                                {...props}
                                href={href}
                                className="text-[var(--gold)] font-semibold no-underline hover:underline cursor-pointer text-xs align-super"
                                onClick={(e) => {
                                    e.preventDefault();
                                    document.getElementById(sourceId)?.scrollIntoView({
                                        behavior: "smooth",
                                        block: "nearest",
                                    });
                                    // Briefly highlight the source badge
                                    const el = document.getElementById(sourceId);
                                    if (el) {
                                        el.classList.add("ring-2", "ring-[var(--gold)]");
                                        setTimeout(() => el.classList.remove("ring-2", "ring-[var(--gold)]"), 1500);
                                    }
                                }}
                            >
                                {children}
                            </a>
                        );
                    }
                    // External links
                    return (
                        <a {...props} href={href} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                            {children}
                        </a>
                    );
                },
            }}
        >
            {processedContent}
        </ReactMarkdown>
    );
}
