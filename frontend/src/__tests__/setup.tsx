import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

// Mock next/navigation globally
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
  usePathname: () => "/",
}));

// Mock next/link to render a plain anchor
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => {
    return <a href={href} {...props}>{children}</a>;
  },
}));

// Mock auth context globally — default to authenticated
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Mock next-intl globally
vi.mock("next-intl", () => ({
  useTranslations: (namespace?: string) => {
    // Return a function that returns the key itself (with namespace prefix for debugging)
    const t = (key: string) => {
      // Return sensible defaults for common keys used in components
      const fullKey = namespace ? `${namespace}.${key}` : key;
      const translations: Record<string, string> = {
        // Header
        "header.chat": "Chat",
        "header.graph": "Graph",
        "header.agents": "Agents",
        "header.upload": "Upload",
        "header.courts": "Courts",
        "header.documents": "Documents",
        "header.searchPlaceholder": "Search Indian case law...",
        "header.login": "Login",
        "header.register": "Register",
        "header.logout": "Logout",
        // Footer
        "footer.brand": "Smriti",
        "footer.tagline": "AI-powered Indian legal research",
        "footer.dataSource": "Supreme Court Judgments dataset by Dattam Labs",
        "footer.disclaimer": "For informational purposes only",
        "footer.copyright": "© 2024 Smriti. All rights reserved.",
        // Agents
        "agents.title": "AI Agent Hub",
        "agents.subtitle": "Specialized AI agents for legal workflows",
        "agents.history": "History",
        "agents.research.title": "Research Agent",
        "agents.research.description": "Deep legal research with citation verification",
        "agents.casePrep.title": "Case Prep Agent",
        "agents.casePrep.description": "Analyze uploaded documents",
        "agents.strategy.title": "Strategy Agent",
        "agents.strategy.description": "Litigation strategy with judge analytics",
        "agents.drafting.title": "Drafting Agent",
        "agents.drafting.description": "Draft Indian legal documents",
        "agents.requiresDocument": "Requires document",
        // Common
        "common.loading": "Loading...",
        "common.error": "Error",
        "common.submit": "Submit",
        "common.cancel": "Cancel",
        "common.back": "Back",
        // Language
        "language.switchToHindi": "Switch to Hindi",
        "language.switchToEnglish": "Switch to English",
      };
      return translations[fullKey] || key;
    };
    return t;
  },
  useLocale: () => "en",
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Stub window.scrollTo
Object.defineProperty(window, "scrollTo", {
  value: vi.fn(),
  writable: true,
});
