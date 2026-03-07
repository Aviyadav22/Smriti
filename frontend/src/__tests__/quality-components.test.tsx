import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { ConfidenceMeter } from "@/components/confidence-meter";

describe("LegalDisclaimer", () => {
  it("renders disclaimer text", () => {
    render(<LegalDisclaimer />);
    expect(screen.getByText(/not legal advice/i)).toBeDefined();
  });

  it("renders with custom className", () => {
    const { container } = render(<LegalDisclaimer className="mt-4" />);
    expect(container.firstChild).toBeDefined();
  });
});

describe("ConfidenceMeter", () => {
  it("renders strong match label for high score", () => {
    render(<ConfidenceMeter score={0.85} />);
    expect(screen.getByText("Strong match")).toBeDefined();
  });

  it("renders partial match label for low score", () => {
    render(<ConfidenceMeter score={0.25} />);
    expect(screen.getByText("Partial match")).toBeDefined();
  });
});
