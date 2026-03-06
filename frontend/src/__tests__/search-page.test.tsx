import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import type { SearchResponse, FacetsResponse } from "@/lib/types";

const pushMock = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", async () => {
  return {
    useRouter: () => ({
      push: pushMock,
      back: vi.fn(),
      replace: vi.fn(),
      prefetch: vi.fn(),
      refresh: vi.fn(),
    }),
    useSearchParams: () => mockSearchParams,
    useParams: () => ({}),
    usePathname: () => "/search",
  };
});

// Mock API module
const mockSearch = vi.fn();
const mockSearchFacets = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    search: (...args: unknown[]) => mockSearch(...args),
    searchFacets: () => mockSearchFacets(),
    loadTokens: vi.fn(),
    getAccessToken: () => null,
  };
});

// We need to import the component AFTER mocks are set up
// Using dynamic import pattern with top-level import is fine since vi.mock is hoisted
import SearchPage from "@/app/search/page";

function makeFacets(): FacetsResponse {
  return {
    courts: ["Supreme Court of India"],
    case_types: ["Civil Appeal"],
    bench_types: ["division"],
    years: { min: 1950, max: 2025 },
  };
}

function makeSearchResponse(overrides: Partial<SearchResponse> = {}): SearchResponse {
  return {
    results: [
      {
        case_id: "case-001",
        score: 0.95,
        title: "State of Kerala v. Peoples Union for Civil Liberties",
        citation: "(2009) 8 SCC 46",
        court: "Supreme Court of India",
        year: 2009,
        date: "2009-08-12",
        case_type: "Civil Appeal",
        judge: "K.G. Balakrishnan",
        snippet: "The right to privacy is a fundamental right under Article 21...",
      },
      {
        case_id: "case-002",
        score: 0.88,
        title: "K.S. Puttaswamy v. Union of India",
        citation: "(2017) 10 SCC 1",
        court: "Supreme Court of India",
        year: 2017,
        date: "2017-08-24",
        case_type: "Writ Petition",
        judge: "J.S. Khehar",
        snippet: "Right to privacy is protected as an intrinsic part of the right to life...",
      },
    ],
    total_count: 2,
    page: 1,
    page_size: 10,
    query_understanding: {
      intent: "case_search",
      original_query: "right to privacy",
      expanded_query: "right to privacy fundamental right Article 21",
      search_strategy: "hybrid",
      filters: {},
      entities: {
        case_names: [],
        statutes: [],
        legal_concepts: ["right to privacy"],
        judges: [],
        courts: [],
      },
    },
    facets: {},
    ...overrides,
  };
}

describe("SearchPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
    mockSearch.mockClear();
    mockSearchFacets.mockClear();
    mockSearchFacets.mockResolvedValue(makeFacets());
    mockSearchParams = new URLSearchParams();
  });

  it("renders the search input with placeholder", () => {
    renderWithProviders(<SearchPage />);
    expect(
      screen.getAllByPlaceholderText(/search.*case law/i).length
    ).toBeGreaterThanOrEqual(1);
  });

  it("shows empty state when no query provided", () => {
    renderWithProviders(<SearchPage />);
    expect(
      screen.getByText(/enter a query to search/i)
    ).toBeInTheDocument();
  });

  it("renders the search submit button", () => {
    renderWithProviders(<SearchPage />);
    const buttons = screen.getAllByRole("button", { name: /search/i });
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it("triggers search on form submit", async () => {
    mockSearch.mockResolvedValue(makeSearchResponse());
    renderWithProviders(<SearchPage />);

    // Find search inputs (there may be one from Header and one from SearchContent)
    const inputs = screen.getAllByPlaceholderText(/search.*case law/i);
    // The SearchContent input is the one inside the border-b bar
    const input = inputs[inputs.length - 1];
    fireEvent.change(input, { target: { value: "right to privacy" } });
    fireEvent.submit(input.closest("form")!);

    // The form submit calls router.push AND executeSearch
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith(
        "/search?q=right%20to%20privacy",
        { scroll: false }
      );
    });

    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalledWith(
        expect.objectContaining({ q: "right to privacy" })
      );
    });
  });

  it("displays search results as cards", async () => {
    mockSearch.mockResolvedValue(makeSearchResponse());
    mockSearchParams = new URLSearchParams("q=right+to+privacy");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(
        screen.getByText("State of Kerala v. Peoples Union for Civil Liberties")
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText("K.S. Puttaswamy v. Union of India")
    ).toBeInTheDocument();
  });

  it("shows result count", async () => {
    mockSearch.mockResolvedValue(makeSearchResponse());
    mockSearchParams = new URLSearchParams("q=right+to+privacy");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("2 results")).toBeInTheDocument();
    });
  });

  it("shows citation badges on result cards", async () => {
    mockSearch.mockResolvedValue(makeSearchResponse());
    mockSearchParams = new URLSearchParams("q=right+to+privacy");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("(2009) 8 SCC 46")).toBeInTheDocument();
      expect(screen.getByText("(2017) 10 SCC 1")).toBeInTheDocument();
    });
  });

  it("shows snippet text on result cards", async () => {
    mockSearch.mockResolvedValue(makeSearchResponse());
    mockSearchParams = new URLSearchParams("q=right+to+privacy");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/The right to privacy is a fundamental right/i)
      ).toBeInTheDocument();
    });
  });

  it("displays no results message when results array is empty", async () => {
    mockSearch.mockResolvedValue(
      makeSearchResponse({ results: [], total_count: 0 })
    );
    mockSearchParams = new URLSearchParams("q=xyznonexistent");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("No results found.")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/try different search terms/i)
    ).toBeInTheDocument();
  });

  it("shows pagination when results span multiple pages", async () => {
    mockSearch.mockResolvedValue(
      makeSearchResponse({ total_count: 25, page_size: 10 })
    );
    mockSearchParams = new URLSearchParams("q=test");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("1 / 3")).toBeInTheDocument();
    });
  });

  it("does not show pagination when all results fit on one page", async () => {
    mockSearch.mockResolvedValue(
      makeSearchResponse({ total_count: 2, page_size: 10 })
    );
    mockSearchParams = new URLSearchParams("q=test");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("2 results")).toBeInTheDocument();
    });

    expect(screen.queryByText(/\d+ \/ \d+/)).not.toBeInTheDocument();
  });

  it("shows error message on search failure", async () => {
    mockSearch.mockRejectedValue(new Error("Network error"));
    mockSearchParams = new URLSearchParams("q=test");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("shows query understanding info when intent is not general", async () => {
    mockSearch.mockResolvedValue(makeSearchResponse());
    mockSearchParams = new URLSearchParams("q=right+to+privacy");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("case search")).toBeInTheDocument();
    });
  });

  it("shows score for each result", async () => {
    mockSearch.mockResolvedValue(makeSearchResponse());
    mockSearchParams = new URLSearchParams("q=test");

    renderWithProviders(<SearchPage />);

    await waitFor(() => {
      expect(screen.getByText("0.95")).toBeInTheDocument();
      expect(screen.getByText("0.88")).toBeInTheDocument();
    });
  });
});
