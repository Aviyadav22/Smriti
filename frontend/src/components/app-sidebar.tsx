"use client";

import { useTranslations } from "next-intl";
import {
    Scale,
    Bot,
    GitBranch,
    Building2,
    Vault,
    PanelLeftClose,
    Settings,
    Trash2,
    Plus,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useSidebar } from "@/hooks/useSidebar";
import { useAgentSidebar } from "@/hooks/useAgentSidebarContext";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { SidebarNavItem } from "@/components/sidebar-nav-item";
import { LanguageToggle } from "@/components/language-toggle";
import { UserMenu } from "@/components/user-menu";
import { ThemeToggle } from "@/components/theme-toggle";

function SidebarContent({
    collapsed,
    onNavClick,
}: {
    collapsed: boolean;
    onNavClick?: () => void;
}) {
    const t = useTranslations("sidebar");
    const agentSidebar = useAgentSidebar();

    return (
        <div className="flex flex-col h-full bg-sidebar text-sidebar-foreground">
            {/* Top: Logo + collapse toggle */}
            <div className={cn(
                "flex items-center h-14 px-3 border-b border-sidebar-border shrink-0",
                collapsed ? "justify-center" : "justify-between",
            )}>
                {collapsed ? (
                    <CollapseButton />
                ) : (
                    <>
                        <div className="flex items-center gap-2.5">
                            <Scale className="h-5 w-5 text-sidebar-primary shrink-0" />
                            <span className="text-lg font-semibold tracking-tight font-[family-name:var(--font-lora)]">
                                Smriti
                            </span>
                        </div>
                        <CollapseButton />
                    </>
                )}
            </div>

            {/* Nav items */}
            <div className="px-2 py-3 shrink-0">
                <div className="space-y-0.5">
                    <SidebarNavItem href="/dashboard" icon={Bot} label={t("agents")} collapsed={collapsed} onClick={onNavClick} />
                    <SidebarNavItem href="/vault" icon={Vault} label={t("vault")} collapsed={collapsed} onClick={onNavClick} />
                    <SidebarNavItem href="/graph" icon={GitBranch} label={t("citationGraph")} collapsed={collapsed} onClick={onNavClick} />
                    <SidebarNavItem href="/courts" icon={Building2} label={t("courts")} collapsed={collapsed} onClick={onNavClick} />
                </div>
            </div>

            {/* Recent sessions — shown when on an agent workspace page */}
            {agentSidebar && !collapsed && (
                <RecentSessions data={agentSidebar} onNavClick={onNavClick} />
            )}

            {/* Spacer to push bottom icons down when no sessions */}
            {(!agentSidebar || collapsed) && <div className="flex-1" />}

            {/* Bottom: utility icons */}
            <div className="border-t border-sidebar-border px-2 py-2 shrink-0">
                <div className={cn(
                    "flex items-center",
                    collapsed ? "flex-col gap-1" : "justify-around",
                )}>
                    <LanguageToggle compact />
                    <ThemeToggle />
                    <SettingsButton />
                    <UserMenu collapsed />
                </div>
            </div>
        </div>
    );
}

function SettingsButton() {
    const router = useRouter();
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent"
                    aria-label="Settings"
                    onClick={() => router.push("/settings")}
                >
                    <Settings className="h-4.5 w-4.5" />
                </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Settings</TooltipContent>
        </Tooltip>
    );
}

function CollapseButton() {
    const { isCollapsed, toggle, autoCollapse } = useSidebar();
    const t = useTranslations("sidebar");

    // Don't show toggle when auto-collapsed (it would be confusing)
    if (autoCollapse) return null;

    if (isCollapsed) {
        // When collapsed, show the Scale logo icon as the expand button
        return (
            <Tooltip>
                <TooltipTrigger asChild>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-sidebar-primary hover:bg-sidebar-accent"
                        onClick={toggle}
                        aria-label={t("expand")}
                    >
                        <Scale className="h-5 w-5" />
                    </Button>
                </TooltipTrigger>
                <TooltipContent side="right">{t("expand")}</TooltipContent>
            </Tooltip>
        );
    }

    return (
        <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-sidebar-foreground hover:bg-sidebar-accent"
            onClick={toggle}
            aria-label={t("collapse")}
        >
            <PanelLeftClose className="h-4 w-4" />
        </Button>
    );
}

