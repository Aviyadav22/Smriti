"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import { Search, Scale, LogOut, Menu, X, MessageSquare, GitBranch, Gavel, Upload, Bot, Building2, FileText, Globe } from "lucide-react";

function LanguageToggle() {
    const [locale, setLocaleState] = useState(() => {
        if (typeof document !== "undefined") {
            const match = document.cookie.match(/(?:^|; )locale=([^;]*)/);
            return match ? match[1] : "en";
        }
        return "en";
    });

    const toggleLocale = () => {
        const newLocale = locale === "en" ? "hi" : "en";
        document.cookie = `locale=${newLocale}; path=/; max-age=${60 * 60 * 24 * 365}`;
        setLocaleState(newLocale);
        window.location.reload();
    };

    return (
        <Button
            variant="ghost"
            size="sm"
            className="text-xs h-8 px-2 gap-1"
            onClick={toggleLocale}
            title={locale === "en" ? "Switch to Hindi" : "Switch to English"}
        >
            <Globe className="h-3.5 w-3.5" />
            <span>{locale === "en" ? "HI" : "EN"}</span>
        </Button>
    );
}

export function Header() {
    const { isAuthenticated, logout } = useAuth();
    const router = useRouter();
    const [query, setQuery] = useState("");
    const [mobileOpen, setMobileOpen] = useState(false);
    const t = useTranslations("header");
    const tc = useTranslations("common");

    function handleSearch(e: React.FormEvent) {
        e.preventDefault();
        if (query.trim()) {
            router.push(`/search?q=${encodeURIComponent(query.trim())}`);
            setQuery("");
        }
    }

    return (
        <header className="sticky top-0 z-50 border-b bg-card/90 backdrop-blur-sm">
            <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
                {/* Logo — classic serif style */}
                <Link href="/" className="flex items-center gap-2.5 shrink-0 group">
                    <Scale className="h-5 w-5 text-[var(--gold)]" />
                    <span className="text-lg font-semibold tracking-tight font-[family-name:var(--font-lora)]">
                        Smriti
                    </span>
                </Link>

                {/* Search bar — desktop */}
                <form onSubmit={handleSearch} className="hidden md:flex flex-1 max-w-lg mx-6">
                    <div className="relative w-full">
                        <label htmlFor="header-search" className="sr-only">{t("searchPlaceholder")}</label>
                        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            id="header-search"
                            placeholder={t("searchPlaceholder")}
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className="pl-9 h-9 text-sm bg-background border focus-visible:ring-1 focus-visible:ring-[var(--gold)]/40 rounded-md"
                        />
                    </div>
                </form>

                {/* Nav — desktop */}
                <nav className="hidden md:flex items-center gap-0.5 ml-auto">
                    <Button variant="ghost" size="sm" className="text-xs uppercase tracking-wider font-medium h-8 px-3" asChild>
                        <Link href="/search">{tc("search")}</Link>
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs uppercase tracking-wider font-medium h-8 px-3" asChild>
                        <Link href="/chat"><MessageSquare className="h-3.5 w-3.5 mr-1" /> {t("chat")}</Link>
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs uppercase tracking-wider font-medium h-8 px-3" asChild>
                        <Link href="/graph"><GitBranch className="h-3.5 w-3.5 mr-1" /> {t("graph")}</Link>
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs uppercase tracking-wider font-medium h-8 px-3" asChild>
                        <Link href="/agents"><Bot className="h-3.5 w-3.5 mr-1" /> {t("agents")}</Link>
                    </Button>
                    <Link href="/judges">
                        <Button variant="ghost" size="sm" className="gap-1.5 text-xs">
                            <Gavel className="h-3.5 w-3.5" />
                            <span className="hidden lg:inline">{t("judges")}</span>
                        </Button>
                    </Link>
                    <Button variant="ghost" size="sm" className="text-xs uppercase tracking-wider font-medium h-8 px-3" asChild>
                        <Link href="/courts"><Building2 className="h-3.5 w-3.5 mr-1" /> {t("courts")}</Link>
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs uppercase tracking-wider font-medium h-8 px-3" asChild>
                        <Link href="/upload"><Upload className="h-3.5 w-3.5 mr-1" /> {t("upload")}</Link>
                    </Button>
                    <Button variant="ghost" size="sm" className="text-xs uppercase tracking-wider font-medium h-8 px-3" asChild>
                        <Link href="/documents"><FileText className="h-3.5 w-3.5 mr-1" /> {t("documents")}</Link>
                    </Button>
                    <LanguageToggle />
                    {isAuthenticated ? (
                        <Button variant="ghost" size="sm" className="text-xs h-8 px-3" onClick={logout}>
                            <LogOut className="h-3.5 w-3.5 mr-1.5" /> {tc("logout")}
                        </Button>
                    ) : (
                        <>
                            <Button variant="ghost" size="sm" className="text-xs h-8 px-3" asChild>
                                <Link href="/login">{tc("login")}</Link>
                            </Button>
                            <Button size="sm" className="text-xs h-8 px-3 rounded-md" asChild>
                                <Link href="/register">{tc("register")}</Link>
                            </Button>
                        </>
                    )}
                </nav>

                {/* Mobile toggle */}
                <Button variant="ghost" size="icon" className="md:hidden ml-auto h-8 w-8" onClick={() => setMobileOpen(!mobileOpen)} aria-label={mobileOpen ? "Close menu" : "Open menu"}>
                    {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
                </Button>
            </div>

            {/* Mobile dropdown */}
            {mobileOpen && (
                <div className="md:hidden border-t px-4 py-3 space-y-2 bg-card">
                    <form onSubmit={handleSearch}>
                        <div className="relative">
                            <label htmlFor="header-search-mobile" className="sr-only">{t("searchPlaceholder")}</label>
                            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                            <Input id="header-search-mobile" placeholder={t("searchPlaceholder")} value={query} onChange={(e) => setQuery(e.target.value)} className="pl-9 text-sm" />
                        </div>
                    </form>
                    <div className="flex flex-col gap-0.5 pt-1">
                        <Button variant="ghost" size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                            <Link href="/search">{tc("search")}</Link>
                        </Button>
                        <Button variant="ghost" size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                            <Link href="/chat"><MessageSquare className="h-3.5 w-3.5 mr-1.5" /> {t("chat")}</Link>
                        </Button>
                        <Button variant="ghost" size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                            <Link href="/graph"><GitBranch className="h-3.5 w-3.5 mr-1.5" /> {t("graph")}</Link>
                        </Button>
                        <Button variant="ghost" size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                            <Link href="/agents"><Bot className="h-3.5 w-3.5 mr-1.5" /> {t("agents")}</Link>
                        </Button>
                        <Button variant="ghost" size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                            <Link href="/judges"><Gavel className="h-3.5 w-3.5 mr-1.5" /> {t("judges")}</Link>
                        </Button>
                        <Button variant="ghost" size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                            <Link href="/courts"><Building2 className="h-3.5 w-3.5 mr-1.5" /> {t("courts")}</Link>
                        </Button>
                        <Button variant="ghost" size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                            <Link href="/upload"><Upload className="h-3.5 w-3.5 mr-1.5" /> {t("upload")}</Link>
                        </Button>
                        <Button variant="ghost" size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                            <Link href="/documents"><FileText className="h-3.5 w-3.5 mr-1.5" /> {t("documents")}</Link>
                        </Button>
                        <LanguageToggle />
                        {isAuthenticated ? (
                            <Button variant="ghost" size="sm" className="justify-start text-xs" onClick={() => { logout(); setMobileOpen(false); }}>
                                <LogOut className="h-3.5 w-3.5 mr-1.5" /> {tc("logout")}
                            </Button>
                        ) : (
                            <>
                                <Button variant="ghost" size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                                    <Link href="/login">{tc("login")}</Link>
                                </Button>
                                <Button size="sm" className="justify-start text-xs" asChild onClick={() => setMobileOpen(false)}>
                                    <Link href="/register">{tc("register")}</Link>
                                </Button>
                            </>
                        )}
                    </div>
                </div>
            )}
        </header>
    );
}
