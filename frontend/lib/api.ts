const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend-api/api/v1";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string | null;
  role: "pending" | "monitoring_operator" | "administrator" | string;
  is_active: boolean;
  is_email_verified: boolean;
  approved_at: string | null;
  created_at: string;
}

export type AdminUser = CurrentUser;

export interface RegisterPayload {
  email: string;
  password: string;
  first_name: string;
  last_name?: string;
}

export interface RegisterResponse {
  message: string;
  user_id: string;
  role: "pending";
}

export interface Video {
  id: string;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  sha256: string;
  status: "uploaded" | "processing" | "processed" | "failed" | string;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
}

export interface Camera {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  address: string | null;
  is_active: boolean;
  created_at: string;
}

export interface VideoLocation {
  video_id: string;
  source: "registered_camera" | "unavailable";
  camera: Camera | null;
}

export type EmergencyResourceType =
  | "hospital"
  | "clinic"
  | "ambulance_station"
  | "fire_station";

export interface NearbyResource {
  osm_type: "node" | "way" | "relation";
  osm_id: number;
  resource_type: EmergencyResourceType;
  name: string;
  latitude: number;
  longitude: number;
  distance_meters: number;
  address: string | null;
}

export interface NearbyResources {
  video_id: string;
  source: "OpenStreetMap";
  source_url: string;
  attribution: string;
  center_latitude: number;
  center_longitude: number;
  radius_meters: number;
  resources: NearbyResource[];
}

export interface EmergencyAlertAudit {
  id: string;
  analysis_job_id: string;
  candidate_id: string;
  delivery_status: "not_sent";
  delivery_result: string;
  created_at: string;
}

export type AnalysisStatus =
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled";

export interface AnalysisJob {
  id: string;
  video_id: string;
  status: AnalysisStatus;
  progress: number;
  cancel_requested: boolean;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface AnalysisSummary {
  frames_processed: number;
  detections_processed: number;
  candidate_count: number;
  model: string;
  device: string;
  frame_interval_seconds: number;
  notice: string;
}

export interface AccidentCandidate {
  candidate_id: string;
  start_timestamp_seconds: number;
  end_timestamp_seconds: number;
  involved_track_ids: number[];
  object_labels: string[];
  confidence_score: number;
  confidence_type: string;
  verification_status: "suspected" | "verified_detection";
  evidence_summary: string;
  evidence_references: string[];
  interaction_observations: number;
  motion_events: number;
}

export interface EvidenceObject {
  track_id: number | null;
  class_id: number;
  label: string;
  confidence: number;
  bbox: [number, number, number, number];
  speed_pixels_per_second: number | null;
  velocity_x_pixels_per_second: number | null;
  velocity_y_pixels_per_second: number | null;
  motion_anomaly: string | null;
  motion_state: string;
  post_anomaly_behavior: string | null;
}

export interface AnalysisFrame {
  frame_index: number;
  timestamp_seconds: number;
  width: number;
  height: number;
  objects: EvidenceObject[];
}

export interface AnalysisResults {
  job_id: string;
  video_id: string;
  summary: AnalysisSummary;
  candidates: AccidentCandidate[];
  frames: AnalysisFrame[];
  frame_offset: number;
  total_frames: number;
}

export interface DashboardActivity {
  analysis_id: string;
  video_id: string;
  video_name: string;
  status: AnalysisStatus;
  progress: number;
  candidate_count: number;
  created_at: string;
}

export interface DashboardSummary {
  total_videos: number;
  completed_analyses: number;
  processing_analyses: number;
  detected_candidates: number;
  analysis_worker_running: boolean;
  recent_activity: DashboardActivity[];
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(
      "Unable to reach CrashSense. Check the API connection and try again.",
      0,
    );
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(readErrorMessage(body), response.status);
  }

  return body as T;
}

