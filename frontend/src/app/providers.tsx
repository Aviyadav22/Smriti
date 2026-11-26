"use client";

import type { ReactNode } from "react";
import { ThemeProvider } from "next-themes";
import { AuthProvider } from "@/lib/auth-context";

export function Providers({ children, nonce }: { children: ReactNode; nonce?: string }) {
    return (
        // The nonce lets next-themes' inline theme script pass the CSP (middleware.ts).
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false} nonce={nonce}>
            <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
    );
}
