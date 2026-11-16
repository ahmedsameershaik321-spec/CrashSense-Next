import {
  cleanup,
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  type Video,
} from "@/lib/api";
import { AnalysisHistory } from "@/components/analysis-history";
import { AnalysisResultsView } from "@/components/analysis-results";
import { VideoDetails } from "@/components/video-details";
import { VideoAnalysisPanel } from "@/components/video-analysis-panel";
import { VideoLibrary } from "@/components/video-library";
import { VideoUpload } from "@/components/video-upload";
import {
  MAX_UPLOAD_SIZE_BYTES,
  filterVideos,
  formatDuration,
  validateVideoUpload,
} from "@/lib/videos";

const mocks = vi.hoisted(() => ({
  listVideos: vi.fn(),
  getVideo: vi.fn(),
  getAnalysisResults: vi.fn(),
  getAnalysisFrames: vi.fn(),
  uploadVideo: vi.fn(),
  deleteVideo: vi.fn(),
  createVideoStreamSession: vi.fn(),
  getAnalysisStatus: vi.fn(),
  startVideoAnalysis: vi.fn(),
  getVideoLocation: vi.fn(),
  getNearbyResources: vi.fn(),
  listCameras: vi.fn(),
  listEmergencyAlertAudit: vi.fn(),
  routerReplace: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    listVideos: mocks.listVideos,
    getVideo: mocks.getVideo,
    getAnalysisResults: mocks.getAnalysisResults,
    getAnalysisFrames: mocks.getAnalysisFrames,
    getAnalysisStatus: mocks.getAnalysisStatus,
    uploadVideo: mocks.uploadVideo,
    deleteVideo: mocks.deleteVideo,
    createVideoStreamSession: mocks.createVideoStreamSession,
    startVideoAnalysis: mocks.startVideoAnalysis,
    getVideoLocation: mocks.getVideoLocation,
    getNearbyResources: mocks.getNearbyResources,
    listCameras: mocks.listCameras,
    listEmergencyAlertAudit: mocks.listEmergencyAlertAudit,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.routerReplace }),
}));

const video: Video = {
  id: "c693e30d-a5a2-4c0d-a4b4-2118102b07f0",
  original_filename: "north-road.mp4",
  content_type: "video/mp4",
  file_size_bytes: 2 * 1024 * 1024,
  sha256: "a".repeat(64),
  status: "uploaded",
  duration_seconds: 87.6,
  created_at: "2026-10-30T12:00:00Z",
  updated_at: "2026-10-30T12:00:00Z",
};

