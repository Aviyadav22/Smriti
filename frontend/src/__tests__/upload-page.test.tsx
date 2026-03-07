import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
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
    usePathname: () => "/upload",
  };
});

const mockUploadDocument = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    uploadDocument: (...args: unknown[]) => mockUploadDocument(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => "test-token",
  };
});

import UploadPage from "@/app/upload/page";

describe("UploadPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders upload area", () => {
    renderWithProviders(<UploadPage />);
    expect(screen.getByText("Upload Document")).toBeInTheDocument();
  });

  it("renders PDF instruction text", () => {
    renderWithProviders(<UploadPage />);
    expect(screen.getByText(/PDF files only/i)).toBeInTheDocument();
  });

  it("shows upload area for drag and drop", () => {
    renderWithProviders(<UploadPage />);
    // Should have a dropzone or file input area
    expect(screen.getByText(/drag|drop|browse|click/i)).toBeInTheDocument();
  });
});
