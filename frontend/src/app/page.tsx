"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { Search, BookOpen, Scale, Building2, ArrowRight } from "lucide-react";

const EXAMPLE_QUERIES = [
  "Right to privacy Supreme Court",
  "Section 498A IPC dowry cruelty",
  "Kesavananda Bharati case",
  "Anticipatory bail conditions 2023",
  "Article 21 right to life",
  "Environmental protection PIL",
];

const STATS = [
  { label: "Judgments", value: "35,000+", icon: BookOpen },
  { label: "Courts", value: "25+", icon: Building2 },
  { label: "Years Covered", value: "1950–2025", icon: Scale },
];

export default function HomePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  }

  function handleExampleClick(q: string) {
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          {/* Subtle texture overlay for parchment feel */}
          <div className="absolute inset-0 opacity-[0.03] bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20width%3D%2260%22%20height%3D%2260%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cfilter%20id%3D%22noise%22%3E%3CfeTurbulence%20baseFrequency%3D%220.65%22%20numOctaves%3D%223%22%20stitchTiles%3D%22stitch%22%2F%3E%3C%2Ffilter%3E%3Crect%20width%3D%22100%25%22%20height%3D%22100%25%22%20filter%3D%22url(%23noise)%22%20opacity%3D%220.4%22%2F%3E%3C%2Fsvg%3E')]" />

          <div className="relative mx-auto max-w-4xl px-4 pt-24 pb-20 text-center">
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-semibold tracking-tight leading-[1.1] mb-4">
              The AI-Powered{" "}
              <span className="text-[var(--gold)]">Paralegal</span>
            </h1>

            <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
              Save hours of case research. Smriti delivers precise judgments
              and case laws in seconds.
            </p>

            {/* Main search */}
            <form onSubmit={handleSearch} className="max-w-xl mx-auto mb-8">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search judgments, statutes, or legal principles…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="pl-11 pr-24 h-12 text-sm bg-card border shadow-sm focus-visible:ring-1 focus-visible:ring-[var(--gold)]/40 rounded-md"
                />
                <Button
                  type="submit"
                  size="sm"
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 h-9 px-4 text-xs rounded-md"
                >
                  Search
                </Button>
              </div>
            </form>

            {/* Example queries */}
            <div className="flex flex-wrap justify-center gap-2">
              {EXAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => handleExampleClick(q)}
                  className="text-xs text-muted-foreground px-3 py-1.5 rounded-md border border-transparent hover:border-border hover:text-foreground bg-muted/50 hover:bg-muted"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Stats bar */}
        <section className="border-y bg-card/50">
          <div className="mx-auto max-w-3xl px-4 py-6">
            <div className="grid grid-cols-3 gap-4 text-center">
              {STATS.map(({ label, value, icon: Icon }) => (
                <div key={label}>
                  <Icon className="h-4 w-4 mx-auto mb-1.5 text-[var(--gold)]" />
                  <div className="text-lg sm:text-xl font-semibold font-[family-name:var(--font-lora)]">
                    {value}
                  </div>
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground mt-0.5">
                    {label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Features */}
        <section className="mx-auto max-w-5xl px-4 py-16">
          <h2 className="text-2xl font-semibold text-center mb-10 tracking-tight">
            How Smriti Works
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                title: "Search",
                desc: "Type a legal query in natural language. Our AI understands intent, extracts entities, and searches across vector and full-text indexes simultaneously.",
                step: "01",
              },
              {
                title: "Discover",
                desc: "Browse results with intelligent filters — by court, year, case type, judge, or statute. Every result includes a relevance-ranked snippet.",
                step: "02",
              },
              {
                title: "Analyze",
                desc: "Read section-tagged judgments, explore citation networks, find similar cases, and trace how legal principles evolved over time.",
                step: "03",
              },
            ].map(({ title, desc, step }) => (
              <div
                key={step}
                className="border rounded-md p-6 bg-card hover:shadow-sm group"
              >
                <div className="text-xs text-[var(--gold)] font-medium uppercase tracking-widest mb-3">
                  Step {step}
                </div>
                <h3 className="text-lg font-semibold mb-2 tracking-tight">{title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="border-t bg-card/50">
          <div className="mx-auto max-w-2xl px-4 py-12 text-center">
            <h2 className="text-xl font-semibold mb-3 tracking-tight">
              Start Researching
            </h2>
            <p className="text-sm text-muted-foreground mb-6">
              Free to use. No credit card required.
            </p>
            <Button asChild className="rounded-md h-10 px-6 text-sm">
              <a href="/register">
                Create Account <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </a>
            </Button>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
