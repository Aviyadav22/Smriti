import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErrorBoundary } from "@/components/error-boundary";

// ---------------------------------------------------------------------------
// A component that throws on demand
// ---------------------------------------------------------------------------

function Thrower({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error("Test explosion");
  }
  return <div>Children rendered OK</div>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ErrorBoundary", () => {
  it("renders children normally when no error", () => {
    render(
      <ErrorBoundary>
        <Thrower shouldThrow={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Children rendered OK")).toBeInTheDocument();
  });

  it("catches error and shows fallback UI", () => {
    // Suppress React error boundary console.error noise
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Thrower shouldThrow={true} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText(/unexpected error occurred/i)).toBeInTheDocument();
    expect(screen.getByText("Try again")).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it("clicking Try again resets the error state", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();

    // We need a component whose throw behavior can change between renders.
    let shouldThrow = true;
    function ConditionalThrower() {
      if (shouldThrow) throw new Error("Boom");
      return <div>Recovered successfully</div>;
    }

    const { rerender } = render(
      <ErrorBoundary>
        <ConditionalThrower />
      </ErrorBoundary>,
    );

    // Should show error state
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // Stop throwing before clicking Try again
    shouldThrow = false;

    // Force rerender so the boundary picks up the non-throwing version
    rerender(
      <ErrorBoundary>
        <ConditionalThrower />
      </ErrorBoundary>,
    );

    await user.click(screen.getByText("Try again"));

    expect(screen.getByText("Recovered successfully")).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
