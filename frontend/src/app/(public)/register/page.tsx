"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth-context";
import { Scale, Loader2 } from "lucide-react";

export default function RegisterPage() {
    const { register } = useAuth();
    const router = useRouter();
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
    const [consentGiven, setConsentGiven] = useState(false);

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
            await register({ name, email, password, consent_given: consentGiven });
            router.push("/dashboard");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Registration failed");
        } finally {
            setLoading(false);
        }
    }

    return (
        <Card className="w-full max-w-sm p-6 rounded-md">
            <div className="text-center mb-6">
                <Scale className="h-6 w-6 mx-auto text-[var(--gold)] mb-2" />
                <h1 className="text-xl font-semibold tracking-tight">Create Account</h1>
                <p className="text-xs text-muted-foreground mt-1">Start your legal research journey</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                    <label htmlFor="register-name" className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Full Name</label>
                    <Input
                        id="register-name"
                        autoComplete="name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Advocate Name"
                        required
                        className="h-9 text-sm rounded-md"
                    />
                </div>
                <div>
                    <label htmlFor="register-email" className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Email</label>
                    <Input
                        id="register-email"
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
                    <label htmlFor="register-password" className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1 block">Password</label>
                    <Input
                        id="register-password"
                        type="password"
                        autoComplete="new-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Min 8 characters"
                        required
                        minLength={8}
                        className="h-9 text-sm rounded-md"
                    />
                    <p className="text-[10px] text-muted-foreground mt-1">Passwords must be at least 8 characters</p>
                    {fieldErrors.password && <p className="text-xs text-red-500 mt-1" role="alert">{fieldErrors.password}</p>}
                </div>

                <div className="flex items-start gap-2 text-xs text-muted-foreground pt-1">
                    <input type="checkbox" required className="mt-0.5" id="consent" checked={consentGiven} onChange={(e) => setConsentGiven(e.target.checked)} />
                    <label htmlFor="consent">
                        I consent to the processing of my data in accordance with the{" "}
                        <span className="text-foreground">Digital Personal Data Protection Act, 2023</span>.
                    </label>
                </div>

                {error && <p className="text-xs text-destructive" role="alert">{error}</p>}

                <Button type="submit" className="w-full h-9 text-xs rounded-md" disabled={loading || !isFormValid}>
                    {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Create Account"}
                </Button>
            </form>

            <p className="text-xs text-center text-muted-foreground mt-4">
                Already have an account?{" "}
                <Link href="/login" className="text-foreground hover:underline">Sign In</Link>
            </p>
        </Card>
    );
}