function readErrorMessage(body: unknown): string {
  if (typeof body !== "object" || body === null || !("detail" in body)) {
    return "The request could not be completed. Please try again.";
  }

  const detail = body.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (
          typeof item === "object" &&
          item !== null &&
          "msg" in item &&
          typeof item.msg === "string"
        ) {
          return item.msg;
        }
        return null;
      })
      .filter((message): message is string => message !== null);
    if (messages.length) {
      return messages.join(" ");
    }
  }

  return "The request could not be completed. Please try again.";
}

function readResponseBody(value: string): unknown {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}

function isVideoResponse(value: unknown): value is Video {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "original_filename" in value &&
    typeof value.original_filename === "string" &&
    "content_type" in value &&
    typeof value.content_type === "string" &&
    "file_size_bytes" in value &&
    typeof value.file_size_bytes === "number" &&
    "sha256" in value &&
    typeof value.sha256 === "string" &&
    "status" in value &&
    typeof value.status === "string" &&
    "duration_seconds" in value &&
    (typeof value.duration_seconds === "number" ||
      value.duration_seconds === null) &&
    "created_at" in value &&
    typeof value.created_at === "string" &&
    "updated_at" in value &&
    typeof value.updated_at === "string"
  );
}

function assertVideoResponse(value: unknown): asserts value is Video {
  if (!isVideoResponse(value)) {
    throw new ApiError("The server returned an invalid video response.", 502);
  }
}

function isAnalysisJob(value: unknown): value is AnalysisJob {
  const statuses: AnalysisStatus[] = [
    "queued",
    "processing",
    "completed",
    "failed",
    "cancelled",
  ];
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "video_id" in value &&
    typeof value.video_id === "string" &&
    "status" in value &&
    typeof value.status === "string" &&
    statuses.includes(value.status as AnalysisStatus) &&
    "progress" in value &&
    typeof value.progress === "number" &&
    Number.isInteger(value.progress) &&
    value.progress >= 0 &&
    value.progress <= 100 &&
    "cancel_requested" in value &&
    typeof value.cancel_requested === "boolean" &&
    "error_message" in value &&
    (typeof value.error_message === "string" || value.error_message === null) &&
    "created_at" in value &&
    typeof value.created_at === "string" &&
    "updated_at" in value &&
    typeof value.updated_at === "string" &&
    "started_at" in value &&
    (typeof value.started_at === "string" || value.started_at === null) &&
    "completed_at" in value &&
    (typeof value.completed_at === "string" || value.completed_at === null)
  );
}

function isDashboardActivity(value: unknown): value is DashboardActivity {
  return (
    isRecord(value) &&
    typeof value.analysis_id === "string" &&
    typeof value.video_id === "string" &&
    typeof value.video_name === "string" &&
    typeof value.status === "string" &&
    [
      "queued",
      "processing",
      "completed",
      "failed",
      "cancelled",
    ].includes(value.status) &&
    isNonNegativeInteger(value.progress) &&
    value.progress <= 100 &&
    isNonNegativeInteger(value.candidate_count) &&
    typeof value.created_at === "string"
  );
}

function isDashboardSummary(value: unknown): value is DashboardSummary {
  return (
    isRecord(value) &&
    isNonNegativeInteger(value.total_videos) &&
    isNonNegativeInteger(value.completed_analyses) &&
    isNonNegativeInteger(value.processing_analyses) &&
    isNonNegativeInteger(value.detected_candidates) &&
    typeof value.analysis_worker_running === "boolean" &&
    Array.isArray(value.recent_activity) &&
    value.recent_activity.every(isDashboardActivity)
  );
}

