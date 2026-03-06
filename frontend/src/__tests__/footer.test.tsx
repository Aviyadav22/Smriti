import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Footer } from "@/components/footer";

describe("Footer", () => {
  it("renders the Smriti brand name", () => {
    render(<Footer />);
    expect(screen.getByText("Smriti")).toBeInTheDocument();
  });

  it("displays the AI Legal Research tagline", () => {
    render(<Footer />);
    expect(screen.getByText(/AI Legal Research/)).toBeInTheDocument();
  });

  it("shows the CC-BY-4.0 license link", () => {
    render(<Footer />);
    const licenseLink = screen.getByText("CC-BY-4.0");
    expect(licenseLink).toBeInTheDocument();
    expect(licenseLink.closest("a")).toHaveAttribute(
      "href",
      "https://creativecommons.org/licenses/by/4.0/"
    );
  });

  it("displays the legal disclaimer", () => {
    render(<Footer />);
    expect(
      screen.getByText(/not legal advice/i)
    ).toBeInTheDocument();
  });

  it("mentions public records as data source", () => {
    render(<Footer />);
    expect(
      screen.getByText(/public records/i)
    ).toBeInTheDocument();
  });
});
