import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";

// ---------------------------------------------------------------------------
// Mock next-intl — returns a translator that resolves to actual English values
// for the keys used by Header and Footer, so the rendered text matches the
// en.json messages file.
// ---------------------------------------------------------------------------
vi.mock("next-intl", () => {
  const messages: Record<string, Record<string, string>> = {
    header: {
      searchPlaceholder: "Search Indian case law...",
      chat: "Chat",
      graph: "Graph",
      agents: "Agents",
      documents: "Documents",
      judges: "Judges",
      upload: "Upload",
      courts: "Courts",
    },
    common: {
      search: "Search",
      login: "Login",
      logout: "Logout",
      register: "Register",
      loading: "Loading...",
    },
    footer: {
      tagline: "AI Legal Research",
      dataSource: "Judgment data from public records",
      disclaimer:
        "AI-assisted legal research — not legal advice. Verify all citations and consult a qualified advocate.",
      copyright: "Smriti — AI Legal Research",
    },
    agents: {
      title: "AI Agents",
      subtitle: "Autonomous legal research and case preparation assistants",
      history: "History",
      requiresDocument: "Requires uploaded document",
      "research.title": "Research Agent",
      "research.description": "Ask a legal question.",
      "casePrep.title": "Case Prep Agent",
      "casePrep.description": "Select a document.",
      "strategy.title": "Strategy Agent",
      "strategy.description": "Enter case facts and desired relief.",
      "drafting.title": "Drafting Agent",
      "drafting.description": "Select a document type.",
    },
    language: {
      en: "English",
      hi: "हिन्दी",
      toggle: "Language",
    },
  };

  return {
    useTranslations: (ns: string) => (key: string) => {
      const nsMessages = messages[ns];
      if (!nsMessages) return `${ns}.${key}`;
      return nsMessages[key] ?? `${ns}.${key}`;
    },
  };
});

// ---------------------------------------------------------------------------
// Mock next/navigation
// ---------------------------------------------------------------------------
const pushMock = vi.fn();

vi.mock("next/navigation", async () => {
  return {
    useRouter: () => ({
      push: pushMock,
      back: vi.fn(),
      replace: vi.fn(),
      prefetch: vi.fn(),
      refresh: vi.fn(),
    }),
    useSearchParams: () => new URLSearchParams(),
    useParams: () => ({}),
    usePathname: () => "/",
  };
});

// ---------------------------------------------------------------------------
// Mock @/lib/auth-context
// ---------------------------------------------------------------------------
vi.mock("@/lib/auth-context", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

// ---------------------------------------------------------------------------
// Mock @/lib/api
// ---------------------------------------------------------------------------
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    loadTokens: vi.fn(),
    getAccessToken: () => null,
  };
});

import { Header } from "@/components/header";
import { Footer } from "@/components/footer";

// ---------------------------------------------------------------------------
// English locale rendering (default)
// ---------------------------------------------------------------------------

