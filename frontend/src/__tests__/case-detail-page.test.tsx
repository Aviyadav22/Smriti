import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import CaseDetailPage from "@/app/case/[id]/page";
import type { CaseDetail } from "@/lib/types";

const pushMock = vi.fn();
const backMock = vi.fn();

vi.mock("next/navigation", async () => {
  return {
    useRouter: () => ({
      push: pushMock,
      back: backMock,
      replace: vi.fn(),
      prefetch: vi.fn(),
      refresh: vi.fn(),
    }),
    useSearchParams: () => new URLSearchParams(),
    useParams: () => ({ id: "case-001" }),
    usePathname: () => "/case/case-001",
  };
});

const mockGetCase = vi.fn();
const mockGetCaseCitations = vi.fn();
const mockGetCaseCitedBy = vi.fn();
const mockGetCaseSimilar = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getCase: (...args: unknown[]) => mockGetCase(...args),
    getCaseCitations: (...args: unknown[]) => mockGetCaseCitations(...args),
    getCaseCitedBy: (...args: unknown[]) => mockGetCaseCitedBy(...args),
    getCaseSimilar: (...args: unknown[]) => mockGetCaseSimilar(...args),
    getCasePdfUrl: (id: string) => `http://localhost:8000/api/v1/cases/${id}/pdf`,
    loadTokens: vi.fn(),
    getAccessToken: () => null,
  };
});

function makeCaseDetail(overrides: Partial<CaseDetail> = {}): CaseDetail {
  return {
    id: "case-001",
    title: "K.S. Puttaswamy v. Union of India",
    citation: "(2017) 10 SCC 1",
    case_id: "case-001",
    cnr: null,
    court: "Supreme Court of India",
    year: 2017,
    case_type: "Writ Petition",
    jurisdiction: "constitutional",
    bench_type: "constitution",
    judge: "J.S. Khehar, D.Y. Chandrachud, S.A. Bobde",
    author_judge: "D.Y. Chandrachud",
    petitioner: "Justice K.S. Puttaswamy (Retd.)",
    respondent: "Union of India",
    decision_date: "2017-08-24",
    disposal_nature: "Allowed",
    description: "Right to privacy declared a fundamental right",
    keywords: ["privacy", "fundamental rights", "Article 21"],
    acts_cited: ["Constitution of India", "Aadhaar Act, 2016"],
    cases_cited: null,
    ratio_decidendi: "Right to privacy is a constitutionally protected right under Part III of the Constitution.",
    pdf_storage_path: "/pdfs/case-001.pdf",
    source: "SCI",
    language: "en",
    chunk_count: 42,
    sections: {
      facts: "The petitioner challenged the constitutional validity of Aadhaar...",
      arguments: "The counsel for the petitioner argued that privacy is inherent...",
      judgment: "The court unanimously held that the right to privacy is protected...",
    },
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("CaseDetailPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
    backMock.mockClear();
    mockGetCase.mockClear();
    mockGetCaseCitations.mockClear();
    mockGetCaseCitedBy.mockClear();
    mockGetCaseSimilar.mockClear();

    mockGetCaseCitations.mockResolvedValue({ case_id: "case-001", citations: [], total: 0 });
    mockGetCaseCitedBy.mockResolvedValue({ case_id: "case-001", cited_by: [], total: 0 });
    mockGetCaseSimilar.mockResolvedValue({ case_id: "case-001", similar: [], total: 0 });
  });

  it("renders case title after loading", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("K.S. Puttaswamy v. Union of India")).toBeInTheDocument();
    });
  });

  it("renders citation badge", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("(2017) 10 SCC 1")).toBeInTheDocument();
    });
  });

  it("renders court and year badges", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Supreme Court of India")).toBeInTheDocument();
      expect(screen.getByText("2017")).toBeInTheDocument();
    });
  });

  it("renders case type and bench type badges", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Writ Petition")).toBeInTheDocument();
      expect(screen.getByText("constitution bench")).toBeInTheDocument();
    });
  });

  it("renders parties information", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Justice K.S. Puttaswamy (Retd.)")).toBeInTheDocument();
      expect(screen.getByText("Union of India")).toBeInTheDocument();
    });
  });

  it("renders judge bench and author judge", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText(/J\.S\. Khehar/)).toBeInTheDocument();
      // D.Y. Chandrachud appears in both the bench list and author line
      const matches = screen.getAllByText(/D\.Y\. Chandrachud/);
      expect(matches.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders ratio decidendi", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/constitutionally protected right/)
      ).toBeInTheDocument();
    });
  });

  it("renders keywords as badges", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("privacy")).toBeInTheDocument();
      expect(screen.getByText("fundamental rights")).toBeInTheDocument();
      expect(screen.getByText("Article 21")).toBeInTheDocument();
    });
  });

  it("renders acts cited", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Constitution of India")).toBeInTheDocument();
      expect(screen.getByText("Aadhaar Act, 2016")).toBeInTheDocument();
    });
  });

  it("renders section tabs", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /facts/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /arguments/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /judgment/i })).toBeInTheDocument();
    });
  });

  it("renders the PDF tab when pdf_storage_path exists", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /pdf/i })).toBeInTheDocument();
    });
  });

  it("renders citations tab", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /citations/i })).toBeInTheDocument();
    });
  });

  it("renders the back button", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Back to results")).toBeInTheDocument();
    });
  });

  it("shows error state when case fails to load", async () => {
    mockGetCase.mockRejectedValue(new Error("Case not found"));
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Case not found")).toBeInTheDocument();
    });
    expect(screen.getByText("Go Back")).toBeInTheDocument();
  });

  it("renders metadata details section", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail());
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Allowed")).toBeInTheDocument();
      expect(screen.getByText("2017-08-24")).toBeInTheDocument();
      expect(screen.getByText("42")).toBeInTheDocument();
    });
  });

  it("does not render PDF tab when no pdf_storage_path", async () => {
    mockGetCase.mockResolvedValue(makeCaseDetail({ pdf_storage_path: null }));
    renderWithProviders(<CaseDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("K.S. Puttaswamy v. Union of India")).toBeInTheDocument();
    });

    expect(screen.queryByRole("tab", { name: /^pdf$/i })).not.toBeInTheDocument();
  });
});
