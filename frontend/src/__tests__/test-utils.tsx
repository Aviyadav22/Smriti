import { render, type RenderOptions } from "@testing-library/react";
import { AuthProvider } from "@/lib/auth-context";
import type { ReactElement, ReactNode } from "react";

/**
 * Custom render that wraps components with AuthProvider context.
 * Use this for any component that calls useAuth().
 */
function AllProviders({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

export { renderWithProviders, render };
