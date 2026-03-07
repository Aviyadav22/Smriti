import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { EquivalentCitations } from "@/components/equivalent-citations";
import { BenchStrength } from "@/components/bench-strength";

describe("LegalDisclaimer", () => {
  it("renders warning text about AI-assisted research", () => {
    render(<LegalDisclaimer />);
    expect(screen.getByText(/not legal advice/i)).toBeDefined();
    expect(screen.getByText(/verify all citations/i)).toBeDefined();
  });

  it("has mobile sticky positioning classes", () => {
    const { container } = render(<LegalDisclaimer />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("fixed");
    expect(el.className).toContain("bottom-0");
    expect(el.className).toContain("left-0");
    expect(el.className).toContain("right-0");
    expect(el.className).toContain("z-30");
  });

  it("has sm: breakpoint classes for non-mobile layout", () => {
    const { container } = render(<LegalDisclaimer />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("sm:relative");
    expect(el.className).toContain("sm:bottom-auto");
  });

  it("accepts custom className", () => {
    const { container } = render(<LegalDisclaimer className="mt-8" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("mt-8");
  });
});

describe("EquivalentCitations", () => {
  it("renders citations", () => {
    const citations = ["(2024) 1 SCC 123", "AIR 2024 SC 456"];
    render(<EquivalentCitations citations={citations} />);
    expect(screen.getByText("(2024) 1 SCC 123")).toBeDefined();
    expect(screen.getByText("AIR 2024 SC 456")).toBeDefined();
  });

  it("renders nothing when citations array is empty", () => {
    const { container } = render(<EquivalentCitations citations={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("puts primary citation first", () => {
    const citations = ["AIR 2024 SC 456", "(2024) 1 SCC 123"];
    const { container } = render(
      <EquivalentCitations citations={citations} primaryCitation="(2024) 1 SCC 123" />
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons[0].textContent).toBe("(2024) 1 SCC 123");
    expect(buttons[1].textContent).toBe("AIR 2024 SC 456");
  });

  it("click-to-copy calls navigator.clipboard.writeText", () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<EquivalentCitations citations={["(2024) 1 SCC 123"]} />);
    fireEvent.click(screen.getByText("(2024) 1 SCC 123"));
    expect(writeText).toHaveBeenCalledWith("(2024) 1 SCC 123");
  });

  it("renders separator between citations", () => {
    const { container } = render(
      <EquivalentCitations citations={["Citation A", "Citation B"]} />
    );
    expect(container.textContent).toContain("|");
  });
});

describe("BenchStrength", () => {
  it("renders constitutional bench as blue badge", () => {
    render(<BenchStrength benchType="constitutional" />);
    const el = screen.getByText("Constitution Bench");
    expect(el.className).toContain("blue");
    expect(el.className).toContain("rounded-full");
  });

  it("renders single judge as muted text", () => {
    render(<BenchStrength benchType="single" />);
    const el = screen.getByText("Single Judge");
    expect(el.className).toContain("text-muted-foreground");
    expect(el.className).not.toContain("rounded-full");
  });

  it("renders division bench", () => {
    render(<BenchStrength benchType="division" />);
    expect(screen.getByText("Division Bench")).toBeDefined();
  });

  it("renders full bench with semibold styling", () => {
    render(<BenchStrength benchType="full" />);
    const el = screen.getByText("Full Bench");
    expect(el.className).toContain("font-semibold");
  });

  it("renders judge count when provided", () => {
    render(<BenchStrength benchType="constitutional" judgeCount={5} />);
    expect(screen.getByText("Constitution Bench (5J)")).toBeDefined();
  });

  it("renders nothing when benchType is null", () => {
    const { container } = render(<BenchStrength benchType={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("falls back gracefully for unknown bench type", () => {
    render(<BenchStrength benchType="special" />);
    expect(screen.getByText("special")).toBeDefined();
  });
});
