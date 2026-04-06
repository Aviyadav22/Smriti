"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SidebarNavGroupProps {
    label: string;
    children: ReactNode;
    collapsed?: boolean;
}

export function SidebarNavGroup({ label, children, collapsed = false }: SidebarNavGroupProps) {
    return (
        <div className="mb-2">
            {collapsed ? (
                <div className="my-2 h-px bg-sidebar-border" />
            ) : (
                <div className="px-3 py-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                        {label}
                    </span>
                </div>
            )}
            <div className={cn("space-y-0.5", collapsed && "flex flex-col items-center")}>
                {children}
            </div>
        </div>
    );
}
