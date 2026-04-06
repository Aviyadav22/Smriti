"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
    User,
    Search,
    Palette,
    Bell,
    CreditCard,
    Users,
    Shield,
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useAuth } from "@/lib/auth-context";
import { ProfileSection } from "@/components/settings/profile-section";
import { PreferencesSection } from "@/components/settings/preferences-section";
import { AppearanceSection } from "@/components/settings/appearance-section";
import { NotificationsSection } from "@/components/settings/notifications-section";
import { BillingSection } from "@/components/settings/billing-section";
import { AdminUsersSection } from "@/components/settings/admin-users-section";
import { AdminAuditSection } from "@/components/settings/admin-audit-section";

const PERSONAL_TABS = [
    { value: "profile", icon: User, labelKey: "profile" },
    { value: "preferences", icon: Search, labelKey: "preferences" },
    { value: "appearance", icon: Palette, labelKey: "appearance" },
    { value: "notifications", icon: Bell, labelKey: "notifications" },
    { value: "billing", icon: CreditCard, labelKey: "billing" },
] as const;

const ADMIN_TABS = [
    { value: "users", icon: Users, labelKey: "userManagement" },
    { value: "audit", icon: Shield, labelKey: "auditLogs" },
] as const;

export default function SettingsPage() {
    const t = useTranslations("settings");
    const { user } = useAuth();
    const isAdmin = user?.role === "admin";

    // Hash-based deep linking
    const [activeTab, setActiveTab] = useState("profile");

    useEffect(() => {
        const hash = window.location.hash.replace("#", "");
        if (hash) setActiveTab(hash);
    }, []);

    const handleTabChange = (value: string) => {
        setActiveTab(value);
        window.history.replaceState(null, "", `#${value}`);
    };

    return (
        <div className="flex flex-col h-full">
            <div className="border-b px-6 py-4">
                <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
                <p className="text-sm text-muted-foreground mt-1">{t("subtitle")}</p>
            </div>

            <Tabs
                value={activeTab}
                onValueChange={handleTabChange}
                orientation="vertical"
                className="flex-1 flex flex-col md:flex-row min-h-0"
            >
                {/* Tab list — vertical on desktop, horizontal scroll on mobile */}
                <div className="md:w-56 shrink-0 border-b md:border-b-0 md:border-r">
                    <ScrollArea className="md:h-full">
                        <TabsList
                            variant="line"
                            className="flex md:flex-col w-full md:w-full md:items-stretch p-2 gap-0.5 overflow-x-auto md:overflow-x-visible"
                        >
                            {PERSONAL_TABS.map(({ value, icon: Icon, labelKey }) => (
                                <TabsTrigger
                                    key={value}
                                    value={value}
                                    className="justify-start gap-2 px-3 py-2 text-sm"
                                >
                                    <Icon className="h-4 w-4 shrink-0" />
                                    <span className="hidden md:inline">{t(`tabs.${labelKey}`)}</span>
                                </TabsTrigger>
                            ))}

                            {isAdmin && (
                                <>
                                    <div className="hidden md:block my-2 border-t" />
                                    {ADMIN_TABS.map(({ value, icon: Icon, labelKey }) => (
                                        <TabsTrigger
                                            key={value}
                                            value={value}
                                            className="justify-start gap-2 px-3 py-2 text-sm"
                                        >
                                            <Icon className="h-4 w-4 shrink-0" />
                                            <span className="hidden md:inline">{t(`tabs.${labelKey}`)}</span>
                                        </TabsTrigger>
                                    ))}
                                </>
                            )}
                        </TabsList>
                    </ScrollArea>
                </div>

                {/* Tab content */}
                <ScrollArea className="flex-1 min-h-0">
                    <div className="max-w-2xl mx-auto p-6">
                        <TabsContent value="profile"><ProfileSection /></TabsContent>
                        <TabsContent value="preferences"><PreferencesSection /></TabsContent>
                        <TabsContent value="appearance"><AppearanceSection /></TabsContent>
                        <TabsContent value="notifications"><NotificationsSection /></TabsContent>
                        <TabsContent value="billing"><BillingSection /></TabsContent>
                        {isAdmin && (
                            <>
                                <TabsContent value="users"><AdminUsersSection /></TabsContent>
                                <TabsContent value="audit"><AdminAuditSection /></TabsContent>
                            </>
                        )}
                    </div>
                </ScrollArea>
            </Tabs>
        </div>
    );
}
