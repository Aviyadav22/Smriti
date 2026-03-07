import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import type { JudgeListResponse } from "@/lib/types";

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
    usePathname: () => "/judges",
  };
});

const mockGetJudges = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getJudges: (...args: unknown[]) => mockGetJudges(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => null,
  };
});

import JudgesPage from "@/app/judges/page";

function makeJudgeListResponse(
  overrides: Partial<JudgeListResponse> = {},
): JudgeListResponse {
  return {
    judges: [
      { name: "D.Y. Chandrachud", total_cases: 450, cases_authored: 312 },
      { name: "S.A. Bobde", total_cases: 280, cases_authored: 195 },
    ],
    total: 2,
    page: 1,
    page_size: 20,
    total_pages: 1,
    ...overrides,
  };
}

describe("JudgesPage", () => {
  beforeEach(() => {
    mockGetJudges.mockClear();
    mockGetJudges.mockResolvedValue(makeJudgeListResponse());
  });

  it("renders page title 'Judge Directory'", async () => {
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      expect(screen.getByText("Judge Directory")).toBeInTheDocument();
    });
  });

  it("displays judge names from API", async () => {
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      expect(screen.getByText("D.Y. Chandrachud")).toBeInTheDocument();
    });
    expect(screen.getByText("S.A. Bobde")).toBeInTheDocument();
  });

  it("displays case counts", async () => {
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      expect(screen.getByText("450")).toBeInTheDocument();
      expect(screen.getByText("312")).toBeInTheDocument();
      expect(screen.getByText("280")).toBeInTheDocument();
      expect(screen.getByText("195")).toBeInTheDocument();
    });
  });

  it("has search input with placeholder 'Search judges'", async () => {
    renderWithProviders(<JudgesPage />);
    expect(screen.getByPlaceholderText("Search judges")).toBeInTheDocument();
  });

  it("shows loading state", async () => {
    mockGetJudges.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithProviders(<JudgesPage />);
    expect(screen.getByText("Loading judges…")).toBeInTheDocument();
  });

  it("links to judge profile pages", async () => {
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      expect(screen.getByText("D.Y. Chandrachud")).toBeInTheDocument();
    });

    const link = screen.getByText("D.Y. Chandrachud").closest("a");
    expect(link).toHaveAttribute(
      "href",
      `/judge/${encodeURIComponent("D.Y. Chandrachud")}`,
    );
  });

  it("shows empty state when no judges found", async () => {
    mockGetJudges.mockResolvedValue(
      makeJudgeListResponse({ judges: [], total: 0 }),
    );
    renderWithProviders(<JudgesPage />);
    await waitFor(() => {
      expect(screen.getByText("No judges found.")).toBeInTheDocument();
    });
  });

  it("triggers search on input change after debounce", async () => {
    renderWithProviders(<JudgesPage />);

    await waitFor(() => {
      expect(mockGetJudges).toHaveBeenCalledTimes(1);
    });

    const input = screen.getByPlaceholderText("Search judges");
    fireEvent.change(input, { target: { value: "Chandrachud" } });

    // After debounce, a new call with search param should fire
    await waitFor(() => {
      expect(mockGetJudges).toHaveBeenCalledWith(
        expect.objectContaining({ search: "Chandrachud", page: 1 }),
      );
    });
  });
});
