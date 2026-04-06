"use client";

import { createContext, useCallback, useContext, useState } from "react";
import type { AgentSession } from "@/lib/types";

/**
 * Lightweight context so the global AppSidebar can show
 * recent sessions from the active agent workspace.
 *
 * Provider lives in AuthLayout (wraps both sidebar & content).
 * AgentWorkspace registers its data via `setAgentSidebar`.
 * AppSidebar reads via `useAgentSidebar`.
 */
export interface AgentSidebarData {
    sessions: AgentSession[];
    activeSessionId: string | null;
    loading: boolean;
    onSelectSession: (id: string) => void;
    onDeleteSession: (id: string) => void;
    onNewSession: () => void;
}

interface AgentSidebarContextValue {
    data: AgentSidebarData | null;
    setData: (data: AgentSidebarData | null) => void;
}

const AgentSidebarCtx = createContext<AgentSidebarContextValue>({
    data: null,
    setData: () => {},
});

export function useAgentSidebar(): AgentSidebarData | null {
    return useContext(AgentSidebarCtx).data;
}

export function useSetAgentSidebar(): (data: AgentSidebarData | null) => void {
    return useContext(AgentSidebarCtx).setData;
}

export function AgentSidebarProvider({ children }: { children: React.ReactNode }) {
    const [data, setDataRaw] = useState<AgentSidebarData | null>(null);
    const setData = useCallback((d: AgentSidebarData | null) => setDataRaw(d), []);
    return (
        <AgentSidebarCtx.Provider value={{ data, setData }}>
            {children}
        </AgentSidebarCtx.Provider>
    );
}
