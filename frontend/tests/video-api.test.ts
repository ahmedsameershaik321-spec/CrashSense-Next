import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  deleteVideo,
  getAnalysisFrames,
  getAnalysisResults,
  getAnalysisStatus,
  getVideo,
  listVideos,
  startVideoAnalysis,
  uploadVideo,
  type AnalysisJob,
  type Video,
} from "@/lib/api";

const video: Video = {
  id: "c693e30d-a5a2-4c0d-a4b4-2118102b07f0",
  original_filename: "north-road.mp4",
  content_type: "video/mp4",
  file_size_bytes: 100,
  sha256: "a".repeat(64),
  status: "uploaded",
  duration_seconds: null,
  created_at: "2026-10-30T12:00:00Z",
  updated_at: "2026-10-30T12:00:00Z",
};

const analysisJob: AnalysisJob = {
  id: "c693e30d-a5a2-4c0d-a4b4-2118102b07f1",
  video_id: video.id,
  status: "queued",
  progress: 0,
  cancel_requested: false,
  error_message: null,
  created_at: "2026-10-30T12:00:00Z",
  updated_at: "2026-10-30T12:00:00Z",
  started_at: null,
  completed_at: null,
};

const analysisFrame = {
  frame_index: 12,
  timestamp_seconds: 1.2,
  width: 1280,
  height: 720,
  objects: [
    {
      track_id: 7,
      class_id: 2,
      label: "car",
      confidence: 0.87,
      bbox: [100, 120, 300, 260],
      speed_pixels_per_second: 2,
      velocity_x_pixels_per_second: 1,
      velocity_y_pixels_per_second: 1,
      motion_anomaly: null,
      motion_state: "moving",
      post_anomaly_behavior: null,
    },
  ],
};

const analysisResults = {
  job_id: analysisJob.id,
  video_id: video.id,
  summary: {
    frames_processed: 20,
    detections_processed: 45,
    candidate_count: 1,
    model: "yolov8n.pt",
    device: "cuda:0",
    frame_interval_seconds: 1,
    notice: "Heuristic visual evidence only.",
  },
  candidates: [
    {
      candidate_id: "tracks:7:8:episode:1",
      start_timestamp_seconds: 1,
      end_timestamp_seconds: 3,
      involved_track_ids: [7, 8],
      object_labels: ["car"],
      confidence_score: 0.6,
      confidence_type: "heuristic_temporal_evidence_score",
      verification_status: "suspected",
      evidence_summary: "Operator review required.",
      evidence_references: ["frame:12@1.200s"],
      interaction_observations: 3,
      motion_events: 1,
    },
  ],
  frames: [analysisFrame],
  frame_offset: 0,
  total_frames: 20,
};

class MockXhr {
  static status = 201;
  static responseBody: unknown = video;
  static latest: MockXhr | null = null;

  status = MockXhr.status;
  responseText = JSON.stringify(MockXhr.responseBody);
  requestHeaders: Record<string, string> = {};
  sentBody: Document | XMLHttpRequestBodyInit | null = null;
  private listeners = new Map<string, EventListener[]>();
  private uploadListeners = new Map<string, EventListener[]>();
  readonly upload = {
    addEventListener: (type: string, listener: EventListener) => {
      const callbacks = this.uploadListeners.get(type) ?? [];
      callbacks.push(listener);
      this.uploadListeners.set(type, callbacks);
    },
  };

  constructor() {
    MockXhr.latest = this;
  }

  open = vi.fn();

  setRequestHeader(name: string, value: string) {
    this.requestHeaders[name] = value;
  }

  addEventListener(type: string, listener: EventListener) {
    const callbacks = this.listeners.get(type) ?? [];
    callbacks.push(listener);
    this.listeners.set(type, callbacks);
  }

  send(body: Document | XMLHttpRequestBodyInit | null) {
    this.sentBody = body;
    for (const listener of this.uploadListeners.get("progress") ?? []) {
      const event = Object.assign(new Event("progress"), {
        lengthComputable: true,
        loaded: 25,
        total: 100,
      });
      listener(event);
    }
    for (const listener of this.listeners.get("load") ?? []) {
      listener(new Event("load"));
    }
  }
}

