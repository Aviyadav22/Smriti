import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import type { GraphStats } from "@/lib/types";

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
    usePathname: () => "/graph",
  };
});

// Mock react-force-graph-2d (canvas-dependent, unavailable in jsdom)
vi.mock("react-force-graph-2d", () => ({
  __esModule: true,
  default: () => <div data-testid="force-graph" />,
}));


const mockGetGraphStats = vi.fn();
const mockGetGraphNeighborhood = vi.fn();
const mockGetGraphDashboard = vi.fn();
const mockSearch = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getGraphStats: () => mockGetGraphStats(),
    getGraphNeighborhood: (...args: unknown[]) => mockGetGraphNeighborhood(...args),
    getGraphDashboard: (...args: unknown[]) => mockGetGraphDashboard(...args),
    getGraphChain: vi.fn().mockResolvedValue({ nodes: [], edges: [] }),
    getGraphAuthorities: vi.fn().mockResolvedValue([]),
    search: (...args: unknown[]) => mockSearch(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => null,
  };
});

import GraphPage from "@/app/graph/page";

function makeStats(overrides: Partial<GraphStats> = {}): GraphStats {
  return {
    total_judgments: 796,
    total_edges: 4500,
    most_cited: [
      {
        id: "top-1",
        title: "Kesavananda Bharati v. State of Kerala",
        citation: "(1973) 4 SCC 225",
        cited_by_count: 250,
      },
    ],
    ...overrides,
  };
}

describe("GraphPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetGraphStats.mockResolvedValue(makeStats());
    mockGetGraphNeighborhood.mockResolvedValue({ nodes: [], edges: [] });
    mockGetGraphDashboard.mockResolvedValue({
      most_cited: [],
      rising: [],
      recently_negative: [],
      communities: [],
      subtopics: [],
      statute_sections: [],
    });
    mockSearch.mockResolvedValue({ results: [], total_count: 0, page: 1, page_size: 5 });
  });

  it("shows view toggle buttons", async () => {
    renderWithProviders(<GraphPage />);

    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeTruthy();
      expect(screen.getByText("Timeline")).toBeTruthy();
      expect(screen.getByText("Network")).toBeTruthy();
    });
  });

  it("shows global graph stats in dashboard view", async () => {
    renderWithProviders(<GraphPage />);

    await waitFor(() => {
      expect(screen.getByText(/796/)).toBeTruthy();
      expect(screen.getAllByText(/judgments/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows search input with placeholder", async () => {
    renderWithProviders(<GraphPage />);

    await waitFor(() => {
      const input = screen.getByPlaceholderText("Search case to explore...");
      expect(input).toBeTruthy();
    });
  });

  it("shows depth and mode controls in network view", async () => {
    renderWithProviders(<GraphPage />);

    // Switch to network view to reveal depth + mode controls
    await waitFor(() => {
      expect(screen.getByText("Network")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Network"));

    await waitFor(() => {
      expect(screen.getByText("1")).toBeTruthy();
      expect(screen.getByText("2")).toBeTruthy();
      expect(screen.getByText("3")).toBeTruthy();
      expect(screen.getByText("Neighborhood")).toBeTruthy();
      expect(screen.getByText("Chain")).toBeTruthy();
      expect(screen.getByText("Path")).toBeTruthy();
    });
  });
});
