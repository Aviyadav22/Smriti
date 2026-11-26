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
    usePathname: () => "/agents/research",
  };
});

const createAgentSession = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    createAgentSession: (...args: unknown[]) => createAgentSession(...args),
    getAgentSessions: vi.fn().mockResolvedValue({ sessions: [] }),
    resumeAgentExecution: vi.fn(),
    loadTokens: vi.fn(),
    getAccessToken: () => "test-token",
  };
});

import ResearchAgentPage from "@/app/(auth)/agents/research/page";

const placeholder = "Ask a legal research question...";

describe("Research agent start errors", () => {
  beforeEach(() => createAgentSession.mockReset());

  it("keeps the question and shows the error when the request is rejected", async () => {
    // The API rejects before streaming anything (e.g. 422 or rate limit).
    createAgentSession.mockImplementation(
      (_type: string, _body: unknown, _onEvent: unknown, onError: (e: Error) => void) => {
        queueMicrotask(() => onError(new Error("Rate limit exceeded")));
        return new AbortController();
      },
    );
    renderWithProviders(<ResearchAgentPage />);

    const box = screen.getByPlaceholderText(placeholder);
    fireEvent.change(box, { target: { value: "Is a comfort letter a guarantee?" } });
    fireEvent.click(screen.getByRole("button", { name: /start legal research/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Rate limit exceeded");
    expect(screen.getByPlaceholderText(placeholder)).toBeVisible();
    expect(screen.getByPlaceholderText(placeholder)).toHaveValue("Is a comfort letter a guarantee?");
  });

  it("blocks questions shorter than the API minimum and says why", async () => {
    renderWithProviders(<ResearchAgentPage />);

    fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value: "bail" } });

    expect(screen.getByRole("button", { name: /start legal research/i })).toBeDisabled();
    expect(screen.getByText(/at least 5 characters/i)).toBeInTheDocument();
    await waitFor(() => expect(createAgentSession).not.toHaveBeenCalled());
  });
});
