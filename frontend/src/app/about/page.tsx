import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { Scale, Database, Brain, Shield } from "lucide-react";

export const metadata = {
  title: "About — Smriti",
  description: "About Smriti, the AI-powered Indian legal research platform.",
};

export default function AboutPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1">
        <section className="mx-auto max-w-3xl px-4 pt-16 pb-12">
          <h1 className="text-3xl font-semibold tracking-tight mb-6">
            About Smriti
          </h1>

          <p className="text-muted-foreground leading-relaxed mb-6">
            Smriti is an AI-powered legal research platform built for Indian
            lawyers, law students, and legal professionals. Our mission is to
            make legal research faster, more accurate, and accessible to
            everyone.
          </p>

          <div className="grid sm:grid-cols-2 gap-4 mb-10">
            {[
              {
                icon: Database,
                title: "Comprehensive Data",
                desc: "35,000+ Supreme Court judgments spanning 1950–2025, with continuous updates.",
              },
              {
                icon: Brain,
                title: "AI-Powered Search",
                desc: "Hybrid semantic + keyword search with query understanding and intelligent reranking.",
              },
              {
                icon: Scale,
                title: "Citation Intelligence",
                desc: "Interactive citation graphs showing how cases relate, cite, overrule, and distinguish each other.",
              },
              {
                icon: Shield,
                title: "Privacy First",
                desc: "DPDP Act 2023 compliant from day one. Your data is encrypted, audited, and under your control.",
              },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="border rounded-md p-4 bg-card">
                <Icon className="h-4 w-4 text-[var(--gold)] mb-2" />
                <h3 className="text-sm font-semibold mb-1">{title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {desc}
                </p>
              </div>
            ))}
          </div>

          <h2 className="text-xl font-semibold tracking-tight mb-4">
            Data Attribution
          </h2>
          <div className="border rounded-md p-4 bg-muted/30 mb-10">
            <p className="text-sm text-muted-foreground leading-relaxed">
              Smriti uses the{" "}
              <strong>Indian Supreme Court Judgments dataset</strong> by{" "}
              <a
                href="https://registry.opendata.aws/indian-supreme-court-judgments/"
                className="text-[var(--gold)] hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Dattam Labs
              </a>
              , licensed under{" "}
              <a
                href="https://creativecommons.org/licenses/by/4.0/"
                className="text-[var(--gold)] hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Creative Commons Attribution 4.0 International (CC-BY-4.0)
              </a>
              . The dataset contains 35,000+ digitized Supreme Court judgments
              with structured metadata, available as open data on AWS.
            </p>
          </div>

          <h2 className="text-xl font-semibold tracking-tight mb-4">
            Contact
          </h2>
          <p className="text-sm text-muted-foreground">
            For questions, feedback, or partnership inquiries, reach us at{" "}
            <a
              href="mailto:hello@smriti.law"
              className="text-[var(--gold)] hover:underline"
            >
              hello@smriti.law
            </a>
          </p>
        </section>
      </main>

      <Footer />
    </div>
  );
}
