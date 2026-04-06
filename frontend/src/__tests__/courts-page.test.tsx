import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import type { CourtStats } from "@/lib/types";

vi.mock("next/navigation", async () => {
    const actual = await vi.importActual("next/navigation");
    return {
        ...actual,
        useRouter: () => ({
            push: vi.fn(),
            back: vi.fn(),
            replace: vi.fn(),
            prefetch: vi.fn(),
            refresh: vi.fn(),
        }),
        usePathname: () => "/courts",
    };
});

// Mock recharts to avoid canvas issues in jsdom
vi.mock("recharts", () => ({
    BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
    Bar: () => <div />,
    XAxis: () => <div />,
    YAxis: () => <div />,
    Tooltip: () => <div />,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    PieChart: ({ children }: { children: React.ReactNode }) => <div data-testid="pie-chart">{children}</div>,
    Pie: () => <div />,
    Cell: () => <div />,
    Legend: () => <div />,
}));

const mockGetCourtStats = vi.fn();

vi.mock("@/lib/api", () => ({
    getCourtStats: (...args: unknown[]) => mockGetCourtStats(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => null,
}));

import CourtsPage from "@/app/(auth)/courts/page";

function makeStats(overrides: Partial<CourtStats> = {}): CourtStats {
    return {
        court: "Supreme Court of India",
        total_cases: 1250,
        cases_by_year: { "2020": 200, "2021": 300, "2022": 350, "2023": 400 },
        case_types: { "Criminal Appeal": 500, "Civil Appeal": 400, "Writ Petition": 350 },
        disposal_patterns: { "Allowed": 450, "Dismissed": 600, "Partly Allowed": 200 },
        top_judges: [
            { judge: "Justice D.Y. Chandrachud", cases: 342 },
            { judge: "Justice Sanjay Kishan Kaul", cases: 280 },
            { judge: "Justice Hima Kohli", cases: 195 },
        ],
        ...overrides,
    };
}

describe("CourtsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders page title 'Court Statistics'", async () => {
        mockGetCourtStats.mockResolvedValue(makeStats());

        renderWithProviders(<CourtsPage />);

        await waitFor(() => {
            expect(screen.getByText("Court Statistics")).toBeInTheDocument();
        });
    });

    it("loads and displays total cases count", async () => {
        mockGetCourtStats.mockResolvedValue(makeStats());

        renderWithProviders(<CourtsPage />);

        await waitFor(() => {
            expect(screen.getByText("1250")).toBeInTheDocument();
        });
        expect(screen.getByText("Total Cases")).toBeInTheDocument();
    });

    it("shows top judges list", async () => {
        mockGetCourtStats.mockResolvedValue(makeStats());

        renderWithProviders(<CourtsPage />);

        await waitFor(() => {
            expect(screen.getByText("Justice D.Y. Chandrachud")).toBeInTheDocument();
        });
        expect(screen.getByText("Justice Sanjay Kishan Kaul")).toBeInTheDocument();
        expect(screen.getByText("Justice Hima Kohli")).toBeInTheDocument();
        expect(screen.getByText("342 cases")).toBeInTheDocument();
    });

    it("shows loading state", () => {
        mockGetCourtStats.mockReturnValue(new Promise(() => {}));

        renderWithProviders(<CourtsPage />);

        const spinner = document.querySelector(".animate-spin");
        expect(spinner).toBeInTheDocument();
    });
});