describe("i18n integration — English (default locale)", () => {
  it("renders the Smriti brand name in the header", () => {
    renderWithProviders(<Header />);
    expect(screen.getByText("Smriti")).toBeInTheDocument();
  });

  it("renders the search placeholder in English", () => {
    renderWithProviders(<Header />);
    const inputs = screen.getAllByPlaceholderText("Search Indian case law...");
    expect(inputs.length).toBeGreaterThanOrEqual(1);
  });

  it("renders Chat navigation label in English", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Chat").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Graph navigation label in English", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Graph").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Agents navigation label in English", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Agents").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Upload navigation label in English", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Upload").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Courts navigation label in English", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Courts").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Documents navigation label in English", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Documents").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Login link when not authenticated", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Login").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Register link when not authenticated", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Register").length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// useTranslations hook — key resolution smoke tests
// ---------------------------------------------------------------------------

describe("i18n integration — useTranslations key resolution", () => {
  it("resolves header.searchPlaceholder to the English string", () => {
    renderWithProviders(<Header />);
    const inputs = screen.getAllByPlaceholderText("Search Indian case law...");
    expect(inputs.length).toBeGreaterThanOrEqual(1);
  });

  it("resolves common.search to 'Search'", () => {
    renderWithProviders(<Header />);
    const searchLinks = screen.getAllByText("Search");
    expect(searchLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("resolves header.chat to 'Chat'", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Chat").length).toBeGreaterThanOrEqual(1);
  });

  it("resolves common.login to 'Login'", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Login").length).toBeGreaterThanOrEqual(1);
  });

  it("resolves common.register to 'Register'", () => {
    renderWithProviders(<Header />);
    expect(screen.getAllByText("Register").length).toBeGreaterThanOrEqual(1);
  });

  it("resolves footer.tagline to 'AI Legal Research'", () => {
    renderWithProviders(<Footer />);
    expect(screen.getByText(/AI Legal Research/)).toBeInTheDocument();
  });

  it("resolves footer.dataSource to expected string", () => {
    renderWithProviders(<Footer />);
    expect(
      screen.getByText("Judgment data from public records"),
    ).toBeInTheDocument();
  });

  it("resolves footer.disclaimer and renders not legal advice text", () => {
    renderWithProviders(<Footer />);
    expect(screen.getByText(/not legal advice/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Language toggle rendering
// ---------------------------------------------------------------------------

describe("i18n integration — Language toggle in Header", () => {
  it("renders the language toggle button", () => {
    renderWithProviders(<Header />);
    // Default locale is "en" so the button shows "HI" (switch to Hindi)
    const hiButtons = screen.queryAllByText("HI");
    const enButtons = screen.queryAllByText("EN");
    // Either "HI" (en locale) or "EN" (hi locale) must be present
    const toggleVisible = hiButtons.length > 0 || enButtons.length > 0;
    expect(toggleVisible).toBe(true);
  });

  it("language toggle button is a button element", () => {
    renderWithProviders(<Header />);
    // The toggle renders as a Button with text "HI" or "EN"
    const hiButtons = screen.queryAllByText("HI");
    const enButtons = screen.queryAllByText("EN");
    const allToggleTexts = [...hiButtons, ...enButtons];
    expect(allToggleTexts.length).toBeGreaterThanOrEqual(1);
    const firstToggle = allToggleTexts[0];
    expect(firstToggle.closest("button")).toBeInTheDocument();
  });

  it("language toggle button has a title attribute", () => {
    renderWithProviders(<Header />);
    // Title is "Switch to Hindi" when locale is "en"
    const switchToHindiButtons = screen.queryAllByTitle("Switch to Hindi");
    const switchToEnglishButtons = screen.queryAllByTitle("Switch to English");
    const hasTitle =
      switchToHindiButtons.length > 0 || switchToEnglishButtons.length > 0;
    expect(hasTitle).toBe(true);
  });

  it("header logo links to home page", () => {
    renderWithProviders(<Header />);
    const logoLink = screen.getByText("Smriti").closest("a");
    expect(logoLink).toHaveAttribute("href", "/");
  });

  it("header search form accepts input", () => {
    renderWithProviders(<Header />);
    const inputs = screen.getAllByPlaceholderText("Search Indian case law...");
    const input = inputs[0];
    fireEvent.change(input, { target: { value: "Article 21" } });
    expect(input).toHaveValue("Article 21");
  });

  it("header search form navigates on submit", () => {
    renderWithProviders(<Header />);
    const inputs = screen.getAllByPlaceholderText("Search Indian case law...");
    const input = inputs[0];
    fireEvent.change(input, { target: { value: "right to privacy" } });
    fireEvent.submit(input.closest("form")!);
    expect(pushMock).toHaveBeenCalledWith(
      "/search?q=right%20to%20privacy",
    );
  });

  it("header search form does not navigate when query is empty", () => {
    pushMock.mockClear();
    renderWithProviders(<Header />);
    const inputs = screen.getAllByPlaceholderText("Search Indian case law...");
    const form = inputs[0].closest("form")!;
    fireEvent.submit(form);
    expect(pushMock).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Footer i18n
// ---------------------------------------------------------------------------

describe("i18n integration — Footer", () => {
  it("renders Smriti brand name", () => {
    renderWithProviders(<Footer />);
    expect(screen.getByText("Smriti")).toBeInTheDocument();
  });

  it("renders AI Legal Research tagline from footer.tagline", () => {
    renderWithProviders(<Footer />);
    expect(screen.getByText(/AI Legal Research/)).toBeInTheDocument();
  });

  it("renders data source attribution from footer.dataSource", () => {
    renderWithProviders(<Footer />);
    expect(
      screen.getByText("Judgment data from public records"),
    ).toBeInTheDocument();
  });

  it("renders CC-BY-4.0 license link pointing to Creative Commons", () => {
    renderWithProviders(<Footer />);
    const ccLink = screen.getByText("CC-BY-4.0");
    expect(ccLink).toBeInTheDocument();
    expect(ccLink.closest("a")).toHaveAttribute(
      "href",
      "https://creativecommons.org/licenses/by/4.0/",
    );
  });

  it("renders disclaimer text from footer.disclaimer", () => {
    renderWithProviders(<Footer />);
    expect(
      screen.getByText(/AI-assisted legal research/),
    ).toBeInTheDocument();
  });

  it("renders disclaimer that mentions 'consult a qualified advocate'", () => {
    renderWithProviders(<Footer />);
    expect(
      screen.getByText(/consult a qualified advocate/i),
    ).toBeInTheDocument();
  });
});
