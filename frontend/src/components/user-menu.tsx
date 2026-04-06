"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { LogOut } from "lucide-react";

export function UserMenu({ collapsed = false }: { collapsed?: boolean }) {
    const { isAuthenticated, logout } = useAuth();
    const router = useRouter();

    if (!isAuthenticated) return null;

    const handleLogout = () => {
        logout();
        router.push("/login");
    };

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent"
                    onClick={handleLogout}
                    aria-label="Sign out"
                >
                    <LogOut className="h-4.5 w-4.5" />
                </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Sign out</TooltipContent>
        </Tooltip>
    );
}
