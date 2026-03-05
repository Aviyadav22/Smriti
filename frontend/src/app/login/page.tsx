"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { useAuth } from "@/lib/auth-context";
import { Scale, Loader2 } from "lucide-react";

export default function LoginPage() {
    const { login } = useAuth();
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await login({ email, password });
            router.push("/search");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Login failed");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1 flex items-center justify-center px-4 py-16">
                <Card className="w-full max-w-sm p-6 rounded-md">
                    <div className="text-center mb-6">
                        <Scale className="h-6 w-6 mx-auto text-[var(--gold)] mb-2" />
                        <h1 className="text-xl font-semibold tracking-tight">Sign In</h1>
                        <p className="text-xs text-muted-foreground mt-1">Access your legal research dashboard</p>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-3">
                        <div>
                            <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Email</label>
                            <Input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="you@firm.com"
                                required
                                className="h-9 text-sm rounded-md"
                            />
                        </div>
                        <div>
                            <label className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Password</label>
                            <Input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                required
                                className="h-9 text-sm rounded-md"
                            />
                        </div>

                        {error && <p className="text-xs text-destructive">{error}</p>}

                        <Button type="submit" className="w-full h-9 text-xs rounded-md" disabled={loading}>
                            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Sign In"}
                        </Button>
                    </form>

                    <p className="text-xs text-center text-muted-foreground mt-4">
                        Don&rsquo;t have an account?{" "}
                        <Link href="/register" className="text-foreground hover:underline">Register</Link>
                    </p>
                </Card>
            </main>
            <Footer />
        </div>
    );
}
