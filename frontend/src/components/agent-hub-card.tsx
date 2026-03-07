"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface AgentHubCardProps {
    title: string;
    description: string;
    icon: React.ReactNode;
    href: string;
    badge?: string;
}

export function AgentHubCard({ title, description, icon, href, badge }: AgentHubCardProps) {
    return (
        <Card className="flex flex-col justify-between">
            <CardHeader>
                <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                            {icon}
                        </div>
                        <div>
                            <CardTitle className="text-base">{title}</CardTitle>
                            {badge && (
                                <Badge variant="secondary" className="mt-1 text-[10px]">
                                    {badge}
                                </Badge>
                            )}
                        </div>
                    </div>
                </div>
                <CardDescription className="mt-2">{description}</CardDescription>
            </CardHeader>
            <CardContent>
                <Button asChild size="sm" className="w-full">
                    <Link href={href}>Start</Link>
                </Button>
            </CardContent>
        </Card>
    );
}
