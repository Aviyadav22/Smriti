import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
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
    usePathname: () => "/agents",
  };
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    loadTokens: vi.fn(),
    getAccessToken: () => "test-token",
  };
});

import AgentsPage from "@/app/agents/page";

describe("AgentsPage", () => {
  it("renders both agent cards", () => {
    renderWithProviders(<AgentsPage />);
    expect(screen.getByText("Research Agent")).toBeInTheDocument();
    expect(screen.getByText("Case Prep Agent")).toBeInTheDocument();
  });

  it("renders page heading", () => {
    renderWithProviders(<AgentsPage />);
    expect(screen.getByText("AI Agent Hub")).toBeInTheDocument();
  });

  it("renders history link", () => {
    renderWithProviders(<AgentsPage />);
    expect(screen.getByText("History")).toBeInTheDocument();
  });

  it("links Research Agent card to /agents/research", () => {
    renderWithProviders(<AgentsPage />);
    const startButtons = screen.getAllByText("Start");
    // First Start button is for Research Agent
    const researchLink = startButtons[0].closest("a");
    expect(researchLink).toHaveAttribute("href", "/agents/research");
  });

  it("links Case Prep Agent card to /agents/case-prep", () => {
    renderWithProviders(<AgentsPage />);
    const startButtons = screen.getAllByText("Start");
    // Second Start button is for Case Prep Agent
    const casePrepLink = startButtons[1].closest("a");
    expect(casePrepLink).toHaveAttribute("href", "/agents/case-prep");
  });

  it("shows badge on Case Prep card", () => {
    renderWithProviders(<AgentsPage />);
    expect(screen.getByText("Requires document")).toBeInTheDocument();
  });

  it("renders Strategy Agent card", () => {
    renderWithProviders(<AgentsPage />);
    expect(screen.getByText("Strategy Agent")).toBeInTheDocument();
  });

  it("renders Drafting Agent card", () => {
    renderWithProviders(<AgentsPage />);
    expect(screen.getByText("Drafting Agent")).toBeInTheDocument();
  });

  it("links Strategy Agent to /agents/strategy", () => {
    renderWithProviders(<AgentsPage />);
    const startButtons = screen.getAllByText("Start");
    // Third Start button is for Strategy Agent
    const strategyLink = startButtons[2].closest("a");
    expect(strategyLink).toHaveAttribute("href", "/agents/strategy");
  });

  it("links Drafting Agent to /agents/drafting", () => {
    renderWithProviders(<AgentsPage />);
    const startButtons = screen.getAllByText("Start");
    // Fourth Start button is for Drafting Agent
    const draftingLink = startButtons[3].closest("a");
    expect(draftingLink).toHaveAttribute("href", "/agents/drafting");
  });
});
