import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AgentStepTimeline } from "@/components/agent-step-timeline";
import { AgentCheckpointPrompt } from "@/components/agent-checkpoint-prompt";
import { AgentMemoViewer } from "@/components/agent-memo-viewer";
import type { AgentStep } from "@/lib/types";

// Mock next/link to render as a plain anchor
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("AgentStepTimeline", () => {
  it("renders steps with human-readable names", () => {
    const steps: AgentStep[] = [
      { name: "classify", status: "completed" },
      { name: "search", status: "active" },
      { name: "synthesize", status: "pending" },
    ];
    render(<AgentStepTimeline steps={steps} />);
    expect(screen.getByText("Understanding your question")).toBeDefined();
    expect(screen.getByText("Searching case law")).toBeDefined();
    expect(screen.getByText("Drafting research memo")).toBeDefined();
  });

  it("falls back to raw name for unknown steps", () => {
    const steps: AgentStep[] = [
      { name: "custom_step", status: "active" },
    ];
    render(<AgentStepTimeline steps={steps} />);
    expect(screen.getByText("custom_step")).toBeDefined();
  });

  it("renders step messages when provided", () => {
    const steps: AgentStep[] = [
      { name: "search", status: "active", message: "Found 12 cases" },
    ];
    render(<AgentStepTimeline steps={steps} />);
    expect(screen.getByText("Found 12 cases")).toBeDefined();
  });

  it("renders error status steps", () => {
    const steps: AgentStep[] = [
      { name: "verify", status: "error", message: "Citation check failed" },
    ];
    render(<AgentStepTimeline steps={steps} />);
    expect(screen.getByText("Verifying citations")).toBeDefined();
    expect(screen.getByText("Citation check failed")).toBeDefined();
  });

  it("renders case prep agent steps correctly", () => {
    const steps: AgentStep[] = [
      { name: "load_analysis", status: "completed" },
      { name: "deep_precedent_search", status: "active" },
      { name: "generate_strategy_memo", status: "pending" },
    ];
    render(<AgentStepTimeline steps={steps} />);
    expect(screen.getByText("Loading document analysis")).toBeDefined();
    expect(screen.getByText("Deep precedent search")).toBeDefined();
    expect(screen.getByText("Generating strategy memo")).toBeDefined();
  });
});

