"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

interface SidebarNavItemProps {
    href: string;
    icon: LucideIcon;
    label: string;
    collapsed?: boolean;
    badge?: string;
    onClick?: () => void;
}

export function SidebarNavItem({
    href,
    icon: Icon,
    label,
    collapsed = false,
    badge,
    onClick,
}: SidebarNavItemProps) {
    const pathname = usePathname();

    // Active: exact match or starts-with for nested routes
    const isActive = pathname === href || pathname.startsWith(href + "/");

    const content = (
        <Link
            href={href}
            onClick={onClick}
            className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-100 ease-out",
                isActive
                    ? "border-l-[3px] border-l-sidebar-primary bg-sidebar-accent text-sidebar-primary pl-[9px]"
                    : "border-l-[3px] border-l-transparent text-sidebar-foreground hover:bg-sidebar-accent pl-[9px]",
                collapsed && "justify-center px-0 py-2",
            )}
        >
            <Icon className={cn("h-4 w-4 shrink-0", isActive && "text-sidebar-primary")} />
            {!collapsed && (
                <>
                    <span className="truncate">{label}</span>
                    {badge && (
                        <span className="ml-auto text-xs rounded-full bg-sidebar-primary/10 text-sidebar-primary px-2 py-0.5">
                            {badge}
                        </span>
                    )}
                </>
            )}
        </Link>
    );

    if (collapsed) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>{content}</TooltipTrigger>
                <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
        );
    }

    return content;
}
