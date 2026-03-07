import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SectionFilter } from "@/components/section-filter";
import { BenchStrength } from "@/components/bench-strength";
import { EquivalentCitations } from "@/components/equivalent-citations";

// Mock next/navigation for components that use it
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

describe("SectionFilter integration", () => {
  it("renders all section options", () => {
    const onChange = vi.fn();
    render(<SectionFilter value={null} onChange={onChange} />);
    // The trigger should show placeholder
    expect(screen.getByText("All sections")).toBeDefined();
  });

  it("shows selected value", () => {
    const onChange = vi.fn();
    render(<SectionFilter value="HOLDINGS" onChange={onChange} />);
    expect(screen.getByText("Holdings")).toBeDefined();
  });
});

describe("BenchStrength integration", () => {
  it("renders bench type label", () => {
    render(<BenchStrength benchType="constitutional" />);
    expect(screen.getByText("Constitution Bench")).toBeDefined();
  });

  it("renders with judge count", () => {
    render(<BenchStrength benchType="division" judgeCount={2} />);
    expect(screen.getByText("Division Bench (2J)")).toBeDefined();
  });

  it("returns null for null benchType", () => {
    const { container } = render(<BenchStrength benchType={null} />);
    expect(container.innerHTML).toBe("");
  });
});

describe("EquivalentCitations integration", () => {
  it("renders multiple citations with separators", () => {
    render(
      <EquivalentCitations
        citations={["(2017) 10 SCC 1", "AIR 2017 SC 4161"]}
        primaryCitation="(2017) 10 SCC 1"
      />
    );
    expect(screen.getByText("(2017) 10 SCC 1")).toBeDefined();
    expect(screen.getByText("AIR 2017 SC 4161")).toBeDefined();
  });

  it("returns null for empty citations", () => {
    const { container } = render(<EquivalentCitations citations={[]} />);
    expect(container.innerHTML).toBe("");
  });
});
