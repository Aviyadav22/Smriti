import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import type { ResearchFootnote } from "@/lib/types";

// Mock FootnotePreview to avoid pdfjs-dist DOMMatrix error in jsdom
vi.mock("@/components/footnote-preview", () => ({
  FootnotePreview: ({ footnote }: { footnote: ResearchFootnote }) => (
    <div data-testid="footnote-preview">Preview: {footnote.title}</div>
  ),
}));

import { FootnotesPanel } from "@/components/footnotes-panel";

function makeMockFootnote(overrides: Partial<ResearchFootnote> = {}): ResearchFootnote {
  return {
    number: 1,
    citation: "State of Punjab v. Davinder Singh (2024) 8 SCC 1",
    source_type: "case_law",
    source_url: "https://example.com/case/123",
    case_id: "case-123",
    excerpt: "The court held that Article 16(4) permits sub-classification.",
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

const mockFootnotes: ResearchFootnote[] = [
  makeMockFootnote({ number: 1, title: "Cited Case One", is_used: true, source_label: "Case" }),
  makeMockFootnote({ number: 2, title: "Cited Case Two", is_used: true, source_label: "Statute" }),
  makeMockFootnote({
    number: 3,
    title: "Unused Web Source",
    is_used: false,
    source_type: "web",
    source_label: "Web",
  }),
  makeMockFootnote({
    number: 4,
    title: "Unused Case Source",
    is_used: false,
    source_label: "Case",
  }),
];

describe("FootnotesPanel", () => {
  const defaultProps = {
    footnotes: mockFootnotes,
    selectedFootnoteNumber: null,
    onFootnoteSelect: vi.fn(),
    isOpen: true,
    onToggle: vi.fn(),
  };

  it("shows footnote count in tab", () => {
    render(<FootnotesPanel {...defaultProps} />);

    // The used footnotes count (2) should appear in the tab badge(s)
    const allTwos = screen.getAllByText("2");
    // At least one "2" is the footnote count badge (the other is footnote number 2)
    expect(allTwos.length).toBeGreaterThanOrEqual(2);
  });

  it("shows 'Searched but Not Cited' section for unused footnotes", () => {
    render(<FootnotesPanel {...defaultProps} />);

    expect(screen.getByText("Searched but Not Cited")).toBeDefined();
    expect(screen.getByText("Unused Web Source")).toBeDefined();
    expect(screen.getByText("Unused Case Source")).toBeDefined();
  });

  it("calls onFootnoteSelect when a footnote is clicked", () => {
    const handleSelect = vi.fn();
    render(
      <FootnotesPanel {...defaultProps} onFootnoteSelect={handleSelect} />
    );

    fireEvent.click(screen.getByText("Cited Case One"));
    expect(handleSelect).toHaveBeenCalledWith(1);
  });

  it("renders all used footnotes in the list", () => {
    render(<FootnotesPanel {...defaultProps} />);

    expect(screen.getByText("Cited Case One")).toBeDefined();
    expect(screen.getByText("Cited Case Two")).toBeDefined();
  });

  it("shows collapsed toggle button when panel is closed", () => {
    render(<FootnotesPanel {...defaultProps} isOpen={false} />);

    expect(screen.getByText("Footnotes")).toBeDefined();
  });

  it("shows 'No footnotes yet' when footnotes array is empty", () => {
    render(<FootnotesPanel {...defaultProps} footnotes={[]} />);

    expect(screen.getByText("No footnotes yet")).toBeDefined();
  });
});
