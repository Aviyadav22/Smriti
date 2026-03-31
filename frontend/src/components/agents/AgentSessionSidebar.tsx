"use client";

import { MessageSquare, Plus, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AgentSession } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Lightweight relative-time formatter (avoids date-fns dependency). */
function timeAgo(dateStr: string): string {
    const seconds = Math.floor(
        (Date.now() - new Date(dateStr).getTime()) / 1000,
    );
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    const months = Math.floor(days / 30);
    return `${months}mo ago`;
}

interface AgentSessionSidebarProps {
    sessions: AgentSession[];
    activeSessionId: string | null;
    onSelectSession: (id: string) => void;
    onDeleteSession: (id: string) => void;
    onNewSession: () => void;
    loading: boolean;
}

export function AgentSessionSidebar({
    sessions,
    activeSessionId,
    onSelectSession,
    onDeleteSession,
    onNewSession,
    loading,
}: AgentSessionSidebarProps) {
    return (
        <div className="flex h-full flex-col border-r">
            {/* New session button */}
            <div className="p-3">
                <Button
                    onClick={onNewSession}
                    className="w-full justify-start gap-2"
                    variant="outline"
                    disabled={loading}
                >
                    <Plus className="h-4 w-4" />
                    New Session
                </Button>
            </div>

            {/* Session list */}
            <ScrollArea className="flex-1">
                {loading ? (
                    <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                        Loading sessions...
                    </div>
                ) : sessions.length === 0 ? (
                    <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                        No sessions yet
                    </div>
                ) : (
                    <div className="flex flex-col gap-1 p-2">
                        {sessions.map((session) => (
                            <div
                                key={session.id}
                                role="button"
                                tabIndex={0}
                                onClick={() => onSelectSession(session.id)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        onSelectSession(session.id);
                                    }
                                }}
                                className={cn(
                                    "group relative flex w-full cursor-pointer flex-col gap-1.5 rounded-md px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent/50",
                                    activeSessionId === session.id && "bg-accent",
                                )}
                            >
                                {/* Title */}
                                <span className="line-clamp-2 font-medium leading-snug">
                                    {session.title || "Untitled Session"}
                                </span>

                                {/* Badges row */}
                                <div className="flex items-center gap-2">
                                    <Badge variant="secondary" className="text-[10px]">
                                        {session.agent_type}
                                    </Badge>
                                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                        <MessageSquare className="h-3 w-3" />
                                        {session.message_count}
                                    </span>
                                </div>

                                {/* Timestamp */}
                                <span className="text-xs text-muted-foreground">
                                    {timeAgo(session.updated_at)}
                                </span>

                                {/* Delete button on hover */}
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDeleteSession(session.id);
                                    }}
                                    className="absolute right-2 top-2 rounded-sm p-1 opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                                    aria-label={`Delete session: ${session.title}`}
                                >
                                    <Trash2 className="h-3.5 w-3.5" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </ScrollArea>
        </div>
    );
}
