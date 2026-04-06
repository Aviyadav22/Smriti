"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
    login as apiLogin,
    register as apiRegister,
    logout as apiLogout,
    loadTokens,
    getAccessToken,
    tryRefreshToken,
    onSessionExpired,
} from "@/lib/api";
import type { LoginRequest, RegisterRequest } from "@/lib/types";

export interface AuthUser {
    id: string;
    role: "admin" | "researcher" | "viewer";
}

interface AuthState {
    isAuthenticated: boolean;
    isLoading: boolean;
    /** Non-null when the last auth operation failed (login, register, session refresh). */
    authError: string | null;
    /** Decoded from JWT — available when authenticated. */
    user: AuthUser | null;
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

function decodeAuthUser(token: string): AuthUser | null {
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        if (payload.sub && payload.role) {
            return { id: payload.sub, role: payload.role };
        }
        return null;
    } catch {
        return null;
    }
}

export function AuthProvider({ children }: { children: ReactNode }) {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [authError, setAuthError] = useState<string | null>(null);
    const [user, setUser] = useState<AuthUser | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function init() {
            // Migrate any legacy localStorage tokens (one-time cleanup)
            loadTokens();
            const token = getAccessToken();

            // Access token is valid — we're good
            if (token && !isTokenExpired(token)) {
                if (!cancelled) {
                    setUser(decodeAuthUser(token));
                    setIsAuthenticated(true);
                    setIsLoading(false);
                }
                return;
            }

            // Access token expired or missing — try refresh via httpOnly cookie.
            // We can't check if the cookie exists from JS, so just attempt it.
            try {
                const ok = await tryRefreshToken();
                if (!cancelled) {
                    setIsAuthenticated(ok);
                    if (ok) {
                        const refreshedToken = getAccessToken();
                        if (refreshedToken) setUser(decodeAuthUser(refreshedToken));
                    } else {
                        setAuthError("Session expired — please log in again");
                    }
                    setIsLoading(false);
                }
                return;
            } catch {
                if (!cancelled) {
                    setAuthError("Session expired — please log in again");
                }
            }

            // No valid session
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
            setUser(null);
            setAuthError("Session expired — please log in again");
        });
        return unsubscribe;
    }, []);

    const login = useCallback(async (req: LoginRequest) => {
        setAuthError(null);
        try {
            await apiLogin(req);
            const token = getAccessToken();
            if (token) setUser(decodeAuthUser(token));
            setIsAuthenticated(true);
        } catch (err) {
            setIsAuthenticated(false);
            setUser(null);
            const msg = err instanceof Error ? err.message : "Login failed";
            setAuthError(msg);
            throw err; // Re-throw so login page can also handle it
        }
    }, []);

    const register = useCallback(async (req: RegisterRequest) => {
        setAuthError(null);
        try {
            await apiRegister(req);
            const token = getAccessToken();
            if (token) setUser(decodeAuthUser(token));
            setIsAuthenticated(true);
        } catch (err) {
            setIsAuthenticated(false);
            setUser(null);
            const msg = err instanceof Error ? err.message : "Registration failed";
            setAuthError(msg);
            throw err;
        }
    }, []);

    const logout = useCallback(() => {
        apiLogout();
        setIsAuthenticated(false);
        setUser(null);
        setAuthError(null);
    }, []);

    const clearAuthError = useCallback(() => setAuthError(null), []);

    const value = useMemo(
        () => ({ isAuthenticated, isLoading, authError, user, login, register, logout, clearAuthError }),
        [isAuthenticated, isLoading, authError, user, login, register, logout, clearAuthError],
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
}
