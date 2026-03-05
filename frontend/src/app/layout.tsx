import type { Metadata } from "next";
import { Inter, Lora } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const lora = Lora({
  subsets: ["latin"],
  variable: "--font-lora",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Smriti — AI Legal Research",
  description:
    "AI-powered Indian legal research platform. Search Supreme Court and High Court judgments, statutes, and legal principles with precision.",
  keywords: [
    "Indian law",
    "legal research",
    "Supreme Court",
    "case law",
    "AI paralegal",
    "judgments",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${lora.variable} font-sans`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
