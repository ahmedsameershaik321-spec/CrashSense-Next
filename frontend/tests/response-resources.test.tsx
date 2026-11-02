import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AlertAuditPanel } from "@/components/alert-audit-panel";
import { ResponseResources } from "@/components/response-resources";
import {
  ApiError,
  type Camera,
  type EmergencyAlertAudit,
  type NearbyResources,
  type VideoLocation,
} from "@/lib/api";

const mocks = vi.hoisted(() => ({
  assignVideoCamera: vi.fn(),
  createEmergencyAlertAudit: vi.fn(),
  getNearbyResources: vi.fn(),
  getVideoLocation: vi.fn(),
  listCameras: vi.fn(),
  listEmergencyAlertAudit: vi.fn(),
  registerCamera: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    assignVideoCamera: mocks.assignVideoCamera,
    createEmergencyAlertAudit: mocks.createEmergencyAlertAudit,
    getNearbyResources: mocks.getNearbyResources,
    getVideoLocation: mocks.getVideoLocation,
    listCameras: mocks.listCameras,
    listEmergencyAlertAudit: mocks.listEmergencyAlertAudit,
    registerCamera: mocks.registerCamera,
  };
});

vi.mock("@/components/resource-map", () => ({
  ResourceMap: () => <div aria-label="Location map" role="img" />,
}));

const camera: Camera = {
  id: "camera-1",
  name: "North Junction",
  latitude: 51.5072,
  longitude: -0.1276,
  address: "Westminster, London",
  is_active: true,
  created_at: "2026-10-30T12:00:00Z",
};
const assignedLocation: VideoLocation = {
  video_id: "video-1",
  source: "registered_camera",
  camera,
};
const resources: NearbyResources = {
  video_id: "video-1",
  source: "OpenStreetMap",
  source_url: "https://www.openstreetmap.org/",
  attribution: "© OpenStreetMap contributors",
  center_latitude: camera.latitude,
  center_longitude: camera.longitude,
  radius_meters: 5000,
  resources: [
    {
      osm_type: "node",
      osm_id: 1,
      resource_type: "ambulance_station",
      name: "Nearest ambulance station",
      latitude: 51.508,
      longitude: -0.127,
      distance_meters: 125,
      address: null,
    },
    {
      osm_type: "way",
      osm_id: 2,
      resource_type: "hospital",
      name: "City hospital",
      latitude: 51.51,
      longitude: -0.13,
      distance_meters: 650,
      address: "Main Road",
    },
  ],
};
const candidate = {
  candidate_id: "tracks:1:2:episode:1",
  start_timestamp_seconds: 1.5,
  end_timestamp_seconds: 3.25,
  involved_track_ids: [1, 2],
  object_labels: ["car"],
  confidence_score: 0.6,
  confidence_type: "heuristic_temporal_evidence_score",
  verification_status: "suspected" as const,
  evidence_summary: "Review required.",
  evidence_references: [],
  interaction_observations: 2,
  motion_events: 1,
};
const auditRecord: EmergencyAlertAudit = {
  id: "audit-1",
  analysis_job_id: "analysis-1",
  candidate_id: candidate.candidate_id,
  delivery_status: "not_sent",
  delivery_result: "External delivery is disabled; this is an audit-only record.",
  created_at: "2026-10-30T12:00:00Z",
};

beforeEach(() => {
  mocks.assignVideoCamera.mockReset();
  mocks.createEmergencyAlertAudit.mockReset();
  mocks.getNearbyResources.mockReset();
  mocks.getVideoLocation.mockReset();
  mocks.listCameras.mockReset();
  mocks.listEmergencyAlertAudit.mockReset();
  mocks.registerCamera.mockReset();
});

afterEach(() => cleanup());

