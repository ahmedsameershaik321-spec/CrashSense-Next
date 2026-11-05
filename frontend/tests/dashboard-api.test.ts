import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  getDashboardSummary,
  type DashboardSummary,
} from "@/lib/api";

const summary: DashboardSummary = {
  total_videos: 4,
  completed_analyses: 3,
  processing_analyses: 1,
  detected_candidates: 2,
  analysis_worker_running: true,
  recent_activity: [],
};

describe("dashboard summary API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests and validates the authenticated dashboard summary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(summary), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getDashboardSummary("operator-token")).resolves.toEqual(summary);
    expect(fetchMock).toHaveBeenCalledWith(
      "/backend-api/api/v1/dashboard/summary",
      expect.objectContaining({
        headers: {
          Accept: "application/json",
          Authorization: "Bearer operator-token",
        },
      }),
    );
  });

  it("rejects malformed summary data instead of treating it as metrics", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ total_videos: "many" }), { status: 200 }),
      ),
    );

    await expect(getDashboardSummary("operator-token")).rejects.toMatchObject({
      name: "ApiError",
      status: 502,
    } satisfies Partial<ApiError>);
  });
});
