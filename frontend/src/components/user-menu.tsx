"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuTrigger,
    DropdownMenuContent,
    DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { User, Settings, LogOut } from "lucide-react";

interface UserMenuProps {
    /** When true, show only the avatar circle (no name text). */
    collapsed?: boolean;
}

export function UserMenu({ collapsed = false }: UserMenuProps) {
    const { isAuthenticated, logout } = useAuth();
    const router = useRouter();

    if (!isAuthenticated) return null;

    const handleLogout = () => {
        logout();
        router.push("/login");
    };

    const avatarCircle = (
        <div className="flex items-center justify-center h-8 w-8 rounded-full bg-sidebar-accent text-sidebar-foreground text-sm font-medium shrink-0">
            <User className="h-4 w-4" />
        </div>
    );

    const trigger = collapsed ? (
        <Tooltip>
            <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                    <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-center h-9 px-2"
                        aria-label="User menu"
                    >
                        {avatarCircle}
                    </Button>
                </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent side="right">Account</TooltipContent>
        </Tooltip>
    ) : (
        <DropdownMenuTrigger asChild>
            <Button
                variant="ghost"
                size="sm"
                className="w-full justify-start h-9 px-3 gap-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent"
                aria-label="User menu"
            >
                {avatarCircle}
                <span className="truncate">Account</span>
            </Button>
        </DropdownMenuTrigger>
    );

    return (
        <DropdownMenu>
            {trigger}
            <DropdownMenuContent side="right" align="end" className="w-48">
                <DropdownMenuItem
                    className="gap-2 cursor-pointer"
                    onClick={() => router.push("/settings")}
                >
                    <Settings className="h-4 w-4" />
                    Settings
                </DropdownMenuItem>
                <DropdownMenuItem
                    className="gap-2 cursor-pointer text-destructive focus:text-destructive"
                    onClick={handleLogout}
                >
                    <LogOut className="h-4 w-4" />
                    Logout
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
