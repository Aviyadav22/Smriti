import { Header } from "@/components/header";
import { Footer } from "@/components/footer";

export default function PrivacyPage() {
    return (
        <div className="flex min-h-screen flex-col bg-background">
            <Header />
            <main className="flex-1">
                <div className="mx-auto max-w-3xl px-4 py-12">
                    <h1 className="text-3xl font-bold font-[family-name:var(--font-lora)] mb-2">
                        Privacy Policy
                    </h1>
                    <p className="text-sm text-muted-foreground mb-8">
                        Last updated: March 2026
                    </p>

                    <div className="prose prose-sm dark:prose-invert max-w-none space-y-8">
                        <section>
                            <h2 className="text-xl font-semibold mb-3">1. Data Collected</h2>
                            <p className="text-muted-foreground leading-relaxed">
                                Smriti collects the following categories of personal data:
                            </p>
                            <ul className="list-disc pl-6 text-muted-foreground space-y-1 mt-2">
                                <li>Account information (email address, name)</li>
                                <li>Authentication data (hashed passwords, session tokens)</li>
                                <li>Chat and research history (queries, agent interactions)</li>
                                <li>Uploaded documents (legal documents for analysis)</li>
                                <li>Usage analytics (search queries, feature usage)</li>
                                <li>Essential cookies (authentication, language preference)</li>
                            </ul>
                        </section>

                        <section>
                            <h2 className="text-xl font-semibold mb-3">2. Purpose of Data Processing</h2>
                            <p className="text-muted-foreground leading-relaxed">
                                Personal data is processed for the following purposes under the
                                Digital Personal Data Protection Act, 2023 (DPDP Act):
                            </p>
                            <ul className="list-disc pl-6 text-muted-foreground space-y-1 mt-2">
                                <li>Providing AI-powered legal research services</li>
                                <li>Authenticating and securing user accounts</li>
                                <li>Maintaining chat and research history for continuity</li>
                                <li>Improving search relevance and AI model responses</li>
                                <li>Compliance with legal obligations</li>
                            </ul>
                        </section>

                        <section>
                            <h2 className="text-xl font-semibold mb-3">3. Data Retention</h2>
                            <p className="text-muted-foreground leading-relaxed">
                                Personal data is retained for a maximum of <strong>365 days</strong> from
                                last activity, unless a longer retention period is required by law.
                                Audit logs required for DPDP compliance may be retained for up to
                                3 years. You may request early deletion at any time through the
                                account settings or DPDP data erasure endpoint.
                            </p>
                        </section>

                        <section>
                            <h2 className="text-xl font-semibold mb-3">4. Your Rights (DPDP Act)</h2>
                            <p className="text-muted-foreground leading-relaxed">
                                Under the DPDP Act 2023, you have the following rights:
                            </p>
                            <ul className="list-disc pl-6 text-muted-foreground space-y-1 mt-2">
                                <li>
                                    <strong>Right to Access (Section 11):</strong> View a summary of all
                                    personal data held about you via the Data Summary feature.
                                </li>
                                <li>
                                    <strong>Right to Erasure (Section 12):</strong> Request deletion of
                                    all personal data. This will deactivate your account and remove
                                    all chat history, documents, and research data.
                                </li>
                                <li>
                                    <strong>Right to Consent Withdrawal (Section 6):</strong> Withdraw
                                    your data processing consent at any time. This will cease all
                                    non-essential data processing.
                                </li>
                                <li>
                                    <strong>Right to Correction:</strong> Request correction of
                                    inaccurate personal data by contacting our support team.
                                </li>
                                <li>
                                    <strong>Right to Grievance Redressal:</strong> File a complaint
                                    regarding data processing practices.
                                </li>
                            </ul>
                        </section>

                        <section>
                            <h2 className="text-xl font-semibold mb-3">5. Data Source Attribution</h2>
                            <p className="text-muted-foreground leading-relaxed">
                                Judgment data is sourced from publicly available court records.
                                The Indian Supreme Court Judgments dataset is provided by{" "}
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
                                    CC-BY-4.0
                                </a>
                                .
                            </p>
                        </section>

                        <section>
                            <h2 className="text-xl font-semibold mb-3">6. Contact</h2>
                            <p className="text-muted-foreground leading-relaxed">
                                For privacy-related queries, data access requests, or grievances,
                                please contact the Data Protection Officer at{" "}
                                <a
                                    href="mailto:privacy@smriti.law"
                                    className="text-[var(--gold)] hover:underline"
                                >
                                    privacy@smriti.law
                                </a>
                                .
                            </p>
                        </section>
                    </div>
                </div>
            </main>
            <Footer />
        </div>
    );
}
