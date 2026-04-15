import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";

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
    usePathname: () => "/chat",
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

const mockGetChatSessions = vi.fn();
const mockGetChatHistory = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getChatSessions: () => mockGetChatSessions(),
    getChatHistory: (...args: unknown[]) => mockGetChatHistory(...args),
    deleteChatSession: vi.fn().mockResolvedValue(undefined),
    createChatSession: vi.fn(),
    sendChatMessage: vi.fn(),
    loadTokens: vi.fn(),
    getAccessToken: () => (mockIsAuthenticated ? "fake-token" : null),
  };
});

import ChatPage from "@/app/(auth)/chat/page";

describe("ChatPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = true;
    mockGetChatSessions.mockResolvedValue([]);
    mockGetChatHistory.mockResolvedValue([]);
    pushMock.mockClear();
    // jsdom does not implement scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("shows empty state with example queries when authenticated", async () => {
    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByText("Legal Research Assistant")).toBeTruthy();
    });

    // At least one example query should be visible
    expect(screen.getByText(/landmark cases on right to privacy/i)).toBeTruthy();
  });

  it("renders session list when sessions exist", async () => {
    mockGetChatSessions.mockResolvedValue([
      {
        id: "sess-1",
        title: "Right to Privacy Discussion",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T01:00:00Z",
        message_count: 4,
      },
      {
        id: "sess-2",
        title: "Article 21 Analysis",
        created_at: "2024-01-02T00:00:00Z",
        updated_at: "2024-01-02T01:00:00Z",
        message_count: 2,
      },
    ]);

    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByText("Right to Privacy Discussion")).toBeTruthy();
      expect(screen.getByText("Article 21 Analysis")).toBeTruthy();
    });
  });

  it("shows 'No conversations yet' when session list is empty", async () => {
    mockGetChatSessions.mockResolvedValue([]);
    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      expect(screen.getByText("No conversations yet")).toBeTruthy();
    });
  });

  it("shows input textarea with placeholder", async () => {
    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      const textarea = screen.getByPlaceholderText("Ask a legal question...");
      expect(textarea).toBeTruthy();
    });
  });

  it("shows send button", async () => {
    renderWithProviders(<ChatPage />);

    await waitFor(() => {
      // The send button exists (it's an icon button)
      const buttons = screen.getAllByRole("button");
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it("renders markdown bold and heading in assistant messages", async () => {
    mockGetChatSessions.mockResolvedValue([
      {
        id: "sess-md",
        title: "Markdown Test",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T01:00:00Z",
        message_count: 2,
      },
    ]);
    mockGetChatHistory.mockResolvedValue([
      {
        id: "msg-1",
        role: "user",
        content: "Tell me about Article 21",
        sources: [],
        created_at: "2024-01-01T00:00:00Z",
      },
      {
        id: "msg-2",
        role: "assistant",
        content: "## Key Principles\n\nThe **right to life** is fundamental.",
        sources: [],
        created_at: "2024-01-01T00:01:00Z",
      },
    ]);

    renderWithProviders(<ChatPage />);

    // Wait for sessions to load, then click on the session
    await waitFor(() => {
      expect(screen.getByText("Markdown Test")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Markdown Test"));

    // Wait for history to load and verify markdown rendering
    await waitFor(() => {
      // Bold text should be rendered in a <strong> tag
      const strongEl = screen.getByText("right to life");
      expect(strongEl.tagName).toBe("STRONG");

      // Heading should be rendered as an h2 element
      const headingEl = screen.getByText("Key Principles");
      expect(headingEl.tagName).toBe("H2");
    });
  });

  it("renders citation link [1] as a clickable anchor", async () => {
    mockGetChatSessions.mockResolvedValue([
      {
        id: "sess-cit",
        title: "Citation Test",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T01:00:00Z",
        message_count: 2,
      },
    ]);
    mockGetChatHistory.mockResolvedValue([
      {
        id: "msg-u1",
        role: "user",
        content: "What is Article 21?",
        sources: [],
        created_at: "2024-01-01T00:00:00Z",
      },
      {
        id: "msg-a1",
        role: "assistant",
        content: "Article 21 protects the right to life [1].",
        sources: [
          {
            case_id: "case-puttaswamy",
            title: "K.S. Puttaswamy v. Union of India",
            citation: "(2017) 10 SCC 1",
            court: "Supreme Court of India",
            year: 2017,
            score: 0.95,
          },
        ],
        created_at: "2024-01-01T00:01:00Z",
      },
    ]);

    renderWithProviders(<ChatPage />);

    // Wait for sessions then click
    await waitFor(() => {
      expect(screen.getByText("Citation Test")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Citation Test"));

    // Wait for the citation link to render
    await waitFor(() => {
      // The [1] in the content should become a clickable anchor link
      const citationLink = screen.getByRole("link", { name: /\[1\]/i });
      expect(citationLink).toBeTruthy();
      expect(citationLink.tagName).toBe("A");
      expect(citationLink.getAttribute("href")).toBe("#source-msg-a1-1");
    });
  });
});
