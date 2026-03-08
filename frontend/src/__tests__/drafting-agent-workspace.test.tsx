import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";

// ---------------------------------------------------------------------------
// Mock next-intl so useTranslations works without NextIntlClientProvider
// ---------------------------------------------------------------------------
vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

// ---------------------------------------------------------------------------
// Mock next/navigation
// ---------------------------------------------------------------------------
vi.mock("next/navigation", async () => {
  return {
    useRouter: () => ({
      push: vi.fn(),
      back: vi.fn(),
      replace: vi.fn(),
      prefetch: vi.fn(),
      refresh: vi.fn(),
    }),
    useSearchParams: () => new URLSearchParams(),
    useParams: () => ({}),
    usePathname: () => "/agents/drafting",
  };
});

// ---------------------------------------------------------------------------
// Mock @/lib/auth-context so the page renders as authenticated
// ---------------------------------------------------------------------------
vi.mock("@/lib/auth-context", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

// ---------------------------------------------------------------------------
// Mock @/lib/api
// ---------------------------------------------------------------------------
const mockGetDraftingTemplates = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getDraftingTemplates: (...args: unknown[]) =>
      mockGetDraftingTemplates(...args),
    runDraftingAgent: vi.fn(),
    resumeAgentExecution: vi.fn(),
    exportDraft: vi.fn(),
    loadTokens: vi.fn(),
    getAccessToken: () => "test-token",
  };
});

import DraftingAgentPage from "@/app/agents/drafting/page";
import { DraftSectionViewer } from "@/components/draft-section-viewer";

describe("DraftingAgentPage", () => {
  it("renders page heading", async () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    expect(screen.getByText("Drafting Agent")).toBeInTheDocument();
  });

  it("renders the page description text", () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    expect(
      screen.getByText(/Select a document type and provide case details/),
    ).toBeInTheDocument();
  });

  it("renders template selector while loading", () => {
    // Return a promise that does not resolve immediately so the loading state persists
    mockGetDraftingTemplates.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<DraftingAgentPage />);
    expect(screen.getByText("Loading templates...")).toBeInTheDocument();
  });

  it("renders template selector placeholder after templates load", async () => {
    mockGetDraftingTemplates.mockResolvedValue({
      templates: [
        {
          doc_type: "bail_application",
          display_name: "Bail Application",
          required_fields: ["accused_name", "offence_section"],
        },
        {
          doc_type: "writ_petition",
          display_name: "Writ Petition",
          required_fields: ["petitioner_name"],
        },
      ],
    });
    renderWithProviders(<DraftingAgentPage />);
    await waitFor(() => {
      expect(screen.getByText("Select document type")).toBeInTheDocument();
    });
  });

  it("renders case facts textarea", () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    expect(
      screen.getByPlaceholderText("Describe the facts of your case..."),
    ).toBeInTheDocument();
  });

  it("renders target court input", () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    expect(
      screen.getByPlaceholderText("e.g., High Court of Delhi"),
    ).toBeInTheDocument();
  });

  it("renders Start Drafting submit button", () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    expect(screen.getByText("Start Drafting")).toBeInTheDocument();
  });

  it("has disabled submit button when no document type is selected", async () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    await waitFor(() => {
      const button = screen.getByText("Start Drafting");
      expect(button).toBeDisabled();
    });
  });

  it("has disabled submit button when case facts is empty and no doc type selected", () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    const button = screen.getByText("Start Drafting");
    expect(button).toBeDisabled();
  });

  it("accepts case facts textarea input", () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    const textarea = screen.getByPlaceholderText(
      "Describe the facts of your case...",
    );
    fireEvent.change(textarea, {
      target: { value: "Petitioner was arrested on 15 March 2026..." },
    });
    expect(textarea).toHaveValue(
      "Petitioner was arrested on 15 March 2026...",
    );
  });

  it("accepts target court input", () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    const courtInput = screen.getByPlaceholderText("e.g., High Court of Delhi");
    fireEvent.change(courtInput, {
      target: { value: "High Court of Bombay" },
    });
    expect(courtInput).toHaveValue("High Court of Bombay");
  });

  it("renders back link to agents hub", () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    const agentLinks = screen.getAllByText("Agents");
    const backLink = agentLinks.find(
      (el) => el.closest("a")?.getAttribute("href") === "/agents",
    );
    expect(backLink).toBeTruthy();
  });

  it("fetches templates on mount", async () => {
    mockGetDraftingTemplates.mockResolvedValue({ templates: [] });
    renderWithProviders(<DraftingAgentPage />);
    await waitFor(() => {
      expect(mockGetDraftingTemplates).toHaveBeenCalled();
    });
  });
});

// ---------------------------------------------------------------------------
// DraftSectionViewer component tests
// ---------------------------------------------------------------------------

