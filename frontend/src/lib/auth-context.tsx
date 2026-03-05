"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
    login as apiLogin,
    register as apiRegister,
    logout as apiLogout,
    loadTokens,
    getAccessToken,
} from "@/lib/api";
import type { LoginRequest, RegisterRequest } from "@/lib/types";

interface AuthState {
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (req: LoginRequest) => Promise<void>;
    register: (req: RegisterRequest) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        loadTokens();
        setIsAuthenticated(!!getAccessToken());
        setIsLoading(false);
    }, []);

    const login = useCallback(async (req: LoginRequest) => {
        await apiLogin(req);
        setIsAuthenticated(true);
    }, []);

    const register = useCallback(async (req: RegisterRequest) => {
        await apiRegister(req);
        setIsAuthenticated(true);
    }, []);

    const logout = useCallback(() => {
        apiLogout();
        setIsAuthenticated(false);
    }, []);

    const value = useMemo(
        () => ({ isAuthenticated, isLoading, login, register, logout }),
        [isAuthenticated, isLoading, login, register, logout],
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
}
