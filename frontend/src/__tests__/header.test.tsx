import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import { Header } from "@/components/header";

// Capture the mock router to assert navigation
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
    usePathname: () => "/",
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

describe("Header", () => {
  beforeEach(() => {
    pushMock.mockClear();
    mockIsAuthenticated = true;
  });

  it("renders the Smriti brand name", () => {
    renderWithProviders(<Header />);
    expect(screen.getByText("Smriti")).toBeInTheDocument();
  });

  it("renders navigation links", () => {
    renderWithProviders(<Header />);
    // Desktop nav links — Chat is translated via header.chat → "Chat"
    const chatLinks = screen.getAllByText("Chat");
    expect(chatLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("shows Login and Register when not authenticated", () => {
    mockIsAuthenticated = false;
    renderWithProviders(<Header />);
    // tc("login") and tc("register") return the key ("login"/"register") since
    // "common.login"/"common.register" are not in the global translation table
    expect(screen.getAllByText(/login/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/register/i).length).toBeGreaterThanOrEqual(1);
  });

  it("renders the search input with correct placeholder", () => {
    renderWithProviders(<Header />);
    const inputs = screen.getAllByPlaceholderText(/search.*case law/i);
    expect(inputs.length).toBeGreaterThanOrEqual(1);
  });

  it("navigates to search page on form submit", () => {
    renderWithProviders(<Header />);
    const inputs = screen.getAllByPlaceholderText(/search.*case law/i);
    const input = inputs[0];

    fireEvent.change(input, { target: { value: "right to privacy" } });
    fireEvent.submit(input.closest("form")!);

    expect(pushMock).toHaveBeenCalledWith(
      "/search?q=right%20to%20privacy"
    );
  });

  it("does not navigate when search input is empty", () => {
    renderWithProviders(<Header />);
    const inputs = screen.getAllByPlaceholderText(/search.*case law/i);
    const form = inputs[0].closest("form")!;

    fireEvent.submit(form);
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("renders the logo link pointing to home", () => {
    renderWithProviders(<Header />);
    const logoLink = screen.getByText("Smriti").closest("a");
    expect(logoLink).toHaveAttribute("href", "/");
  });
});