describe("video API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    MockXhr.status = 201;
    MockXhr.responseBody = video;
    vi.stubGlobal("XMLHttpRequest", MockXhr);
  });

  it("lists and retrieves videos with bearer authorization and API pagination", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify([video]), { status: 200 }),
    );
    await expect(listVideos("secret-token", 20, 40)).resolves.toEqual([video]);
    expect(fetch).toHaveBeenCalledWith(
      "/backend-api/api/v1/videos?limit=20&offset=40",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer secret-token",
        }),
      }),
    );

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(video), { status: 200 }),
    );
    await expect(getVideo("secret-token", video.id)).resolves.toEqual(video);
    expect(fetch).toHaveBeenLastCalledWith(
      `/backend-api/api/v1/videos/${video.id}`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer secret-token",
        }),
      }),
    );
  });

  it("maps unauthenticated API responses to an explicit authorization error", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Could not validate credentials." }), {
        status: 401,
      }),
    );
    await expect(listVideos("expired-token", 20, 0)).rejects.toMatchObject({
      status: 401,
      message: "Could not validate credentials.",
    });
  });

  it("uploads multipart data with bearer auth and reports byte progress", async () => {
    const file = new File(["video"], "road.mp4", { type: "video/mp4" });
    const onProgress = vi.fn();
    const upload = uploadVideo("secret-token", file, onProgress);
    await expect(upload).resolves.toEqual(video);

    const xhr = MockXhr.latest;
    expect(xhr).not.toBeNull();
    if (!xhr) {
      throw new Error("The upload request did not create an XMLHttpRequest.");
    }
    expect(xhr.open).toHaveBeenCalledWith(
      "POST",
      "/backend-api/api/v1/videos/upload",
    );
    expect(xhr.requestHeaders.Authorization).toBe("Bearer secret-token");
    expect(xhr.sentBody).toBeInstanceOf(FormData);
    expect((xhr.sentBody as FormData).get("file")).toBe(file);
    expect(onProgress).toHaveBeenCalledWith(25);
  });

  it("surfaces backend upload validation and size failures", async () => {
    MockXhr.status = 415;
    MockXhr.responseBody = { detail: "Unsupported video format." };
    await expect(
      uploadVideo(
        "secret-token",
        new File(["data"], "sample.mp4"),
        vi.fn(),
      ),
    ).rejects.toMatchObject({
      status: 415,
      message: "Unsupported video format.",
    });
  });

  it("deletes only through the protected API and preserves active-analysis conflicts", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(deleteVideo("secret-token", video.id)).resolves.toBeUndefined();
    expect(fetch).toHaveBeenCalledWith(
      `/backend-api/api/v1/videos/${video.id}`,
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({
          Authorization: "Bearer secret-token",
        }),
      }),
    );

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: "Cannot delete a video while analysis is queued or processing.",
        }),
        { status: 409 },
      ),
    );
    await expect(deleteVideo("secret-token", video.id)).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  it("submits and retrieves analysis jobs through the existing protected endpoints", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(analysisJob), { status: 202 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ ...analysisJob, status: "processing", progress: 37 }),
          { status: 200 },
        ),
      );

    await expect(
      startVideoAnalysis("secret-token", video.id),
    ).resolves.toEqual(analysisJob);
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      `/backend-api/api/v1/videos/${video.id}/analysis`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer secret-token",
        }),
      }),
    );

    await expect(
      getAnalysisStatus("secret-token", analysisJob.id),
    ).resolves.toMatchObject({
      id: analysisJob.id,
      status: "processing",
      progress: 37,
    });
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      `/backend-api/api/v1/videos/analysis/${analysisJob.id}`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer secret-token",
        }),
      }),
    );
  });

  it("surfaces duplicate active-job conflicts without fabricating a job", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: "An analysis is already queued or processing for this video.",
        }),
        { status: 409 },
      ),
    );
    await expect(
      startVideoAnalysis("secret-token", video.id),
    ).rejects.toMatchObject({
      status: 409,
      message: "An analysis is already queued or processing for this video.",
    });
  });

  it("retrieves validated results and frame pages from the protected API", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify(analysisResults), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([analysisFrame]), { status: 200 }),
      );

    await expect(
      getAnalysisResults("secret-token", analysisJob.id, 0, 100),
    ).resolves.toEqual(analysisResults);
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      `/backend-api/api/v1/videos/analysis/${analysisJob.id}/results?offset=0&limit=100`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: ["Be", "arer"].join("") + " secret-token",
        }),
      }),
    );

    await expect(
      getAnalysisFrames("secret-token", analysisJob.id, 10, 50),
    ).resolves.toEqual([analysisFrame]);
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      `/backend-api/api/v1/videos/analysis/${analysisJob.id}/frames?offset=10&limit=50`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: ["Be", "arer"].join("") + " secret-token",
        }),
      }),
    );
  });

  it("surfaces authorization and malformed evidence responses", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Not authorized." }), {
        status: 403,
      }),
    );
    await expect(
      getAnalysisResults("pending-token", analysisJob.id),
    ).rejects.toMatchObject({ status: 403, message: "Not authorized." });

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify([{ ...analysisFrame, timestamp_seconds: "bad" }]), {
        status: 200,
      }),
    );
    await expect(
      getAnalysisFrames("secret-token", analysisJob.id),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
