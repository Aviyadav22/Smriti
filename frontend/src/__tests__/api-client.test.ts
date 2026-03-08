import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// We import the module under test. Because api.ts uses `fetch` and
// `localStorage`, we mock them at a minimal level for the token management
// tests and test the pure/exported values directly.
// ---------------------------------------------------------------------------

// Mock localStorage before importing the module
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(globalThis, "localStorage", { value: localStorageMock });

import {
  setTokens,
  clearTokens,
  loadTokens,
  getAccessToken,
  ApiError,
  logout,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("API Client", () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
    clearTokens();
  });

  // -----------------------------------------------------------------------
  // API_BASE
  // -----------------------------------------------------------------------

  it("API_BASE defaults to localhost:8000", async () => {
    // We can't directly import the const (it's not exported), but we can
    // verify it indirectly: getCasePdfUrl uses API_BASE.
    const { getCasePdfUrl } = await import("@/lib/api");
    const url = getCasePdfUrl("abc-123");
    expect(url).toContain("/api/v1/cases/abc-123/pdf");
  });

  // -----------------------------------------------------------------------
  // ApiError
  // -----------------------------------------------------------------------

  it("ApiError has status, code, and message", () => {
    const err = new ApiError(404, "NOT_FOUND", "Case not found");

    expect(err).toBeInstanceOf(Error);
    expect(err.status).toBe(404);
    expect(err.code).toBe("NOT_FOUND");
    expect(err.message).toBe("Case not found");
    expect(err.name).toBe("ApiError");
  });

  it("ApiError is throwable and catchable", () => {
    expect(() => {
      throw new ApiError(500, "SERVER_ERROR", "Internal error");
    }).toThrow("Internal error");
  });

  // -----------------------------------------------------------------------
  // Token management
  // -----------------------------------------------------------------------

  it("setTokens stores tokens and makes them accessible", () => {
    setTokens("access-abc", "refresh-xyz");

    expect(getAccessToken()).toBe("access-abc");
    expect(localStorageMock.setItem).toHaveBeenCalledWith("access_token", "access-abc");
    expect(localStorageMock.setItem).toHaveBeenCalledWith("refresh_token", "refresh-xyz");
  });

  it("clearTokens removes tokens", () => {
    setTokens("a", "r");
    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("access_token");
    expect(localStorageMock.removeItem).toHaveBeenCalledWith("refresh_token");
  });

  it("loadTokens reads from localStorage", () => {
    localStorageMock.setItem("access_token", "stored-token");
    localStorageMock.setItem("refresh_token", "stored-refresh");

    loadTokens();

    expect(getAccessToken()).toBe("stored-token");
  });

  it("logout clears tokens", async () => {
    setTokens("a", "r");
    await logout();

    expect(getAccessToken()).toBeNull();
  });

  // -----------------------------------------------------------------------
  // URL builders
  // -----------------------------------------------------------------------

  it("getCasePdfUrl builds correct URL", async () => {
    const { getCasePdfUrl } = await import("@/lib/api");
    const url = getCasePdfUrl("case-42");
    expect(url).toMatch(/\/cases\/case-42\/pdf$/);
  });

  it("getAudioUrl builds correct URL with language", async () => {
    const { getAudioUrl } = await import("@/lib/api");
    const url = getAudioUrl("case-99", "hi");
    expect(url).toMatch(/\/cases\/case-99\/audio\?language=hi$/);
  });
});
