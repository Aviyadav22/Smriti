import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import type { AudioDigestStatus } from "@/lib/types";

vi.mock("next/navigation", async () => {
  return {
    useRouter: () => ({
      push: vi.fn(),
      back: vi.fn(),
      replace: vi.fn(),
      prefetch: vi.fn(),
      refresh: vi.fn(),
    }),
    useSearchParams: () => new URLSearchParams(),
    useParams: () => ({}),
    usePathname: () => "/case/test-id",
  };
});

const mockGetAudioStatus = vi.fn();
const mockGenerateAudioDigest = vi.fn();
const mockGetAudioUrl = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getAudioStatus: (...args: unknown[]) => mockGetAudioStatus(...args),
    generateAudioDigest: (...args: unknown[]) => mockGenerateAudioDigest(...args),
    getAudioUrl: (...args: unknown[]) => mockGetAudioUrl(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => "test-token",
  };
});

import AudioPlayer from "@/components/audio-player";

describe("AudioPlayer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAudioUrl.mockReturnValue("http://localhost:8000/api/v1/cases/test-id/audio?language=en");
  });

  it("shows generate button when no audio available", async () => {
    mockGetAudioStatus.mockResolvedValue({
      case_id: "test-id",
      available: [],
      generating: [],
      digests: [],
    });
    renderWithProviders(<AudioPlayer caseId="test-id" />);
    await waitFor(() => {
      expect(screen.getByText(/generate/i)).toBeInTheDocument();
    });
  });

  it("shows player controls when audio is available", async () => {
    mockGetAudioStatus.mockResolvedValue({
      case_id: "test-id",
      available: ["en"],
      generating: [],
      digests: [{ language: "en", status: "completed", duration_seconds: 180 }],
    });
    renderWithProviders(<AudioPlayer caseId="test-id" />);
    await waitFor(() => {
      // Should show play button or audio controls
      expect(screen.getByRole("button")).toBeInTheDocument();
    });
  });

  it("shows generating state", async () => {
    mockGetAudioStatus.mockResolvedValue({
      case_id: "test-id",
      available: [],
      generating: ["en"],
      digests: [{ language: "en", status: "generating", duration_seconds: null }],
    });
    renderWithProviders(<AudioPlayer caseId="test-id" />);
    await waitFor(() => {
      expect(screen.getByText(/generating/i)).toBeInTheDocument();
    });
  });

  it("calls generateAudioDigest on button click", async () => {
    mockGetAudioStatus.mockResolvedValue({
      case_id: "test-id",
      available: [],
      generating: [],
      digests: [],
    });
    mockGenerateAudioDigest.mockResolvedValue({ status: "queued" });
    renderWithProviders(<AudioPlayer caseId="test-id" />);

    await waitFor(() => {
      expect(screen.getByText(/generate/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/generate/i));

    await waitFor(() => {
      expect(mockGenerateAudioDigest).toHaveBeenCalledWith("test-id", "en");
    });
  });
});
