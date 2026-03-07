import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import type { JudgeProfile, JudgeCasesResponse } from "@/lib/types";

vi.mock("next/navigation", async () => {
    const actual = await vi.importActual("next/navigation");
    return {
        ...actual,
        useParams: () => ({ name: "Justice D.Y. Chandrachud" }),
        useRouter: () => ({
            push: vi.fn(),
            back: vi.fn(),
            replace: vi.fn(),
            prefetch: vi.fn(),
            refresh: vi.fn(),
        }),
        usePathname: () => "/judge/Justice%20D.Y.%20Chandrachud",
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

const mockGetJudgeProfile = vi.fn();
const mockGetJudgeCases = vi.fn();

vi.mock("@/lib/api", () => ({
    getJudgeProfile: (...args: unknown[]) => mockGetJudgeProfile(...args),
    getJudgeCases: (...args: unknown[]) => mockGetJudgeCases(...args),
    loadTokens: vi.fn(),
    getAccessToken: () => null,
}));

import JudgeProfilePage from "@/app/judge/[name]/page";

function makeProfile(overrides: Partial<JudgeProfile> = {}): JudgeProfile {
    return {
        name: "Justice D.Y. Chandrachud",
        total_cases: 342,
        cases_authored: 198,
        cases_by_year: { "2020": 45, "2021": 60, "2022": 78, "2023": 90, "2024": 69 },
        disposal_patterns: { "Allowed": 120, "Dismissed": 180, "Partly Allowed": 42 },
        bench_combinations: [
            { judge: "Justice Hima Kohli", cases_together: 52 },
            { judge: "Justice J.B. Pardiwala", cases_together: 41 },
        ],
        top_cited_judgments: [
            {
                id: "case-1",
                title: "K.S. Puttaswamy v. Union of India",
                citation: "(2017) 10 SCC 1",
                year: 2017,
                citation_count: 250,
            },
            {
                id: "case-2",
                title: "Navtej Singh Johar v. Union of India",
                citation: "(2018) 10 SCC 1",
                year: 2018,
                citation_count: 180,
            },
        ],
        acts_frequency: {
            "Constitution of India": 210,
            "Code of Criminal Procedure, 1973": 95,
            "Indian Penal Code, 1860": 80,
        },
        case_types: {
            "Criminal Appeal": 120,
            "Civil Appeal": 100,
            "Writ Petition": 80,
            "SLP": 42,
        },
        ...overrides,
    };
}

function makeCases(overrides: Partial<JudgeCasesResponse> = {}): JudgeCasesResponse {
    return {
        items: [
            {
                id: "recent-1",
                title: "State of Maharashtra v. Respondent",
                citation: "(2024) 3 SCC 100",
                year: 2024,
                case_type: "Criminal Appeal",
                court: "Supreme Court of India",
                decision_date: "2024-02-15",
                is_author: true,
            },
        ],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1,
        ...overrides,
    };
}

describe("JudgeProfilePage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders judge name", async () => {
        mockGetJudgeProfile.mockResolvedValue(makeProfile());
        mockGetJudgeCases.mockResolvedValue(makeCases());

        renderWithProviders(<JudgeProfilePage />);

        await waitFor(() => {
            expect(screen.getByText("Justice D.Y. Chandrachud")).toBeInTheDocument();
        });
    });

    it("shows total cases stat", async () => {
        mockGetJudgeProfile.mockResolvedValue(makeProfile());
        mockGetJudgeCases.mockResolvedValue(makeCases());

        renderWithProviders(<JudgeProfilePage />);

        await waitFor(() => {
            expect(screen.getByText("342")).toBeInTheDocument();
        });
        expect(screen.getByText("Total Cases")).toBeInTheDocument();
    });

    it("shows cases authored stat", async () => {
        mockGetJudgeProfile.mockResolvedValue(makeProfile());
        mockGetJudgeCases.mockResolvedValue(makeCases());

        renderWithProviders(<JudgeProfilePage />);

        await waitFor(() => {
            expect(screen.getByText("198")).toBeInTheDocument();
        });
        expect(screen.getByText("Cases Authored")).toBeInTheDocument();
    });

    it("renders disposal patterns section", async () => {
        mockGetJudgeProfile.mockResolvedValue(makeProfile());
        mockGetJudgeCases.mockResolvedValue(makeCases());

        renderWithProviders(<JudgeProfilePage />);

        await waitFor(() => {
            expect(screen.getByText("Disposal Patterns")).toBeInTheDocument();
        });
    });

    it("renders cases by year section", async () => {
        mockGetJudgeProfile.mockResolvedValue(makeProfile());
        mockGetJudgeCases.mockResolvedValue(makeCases());

        renderWithProviders(<JudgeProfilePage />);

        await waitFor(() => {
            expect(screen.getByText("Cases by Year")).toBeInTheDocument();
        });
    });

    it("renders top cited judgments", async () => {
        mockGetJudgeProfile.mockResolvedValue(makeProfile());
        mockGetJudgeCases.mockResolvedValue(makeCases());

        renderWithProviders(<JudgeProfilePage />);

        await waitFor(() => {
            expect(screen.getByText("K.S. Puttaswamy v. Union of India")).toBeInTheDocument();
        });
        expect(screen.getByText("Navtej Singh Johar v. Union of India")).toBeInTheDocument();
        expect(screen.getByText("250 citations")).toBeInTheDocument();
    });

    it("renders acts frequency", async () => {
        mockGetJudgeProfile.mockResolvedValue(makeProfile());
        mockGetJudgeCases.mockResolvedValue(makeCases());

        renderWithProviders(<JudgeProfilePage />);

        await waitFor(() => {
            expect(screen.getByText("Constitution of India")).toBeInTheDocument();
        });
        expect(screen.getByText("Code of Criminal Procedure, 1973")).toBeInTheDocument();
        expect(screen.getByText("Indian Penal Code, 1860")).toBeInTheDocument();
    });

    it("shows loading state", () => {
        mockGetJudgeProfile.mockReturnValue(new Promise(() => {}));
        mockGetJudgeCases.mockReturnValue(new Promise(() => {}));

        renderWithProviders(<JudgeProfilePage />);

        // The Loader2 spinner should be present (it has animate-spin class)
        const spinner = document.querySelector(".animate-spin");
        expect(spinner).toBeInTheDocument();
    });

    it("shows error state", async () => {
        mockGetJudgeProfile.mockRejectedValue(new Error("Network error"));
        mockGetJudgeCases.mockRejectedValue(new Error("Network error"));

        renderWithProviders(<JudgeProfilePage />);

        await waitFor(() => {
            expect(screen.getByText("Judge not found")).toBeInTheDocument();
        });
        expect(screen.getByText("Go Back")).toBeInTheDocument();
    });
});
