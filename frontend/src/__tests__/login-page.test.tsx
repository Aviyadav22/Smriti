import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import LoginPage from "@/app/login/page";

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
    usePathname: () => "/login",
  };
});

const mockApiLogin = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    login: (...args: unknown[]) => mockApiLogin(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => null,
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
    mockApiLogin.mockClear();
  });

  it("renders the Sign In heading", () => {
    renderWithProviders(<LoginPage />);
    const heading = screen.getByRole("heading", { name: /sign in/i });
    expect(heading).toBeInTheDocument();
  });

  it("renders the subheading", () => {
    renderWithProviders(<LoginPage />);
    expect(
      screen.getByText(/access your legal research dashboard/i)
    ).toBeInTheDocument();
  });

  it("renders email and password inputs", () => {
    renderWithProviders(<LoginPage />);
    expect(screen.getByPlaceholderText("you@firm.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/••••/)).toBeInTheDocument();
  });

  it("renders the Sign In submit button", () => {
    renderWithProviders(<LoginPage />);
    expect(
      screen.getByRole("button", { name: /sign in/i })
    ).toBeInTheDocument();
  });

  it("renders link to register page", () => {
    renderWithProviders(<LoginPage />);
    // The main content area has "Don't have an account? Register"
    // Use getAllByText since Header also has a Register link
    const registerLinks = screen.getAllByText("Register");
    const mainRegisterLink = registerLinks.find(
      (el) => el.closest("main") !== null || el.closest("p") !== null
    );
    expect(mainRegisterLink).toBeDefined();
    expect(mainRegisterLink!.closest("a")).toHaveAttribute("href", "/register");
  });

  it("handles email input change", () => {
    renderWithProviders(<LoginPage />);
    const emailInput = screen.getByPlaceholderText("you@firm.com");
    fireEvent.change(emailInput, { target: { value: "test@firm.com" } });
    expect(emailInput).toHaveValue("test@firm.com");
  });

  it("handles password input change", () => {
    renderWithProviders(<LoginPage />);
    const passwordInput = screen.getByPlaceholderText(/••••/);
    fireEvent.change(passwordInput, { target: { value: "secret123" } });
    expect(passwordInput).toHaveValue("secret123");
  });

  it("calls login API on form submit and navigates to search", async () => {
    mockApiLogin.mockResolvedValue({
      access_token: "token",
      refresh_token: "refresh",
      expires_in: 3600,
    });

    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText("you@firm.com"), {
      target: { value: "test@firm.com" },
    });
    fireEvent.change(screen.getByPlaceholderText(/••••/), {
      target: { value: "password123" },
    });
    fireEvent.submit(screen.getByRole("button", { name: /sign in/i }).closest("form")!);

    await waitFor(() => {
      expect(mockApiLogin).toHaveBeenCalledWith({
        email: "test@firm.com",
        password: "password123",
      });
    });

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/search");
    });
  });

  it("shows error message on login failure", async () => {
    mockApiLogin.mockRejectedValue(new Error("Invalid credentials"));

    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText("you@firm.com"), {
      target: { value: "bad@firm.com" },
    });
    fireEvent.change(screen.getByPlaceholderText(/••••/), {
      target: { value: "wrong" },
    });
    fireEvent.submit(screen.getByRole("button", { name: /sign in/i }).closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
    });
  });

  it("has required attribute on email and password inputs", () => {
    renderWithProviders(<LoginPage />);
    expect(screen.getByPlaceholderText("you@firm.com")).toBeRequired();
    expect(screen.getByPlaceholderText(/••••/)).toBeRequired();
  });

  it("email input has type=email", () => {
    renderWithProviders(<LoginPage />);
    expect(screen.getByPlaceholderText("you@firm.com")).toHaveAttribute("type", "email");
  });

  it("password input has type=password", () => {
    renderWithProviders(<LoginPage />);
    expect(screen.getByPlaceholderText(/••••/)).toHaveAttribute("type", "password");
  });
});
