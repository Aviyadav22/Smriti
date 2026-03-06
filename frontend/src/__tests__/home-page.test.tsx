import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import HomePage from "@/app/page";

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

describe("HomePage", () => {
  beforeEach(() => {
    pushMock.mockClear();
  });

  it("renders the hero headline", () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByText("The AI-Powered")).toBeInTheDocument();
    expect(screen.getByText("Paralegal")).toBeInTheDocument();
  });

  it("renders the main search input", () => {
    renderWithProviders(<HomePage />);
    expect(
      screen.getByPlaceholderText(/search judgments/i)
    ).toBeInTheDocument();
  });

  it("renders the Search submit button", () => {
    renderWithProviders(<HomePage />);
    // There may be multiple "Search" elements; one is the submit button in the hero form
    const buttons = screen.getAllByRole("button", { name: /search/i });
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it("handles search input changes", () => {
    renderWithProviders(<HomePage />);
    const input = screen.getByPlaceholderText(/search judgments/i);
    fireEvent.change(input, { target: { value: "Article 21" } });
    expect(input).toHaveValue("Article 21");
  });

  it("navigates to search page on form submit", () => {
    renderWithProviders(<HomePage />);
    const input = screen.getByPlaceholderText(/search judgments/i);
    fireEvent.change(input, { target: { value: "Article 21" } });
    fireEvent.submit(input.closest("form")!);

    expect(pushMock).toHaveBeenCalledWith("/search?q=Article%2021");
  });

  it("does not navigate when query is empty or whitespace", () => {
    renderWithProviders(<HomePage />);
    const input = screen.getByPlaceholderText(/search judgments/i);
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.submit(input.closest("form")!);

    expect(pushMock).not.toHaveBeenCalled();
  });

  it("renders example query chips", () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByText("Right to privacy Supreme Court")).toBeInTheDocument();
    expect(screen.getByText("Kesavananda Bharati case")).toBeInTheDocument();
    expect(screen.getByText("Article 21 right to life")).toBeInTheDocument();
  });

  it("navigates to search with example query on chip click", () => {
    renderWithProviders(<HomePage />);
    const chip = screen.getByText("Kesavananda Bharati case");
    fireEvent.click(chip);

    expect(pushMock).toHaveBeenCalledWith(
      "/search?q=Kesavananda%20Bharati%20case"
    );
  });

  it("renders stats section", () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByText("35,000+")).toBeInTheDocument();
    expect(screen.getByText("25+")).toBeInTheDocument();
    expect(screen.getByText(/1950/)).toBeInTheDocument();
  });

  it("renders How Smriti Works section", () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByText("How Smriti Works")).toBeInTheDocument();
    expect(screen.getByText("Step 01")).toBeInTheDocument();
    expect(screen.getByText("Step 02")).toBeInTheDocument();
    expect(screen.getByText("Step 03")).toBeInTheDocument();
  });

  it("renders CTA section with register link", () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByText("Start Researching")).toBeInTheDocument();
    const registerLink = screen.getByText("Create Account").closest("a");
    expect(registerLink).toHaveAttribute("href", "/register");
  });
});
