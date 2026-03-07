import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import type { DocumentDetail } from "@/lib/types";

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
    useParams: () => ({ id: "test-doc-id" }),
    usePathname: () => "/documents/test-doc-id",
  };
});

const mockGetDocument = vi.fn();
const mockDeleteDocument = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getDocument: (...args: unknown[]) => mockGetDocument(...args),
    deleteDocument: (...args: unknown[]) => mockDeleteDocument(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => "test-token",
  };
});

import DocumentDetailPage from "@/app/documents/[id]/page";

function makeCompletedDoc(): DocumentDetail {
  return {
    id: "test-doc-id",
    filename: "test-brief.pdf",
    status: "completed",
    processing_step: null,
    file_size: 1024,
    created_at: "2026-03-07T00:00:00Z",
    updated_at: "2026-03-07T00:01:00Z",
    error_message: null,
    processing_started_at: "2026-03-07T00:00:00Z",
    processing_completed_at: "2026-03-07T00:01:00Z",
    analysis: {
      issues: [
        {
          title: "Right to Privacy",
          description: "Whether Article 21 is violated",
          supporting_precedents: [
            { case_id: "case-1", title: "Puttaswamy v. UOI", citation: "(2017) 10 SCC 1", score: 0.95 },
          ],
          statutes: ["IT Act, 2000"],
        },
      ],
      parties: { petitioner: "John Doe", respondent: "State" },
      key_facts: "Key fact 1\nKey fact 2",
      relief_sought: "Quash order",
      counter_arguments: [
        { issue_title: "Privacy", argument: "State power", response: "Must be proportional" },
      ],
      research_memo: "# Research Memo\n\nThis is the memo content.",
    },
  };
}

describe("DocumentDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state initially", () => {
    mockGetDocument.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithProviders(<DocumentDetailPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows completed analysis", async () => {
    mockGetDocument.mockResolvedValue(makeCompletedDoc());
    renderWithProviders(<DocumentDetailPage />);
    await waitFor(() => {
      expect(screen.getByText(/Right to Privacy/)).toBeInTheDocument();
    });
  });

  it("shows research memo", async () => {
    mockGetDocument.mockResolvedValue(makeCompletedDoc());
    renderWithProviders(<DocumentDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Research Memo/ })).toBeInTheDocument();
    });
  });

  it("shows processing status when not completed", async () => {
    mockGetDocument.mockResolvedValue({
      ...makeCompletedDoc(),
      status: "analyzing",
      processing_step: "Identifying legal issues",
      analysis: undefined,
    });
    renderWithProviders(<DocumentDetailPage />);
    await waitFor(() => {
      expect(screen.getByText(/analyzing/i)).toBeInTheDocument();
    });
  });

  it("shows error when failed", async () => {
    mockGetDocument.mockResolvedValue({
      ...makeCompletedDoc(),
      status: "failed",
      error_message: "Processing error occurred",
      analysis: undefined,
    });
    renderWithProviders(<DocumentDetailPage />);
    await waitFor(() => {
      expect(screen.getByText(/Processing error occurred/)).toBeInTheDocument();
    });
  });
});
