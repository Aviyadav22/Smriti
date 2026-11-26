import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { AgentSessionMessage, SessionDetail } from "@/lib/types";

const getAgentSessionMessages = vi.fn();
const getAgentSessionDetail = vi.fn();

vi.mock("@/lib/api", () => ({
    createAgentSession: vi.fn(),
    resumeAgentExecution: vi.fn(),
    getAgentSessions: vi.fn().mockResolvedValue({ sessions: [] }),
    getAgentSessionMessages: (sid: string) => getAgentSessionMessages(sid),
    getAgentSessionDetail: (sid: string) => getAgentSessionDetail(sid),
    deleteAgentSession: vi.fn(),
}));

import { useAgentSession } from "@/hooks/useAgentSession";

function memoMessage(content: string): AgentSessionMessage {
    return {
        id: `m-${content}`,
        role: "assistant",
        content,
        sources: null,
        message_type: "memo",
        execution_id: null,
        created_at: "2026-11-26T00:00:00Z",
    };
}

function emptyDetail(id: string): SessionDetail {
    return {
        id,
        agent_type: "research",
        title: id,
        created_at: "2026-11-26T00:00:00Z",
        updated_at: "2026-11-26T00:00:00Z",
        executions: [],
    };
}

function deferred<T>() {
    let resolve!: (v: T) => void;
    const promise = new Promise<T>((r) => { resolve = r; });
    return { promise, resolve };
}

describe("useAgentSession.loadSession", () => {
    beforeEach(() => {
        getAgentSessionMessages.mockReset();
        getAgentSessionDetail.mockReset();
    });

    it("reports loading until the session data arrives", async () => {
        const messages = deferred<AgentSessionMessage[]>();
        getAgentSessionMessages.mockReturnValue(messages.promise);
        getAgentSessionDetail.mockResolvedValue(emptyDetail("s1"));

        const { result } = renderHook(() => useAgentSession("research"));

        let load!: Promise<void>;
        act(() => { load = result.current.loadSession("s1"); });

        // While fetching: follow-up mode with no memo yet, but flagged as loading,
        // so the workspace shows a spinner rather than "did not complete".
        expect(result.current.isLoadingSession).toBe(true);
        expect(result.current.isFollowUp).toBe(true);
        expect(result.current.memo).toBe("");

        await act(async () => {
            messages.resolve([memoMessage("Memo for s1")]);
            await load;
        });

        expect(result.current.isLoadingSession).toBe(false);
        expect(result.current.memo).toBe("Memo for s1");
    });

    it("ignores a slow response for a session the user already left", async () => {
        const first = deferred<AgentSessionMessage[]>();
        getAgentSessionMessages.mockImplementation((sid: string) =>
            sid === "s1" ? first.promise : Promise.resolve([memoMessage("Memo for s2")]),
        );
        getAgentSessionDetail.mockImplementation((sid: string) => Promise.resolve(emptyDetail(sid)));

        const { result } = renderHook(() => useAgentSession("research"));

        let loadFirst!: Promise<void>;
        act(() => { loadFirst = result.current.loadSession("s1"); });
        await act(async () => { await result.current.loadSession("s2"); });

        expect(result.current.memo).toBe("Memo for s2");
        expect(result.current.isLoadingSession).toBe(false);

        await act(async () => {
            first.resolve([memoMessage("Memo for s1")]);
            await loadFirst;
        });

        await waitFor(() => expect(result.current.memo).toBe("Memo for s2"));
        expect(result.current.sessionId).toBe("s2");
        expect(result.current.isLoadingSession).toBe(false);
    });
});