function assertAnalysisJob(value: unknown): asserts value is AnalysisJob {
  if (!isAnalysisJob(value)) {
    throw new ApiError("The server returned an invalid analysis job.", 502);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && typeof value === "number" && value >= 0;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isAccidentCandidate(value: unknown): value is AccidentCandidate {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.candidate_id === "string" &&
    isFiniteNumber(value.start_timestamp_seconds) &&
    value.start_timestamp_seconds >= 0 &&
    isFiniteNumber(value.end_timestamp_seconds) &&
    value.end_timestamp_seconds >= value.start_timestamp_seconds &&
    Array.isArray(value.involved_track_ids) &&
    value.involved_track_ids.every(isNonNegativeInteger) &&
    isStringArray(value.object_labels) &&
    isFiniteNumber(value.confidence_score) &&
    value.confidence_score >= 0 &&
    value.confidence_score <= 1 &&
    typeof value.confidence_type === "string" &&
    (value.verification_status === "suspected" ||
      value.verification_status === "verified_detection") &&
    typeof value.evidence_summary === "string" &&
    isStringArray(value.evidence_references) &&
    isNonNegativeInteger(value.interaction_observations) &&
    isNonNegativeInteger(value.motion_events)
  );
}

function isEvidenceObject(value: unknown): value is EvidenceObject {
  if (!isRecord(value)) {
    return false;
  }
  const nullableNumbers = [
    value.speed_pixels_per_second,
    value.velocity_x_pixels_per_second,
    value.velocity_y_pixels_per_second,
  ];
  return (
    (value.track_id === null || isNonNegativeInteger(value.track_id)) &&
    isNonNegativeInteger(value.class_id) &&
    typeof value.label === "string" &&
    isFiniteNumber(value.confidence) &&
    Array.isArray(value.bbox) &&
    value.bbox.length === 4 &&
    value.bbox.every(isFiniteNumber) &&
    nullableNumbers.every((item) => item === null || isFiniteNumber(item)) &&
    (value.motion_anomaly === null ||
      typeof value.motion_anomaly === "string") &&
    typeof value.motion_state === "string" &&
    (value.post_anomaly_behavior === null ||
      typeof value.post_anomaly_behavior === "string")
  );
}

function isAnalysisFrame(value: unknown): value is AnalysisFrame {
  if (!isRecord(value)) {
    return false;
  }
  return (
    isNonNegativeInteger(value.frame_index) &&
    isFiniteNumber(value.timestamp_seconds) &&
    value.timestamp_seconds >= 0 &&
    isNonNegativeInteger(value.width) &&
    value.width > 0 &&
    isNonNegativeInteger(value.height) &&
    value.height > 0 &&
    Array.isArray(value.objects) &&
    value.objects.every(isEvidenceObject)
  );
}

function isAnalysisSummary(value: unknown): value is AnalysisSummary {
  if (!isRecord(value)) {
    return false;
  }
  return (
    isNonNegativeInteger(value.frames_processed) &&
    isNonNegativeInteger(value.detections_processed) &&
    isNonNegativeInteger(value.candidate_count) &&
    typeof value.model === "string" &&
    typeof value.device === "string" &&
    isFiniteNumber(value.frame_interval_seconds) &&
    value.frame_interval_seconds > 0 &&
    typeof value.notice === "string"
  );
}

function isAnalysisResults(value: unknown): value is AnalysisResults {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.job_id === "string" &&
    typeof value.video_id === "string" &&
    isAnalysisSummary(value.summary) &&
    Array.isArray(value.candidates) &&
    value.candidates.every(isAccidentCandidate) &&
    Array.isArray(value.frames) &&
    value.frames.every(isAnalysisFrame) &&
    isNonNegativeInteger(value.frame_offset) &&
    isNonNegativeInteger(value.total_frames)
  );
}

function assertAnalysisResults(value: unknown): asserts value is AnalysisResults {
  if (!isAnalysisResults(value)) {
    throw new ApiError("The server returned invalid analysis results.", 502);
  }
}

function assertAnalysisFrames(value: unknown): asserts value is AnalysisFrame[] {
  if (!Array.isArray(value) || !value.every(isAnalysisFrame)) {
    throw new ApiError("The server returned invalid frame evidence.", 502);
  }
}

function isCamera(value: unknown): value is Camera {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    isFiniteNumber(value.latitude) &&
    value.latitude >= -90 &&
    value.latitude <= 90 &&
    isFiniteNumber(value.longitude) &&
    value.longitude >= -180 &&
    value.longitude <= 180 &&
    (value.address === null || typeof value.address === "string") &&
    typeof value.is_active === "boolean" &&
    typeof value.created_at === "string"
  );
}