const analysisId = "c693e30d-a5a2-4c0d-a4b4-2118102b07f1";
const analysisJob = {
  id: analysisId,
  video_id: video.id,
  status: "completed" as const,
  progress: 100,
  cancel_requested: false,
  error_message: null,
  created_at: "2026-10-30T12:00:00Z",
  updated_at: "2026-10-30T12:01:00Z",
  started_at: "2026-10-30T12:00:01Z",
  completed_at: "2026-10-30T12:01:00Z",
};
const candidates = [
  {
    candidate_id: "tracks:7:8:episode:1",
    start_timestamp_seconds: 1,
    end_timestamp_seconds: 3,
    involved_track_ids: [7, 8],
    object_labels: ["car"],
    confidence_score: 0.6,
    confidence_type: "heuristic_temporal_evidence_score",
    verification_status: "suspected" as const,
    evidence_summary: "Potential close tracked interaction; operator review required.",
    evidence_references: ["frame:12@1.200s"],
    interaction_observations: 3,
    motion_events: 1,
    event_state: "suspected" as const,
    accident_category: "UNKNOWN" as const,
    classification_confidence: null,
    classification_reasoning:
      "The available model detects objects, not accident events.",
    severity: "UNKNOWN" as const,
    severity_confidence: null,
    severity_reasoning_factors: [
      "No validated impact, rollover, damage, or injury signal is available.",
    ],
    severity_missing_information: ["Validated collision or impact evidence."],
    human_review_required: true,
  },
  {
    candidate_id: "tracks:11:12:episode:2",
    start_timestamp_seconds: 5,
    end_timestamp_seconds: 6,
    involved_track_ids: [11, 12],
    object_labels: ["car", "person"],
    confidence_score: 0.8,
    confidence_type: "heuristic_temporal_evidence_score",
    verification_status: "verified_detection" as const,
    evidence_summary: "Pipeline verification classification; no medical assessment.",
    evidence_references: ["frame:52@5.200s"],
    interaction_observations: 4,
    motion_events: 2,
    event_state: "needs_review" as const,
    accident_category: "UNKNOWN" as const,
    classification_confidence: null,
    classification_reasoning:
      "The available model detects objects, not accident events.",
    severity: "UNKNOWN" as const,
    severity_confidence: null,
    severity_reasoning_factors: [
      "No validated impact, rollover, damage, or injury signal is available.",
    ],
    severity_missing_information: ["Validated collision or impact evidence."],
    human_review_required: true,
  },
];
const evidenceFrames = [
  {
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
        bbox: [100, 120, 300, 260] as [number, number, number, number],
        speed_pixels_per_second: 2,
        velocity_x_pixels_per_second: 1,
        velocity_y_pixels_per_second: 1,
        motion_anomaly: null,
        motion_state: "moving",
        post_anomaly_behavior: null,
      },
    ],
  },
  {
    frame_index: 52,
    timestamp_seconds: 5.2,
    width: 1280,
    height: 720,
    objects: [],
  },
];
const analysisResults = {
  job_id: analysisId,
  video_id: video.id,
  summary: {
    frames_processed: 20,
    detections_processed: 45,
    candidate_count: 2,
    model: "yolov8n.pt",
    device: "cuda:0",
    frame_interval_seconds: 1,
    processing_seconds: 12.5,
    processing_fps: 1.6,
    notice: "Heuristic visual evidence only; not a calibrated probability.",
    accident_classification: {
      label: "UNKNOWN" as const,
      model_status: "not_configured" as const,
      model: null,
      device: "cpu",
      frames_sampled: 0,
      windows_evaluated: 0,
      partial_window_frames: 0,
      inference_seconds: 0,
      max_accident_score: null,
      thresholds: { normal: 0.1, accident: 0.9 },
      evidence_windows: [],
      human_review_required: true,
      confidence: null,
      reason_code: "weights_not_configured",
      reason: "No trained accident-classifier checkpoint is configured.",
    },
  },
  candidates,
  frames: [evidenceFrames[0]],
  frame_offset: 0,
  total_frames: 20,
};

