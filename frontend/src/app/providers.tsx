"use client";

import type { ReactNode } from "react";
import { ThemeProvider } from "next-themes";
import { AuthProvider } from "@/lib/auth-context";

export function Providers({ children }: { children: ReactNode }) {
    return (
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
            <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
    );
}
