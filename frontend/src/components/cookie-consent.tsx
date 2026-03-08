"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useTranslations } from "next-intl";

const CONSENT_KEY = "smriti_cookie_consent";

export function CookieConsent() {
    const t = useTranslations("cookieConsent");
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const consent = localStorage.getItem(CONSENT_KEY);
        if (!consent) {
            setVisible(true);
        }
    }, []);

    function accept(level: "all" | "essential") {
        localStorage.setItem(CONSENT_KEY, level);
        setVisible(false);
    }

    if (!visible) return null;

    return (
        <div className="fixed bottom-0 inset-x-0 z-50 border-t bg-card/95 backdrop-blur-sm p-4">
            <div className="mx-auto max-w-4xl flex flex-col sm:flex-row items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground text-center sm:text-left">
                    {t("message")}
                </p>
                <div className="flex items-center gap-2 shrink-0">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => accept("essential")}
                    >
                        {t("essentialOnly")}
                    </Button>
                    <Button
                        size="sm"
                        onClick={() => accept("all")}
                    >
                        {t("acceptAll")}
                    </Button>
                </div>
            </div>
        </div>
    );
}