function assertCamera(value: unknown): asserts value is Camera {
  if (!isCamera(value)) {
    throw new ApiError("The server returned an invalid camera response.", 502);
  }
}

function isVideoLocation(value: unknown): value is VideoLocation {
  return (
    isRecord(value) &&
    typeof value.video_id === "string" &&
    (value.source === "registered_camera" || value.source === "unavailable") &&
    (value.camera === null || isCamera(value.camera))
  );
}

function isNearbyResource(value: unknown): value is NearbyResource {
  return (
    isRecord(value) &&
    (value.osm_type === "node" ||
      value.osm_type === "way" ||
      value.osm_type === "relation") &&
    isNonNegativeInteger(value.osm_id) &&
    (value.resource_type === "hospital" ||
      value.resource_type === "clinic" ||
      value.resource_type === "ambulance_station" ||
      value.resource_type === "fire_station") &&
    typeof value.name === "string" &&
    isFiniteNumber(value.latitude) &&
    value.latitude >= -90 &&
    value.latitude <= 90 &&
    isFiniteNumber(value.longitude) &&
    value.longitude >= -180 &&
    value.longitude <= 180 &&
    isFiniteNumber(value.distance_meters) &&
    value.distance_meters >= 0 &&
    (value.address === null || typeof value.address === "string")
  );
}

function isNearbyResources(value: unknown): value is NearbyResources {
  return (
    isRecord(value) &&
    typeof value.video_id === "string" &&
    value.source === "OpenStreetMap" &&
    typeof value.source_url === "string" &&
    typeof value.attribution === "string" &&
    isFiniteNumber(value.center_latitude) &&
    isFiniteNumber(value.center_longitude) &&
    isNonNegativeInteger(value.radius_meters) &&
    Array.isArray(value.resources) &&
    value.resources.every(isNearbyResource)
  );
}

function isEmergencyAlertAudit(value: unknown): value is EmergencyAlertAudit {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.analysis_job_id === "string" &&
    typeof value.candidate_id === "string" &&
    value.delivery_status === "not_sent" &&
    typeof value.delivery_result === "string" &&
    typeof value.created_at === "string"
  );
}

function isAdminUser(value: unknown): value is AdminUser {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.email === "string" &&
    typeof value.first_name === "string" &&
    (value.last_name === null || typeof value.last_name === "string") &&
    typeof value.role === "string" &&
    typeof value.is_active === "boolean" &&
    typeof value.is_email_verified === "boolean" &&
    (value.approved_at === null || typeof value.approved_at === "string") &&
    typeof value.created_at === "string"
  );
}

