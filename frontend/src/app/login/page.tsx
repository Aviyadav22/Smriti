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
    const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});

    function validate(): boolean {
        const newErrors: { email?: string; password?: string } = {};
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            newErrors.email = "Please enter a valid email address";
        }
        if (password.length < 8) {
            newErrors.password = "Password must be at least 8 characters";
        }
        setFieldErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    }

    const isFormValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && password.length >= 8;

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setError("");
        if (!validate()) return;
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
                            <label htmlFor="login-email" className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Email</label>
                            <Input
                                id="login-email"
                                type="email"
                                autoComplete="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="you@firm.com"
                                required
                                className="h-9 text-sm rounded-md"
                            />
                            {fieldErrors.email && <p className="text-xs text-red-500 mt-1" role="alert">{fieldErrors.email}</p>}
                        </div>
                        <div>
                            <label htmlFor="login-password" className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Password</label>
                            <Input
                                id="login-password"
                                type="password"
                                autoComplete="current-password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                required
                                className="h-9 text-sm rounded-md"
                            />
                            <p className="text-[10px] text-muted-foreground mt-1">Passwords must be at least 8 characters</p>
                            {fieldErrors.password && <p className="text-xs text-red-500 mt-1" role="alert">{fieldErrors.password}</p>}
                        </div>

                        {error && <p className="text-xs text-destructive" role="alert">{error}</p>}

                        <Button type="submit" className="w-full h-9 text-xs rounded-md" disabled={loading || !isFormValid}>
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
