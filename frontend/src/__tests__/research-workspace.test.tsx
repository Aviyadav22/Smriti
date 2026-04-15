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
    usePathname: () => "/agents/research",
  };
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    runResearchAgent: vi.fn(),
    resumeAgentExecution: vi.fn(),
    loadTokens: vi.fn(),
    getAccessToken: () => "test-token",
  };
});

import ResearchAgentPage from "@/app/(auth)/agents/research/page";

describe("ResearchAgentPage", () => {
  it("renders page heading", () => {
    renderWithProviders(<ResearchAgentPage />);
    expect(screen.getByText("Research Agent")).toBeInTheDocument();
  });

  it("renders input form with textarea", () => {
    renderWithProviders(<ResearchAgentPage />);
    expect(
      screen.getByPlaceholderText("Ask a legal research question..."),
    ).toBeInTheDocument();
  });

  it("renders submit button", () => {
    renderWithProviders(<ResearchAgentPage />);
    expect(
      screen.getByRole("button", { name: /start legal research/i }),
    ).toBeInTheDocument();
  });

  it("has disabled submit button when query is empty", () => {
    renderWithProviders(<ResearchAgentPage />);
    const button = screen.getByRole("button", { name: /start legal research/i });
    expect(button).toBeDisabled();
  });
});
