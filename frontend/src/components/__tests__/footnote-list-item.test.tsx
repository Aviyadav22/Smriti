import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { FootnoteListItem } from "@/components/footnote-list-item";
import type { ResearchFootnote } from "@/lib/types";

function makeMockFootnote(overrides: Partial<ResearchFootnote> = {}): ResearchFootnote {
  return {
    number: 1,
    citation: "State of Punjab v. Davinder Singh (2024) 8 SCC 1",
    source_type: "case_law",
    source_url: "https://example.com/case/123",
    case_id: "case-123",
    excerpt: "The court held that Article 16(4) permits sub-classification within reserved categories.",
    is_used: true,
    verification_status: "verified",
    verified_against: "pinecone",
    title: "State of Punjab v. Davinder Singh",
    court: "Supreme Court of India",
    year: 2024,
    author: "CJI D.Y. Chandrachud",
    bench: "7-Judge Constitution Bench",
    ik_doc_id: "doc-abc-123",
    pdf_available: true,
    source_label: "Case",
    ...overrides,
  };
}

describe("FootnoteListItem", () => {
  it("renders footnote number and title", () => {
    const footnote = makeMockFootnote();
    render(
      <FootnoteListItem footnote={footnote} isSelected={false} onClick={vi.fn()} />
    );

    expect(screen.getByText("1")).toBeDefined();
    expect(screen.getByText("State of Punjab v. Davinder Singh")).toBeDefined();
  });

  it("shows 'Case' badge for case_law source", () => {
    const footnote = makeMockFootnote({ source_label: "Case" });
    render(
      <FootnoteListItem footnote={footnote} isSelected={false} onClick={vi.fn()} />
    );

    expect(screen.getByText("Case")).toBeDefined();
  });

  it("shows 'Web' badge for web source", () => {
    const footnote = makeMockFootnote({
      source_type: "web",
      source_label: "Web",
    });
    render(
      <FootnoteListItem footnote={footnote} isSelected={false} onClick={vi.fn()} />
    );

    expect(screen.getByText("Web")).toBeDefined();
  });

  it("calls onClick when clicked", () => {
    const handleClick = vi.fn();
    const footnote = makeMockFootnote();
    render(
      <FootnoteListItem footnote={footnote} isSelected={false} onClick={handleClick} />
    );

    fireEvent.click(screen.getByRole("button"));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("highlights when selected with gold-related class", () => {
    const footnote = makeMockFootnote();
    render(
      <FootnoteListItem footnote={footnote} isSelected={true} onClick={vi.fn()} />
    );

    const button = screen.getByRole("button");
    expect(button.className).toContain("gold");
  });

  it("falls back to citation when title is empty", () => {
    const footnote = makeMockFootnote({ title: "" });
    render(
      <FootnoteListItem footnote={footnote} isSelected={false} onClick={vi.fn()} />
    );

    expect(
      screen.getByText("State of Punjab v. Davinder Singh (2024) 8 SCC 1")
    ).toBeDefined();
  });
});