describe("AgentCheckpointPrompt", () => {
  it("renders the question text", () => {
    const onSubmit = vi.fn();
    render(<AgentCheckpointPrompt question="Review these findings?" onSubmit={onSubmit} />);
    expect(screen.getByText("Review these findings?")).toBeDefined();
  });

  it("renders suggestion chips", () => {
    const onSubmit = vi.fn();
    render(<AgentCheckpointPrompt question="Review?" onSubmit={onSubmit} />);
    // Default chips when no context provided
    expect(screen.getByText("Looks good, proceed")).toBeDefined();
  });

  it("clicking a suggestion chip submits structured JSON", () => {
    const onSubmit = vi.fn();
    render(<AgentCheckpointPrompt question="Review?" onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText("Looks good, proceed"));
    // Proceed chips send structured JSON with action: "approve"
    expect(onSubmit).toHaveBeenCalledWith(JSON.stringify({ action: "approve" }));
  });

  it("submits user input as structured JSON and clears the textarea", () => {
    const onSubmit = vi.fn();
    render(<AgentCheckpointPrompt question="Review?" onSubmit={onSubmit} />);
    const textarea = screen.getByPlaceholderText("Additional instructions or modifications...");
    fireEvent.change(textarea, { target: { value: "Proceed with analysis" } });
    fireEvent.click(screen.getByText("Submit"));
    // [M50] "Proceed with analysis" is feedback (not bare "proceed"), treated as feedback
    expect(onSubmit).toHaveBeenCalledWith(JSON.stringify({ action: "feedback", text: "Proceed with analysis" }));
    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("bare 'proceed' is treated as approve", () => {
    const onSubmit = vi.fn();
    render(<AgentCheckpointPrompt question="Review?" onSubmit={onSubmit} />);
    const textarea = screen.getByPlaceholderText("Additional instructions or modifications...");
    fireEvent.change(textarea, { target: { value: "proceed" } });
    fireEvent.click(screen.getByText("Submit"));
    expect(onSubmit).toHaveBeenCalledWith(JSON.stringify({ action: "approve" }));
  });

  it("does not submit empty input", () => {
    const onSubmit = vi.fn();
    render(<AgentCheckpointPrompt question="Review?" onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText("Submit"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("renders context when provided", () => {
    const onSubmit = vi.fn();
    const context = { sub_questions: ["What is Article 21?", "Right to life scope"] };
    render(<AgentCheckpointPrompt question="Review?" context={context} onSubmit={onSubmit} />);
    expect(screen.getByText("sub questions")).toBeDefined();
    expect(screen.getByText("What is Article 21?")).toBeDefined();
    expect(screen.getByText("Right to life scope")).toBeDefined();
  });

  it("disables inputs when disabled prop is true", () => {
    const onSubmit = vi.fn();
    render(<AgentCheckpointPrompt question="Review?" onSubmit={onSubmit} disabled />);
    const textarea = screen.getByPlaceholderText("Additional instructions or modifications...");
    expect((textarea as HTMLTextAreaElement).disabled).toBe(true);
    expect((screen.getByText("Submit") as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("AgentMemoViewer", () => {
  it("renders memo content", () => {
    render(<AgentMemoViewer content="This is a research memo about Article 21." />);
    expect(screen.getByText(/research memo about Article 21/)).toBeDefined();
  });

  it("renders confidence badge when provided", () => {
    render(<AgentMemoViewer content="Memo content" confidence={0.85} />);
    expect(screen.getByText("High Confidence: 85%")).toBeDefined();
  });

  it("does not render confidence badge when not provided", () => {
    render(<AgentMemoViewer content="Memo content" />);
    expect(screen.queryByText(/Confidence:/)).toBeNull();
  });

  it("renders section headings from markdown ## syntax", () => {
    const content = "## Key Findings\nSome findings here\n## Conclusion\nFinal thoughts";
    render(<AgentMemoViewer content={content} />);
    expect(screen.getByText("Key Findings")).toBeDefined();
    expect(screen.getByText("Conclusion")).toBeDefined();
  });

  it("renders copy button", () => {
    render(<AgentMemoViewer content="Test content" />);
    expect(screen.getByText("Copy")).toBeDefined();
  });

  it("renders download button", () => {
    render(<AgentMemoViewer content="Test content" />);
    expect(screen.getByText("Download MD")).toBeDefined();
  });

  it("copy button calls navigator.clipboard.writeText", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<AgentMemoViewer content="Copy this content" />);
    fireEvent.click(screen.getByText("Copy"));
    expect(writeText).toHaveBeenCalledWith("Copy this content");
  });

  it("download button triggers file download", () => {
    const createObjectURL = vi.fn().mockReturnValue("blob:test");
    const revokeObjectURL = vi.fn();
    global.URL.createObjectURL = createObjectURL;
    global.URL.revokeObjectURL = revokeObjectURL;

    render(<AgentMemoViewer content="Download this" />);

    // Spy on appendChild/removeChild after render so it doesn't interfere with React rendering
    const clickSpy = vi.fn();
    const originalAppendChild = document.body.appendChild.bind(document.body);
    const originalRemoveChild = document.body.removeChild.bind(document.body);
    const appendChildSpy = vi.spyOn(document.body, "appendChild").mockImplementation((node) => {
      if (node instanceof HTMLAnchorElement) {
        node.click = clickSpy;
        return node;
      }
      return originalAppendChild(node);
    });
    const removeChildSpy = vi.spyOn(document.body, "removeChild").mockImplementation((node) => {
      if (node instanceof HTMLAnchorElement) {
        return node;
      }
      return originalRemoveChild(node);
    });

    fireEvent.click(screen.getByText("Download MD"));
    expect(createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();

    appendChildSpy.mockRestore();
    removeChildSpy.mockRestore();
  });
});