beforeEach(() => {
  vi.useRealTimers();
  localStorage.clear();
  mocks.listVideos.mockReset();
  mocks.getVideo.mockReset();
  mocks.getAnalysisResults.mockReset();
  mocks.getAnalysisFrames.mockReset();
  mocks.uploadVideo.mockReset();
  mocks.deleteVideo.mockReset();
  mocks.createVideoStreamSession.mockReset();
  mocks.getAnalysisStatus.mockReset();
  mocks.startVideoAnalysis.mockReset();
  mocks.getVideoLocation.mockReset();
  mocks.getNearbyResources.mockReset();
  mocks.listCameras.mockReset();
  mocks.listEmergencyAlertAudit.mockReset();
  mocks.routerReplace.mockReset();
  mocks.getVideoLocation.mockResolvedValue({
    video_id: video.id,
    source: "unavailable",
    camera: null,
  });
  mocks.listEmergencyAlertAudit.mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("video library", () => {
  it("loads an authenticated API page and searches returned video metadata", async () => {
    mocks.listVideos.mockResolvedValue([video]);
    render(<VideoLibrary accessToken="operator-token" userId="operator-id" />);

    expect(await screen.findByText("north-road.mp4")).toBeInTheDocument();
    expect(mocks.listVideos).toHaveBeenCalledWith("operator-token", 20, 0);
    expect(screen.getByText("2.0 MB")).toBeInTheDocument();
    expect(screen.getByText("1:27")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search this page" }), {
      target: { value: "not-present" },
    });
    expect(await screen.findByText("No matching videos")).toBeInTheDocument();
  });

  it("shows protected API errors instead of fabricating an empty library", async () => {
    mocks.listVideos.mockRejectedValue(
      new ApiError("You do not have permission to access this resource.", 403),
    );
    render(<VideoLibrary accessToken="pending-token" userId="pending-id" />);
    expect(
      await screen.findByText("You do not have permission to access this resource."),
    ).toBeInTheDocument();
  });

  it("requests the next page using the API offset pagination", async () => {
    mocks.listVideos
      .mockResolvedValueOnce(
        Array.from({ length: 20 }, (_, index) => ({
          ...video,
          id: `c693e30d-a5a2-4c0d-a4b4-${String(index).padStart(12, "0")}`,
          original_filename: `road-${index}.mp4`,
        })),
      )
      .mockResolvedValueOnce([]);
    render(<VideoLibrary accessToken="operator-token" userId="operator-id" />);
    await screen.findByText("road-0.mp4");
    fireEvent.click(screen.getByRole("button", { name: "Next videos page" }));
    await waitFor(() => {
      expect(mocks.listVideos).toHaveBeenLastCalledWith("operator-token", 20, 20);
    });
    expect(await screen.findByText("No videos in this library page")).toBeInTheDocument();
  });
});

describe("video upload", () => {
  it("submits a supported file once and reports completion", async () => {
    mocks.uploadVideo.mockImplementation(
      async (_token: string, _file: File, onProgress: (progress: number) => void) => {
        onProgress(100);
        return video;
      },
    );
    const onUploaded = vi.fn();
    render(<VideoUpload accessToken="operator-token" onUploaded={onUploaded} />);

    const file = new File(["video-data"], "north-road.mp4", { type: "video/mp4" });
    fireEvent.change(screen.getByLabelText("Choose video file"), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload video" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "north-road.mp4 was uploaded successfully.",
    );
    expect(mocks.uploadVideo).toHaveBeenCalledTimes(1);
    expect(mocks.uploadVideo).toHaveBeenCalledWith(
      "operator-token",
      file,
      expect.any(Function),
    );
    expect(onUploaded).toHaveBeenCalledWith(video);
  });

  it("keeps a successful upload successful when the library refresh fails", async () => {
    mocks.uploadVideo.mockResolvedValue(video);
    const onUploaded = vi.fn().mockRejectedValue(new Error("refresh failed"));
    render(<VideoUpload accessToken="operator-token" onUploaded={onUploaded} />);
    fireEvent.change(screen.getByLabelText("Choose video file"), {
      target: { files: [new File(["video-data"], "north-road.mp4")] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload video" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "north-road.mp4 was uploaded successfully.",
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The video was uploaded, but the library could not refresh.",
    );
    expect(mocks.uploadVideo).toHaveBeenCalledTimes(1);
  });

  it("prevents a duplicate submission while the upload request is pending", async () => {
    let finishUpload: ((result: Video) => void) | undefined;
    mocks.uploadVideo.mockImplementation(
      () =>
        new Promise<Video>((resolve) => {
          finishUpload = resolve;
        }),
    );
    render(<VideoUpload accessToken="operator-token" onUploaded={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Choose video file"), {
      target: {
        files: [new File(["video-data"], "north-road.mp4", { type: "video/mp4" })],
      },
    });
    const submit = screen.getByRole("button", { name: "Upload video" });
    fireEvent.click(submit);
    expect(submit).toBeDisabled();
    fireEvent.click(submit);
    expect(mocks.uploadVideo).toHaveBeenCalledTimes(1);

    finishUpload?.(video);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "north-road.mp4 was uploaded successfully.",
    );
  });

  it("rejects unsupported and over-limit files before making an API request", async () => {
    render(<VideoUpload accessToken="operator-token" onUploaded={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Choose video file"), {
      target: { files: [new File(["bad"], "notes.pdf", { type: "application/pdf" })] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Choose an MP4, MOV, AVI, or MKV video.",
    );
    expect(mocks.uploadVideo).not.toHaveBeenCalled();

    expect(
      validateVideoUpload({ name: "large.mp4", size: MAX_UPLOAD_SIZE_BYTES + 1 }),
    ).toMatch(/100 MB or smaller/);
    expect(
      validateVideoUpload({ name: "empty.mp4", size: 0 }),
    ).toMatch(/empty/);
    expect(mocks.uploadVideo).not.toHaveBeenCalled();
  });

  it("surfaces API-side upload failures such as oversized uploads", async () => {
    mocks.uploadVideo.mockRejectedValue(
      new ApiError("Video exceeds the maximum upload size of 100 MB.", 413),
    );
    render(<VideoUpload accessToken="operator-token" onUploaded={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Choose video file"), {
      target: { files: [new File(["content"], "road.mp4", { type: "video/mp4" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload video" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Video exceeds the maximum upload size of 100 MB.",
    );
  });
});

describe("video details and playback", () => {
  it("loads metadata and uses a token-free same-origin URL for protected range playback", async () => {
    mocks.getVideo.mockResolvedValue(video);
    mocks.createVideoStreamSession.mockResolvedValue(undefined);
    render(
      <VideoDetails
        accessToken="operator-token"
        expiresInSeconds={900}
        userId="operator-id"
        videoId={video.id}
      />,
    );

    expect(await screen.findByRole("heading", { name: "north-road.mp4" })).toBeInTheDocument();
    const player = document.querySelector("video");
    expect(player).toHaveAttribute("src", `/api/videos/${video.id}/stream`);
    expect(player).toHaveAttribute("controls");
    expect(mocks.getVideo).toHaveBeenCalledWith("operator-token", video.id);
    expect(mocks.createVideoStreamSession).toHaveBeenCalledWith(
      "operator-token",
      900,
    );
  });

  it("reports authorization errors while loading video metadata", async () => {
    mocks.getVideo.mockRejectedValue(
      new ApiError("Your account is inactive.", 403),
    );
    render(
      <VideoDetails
        accessToken="inactive-token"
        expiresInSeconds={900}
        userId="inactive-id"
        videoId={video.id}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your account is inactive.",
    );
  });

  it("keeps analysis-active deletion restrictions visible and retains the video", async () => {
    mocks.getVideo.mockResolvedValue(video);
    mocks.createVideoStreamSession.mockResolvedValue(undefined);
    mocks.deleteVideo.mockRejectedValue(
      new ApiError(
        "Cannot delete a video while analysis is queued or processing.",
        409,
      ),
    );
    render(
      <VideoDetails
        accessToken="operator-token"
        expiresInSeconds={900}
        userId="operator-id"
        videoId={video.id}
      />,
    );

    await screen.findByRole("heading", { name: "north-road.mp4" });
    fireEvent.click(screen.getByRole("button", { name: "Delete video" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete video" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "This video has an analysis queued or in progress and cannot be deleted yet.",
    );
    expect(mocks.routerReplace).not.toHaveBeenCalled();
  });
});

describe("video analysis controls", () => {
  const queuedJob = {
    id: "c693e30d-a5a2-4c0d-a4b4-2118102b07f1",
    video_id: video.id,
    status: "queued" as const,
    progress: 0,
    cancel_requested: false,
    error_message: null,
    created_at: "2026-10-30T12:00:00Z",
    updated_at: "2026-10-30T12:00:00Z",
    started_at: null,
    completed_at: null,
  };

  it("submits once, polls backend progress, and stops when the job completes", async () => {
    mocks.startVideoAnalysis.mockResolvedValue(queuedJob);
    mocks.getAnalysisStatus
      .mockResolvedValueOnce({
        ...queuedJob,
        status: "processing",
        progress: 43,
      })
      .mockResolvedValueOnce({
        ...queuedJob,
        status: "completed",
        progress: 100,
        completed_at: "2026-10-30T12:01:00Z",
      });
    render(
      <VideoAnalysisPanel
        accessToken="operator-token"
        userId="operator-id"
        videoId={video.id}
      />,
    );

    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Analyze video" }));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(mocks.startVideoAnalysis).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("button", { name: "Analysis in progress" }),
    ).toBeDisabled();
    expect(screen.getByText("0%")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(mocks.getAnalysisStatus).toHaveBeenCalledWith(
      "operator-token",
      queuedJob.id,
    );
    expect(screen.getByText("43%")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(screen.getByText("Completed")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(mocks.getAnalysisStatus).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("reopens saved job IDs by fetching their real status and retries failed jobs", async () => {
    const failedJob = {
      ...queuedJob,
      status: "failed" as const,
      progress: 28,
      error_message: "Model weights were unavailable.",
      completed_at: "2026-10-30T12:01:00Z",
    };
    localStorage.setItem(
      `crashsense.analysis-history.v1:operator-id:${video.id}`,
      JSON.stringify([failedJob.id]),
    );
    mocks.getAnalysisStatus.mockResolvedValue(failedJob);
    mocks.startVideoAnalysis.mockResolvedValue({
      ...queuedJob,
      id: "d693e30d-a5a2-4c0d-a4b4-2118102b07f2",
    });
    render(
      <VideoAnalysisPanel
        accessToken="operator-token"
        userId="operator-id"
        videoId={video.id}
      />,
    );

    expect(await screen.findByText("Failed")).toBeInTheDocument();
    expect(mocks.getAnalysisStatus).toHaveBeenCalledWith(
      "operator-token",
      failedJob.id,
    );
    fireEvent.click(screen.getByRole("button", { name: "Analyze again" }));
    expect(await screen.findByText("Queued")).toBeInTheDocument();
    expect(mocks.startVideoAnalysis).toHaveBeenCalledWith(
      "operator-token",
      video.id,
    );
  });

  it("shows unauthorized and duplicate-active errors without displaying a fake job", async () => {
    mocks.startVideoAnalysis.mockRejectedValue(
      new ApiError(
        "An analysis is already queued or processing for this video.",
        409,
      ),
    );
    render(
      <VideoAnalysisPanel
        accessToken="pending-token"
        userId="pending-user"
        videoId={video.id}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Analyze video" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "An analysis is already queued or processing for this video.",
    );
    expect(screen.queryByText("Queued")).not.toBeInTheDocument();

    cleanup();
    mocks.startVideoAnalysis.mockRejectedValue(
      new ApiError("You do not have permission to access this resource.", 403),
    );
    render(
      <VideoAnalysisPanel
        accessToken="pending-token"
        userId="pending-user-2"
        videoId={video.id}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Analyze video" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your account is not authorized to run video analysis.",
    );
  });
});

describe("analysis history and results", () => {
  it("loads saved jobs from the protected API and links into analysis review", async () => {
    localStorage.setItem(
      `crashsense.analysis-history.v1:operator-id:${video.id}`,
      JSON.stringify([analysisId]),
    );
    mocks.getAnalysisStatus.mockResolvedValue(analysisJob);
    render(
      <AnalysisHistory accessToken="operator-token" userId="operator-id" />,
    );

    expect(await screen.findByText(`Job ${analysisId}`)).toBeInTheDocument();
    expect(mocks.getAnalysisStatus).toHaveBeenCalledWith(
      "operator-token",
      analysisId,
    );
    expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute(
      "href",
      `/dashboard/analysis/${analysisId}`,
    );
  });

  it("shows candidate results, changes candidates, and navigates sampled frame evidence", async () => {
    mocks.getAnalysisStatus.mockResolvedValue(analysisJob);
    mocks.getAnalysisResults.mockResolvedValue(analysisResults);
    mocks.getAnalysisFrames.mockResolvedValue(evidenceFrames);
    mocks.getVideo.mockResolvedValue(video);
    mocks.createVideoStreamSession.mockResolvedValue(undefined);
    render(
      <AnalysisResultsView
        accessToken="operator-token"
        analysisId={analysisId}
        expiresInSeconds={900}
      />,
    );

    expect(await screen.findByText("45")).toBeInTheDocument();
    expect(screen.getByText("north-road.mp4")).toBeInTheDocument();
    expect(screen.getByText("Potential close tracked interaction; operator review required.")).toBeInTheDocument();
    expect(screen.getAllByText("Needs human review").length).toBeGreaterThan(0);
    expect(screen.getAllByText("UNKNOWN")).toHaveLength(3);
    expect(screen.getByText("Not configured")).toBeInTheDocument();
    expect(
      screen.getByText("No trained accident-classifier checkpoint is configured."),
    ).toBeInTheDocument();
    expect(screen.getByText("1.60 frames/s")).toBeInTheDocument();
    expect(
      screen.getByText(/The available model detects objects, not accident events/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/no human confirmation or medical assessment is recorded/i),
    ).toBeInTheDocument();
    expect(await screen.findByText("Frame 12 · 0:01.200")).toBeInTheDocument();
    expect(screen.getByText("Track 7")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Candidate 2/ }));
    expect(
      await screen.findByText(/Pipeline verification classification/),
    ).toBeInTheDocument();
    expect(await screen.findByText("Frame 52 · 0:05.200")).toBeInTheDocument();
    expect(screen.getAllByText("Needs human review").length).toBeGreaterThan(0);
    expect(screen.queryByText("Verified detection")).not.toBeInTheDocument();
    expect(mocks.getAnalysisFrames).toHaveBeenCalledWith(
      "operator-token",
      analysisId,
      0,
      100,
    );
    expect(mocks.createVideoStreamSession).toHaveBeenCalledWith(
      "operator-token",
      900,
    );
  });

  it("reports analysis API errors and can retry result loading", async () => {
    mocks.getAnalysisStatus.mockResolvedValue(analysisJob);
    mocks.getAnalysisResults
      .mockRejectedValueOnce(
        new ApiError("You do not have permission to access this resource.", 403),
      )
      .mockResolvedValueOnce(analysisResults);
    mocks.getVideo.mockResolvedValue(video);
    mocks.createVideoStreamSession.mockResolvedValue(undefined);
    render(
      <AnalysisResultsView
        accessToken="pending-token"
        analysisId={analysisId}
        expiresInSeconds={900}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your account is not authorized to review analysis results.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "Candidate review" }),
    ).toBeInTheDocument();
  });

  it("reports evidence-frame API errors and retries the selected candidate page", async () => {
    mocks.getAnalysisStatus.mockResolvedValue(analysisJob);
    mocks.getAnalysisResults.mockResolvedValue(analysisResults);
    mocks.getAnalysisFrames
      .mockRejectedValueOnce(
        new ApiError("Frame evidence is not available.", 403),
      )
      .mockResolvedValueOnce(evidenceFrames);
    mocks.getVideo.mockResolvedValue(video);
    mocks.createVideoStreamSession.mockResolvedValue(undefined);
    render(
      <AnalysisResultsView
        accessToken="operator-token"
        analysisId={analysisId}
        expiresInSeconds={900}
      />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your account is not authorized to review analysis results.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry evidence" }));
    expect(await screen.findByText("Frame 12 · 0:01.200")).toBeInTheDocument();
    expect(mocks.getAnalysisFrames).toHaveBeenCalledTimes(2);
  });

  it("shows a real empty state when analysis completed without candidates", async () => {
    mocks.getAnalysisStatus.mockResolvedValue(analysisJob);
    mocks.getAnalysisResults.mockResolvedValue({
      ...analysisResults,
      summary: { ...analysisResults.summary, candidate_count: 0 },
      candidates: [],
    });
    mocks.getVideo.mockResolvedValue(video);
    mocks.createVideoStreamSession.mockResolvedValue(undefined);
    render(
      <AnalysisResultsView
        accessToken="operator-token"
        analysisId={analysisId}
        expiresInSeconds={900}
      />,
    );

    expect(await screen.findByText("No candidates were returned")).toBeInTheDocument();
    expect(screen.getByText(/No incident has been inferred/)).toBeInTheDocument();
  });
});

describe("video metadata helpers", () => {
  it("filters by name and status and formats duration", () => {
    expect(filterVideos([video], "NORTH", "uploaded")).toHaveLength(1);
    expect(filterVideos([video], "NORTH", "failed")).toHaveLength(0);
    expect(formatDuration(3661)).toBe("1:01:01");
  });
});
