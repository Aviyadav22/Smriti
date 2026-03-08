import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "./test-utils";
import type { AgentExecution } from "@/lib/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

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
    usePathname: () => "/agents/history",
  };
});

// Override global auth mock — allow per-test control of isAuthenticated
let mockIsAuthenticated = true;
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    isAuthenticated: mockIsAuthenticated,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const getAgentExecutionsMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getAgentExecutions: (...args: unknown[]) => getAgentExecutionsMock(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => "test-token",
  };
});

import AgentHistoryPage from "@/app/agents/history/page";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeExecution(overrides: Partial<AgentExecution> = {}): AgentExecution {
  return {
    id: "exec-1",
    agent_type: "research",
    status: "completed",
    input_data: { query: "Right to privacy under Article 21" },
    result_data: { memo: "# Research Memo\n\nFindings here." },
    current_step: null,
    steps_completed: 5,
    total_steps: 5,
    created_at: "2026-03-01T10:00:00Z",
    updated_at: "2026-03-01T10:05:00Z",
    completed_at: "2026-03-01T10:05:00Z",
    error_message: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AgentHistoryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = true;
  });

  it("renders execution history list", async () => {
    const executions = [
      makeExecution({ id: "exec-1", input_data: { query: "Article 21 privacy" } }),
      makeExecution({ id: "exec-2", agent_type: "case_prep", input_data: { query: "Land acquisition" } }),
    ];
    getAgentExecutionsMock.mockResolvedValue({
      executions,
      total: 2,
      page: 1,
      page_size: 20,
    });

    renderWithProviders(<AgentHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Executions")).toBeInTheDocument();
    });

    expect(screen.getByText("Article 21 privacy")).toBeInTheDocument();
    expect(screen.getByText("Land acquisition")).toBeInTheDocument();
  });

  it("shows status badges for running, completed, and failed", async () => {
    const executions = [
      makeExecution({ id: "e1", status: "running", result_data: null }),
      makeExecution({ id: "e2", status: "completed" }),
      makeExecution({ id: "e3", status: "failed", result_data: null, error_message: "timeout" }),
    ];
    getAgentExecutionsMock.mockResolvedValue({
      executions,
      total: 3,
      page: 1,
      page_size: 20,
    });

    renderWithProviders(<AgentHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText("running")).toBeInTheDocument();
    });

    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
  });

  it("pagination works — next/prev buttons call API", async () => {
    const user = userEvent.setup();

    // First page
    getAgentExecutionsMock.mockResolvedValueOnce({
      executions: [makeExecution({ id: "e1", input_data: { query: "Page 1 query" } })],
      total: 40,
      page: 1,
      page_size: 20,
    });

    renderWithProviders(<AgentHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Page 1 query")).toBeInTheDocument();
    });

    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();

    // Setup mock for next page
    getAgentExecutionsMock.mockResolvedValueOnce({
      executions: [makeExecution({ id: "e2", input_data: { query: "Page 2 query" } })],
      total: 40,
      page: 2,
      page_size: 20,
    });

    const nextButton = screen.getByText("Next");
    await user.click(nextButton);

    await waitFor(() => {
      expect(getAgentExecutionsMock).toHaveBeenCalledWith(2);
    });
  });

  it("clicking View Results opens memo modal", async () => {
    const user = userEvent.setup();

    getAgentExecutionsMock.mockResolvedValue({
      executions: [
        makeExecution({
          id: "e1",
          status: "completed",
          result_data: { memo: "# Legal Analysis\n\nSome findings." },
        }),
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderWithProviders(<AgentHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText("View Results")).toBeInTheDocument();
    });

    await user.click(screen.getByText("View Results"));

    await waitFor(() => {
      expect(screen.getByText("Research Agent Results")).toBeInTheDocument();
    });
  });

  it("shows empty state when no executions", async () => {
    getAgentExecutionsMock.mockResolvedValue({
      executions: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    renderWithProviders(<AgentHistoryPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/No agent executions yet/),
      ).toBeInTheDocument();
    });
  });

  it("redirects unauthenticated users to login", async () => {
    mockIsAuthenticated = false;

    renderWithProviders(<AgentHistoryPage />);

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/login");
    });
  });
});
