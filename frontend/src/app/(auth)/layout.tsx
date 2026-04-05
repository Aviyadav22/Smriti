"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { SidebarProvider } from "@/hooks/useSidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Menu, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/hooks/useSidebar";

// Inner component that uses useSidebar (must be inside SidebarProvider)
function AuthShell({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading } = useAuth();
    const router = useRouter();
    const { setMobileOpen } = useSidebar();

    useEffect(() => {
        if (!isLoading && !isAuthenticated) {
            router.push("/login");
        }
    }, [isLoading, isAuthenticated, router]);

    if (isLoading) {
        return (
            <div className="flex h-screen items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!isAuthenticated) return null;

    return (
        <div className="flex h-screen overflow-hidden">
            <AppSidebar />
            <div className="flex-1 flex flex-col min-w-0">
                {/* Mobile top bar */}
                <div className="md:hidden flex items-center h-12 px-3 border-b bg-card/90 backdrop-blur-sm">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => setMobileOpen(true)}
                    >
                        <Menu className="h-4 w-4" />
                    </Button>
                    <span className="ml-2 text-sm font-semibold font-[family-name:var(--font-lora)]">
                        Smriti
                    </span>
                </div>
                <main className="flex-1 overflow-y-auto">
                    {children}
                </main>
            </div>
        </div>
    );
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
    return (
        <TooltipProvider delayDuration={0}>
            <SidebarProvider>
                <AuthShell>{children}</AuthShell>
            </SidebarProvider>
        </TooltipProvider>
    );
}
