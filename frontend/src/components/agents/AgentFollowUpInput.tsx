"use client";

import { useCallback, useRef, useState, type KeyboardEvent, type ChangeEvent } from "react";
import { Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface AgentFollowUpInputProps {
    onSend: (message: string) => void;
    disabled: boolean;
    placeholder?: string;
}

const MAX_HEIGHT = 120;
const MIN_CHARS = 5;

export function AgentFollowUpInput({
    onSend,
    disabled,
    placeholder = "Ask a follow-up question...",
}: AgentFollowUpInputProps) {
    const [value, setValue] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const canSend = value.trim().length >= MIN_CHARS && !disabled;

    const handleSend = useCallback(() => {
        const trimmed = value.trim();
        if (trimmed.length < MIN_CHARS || disabled) return;
        onSend(trimmed);
        setValue("");
        // Reset textarea height
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
        }
    }, [value, disabled, onSend]);

    const handleKeyDown = useCallback(
        (e: KeyboardEvent<HTMLTextAreaElement>) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        },
        [handleSend],
    );

    const handleChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
        setValue(e.target.value);
        // Auto-resize
        const el = e.target;
        el.style.height = "auto";
        el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
    }, []);

    return (
        <div className="flex items-end gap-2 border-t p-3">
            <Textarea
                ref={textareaRef}
                value={value}
                onChange={handleChange}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={disabled}
                rows={1}
                className="min-h-[40px] max-h-[120px] resize-none"
            />
            <Button
                size="icon"
                onClick={handleSend}
                disabled={!canSend}
                aria-label="Send message"
            >
                <Send className="h-4 w-4" />
            </Button>
        </div>
    );
}
