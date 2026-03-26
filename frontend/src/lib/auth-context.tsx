"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
    login as apiLogin,
    register as apiRegister,
    logout as apiLogout,
    loadTokens,
    getAccessToken,
    getRefreshToken,
    tryRefreshToken,
    onSessionExpired,
} from "@/lib/api";
import type { LoginRequest, RegisterRequest } from "@/lib/types";

interface AuthState {
    isAuthenticated: boolean;
    isLoading: boolean;
    /** Non-null when the last auth operation failed (login, register, session refresh). */
    authError: string | null;
    login: (req: LoginRequest) => Promise<void>;
    register: (req: RegisterRequest) => Promise<void>;
    logout: () => void;
    clearAuthError: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function isTokenExpired(token: string): boolean {
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        // 60s buffer to match api.ts — avoid mid-request expiration race
        return payload.exp * 1000 < Date.now() + 60_000;
    } catch {
        return true;
    }
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [authError, setAuthError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function init() {
            loadTokens();
            const token = getAccessToken();

            // Access token is valid — we're good
            if (token && !isTokenExpired(token)) {
                if (!cancelled) {
                    setIsAuthenticated(true);
                    setIsLoading(false);
                }
                return;
            }

            // Access token expired or missing — try refresh
            const refresh = getRefreshToken();
            if (refresh && !isTokenExpired(refresh)) {
                try {
                    const ok = await tryRefreshToken();
                    if (!cancelled) {
                        setIsAuthenticated(ok);
                        if (!ok) setAuthError("Session expired — please log in again");
                        setIsLoading(false);
                    }
                    return;
                } catch {
                    if (!cancelled) {
                        setAuthError("Session expired — please log in again");
                    }
                }
            }

            // No valid tokens at all
            if (!cancelled) {
                setIsAuthenticated(false);
                setIsLoading(false);
            }
        }

        init();
        return () => { cancelled = true; };
    }, []);

    // Listen for session-expired events from API layer — any 401 after refresh failure
    useEffect(() => {
        const unsubscribe = onSessionExpired(() => {
            setIsAuthenticated(false);
            setAuthError("Session expired — please log in again");
        });
        return unsubscribe;
    }, []);

    const login = useCallback(async (req: LoginRequest) => {
        setAuthError(null);
        try {
            await apiLogin(req);
            setIsAuthenticated(true);
        } catch (err) {
            setIsAuthenticated(false);
            const msg = err instanceof Error ? err.message : "Login failed";
            setAuthError(msg);
            throw err; // Re-throw so login page can also handle it
        }
    }, []);

    const register = useCallback(async (req: RegisterRequest) => {
        setAuthError(null);
        try {
            await apiRegister(req);
            setIsAuthenticated(true);
        } catch (err) {
            setIsAuthenticated(false);
            const msg = err instanceof Error ? err.message : "Registration failed";
            setAuthError(msg);
            throw err;
        }
    }, []);

    const logout = useCallback(() => {
        apiLogout();
        setIsAuthenticated(false);
        setAuthError(null);
    }, []);

    const clearAuthError = useCallback(() => setAuthError(null), []);

    const value = useMemo(
        () => ({ isAuthenticated, isLoading, authError, login, register, logout, clearAuthError }),
        [isAuthenticated, isLoading, authError, login, register, logout, clearAuthError],
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
}