describe("DraftSectionViewer", () => {
  it("renders section names from the sections prop", () => {
    const sections = {
      introduction: "This is the introduction section of the draft.",
      prayer: "The petitioner humbly prays for the following relief...",
    };
    renderWithProviders(<DraftSectionViewer sections={sections} />);
    expect(screen.getByText("Introduction")).toBeInTheDocument();
    expect(screen.getByText("Prayer")).toBeInTheDocument();
  });

  it("renders section content when expanded (all sections expand by default)", () => {
    const sections = {
      introduction: "This is the introduction section of the draft.",
    };
    renderWithProviders(<DraftSectionViewer sections={sections} />);
    expect(
      screen.getByText("This is the introduction section of the draft."),
    ).toBeInTheDocument();
  });

  it("renders export buttons when onExport is provided", () => {
    const sections = { prayer: "Relief sought..." };
    const mockExport = vi.fn();
    renderWithProviders(
      <DraftSectionViewer sections={sections} onExport={mockExport} />,
    );
    expect(screen.getByText("Download DOCX")).toBeInTheDocument();
    expect(screen.getByText("Download PDF")).toBeInTheDocument();
  });

  it("does not render export buttons when onExport is not provided", () => {
    const sections = { prayer: "Relief sought..." };
    renderWithProviders(<DraftSectionViewer sections={sections} />);
    expect(screen.queryByText("Download DOCX")).not.toBeInTheDocument();
    expect(screen.queryByText("Download PDF")).not.toBeInTheDocument();
  });

  it("calls onExport with 'docx' when Download DOCX is clicked", () => {
    const sections = { prayer: "Relief sought..." };
    const mockExport = vi.fn();
    renderWithProviders(
      <DraftSectionViewer sections={sections} onExport={mockExport} />,
    );
    fireEvent.click(screen.getByText("Download DOCX"));
    expect(mockExport).toHaveBeenCalledWith("docx");
  });

  it("calls onExport with 'pdf' when Download PDF is clicked", () => {
    const sections = { prayer: "Relief sought..." };
    const mockExport = vi.fn();
    renderWithProviders(
      <DraftSectionViewer sections={sections} onExport={mockExport} />,
    );
    fireEvent.click(screen.getByText("Download PDF"));
    expect(mockExport).toHaveBeenCalledWith("pdf");
  });

  it("shows Revise button when onRevise is provided and section is expanded", () => {
    const sections = { introduction: "Introduction content." };
    const mockRevise = vi.fn();
    renderWithProviders(
      <DraftSectionViewer sections={sections} onRevise={mockRevise} />,
    );
    // Section is expanded by default; Revise button should be visible
    expect(screen.getByText("Revise")).toBeInTheDocument();
  });

  it("does not show Revise button when onRevise is not provided", () => {
    const sections = { introduction: "Introduction content." };
    renderWithProviders(<DraftSectionViewer sections={sections} />);
    expect(screen.queryByText("Revise")).not.toBeInTheDocument();
  });

  it("shows revision feedback textarea after clicking Revise", () => {
    const sections = { introduction: "Introduction content." };
    const mockRevise = vi.fn();
    renderWithProviders(
      <DraftSectionViewer sections={sections} onRevise={mockRevise} />,
    );
    fireEvent.click(screen.getByText("Revise"));
    expect(
      screen.getByPlaceholderText(
        "Describe what changes you want for this section...",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Submit Revision")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("Submit Revision button is disabled when feedback is empty", () => {
    const sections = { introduction: "Introduction content." };
    const mockRevise = vi.fn();
    renderWithProviders(
      <DraftSectionViewer sections={sections} onRevise={mockRevise} />,
    );
    fireEvent.click(screen.getByText("Revise"));
    const submitButton = screen.getByText("Submit Revision");
    expect(submitButton).toBeDisabled();
  });

  it("calls onRevise with section name and feedback when Submit Revision is clicked", () => {
    const sections = { introduction: "Introduction content." };
    const mockRevise = vi.fn();
    renderWithProviders(
      <DraftSectionViewer sections={sections} onRevise={mockRevise} />,
    );
    fireEvent.click(screen.getByText("Revise"));
    const feedbackTextarea = screen.getByPlaceholderText(
      "Describe what changes you want for this section...",
    );
    fireEvent.change(feedbackTextarea, {
      target: { value: "Make it more concise." },
    });
    fireEvent.click(screen.getByText("Submit Revision"));
    expect(mockRevise).toHaveBeenCalledWith(
      "introduction",
      "Make it more concise.",
    );
  });

  it("hides revision form after Cancel is clicked", () => {
    const sections = { introduction: "Introduction content." };
    const mockRevise = vi.fn();
    renderWithProviders(
      <DraftSectionViewer sections={sections} onRevise={mockRevise} />,
    );
    fireEvent.click(screen.getByText("Revise"));
    expect(
      screen.getByPlaceholderText(
        "Describe what changes you want for this section...",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText("Cancel"));
    expect(
      screen.queryByPlaceholderText(
        "Describe what changes you want for this section...",
      ),
    ).not.toBeInTheDocument();
  });

  it("formats multi-word section names with title case", () => {
    const sections = { case_background: "Background facts..." };
    renderWithProviders(<DraftSectionViewer sections={sections} />);
    expect(screen.getByText("Case Background")).toBeInTheDocument();
  });

  it("collapses section content when header is clicked", () => {
    const sections = { introduction: "Introduction content text." };
    renderWithProviders(<DraftSectionViewer sections={sections} />);
    // Content is initially visible
    expect(screen.getByText("Introduction content text.")).toBeInTheDocument();
    // Click the section header to collapse
    fireEvent.click(screen.getByText("Introduction"));
    // Content should be hidden
    expect(
      screen.queryByText("Introduction content text."),
    ).not.toBeInTheDocument();
  });

  it("re-expands section content when collapsed header is clicked again", () => {
    const sections = { introduction: "Introduction content text." };
    renderWithProviders(<DraftSectionViewer sections={sections} />);
    // Collapse
    fireEvent.click(screen.getByText("Introduction"));
    expect(
      screen.queryByText("Introduction content text."),
    ).not.toBeInTheDocument();
    // Expand again
    fireEvent.click(screen.getByText("Introduction"));
    expect(screen.getByText("Introduction content text.")).toBeInTheDocument();
  });
});
