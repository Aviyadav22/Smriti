import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PrecedentBadge } from "@/components/precedent-badge";

describe("PrecedentBadge", () => {
  it("renders BINDING with green styling", () => {
    render(<PrecedentBadge strength="BINDING" />);
    const badge = screen.getByText("Binding");
    expect(badge).toBeDefined();
    expect(badge.className).toContain("green");
  });

  it("renders PERSUASIVE with yellow styling", () => {
    render(<PrecedentBadge strength="PERSUASIVE" />);
    expect(screen.getByText("Persuasive")).toBeDefined();
  });

  it("renders OVERRULED with red styling and strikethrough", () => {
    render(<PrecedentBadge strength="OVERRULED" />);
    const badge = screen.getByText("Overruled");
    expect(badge.className).toContain("line-through");
  });
});