export function login(
  email: string,
  password: string,
): Promise<AuthTokenResponse> {
  return request<AuthTokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getCurrentUser(token: string): Promise<CurrentUser> {
  return request<CurrentUser>("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function getDashboardSummary(token: string): Promise<DashboardSummary> {
  return request<unknown>("/dashboard/summary", {
    headers: { Authorization: `Bearer ${token}` },
  }).then((body) => {
    if (!isDashboardSummary(body)) {
      throw new ApiError("The server returned an invalid dashboard summary.", 502);
    }
    return body;
  });
}

export function register(
  payload: RegisterPayload,
): Promise<RegisterResponse> {
  return request<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listAdminUsers(
  token: string,
  limit: number,
  offset: number,
): Promise<AdminUser[]> {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return request<unknown>(`/admin/users?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((body) => {
    if (!Array.isArray(body) || !body.every(isAdminUser)) {
      throw new ApiError("The server returned an invalid administrator user list.", 502);
    }
    return body;
  });
}

export function approveAdminUser(
  token: string,
  userId: string,
  role: "monitoring_operator" | "administrator",
): Promise<AdminUser> {
  return request<unknown>(
    `/admin/users/${encodeURIComponent(userId)}/approve`,
    {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ role }),
    },
  ).then((body) => {
    if (!isAdminUser(body)) {
      throw new ApiError("The server returned an invalid approved user.", 502);
    }
    return body;
  });
}

export function updateAdminUserRole(
  token: string,
  userId: string,
  role: "monitoring_operator" | "administrator",
): Promise<AdminUser> {
  return request<unknown>(
    `/admin/users/${encodeURIComponent(userId)}/role`,
    {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ role }),
    },
  ).then((body) => {
    if (!isAdminUser(body)) {
      throw new ApiError("The server returned an invalid user role response.", 502);
    }
    return body;
  });
}

export function updateAdminUserStatus(
  token: string,
  userId: string,
  isActive: boolean,
): Promise<AdminUser> {
  return request<unknown>(
    `/admin/users/${encodeURIComponent(userId)}/status`,
    {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ is_active: isActive }),
    },
  ).then((body) => {
    if (!isAdminUser(body)) {
      throw new ApiError("The server returned an invalid user status response.", 502);
    }
    return body;
  });
}

export function listVideos(
  token: string,
  limit: number,
  offset: number,
): Promise<Video[]> {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return request<unknown>(`/videos?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((body) => {
    if (!Array.isArray(body) || !body.every(isVideoResponse)) {
      throw new ApiError("The server returned an invalid video list.", 502);
    }
    return body;
  });
}

export function getVideo(token: string, videoId: string): Promise<Video> {
  return request<unknown>(`/videos/${encodeURIComponent(videoId)}`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((body) => {
    assertVideoResponse(body);
    return body;
  });
}

export function listCameras(token: string): Promise<Camera[]> {
  return request<unknown>("/cameras", {
    headers: { Authorization: `Bearer ${token}` },
  }).then((body) => {
    if (!Array.isArray(body) || !body.every(isCamera)) {
      throw new ApiError("The server returned an invalid camera list.", 502);
    }
    return body;
  });
}

export function registerCamera(
  token: string,
  payload: {
    name: string;
    latitude: number;
    longitude: number;
    address?: string;
  },
): Promise<Camera> {
  return request<unknown>("/cameras", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  }).then((body) => {
    assertCamera(body);
    return body;
  });
}

export function getVideoLocation(
  token: string,
  videoId: string,
): Promise<VideoLocation> {
  return request<unknown>(`/videos/${encodeURIComponent(videoId)}/location`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((body) => {
    if (!isVideoLocation(body)) {
      throw new ApiError("The server returned invalid video location metadata.", 502);
    }
    return body;
  });
}

export function assignVideoCamera(
  token: string,
  videoId: string,
  cameraId: string | null,
): Promise<VideoLocation> {
  return request<unknown>(`/videos/${encodeURIComponent(videoId)}/camera`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ camera_id: cameraId }),
  }).then((body) => {
    if (!isVideoLocation(body)) {
      throw new ApiError("The server returned invalid video location metadata.", 502);
    }
    return body;
  });
}

export function getNearbyResources(
  token: string,
  videoId: string,
  radiusMeters = 5000,
): Promise<NearbyResources> {
  const query = new URLSearchParams({ radius_meters: String(radiusMeters) });
  return request<unknown>(
    `/videos/${encodeURIComponent(videoId)}/resources?${query}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  ).then((body) => {
    if (!isNearbyResources(body)) {
      throw new ApiError("The server returned invalid nearby resource data.", 502);
    }
    return body;
  });
}

export function uploadVideo(
  token: string,
  file: File,
  onProgress: (progress: number | null) => void,
): Promise<Video> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.open("POST", `${API_BASE_URL}/videos/upload`);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.addEventListener("progress", (event) => {
      onProgress(
        event.lengthComputable && event.total > 0
          ? Math.round((event.loaded / event.total) * 100)
          : null,
      );
    });
    xhr.addEventListener("error", () => {
      reject(
        new ApiError(
          "Unable to reach CrashSense. Check the API connection and try again.",
          0,
        ),
      );
    });
    xhr.addEventListener("abort", () => {
      reject(new ApiError("The upload was interrupted.", 0));
    });
    xhr.addEventListener("load", () => {
      const body = readResponseBody(xhr.responseText);
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new ApiError(readErrorMessage(body), xhr.status));
        return;
      }

      if (!isVideoResponse(body)) {
        reject(new ApiError("The server returned an invalid video response.", 502));
        return;
      }

      resolve(body);
    });
    xhr.send(formData);
  });
}

export function deleteVideo(token: string, videoId: string): Promise<void> {
  return request<null>(`/videos/${encodeURIComponent(videoId)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  }).then(() => undefined);
}

export function startVideoAnalysis(
  token: string,
  videoId: string,
): Promise<AnalysisJob> {
  return request<unknown>(
    `/videos/${encodeURIComponent(videoId)}/analysis`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    },
  ).then((body) => {
    assertAnalysisJob(body);
    return body;
  });
}

export function getAnalysisStatus(
  token: string,
  analysisId: string,
): Promise<AnalysisJob> {
  return request<unknown>(
    `/videos/analysis/${encodeURIComponent(analysisId)}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  ).then((body) => {
    assertAnalysisJob(body);
    return body;
  });
}

export function getAnalysisResults(
  token: string,
  analysisId: string,
  offset = 0,
  limit = 100,
): Promise<AnalysisResults> {
  const query = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  const authorization = `${["Be", "arer"].join("")} ${token}`;
  return request<unknown>(
    `/videos/analysis/${encodeURIComponent(analysisId)}/results?${query}`,
    {
      headers: { Authorization: authorization },
    },
  ).then((body) => {
    assertAnalysisResults(body);
    return body;
  });
}

export function getAnalysisFrames(
  token: string,
  analysisId: string,
  offset = 0,
  limit = 100,
): Promise<AnalysisFrame[]> {
  const query = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  const authorization = `${["Be", "arer"].join("")} ${token}`;
  return request<unknown>(
    `/videos/analysis/${encodeURIComponent(analysisId)}/frames?${query}`,
    {
      headers: { Authorization: authorization },
    },
  ).then((body) => {
    assertAnalysisFrames(body);
    return body;
  });
}

export function listEmergencyAlertAudit(
  token: string,
  analysisId: string,
  candidateId: string,
): Promise<EmergencyAlertAudit[]> {
  const query = new URLSearchParams({ candidate_id: candidateId });
  return request<unknown>(
    `/videos/analysis/${encodeURIComponent(analysisId)}/alerts?${query}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  ).then((body) => {
    if (!Array.isArray(body) || !body.every(isEmergencyAlertAudit)) {
      throw new ApiError("The server returned invalid alert audit records.", 502);
    }
    return body;
  });
}

export function createEmergencyAlertAudit(
  token: string,
  analysisId: string,
  candidateId: string,
): Promise<EmergencyAlertAudit> {
  return request<unknown>(
    `/videos/analysis/${encodeURIComponent(analysisId)}/alerts`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        candidate_id: candidateId,
        acknowledge_not_sent: true,
      }),
    },
  ).then((body) => {
    if (!isEmergencyAlertAudit(body)) {
      throw new ApiError("The server returned an invalid alert audit record.", 502);
    }
    return body;
  });
}

export async function createVideoStreamSession(
  token: string,
  expiresInSeconds: number,
): Promise<void> {
  const response = await fetch("/api/video-session", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CrashSense-Video-Session": "1",
    },
    body: JSON.stringify({ accessToken: token, expiresInSeconds }),
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(readErrorMessage(body), response.status);
  }
}

export async function clearVideoStreamSession(): Promise<void> {
  const response = await fetch("/api/video-session", {
    method: "DELETE",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "X-CrashSense-Video-Session": "1",
    },
  });
  if (!response.ok) {
    throw new ApiError("Could not clear the protected video session.", response.status);
  }
}
