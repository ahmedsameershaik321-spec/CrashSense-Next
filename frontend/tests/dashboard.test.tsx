import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/dashboard/page";
import { ApiError, type DashboardSummary } from "@/lib/api";

const mocks = vi.hoisted(() => ({
  getDashboardSummary: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getDashboardSummary: mocks.getDashboardSummary,
  };
});

vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({
    session: {
      accessToken: "operator-token",
      user: {
        id: "operator-id",
        first_name: "Casey",
        last_name: "Operator",
        role: "monitoring_operator",
      },
    },
  }),
}));

const summary: DashboardSummary = {
  total_videos: 12,
  completed_analyses: 8,
  processing_analyses: 2,
  detected_candidates: 5,
  analysis_worker_running: true,
  recent_activity: [
    {
      analysis_id: "c693e30d-a5a2-4c0d-a4b4-2118102b07f1",
      video_id: "c693e30d-a5a2-4c0d-a4b4-2118102b07f0",
      video_name: "north-road.mp4",
      status: "completed",
      progress: 100,
      candidate_count: 2,
      created_at: "2026-11-05T07:00:00Z",
    },
  ],
};

describe("monitoring dashboard", () => {
  beforeEach(() => {
    mocks.getDashboardSummary.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders API metrics, worker state, and linked recent activity", async () => {
    mocks.getDashboardSummary.mockResolvedValue(summary);
    render(<DashboardPage />);

    expect(await screen.findByText("Good to see you, Casey.")).toBeInTheDocument();
    expect(await screen.findByText("Worker process running")).toBeInTheDocument();
    expect(
      screen.getByText(/model readiness is not reported by this API/i),
    ).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("north-road.mp4")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "Analysis job statuses among the latest 1 jobs",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /north-road\.mp4/ }),
    ).toHaveAttribute(
      "href",
      "/dashboard/analysis/c693e30d-a5a2-4c0d-a4b4-2118102b07f1",
    );
    expect(mocks.getDashboardSummary).toHaveBeenCalledWith("operator-token");
  });

  it("shows a real empty state when the API reports no activity", async () => {
    mocks.getDashboardSummary.mockResolvedValue({
      ...summary,
      total_videos: 0,
      completed_analyses: 0,
      processing_analyses: 0,
      detected_candidates: 0,
      recent_activity: [],
    });
    render(<DashboardPage />);

    expect(await screen.findByText("No analysis activity yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse protected videos" })).toHaveAttribute(
      "href",
      "/dashboard/videos",
    );
  });

  it("reports API errors and retries without showing fabricated values", async () => {
    mocks.getDashboardSummary
      .mockRejectedValueOnce(new ApiError("Service unavailable.", 503))
      .mockResolvedValueOnce(summary);
    render(<DashboardPage />);

    expect(await screen.findByText("Service unavailable.")).toBeInTheDocument();
    expect(screen.getByText("Worker status unavailable")).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Monitoring metrics" })).getAllByText("—"),
    ).toHaveLength(4);

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => {
      expect(screen.getByText("Worker process running")).toBeInTheDocument();
    });
    expect(mocks.getDashboardSummary).toHaveBeenCalledTimes(2);
  });
});
