import { Header } from "@/components/header";
import { Footer } from "@/components/footer";

export const metadata = {
  title: "Terms of Service — Smriti",
  description: "Terms of service for using the Smriti legal research platform.",
};

export default function TermsPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1">
        <section className="mx-auto max-w-3xl px-4 pt-16 pb-12">
          <h1 className="text-3xl font-semibold tracking-tight mb-2">
            Terms of Service
          </h1>
          <p className="text-xs text-muted-foreground mb-8">
            Last updated: March 2026
          </p>

          <div className="space-y-6 text-sm text-muted-foreground leading-relaxed">
            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                1. Acceptance of Terms
              </h2>
              <p>
                By accessing or using Smriti (&quot;the Platform&quot;), you agree to be
                bound by these Terms of Service. If you do not agree, do not use
                the Platform.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                2. Description of Service
              </h2>
              <p>
                Smriti provides AI-assisted legal research tools including case
                search, citation analysis, AI agents, and document drafting. The
                Platform is designed to assist legal professionals and is not a
                substitute for qualified legal advice.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                3. No Legal Advice
              </h2>
              <p>
                Content provided by Smriti, including AI-generated analyses,
                research memos, and draft documents, does not constitute legal
                advice. Users should independently verify all citations, legal
                principles, and conclusions. Always consult a qualified advocate
                before relying on any information from the Platform.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                4. User Accounts
              </h2>
              <p>
                You are responsible for maintaining the security of your account
                credentials. You must not share your account with others or use
                another person&apos;s account. Notify us immediately of any
                unauthorized access.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                5. Acceptable Use
              </h2>
              <p>You agree not to:</p>
              <ul className="list-disc pl-6 mt-2 space-y-1">
                <li>
                  Use the Platform for any unlawful purpose
                </li>
                <li>
                  Attempt to reverse engineer, decompile, or extract source code
                </li>
                <li>
                  Scrape, crawl, or systematically download content beyond normal
                  use
                </li>
                <li>
                  Upload malicious files or attempt to compromise Platform
                  security
                </li>
                <li>
                  Misrepresent AI-generated content as human-authored legal work
                </li>
              </ul>
            </section>

            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                6. Intellectual Property
              </h2>
              <p>
                Court judgments are public domain. AI-generated analyses and
                research memos are provided for your personal and professional
                use. The Smriti platform, its code, design, and branding are
                proprietary.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                7. Data Privacy
              </h2>
              <p>
                Your use of the Platform is subject to our{" "}
                <a href="/privacy" className="text-[var(--gold)] hover:underline">
                  Privacy Policy
                </a>
                . We comply with the Digital Personal Data Protection Act, 2023
                (DPDP Act).
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                8. Limitation of Liability
              </h2>
              <p>
                Smriti is provided &quot;as is&quot; without warranties of any kind. We
                are not liable for any damages arising from your use of the
                Platform, including reliance on AI-generated content. Our total
                liability is limited to the amount you paid for the service in
                the preceding 12 months.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                9. Changes to Terms
              </h2>
              <p>
                We may update these terms from time to time. Continued use of
                the Platform after changes constitutes acceptance of the revised
                terms.
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold text-foreground mb-2">
                10. Governing Law
              </h2>
              <p>
                These terms are governed by the laws of India. Any disputes
                shall be subject to the exclusive jurisdiction of the courts in
                New Delhi.
              </p>
            </section>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
