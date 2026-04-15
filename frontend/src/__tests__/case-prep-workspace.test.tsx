import { describe, it, expect, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";

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
    usePathname: () => "/agents/case-prep",
  };
});

const mockGetDocuments = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getDocuments: (...args: unknown[]) => mockGetDocuments(...args),
    runCasePrepAgent: vi.fn(),
    resumeAgentExecution: vi.fn(),
    loadTokens: vi.fn(),
    getAccessToken: () => "test-token",
  };
});

import CasePrepAgentPage from "@/app/(auth)/agents/case-prep/page";

describe("CasePrepAgentPage", () => {
  it("renders page heading", () => {
    mockGetDocuments.mockResolvedValue({ documents: [], total: 0, page: 1, page_size: 100, total_pages: 1 });
    renderWithProviders(<CasePrepAgentPage />);
    expect(screen.getByText("Case Prep Agent")).toBeInTheDocument();
  });

  it("shows empty state when no completed documents", async () => {
    mockGetDocuments.mockResolvedValue({ documents: [], total: 0, page: 1, page_size: 100, total_pages: 1 });
    renderWithProviders(<CasePrepAgentPage />);
    await waitFor(() => {
      expect(screen.getByText(/No analyzed documents found/)).toBeInTheDocument();
    });
  });

  it("renders document selector when documents exist", async () => {
    mockGetDocuments.mockResolvedValue({
      documents: [
        { id: "doc-1", filename: "test.pdf", status: "completed", processing_step: null, file_size: 1000, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", error_message: null },
      ],
      total: 1,
      page: 1,
      page_size: 100,
      total_pages: 1,
    });
    renderWithProviders(<CasePrepAgentPage />);
    await waitFor(() => {
      expect(screen.getByLabelText("Select a document")).toBeInTheDocument();
    });
  });

});