function timeAgo(dateStr: string): string {
    const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

function RecentSessions({
    data,
    onNavClick,
}: {
    data: NonNullable<ReturnType<typeof useAgentSidebar>>;
    onNavClick?: () => void;
}) {
    return (
        <div className="flex flex-col flex-1 min-h-0 border-t border-sidebar-border">
            {/* Header + new session */}
            <div className="flex items-center justify-between px-3 pt-3 pb-1">
                <span className="text-[11px] font-medium text-sidebar-foreground/40 uppercase tracking-wider">
                    Recent sessions
                </span>
                <button
                    onClick={() => { data.onNewSession(); onNavClick?.(); }}
                    className="p-1 rounded-md text-sidebar-foreground/40 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
                    aria-label="New session"
                >
                    <Plus className="h-3.5 w-3.5" />
                </button>
            </div>

            {/* Session list */}
            <ScrollArea className="flex-1 px-2 pb-2">
                {data.loading ? (
                    <p className="text-xs text-sidebar-foreground/30 px-2 py-4 text-center">Loading...</p>
                ) : data.sessions.length === 0 ? (
                    <p className="text-xs text-sidebar-foreground/30 px-2 py-4 text-center">No sessions yet</p>
                ) : (
                    <div className="space-y-0.5">
                        {data.sessions.map((s) => (
                            <div
                                key={s.id}
                                role="button"
                                tabIndex={0}
                                onClick={() => { data.onSelectSession(s.id); onNavClick?.(); }}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        data.onSelectSession(s.id);
                                        onNavClick?.();
                                    }
                                }}
                                className={cn(
                                    "group relative flex flex-col gap-0.5 rounded-md px-2.5 py-2 cursor-pointer transition-colors hover:bg-sidebar-accent/50",
                                    data.activeSessionId === s.id && "bg-sidebar-accent",
                                )}
                            >
                                <span className="text-xs font-medium leading-snug line-clamp-2 text-sidebar-foreground/80">
                                    {s.title || "Untitled"}
                                </span>
                                <span className="text-[10px] text-sidebar-foreground/30">
                                    {timeAgo(s.updated_at)}
                                </span>

                                {/* Delete on hover */}
                                <button
                                    type="button"
                                    onClick={(e) => { e.stopPropagation(); data.onDeleteSession(s.id); }}
                                    className="absolute right-1.5 top-1.5 p-0.5 rounded opacity-0 group-hover:opacity-100 text-sidebar-foreground/30 hover:text-destructive transition-all"
                                    aria-label="Delete session"
                                >
                                    <Trash2 className="h-3 w-3" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </ScrollArea>
        </div>
    );
}

export function AppSidebar() {
    const { isCollapsed, isMobileOpen, setMobileOpen, autoCollapse } = useSidebar();

    // Effective collapsed state: auto-collapse overrides user preference
    const collapsed = autoCollapse || isCollapsed;

    return (
        <>
            {/* Desktop sidebar */}
            <aside
                className={cn(
                    "hidden md:flex flex-col shrink-0 border-r border-sidebar-border transition-all duration-200 ease-out h-screen sticky top-0",
                    collapsed ? "w-[60px]" : "w-60",
                )}
            >
                <SidebarContent collapsed={collapsed} />
            </aside>

            {/* Mobile sidebar (Sheet) */}
            <Sheet open={isMobileOpen} onOpenChange={setMobileOpen}>
                <SheetContent side="left" className="w-60 p-0">
                    <SheetTitle className="sr-only">Navigation</SheetTitle>
                    <SidebarContent
                        collapsed={false}
                        onNavClick={() => setMobileOpen(false)}
                    />
                </SheetContent>
            </Sheet>
        </>
    );
}
