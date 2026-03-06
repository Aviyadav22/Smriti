import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import RegisterPage from "@/app/register/page";

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
    usePathname: () => "/register",
  };
});

const mockApiRegister = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    register: (...args: unknown[]) => mockApiRegister(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => null,
  };
});

describe("RegisterPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
    mockApiRegister.mockClear();
  });

  it("renders the Create Account heading", () => {
    renderWithProviders(<RegisterPage />);
    const heading = screen.getByRole("heading", { name: /create account/i });
    expect(heading).toBeInTheDocument();
  });

  it("renders the subheading", () => {
    renderWithProviders(<RegisterPage />);
    expect(
      screen.getByText(/start your legal research journey/i)
    ).toBeInTheDocument();
  });

  it("renders name, email, and password inputs", () => {
    renderWithProviders(<RegisterPage />);
    expect(screen.getByPlaceholderText("Advocate Name")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("you@firm.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Min 8 characters")).toBeInTheDocument();
  });

  it("renders the Create Account submit button", () => {
    renderWithProviders(<RegisterPage />);
    expect(
      screen.getByRole("button", { name: /create account/i })
    ).toBeInTheDocument();
  });

  it("renders link to login page", () => {
    renderWithProviders(<RegisterPage />);
    const signInLink = screen.getByText("Sign In");
    expect(signInLink.closest("a")).toHaveAttribute("href", "/login");
  });

  it("renders DPDP consent checkbox", () => {
    renderWithProviders(<RegisterPage />);
    expect(
      screen.getByText(/Digital Personal Data Protection Act/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).toBeInTheDocument();
  });

  it("handles input changes", () => {
    renderWithProviders(<RegisterPage />);

    const nameInput = screen.getByPlaceholderText("Advocate Name");
    const emailInput = screen.getByPlaceholderText("you@firm.com");
    const passwordInput = screen.getByPlaceholderText("Min 8 characters");

    fireEvent.change(nameInput, { target: { value: "Advocate Sharma" } });
    fireEvent.change(emailInput, { target: { value: "sharma@firm.com" } });
    fireEvent.change(passwordInput, { target: { value: "securepass" } });

    expect(nameInput).toHaveValue("Advocate Sharma");
    expect(emailInput).toHaveValue("sharma@firm.com");
    expect(passwordInput).toHaveValue("securepass");
  });

  it("shows error when password is shorter than 8 characters", async () => {
    renderWithProviders(<RegisterPage />);

    fireEvent.change(screen.getByPlaceholderText("Advocate Name"), {
      target: { value: "Test" },
    });
    fireEvent.change(screen.getByPlaceholderText("you@firm.com"), {
      target: { value: "test@firm.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Min 8 characters"), {
      target: { value: "short" },
    });

    // Need to check the consent checkbox for native validation
    fireEvent.click(screen.getByRole("checkbox"));

    fireEvent.submit(
      screen.getByRole("button", { name: /create account/i }).closest("form")!
    );

    await waitFor(() => {
      expect(
        screen.getByText("Password must be at least 8 characters")
      ).toBeInTheDocument();
    });

    expect(mockApiRegister).not.toHaveBeenCalled();
  });

  it("calls register API on valid form submit", async () => {
    mockApiRegister.mockResolvedValue({
      access_token: "token",
      refresh_token: "refresh",
      expires_in: 3600,
    });

    renderWithProviders(<RegisterPage />);

    fireEvent.change(screen.getByPlaceholderText("Advocate Name"), {
      target: { value: "Advocate Sharma" },
    });
    fireEvent.change(screen.getByPlaceholderText("you@firm.com"), {
      target: { value: "sharma@firm.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Min 8 characters"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("checkbox"));

    fireEvent.submit(
      screen.getByRole("button", { name: /create account/i }).closest("form")!
    );

    await waitFor(() => {
      expect(mockApiRegister).toHaveBeenCalledWith({
        name: "Advocate Sharma",
        email: "sharma@firm.com",
        password: "password123",
      });
    });

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/search");
    });
  });

  it("shows error message on registration failure", async () => {
    mockApiRegister.mockRejectedValue(new Error("Email already exists"));

    renderWithProviders(<RegisterPage />);

    fireEvent.change(screen.getByPlaceholderText("Advocate Name"), {
      target: { value: "Test" },
    });
    fireEvent.change(screen.getByPlaceholderText("you@firm.com"), {
      target: { value: "dup@firm.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Min 8 characters"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("checkbox"));

    fireEvent.submit(
      screen.getByRole("button", { name: /create account/i }).closest("form")!
    );

    await waitFor(() => {
      expect(screen.getByText("Email already exists")).toBeInTheDocument();
    });
  });

  it("all form inputs are required", () => {
    renderWithProviders(<RegisterPage />);
    expect(screen.getByPlaceholderText("Advocate Name")).toBeRequired();
    expect(screen.getByPlaceholderText("you@firm.com")).toBeRequired();
    expect(screen.getByPlaceholderText("Min 8 characters")).toBeRequired();
    expect(screen.getByRole("checkbox")).toBeRequired();
  });

  it("password input has minLength attribute", () => {
    renderWithProviders(<RegisterPage />);
    expect(screen.getByPlaceholderText("Min 8 characters")).toHaveAttribute(
      "minLength",
      "8"
    );
  });
});