describe("incident location and emergency resources", () => {
  it("shows camera proxy and actual nearby resources in API distance order", async () => {
    mocks.getVideoLocation.mockResolvedValue(assignedLocation);
    mocks.getNearbyResources.mockResolvedValue(resources);
    render(
      <ResponseResources
        accessToken="operator-token"
        candidate={candidate}
        isAdministrator={false}
        videoId="video-1"
      />,
    );

    expect(await screen.findByText("North Junction")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Location map" })).toBeInTheDocument();
    expect(
      screen.getByText(/not GPS extracted from the video/i),
    ).toBeInTheDocument();
    const listedResources = await screen.findByRole("list", {
      name: "Nearby emergency resources, ordered by distance",
    });
    const names = Array.from(listedResources.querySelectorAll("li")).map(
      (item) => item.textContent,
    );
    expect(names[0]).toContain("Nearest ambulance station");
    expect(names[1]).toContain("City hospital");
    expect(mocks.getNearbyResources).toHaveBeenCalledWith(
      "operator-token",
      "video-1",
    );
  });

  it("does not imply a location or perform resource lookup without an assigned camera", async () => {
    mocks.getVideoLocation.mockResolvedValue({
      video_id: "video-1",
      source: "unavailable",
      camera: null,
    } satisfies VideoLocation);
    mocks.getNearbyResources.mockResolvedValue(resources);
    render(
      <ResponseResources
        accessToken="operator-token"
        candidate={null}
        isAdministrator={false}
        videoId="video-1"
      />,
    );

    expect(
      await screen.findByText("No active camera location is assigned"),
    ).toBeInTheDocument();
    expect(mocks.getNearbyResources).not.toHaveBeenCalled();
    expect(screen.queryByRole("img", { name: "Location map" })).not.toBeInTheDocument();
  });

  it("retries a failed OpenStreetMap lookup", async () => {
    mocks.getVideoLocation.mockResolvedValue(assignedLocation);
    mocks.getNearbyResources
      .mockRejectedValueOnce(new ApiError("Nearby OpenStreetMap resources are temporarily unavailable.", 503))
      .mockResolvedValueOnce(resources);
    render(
      <ResponseResources
        accessToken="operator-token"
        candidate={candidate}
        isAdministrator={false}
        videoId="video-1"
      />,
    );

    expect(
      await screen.findByText("Nearby OpenStreetMap resources are temporarily unavailable."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry nearby search" }));
    expect(await screen.findByText(/Nearest ambulance station/)).toBeInTheDocument();
    expect(mocks.getNearbyResources).toHaveBeenCalledTimes(2);
  });

  it("allows administrators to register and assign a camera", async () => {
    const unassigned: VideoLocation = {
      video_id: "video-1",
      source: "unavailable",
      camera: null,
    };
    mocks.getVideoLocation
      .mockResolvedValueOnce(unassigned)
      .mockResolvedValueOnce(assignedLocation);
    mocks.listCameras.mockResolvedValue([]);
    mocks.registerCamera.mockResolvedValue(camera);
    mocks.assignVideoCamera.mockResolvedValue(assignedLocation);
    mocks.getNearbyResources.mockResolvedValue(resources);
    render(
      <ResponseResources
        accessToken="admin-token"
        candidate={null}
        isAdministrator
        videoId="video-1"
      />,
    );

    fireEvent.click(
      await screen.findByText("Register a camera location"),
    );
    fireEvent.change(screen.getByLabelText("Camera name"), {
      target: { value: "North Junction" },
    });
    fireEvent.change(screen.getByLabelText("Address (optional)"), {
      target: { value: "Westminster, London" },
    });
    fireEvent.change(screen.getByLabelText("Latitude"), {
      target: { value: "51.5072" },
    });
    fireEvent.change(screen.getByLabelText("Longitude"), {
      target: { value: "-0.1276" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Register and assign camera" }));

    await waitFor(() => {
      expect(mocks.registerCamera).toHaveBeenCalledWith("admin-token", {
        name: "North Junction",
        latitude: 51.5072,
        longitude: -0.1276,
        address: "Westminster, London",
      });
      expect(mocks.assignVideoCamera).toHaveBeenCalledWith(
        "admin-token",
        "video-1",
        "camera-1",
      );
    });
  });
});

describe("audit-only notification status", () => {
  it("requires explicit acknowledgement and displays audit status as not sent", async () => {
    mocks.listEmergencyAlertAudit
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([auditRecord]);
    mocks.createEmergencyAlertAudit.mockResolvedValue(auditRecord);
    render(
      <AlertAuditPanel
        accessToken="operator-token"
        analysisId="analysis-1"
        candidateId={candidate.candidate_id}
      />,
    );

    const recordButton = await screen.findByRole("button", {
      name: "Record review (not sent)",
    });
    expect(recordButton).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(
        "I understand this action will not send or deliver a notification.",
      ),
    );
    expect(recordButton).toBeEnabled();
    fireEvent.click(recordButton);

    expect(await screen.findByText("Not sent")).toBeInTheDocument();
    expect(
      screen.getByText(/External delivery is disabled/),
    ).toBeInTheDocument();
    expect(mocks.createEmergencyAlertAudit).toHaveBeenCalledWith(
      "operator-token",
      "analysis-1",
      candidate.candidate_id,
    );
  });

  it("shows protected API errors and offers retry", async () => {
    mocks.listEmergencyAlertAudit
      .mockRejectedValueOnce(new ApiError("Not authorized.", 403))
      .mockResolvedValueOnce([]);
    render(
      <AlertAuditPanel
        accessToken="pending-token"
        analysisId="analysis-1"
        candidateId={candidate.candidate_id}
      />,
    );
    expect(
      await screen.findByText(
        "Your account is not authorized to view alert audit records.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry notification audit" }));
    await waitFor(() => {
      expect(mocks.listEmergencyAlertAudit).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText("No audit entries for this candidate.")).toBeInTheDocument();
  });
});
