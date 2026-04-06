"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Hook that intercepts navigation when a blocking condition is active
 * (e.g., a research agent is running). Shows an alert dialog for in-app
 * navigation and uses `beforeunload` for tab/window close.
 */
export function useNavigationGuard(isBlocked: boolean) {
    const router = useRouter();
    const [showDialog, setShowDialog] = useState(false);
    const pendingHref = useRef<string | null>(null);
    const pendingAction = useRef<(() => void) | null>(null);

    // Browser tab/window close guard
    useEffect(() => {
        if (!isBlocked) return;
        const handler = (e: BeforeUnloadEvent) => {
            e.preventDefault();
        };
        window.addEventListener("beforeunload", handler);
        return () => window.removeEventListener("beforeunload", handler);
    }, [isBlocked]);

    /** Call this instead of router.push() — shows dialog if blocked. */
    const guardedNavigate = useCallback(
        (href: string) => {
            if (isBlocked) {
                pendingHref.current = href;
                pendingAction.current = null;
                setShowDialog(true);
            } else {
                router.push(href);
            }
        },
        [isBlocked, router],
    );

    /** Guard a non-navigation action (e.g., switching sessions via state). */
    const guardedAction = useCallback(
        (action: () => void) => {
            if (isBlocked) {
                pendingHref.current = null;
                pendingAction.current = action;
                setShowDialog(true);
            } else {
                action();
            }
        },
        [isBlocked],
    );

    /** User chose "Continue in Background" — proceed with pending navigation/action. */
    const confirmLeave = useCallback(() => {
        setShowDialog(false);
        if (pendingHref.current) {
            router.push(pendingHref.current);
        } else if (pendingAction.current) {
            pendingAction.current();
        }
        pendingHref.current = null;
        pendingAction.current = null;
    }, [router]);

    /** User chose "Stay" or closed the dialog. */
    const cancelLeave = useCallback(() => {
        setShowDialog(false);
        pendingHref.current = null;
        pendingAction.current = null;
    }, []);

    return {
        showDialog,
        guardedNavigate,
        guardedAction,
        confirmLeave,
        cancelLeave,
    };
}
