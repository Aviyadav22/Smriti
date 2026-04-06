"use client";

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
    type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import { createElement } from "react";

interface SidebarState {
    /** User preference for collapsed state (persisted in localStorage) */
    isCollapsed: boolean;
    /** Whether the mobile sheet is open */
    isMobileOpen: boolean;
    /** True when on agent workspace or chat pages — sidebar renders collapsed regardless */
    autoCollapse: boolean;
    /** Toggle the collapsed state */
    toggle: () => void;
    /** Control the mobile sheet */
    setMobileOpen: (open: boolean) => void;
}

const STORAGE_KEY = "smriti-sidebar-collapsed";

const SidebarContext = createContext<SidebarState | null>(null);

export function SidebarProvider({ children }: { children: ReactNode }) {
    const pathname = usePathname();

    const [isCollapsed, setIsCollapsed] = useState(() => {
        if (typeof window === "undefined") return false;
        try {
            return localStorage.getItem(STORAGE_KEY) === "true";
        } catch {
            return false;
        }
    });

    const [isMobileOpen, setMobileOpen] = useState(false);

    // Auto-collapse on chat pages (they have their own content sidebar)
    const autoCollapse = useMemo(() => {
        if (!pathname) return false;
        const isChatPage = pathname.startsWith("/chat");
        return isChatPage;
    }, [pathname]);

    const toggle = useCallback(() => {
        setIsCollapsed((prev) => {
            const next = !prev;
            try {
                localStorage.setItem(STORAGE_KEY, String(next));
            } catch {
                // localStorage unavailable
            }
            return next;
        });
    }, []);

    const setMobileOpenCb = useCallback((open: boolean) => {
        setMobileOpen(open);
    }, []);

    // Close mobile sheet on route change
    useEffect(() => {
        setMobileOpen(false);
    }, [pathname]);

    const value = useMemo(
        () => ({
            isCollapsed,
            isMobileOpen,
            autoCollapse,
            toggle,
            setMobileOpen: setMobileOpenCb,
        }),
        [isCollapsed, isMobileOpen, autoCollapse, toggle, setMobileOpenCb],
    );

    return createElement(SidebarContext.Provider, { value }, children);
}

export function useSidebar(): SidebarState {
    const ctx = useContext(SidebarContext);
    if (!ctx) throw new Error("useSidebar must be used within SidebarProvider");
    return ctx;
}
