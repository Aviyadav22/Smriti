"use client";

import { useTranslations } from "next-intl";
import {
    Scale,
    Search,
    FileText,
    PenTool,
    GitBranch,
    Gavel,
    Building2,
    Upload,
    PanelLeftClose,
    PanelLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useSidebar } from "@/hooks/useSidebar";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { SidebarNavGroup } from "@/components/sidebar-nav-group";
import { SidebarNavItem } from "@/components/sidebar-nav-item";
import { LanguageToggle } from "@/components/language-toggle";
import { UserMenu } from "@/components/user-menu";

function SidebarContent({
    collapsed,
    onNavClick,
}: {
    collapsed: boolean;
    onNavClick?: () => void;
}) {
    const t = useTranslations("sidebar");

    return (
        <div className="flex flex-col h-full bg-sidebar text-sidebar-foreground">
            {/* Top: Logo + collapse toggle */}
            <div className="flex items-center h-14 px-3 border-b border-sidebar-border shrink-0">
                <div className={cn("flex items-center gap-2.5", collapsed && "justify-center w-full")}>
                    <Scale className="h-5 w-5 text-sidebar-primary shrink-0" />
                    {!collapsed && (
                        <span className="text-lg font-semibold tracking-tight font-[family-name:var(--font-lora)]">
                            Smriti
                        </span>
                    )}
                </div>
                {!collapsed && <CollapseButton />}
            </div>

            {/* Nav items (scrollable) */}
            <ScrollArea className="flex-1 px-2 py-3">
                <SidebarNavGroup label={t("agents")} collapsed={collapsed}>
                    <SidebarNavItem href="/agents/research" icon={Search} label={t("research")} collapsed={collapsed} onClick={onNavClick} />
                    <SidebarNavItem href="/agents/case-prep" icon={FileText} label={t("casePrep")} collapsed={collapsed} onClick={onNavClick} />
                    <SidebarNavItem href="/agents/strategy" icon={Scale} label={t("argBuilder")} collapsed={collapsed} onClick={onNavClick} />
                    <SidebarNavItem href="/agents/drafting" icon={PenTool} label={t("drafting")} collapsed={collapsed} onClick={onNavClick} />
                </SidebarNavGroup>

                <SidebarNavGroup label={t("explore")} collapsed={collapsed}>
                    <SidebarNavItem href="/graph" icon={GitBranch} label={t("citationGraph")} collapsed={collapsed} onClick={onNavClick} />
                    <SidebarNavItem href="/judges" icon={Gavel} label={t("judges")} collapsed={collapsed} onClick={onNavClick} />
                    <SidebarNavItem href="/courts" icon={Building2} label={t("courts")} collapsed={collapsed} onClick={onNavClick} />
                </SidebarNavGroup>

                <SidebarNavGroup label={t("myWork")} collapsed={collapsed}>
                    <SidebarNavItem href="/documents" icon={FileText} label={t("documents")} collapsed={collapsed} onClick={onNavClick} />
                    <SidebarNavItem href="/upload" icon={Upload} label={t("upload")} collapsed={collapsed} onClick={onNavClick} />
                </SidebarNavGroup>
            </ScrollArea>

            {/* Bottom: Language + User */}
            <div className="border-t border-sidebar-border px-2 py-2 space-y-1 shrink-0">
                <LanguageToggle compact={collapsed} />
                <UserMenu collapsed={collapsed} />
            </div>
        </div>
    );
}

function CollapseButton() {
    const { isCollapsed, toggle, autoCollapse } = useSidebar();
    const t = useTranslations("sidebar");

    // Don't show toggle when auto-collapsed (it would be confusing)
    if (autoCollapse) return null;

    return (
        <Button
            variant="ghost"
            size="icon"
            className="ml-auto h-7 w-7 text-sidebar-foreground hover:bg-sidebar-accent"
            onClick={toggle}
            aria-label={isCollapsed ? t("expand") : t("collapse")}
        >
            {isCollapsed ? (
                <PanelLeft className="h-4 w-4" />
            ) : (
                <PanelLeftClose className="h-4 w-4" />
            )}
        </Button>
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
