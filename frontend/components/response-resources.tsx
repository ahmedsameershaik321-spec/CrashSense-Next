"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Hospital,
  LoaderCircle,
  MapPin,
  Plus,
  RefreshCw,
  Save,
  ShieldAlert,
} from "lucide-react";
import {
  ApiError,
  assignVideoCamera,
  getNearbyResources,
  getVideoLocation,
  listCameras,
  registerCamera,
  type AccidentCandidate,
  type Camera,
  type NearbyResource,
  type VideoLocation,
} from "@/lib/api";
import { ResourceMap } from "@/components/resource-map";

interface ResponseResourcesProps {
  accessToken: string;
  videoId: string;
  candidate: AccidentCandidate | null;
  isAdministrator: boolean;
}

function errorMessage(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 401) {
      return "Your session has expired. Sign in again to view location resources.";
    }
    if (reason.status === 403) {
      return "Your account is not authorized to manage camera locations.";
    }
    return reason.message;
  }
  return "The location information could not be loaded. Check the connection and retry.";
}

function resourceLabel(resource: NearbyResource): string {
  return resource.resource_type.replaceAll("_", " ");
}

export function ResponseResources({
  accessToken,
  videoId,
  candidate,
  isAdministrator,
}: ResponseResourcesProps) {
  const [location, setLocation] = useState<VideoLocation | null>(null);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState("");
  const [resources, setResources] = useState<NearbyResource[]>([]);
  const [resourceSource, setResourceSource] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [resourceLoading, setResourceLoading] = useState(false);
  const [error, setError] = useState("");
  const [cameraError, setCameraError] = useState("");
  const [resourceError, setResourceError] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [cameraName, setCameraName] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [address, setAddress] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);

  const loadLocation = useCallback(async (isActive: () => boolean) => {
    setLoading(true);
    setError("");
    setCameraError("");
    setResourceError("");
    setNotice("");
    setResources([]);
    setResourceSource("");
    setSourceUrl("");

    const [locationResult, camerasResult] = await Promise.allSettled([
      getVideoLocation(accessToken, videoId),
      isAdministrator ? listCameras(accessToken) : Promise.resolve([]),
    ]);

    if (!isActive()) {
      return;
    }

    if (locationResult.status === "rejected") {
      setLocation(null);
      setError(errorMessage(locationResult.reason));
      setLoading(false);
      return;
    }

    const videoLocation = locationResult.value;
    setLocation(videoLocation);
    setSelectedCameraId(videoLocation.camera?.id ?? "");
    if (camerasResult.status === "fulfilled") {
      setCameras(camerasResult.value);
    } else {
      setCameraError(errorMessage(camerasResult.reason));
    }
    setLoading(false);

    if (videoLocation.camera) {
      setResourceLoading(true);
      try {
        const nearby = await getNearbyResources(accessToken, videoId);
        if (isActive()) {
          setResources(nearby.resources);
          setResourceSource(nearby.attribution);
          setSourceUrl(nearby.source_url);
        }
      } catch (reason) {
        if (isActive()) {
          setResourceError(
            reason instanceof ApiError
              ? reason.message
              : "Nearby resources could not be retrieved. Retry the lookup.",
          );
        }
      } finally {
        if (isActive()) {
          setResourceLoading(false);
        }
      }
    }
  }, [accessToken, isAdministrator, videoId]);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void loadLocation(() => active);
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [loadLocation, refreshVersion]);

  const refresh = () => setRefreshVersion((current) => current + 1);

  const handleAssignCamera = async () => {
    setSaving(true);
    setNotice("");
    setCameraError("");
    try {
      const updated = await assignVideoCamera(
        accessToken,
        videoId,
        selectedCameraId || null,
      );
      setLocation(updated);
      setNotice(
        updated.camera
          ? "Camera location assigned. Nearby resources are sorted by distance."
          : "Camera location removed from this video.",
      );
      refresh();
    } catch (reason) {
      setCameraError(errorMessage(reason));
    } finally {
      setSaving(false);
    }
  };

  const handleRegisterCamera = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsedLatitude = Number(latitude);
    const parsedLongitude = Number(longitude);
    if (
      !cameraName.trim() ||
      !Number.isFinite(parsedLatitude) ||
      !Number.isFinite(parsedLongitude) ||
      parsedLatitude < -90 ||
      parsedLatitude > 90 ||
      parsedLongitude < -180 ||
      parsedLongitude > 180
    ) {
      setCameraError("Enter a camera name and valid latitude and longitude.");
      return;
    }

    setSaving(true);
    setCameraError("");
    setNotice("");
    try {
      const createdCamera = await registerCamera(accessToken, {
        name: cameraName.trim(),
        latitude: parsedLatitude,
        longitude: parsedLongitude,
        address: address.trim() || undefined,
      });
      setCameras((current) =>
        [...current, createdCamera].sort((first, second) =>
          first.name.localeCompare(second.name),
        ),
      );
      setSelectedCameraId(createdCamera.id);
      setCameraName("");
      setLatitude("");
      setLongitude("");
      setAddress("");
      try {
        await assignVideoCamera(accessToken, videoId, createdCamera.id);
        setNotice("Camera registered and assigned to this video.");
        refresh();
      } catch (reason) {
        setCameraError(
          `Camera registered, but it could not be assigned to this video: ${errorMessage(reason)}`,
        );
      }
    } catch (reason) {
      setCameraError(errorMessage(reason));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      aria-labelledby="response-resources-title"
      className="rounded-xl border border-line bg-panel p-4 sm:p-5"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-blue-700">
            <MapPin aria-hidden="true" className="h-4 w-4" />
            Location & response resources
          </p>
          <h2
            className="mt-2 text-base font-semibold text-slate-900"
            id="response-resources-title"
          >
            Approximate scene location
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-600">
            A registered camera location is only a scene-location proxy. It is
            not GPS extracted from the video or a verified point of impact.
          </p>
        </div>
        <button
          aria-label="Refresh location and resources"
          className="inline-flex w-fit items-center gap-2 rounded-lg border border-line px-3 py-2 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          disabled={loading || resourceLoading}
          onClick={refresh}
          type="button"
        >
          <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="mt-5 flex items-center gap-2 text-xs text-slate-600" role="status">
          <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
          Loading registered camera location…
        </div>
      ) : error ? (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3">
          <p className="flex items-center gap-2 text-xs text-rose-700" role="alert">
            <AlertCircle aria-hidden="true" className="h-4 w-4 shrink-0" />
            {error}
          </p>
          <button
            className="rounded-md border border-line px-3 py-1.5 text-xs text-slate-700"
            onClick={refresh}
            type="button"
          >
            Retry
          </button>
        </div>
      ) : location?.camera ? (
        <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(260px,0.8fr)]">
          <div className="min-w-0">
            <ResourceMap
              cameraName={location.camera.name}
              candidateLabel={
                candidate
                  ? `Selected candidate ${candidate.start_timestamp_seconds.toFixed(2)}–${candidate.end_timestamp_seconds.toFixed(2)}s`
                  : "Analysis scene location, approximate camera proxy"
              }
              latitude={location.camera.latitude}
              longitude={location.camera.longitude}
              resources={resources}
            />
            <p className="mt-2 text-[10px] leading-4 text-slate-500">
              Map tiles and the nearby search use OpenStreetMap public services.
              Camera coordinates are shared with the resource lookup. Resource
              coverage may be incomplete or out of date.
            </p>
          </div>
          <div className="space-y-3">
            <div className="rounded-lg border border-line bg-slate-50 p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Registered camera
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {location.camera.name}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                {location.camera.address || "No address recorded"}
              </p>
              <p className="mt-2 font-mono text-[10px] text-slate-500">
                {location.camera.latitude.toFixed(5)},{" "}
                {location.camera.longitude.toFixed(5)}
              </p>
            </div>
            <div className="flex items-center justify-between gap-3">
              <h3 className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                <Hospital aria-hidden="true" className="h-4 w-4 text-emerald-800" />
                Nearby mapped resources
              </h3>
              {sourceUrl && (
                <a
                  className="inline-flex items-center gap-1 text-[10px] text-blue-700 hover:text-slate-900"
                  href={sourceUrl}
                  rel="noreferrer"
                  target="_blank"
                >
                  {resourceSource || "OpenStreetMap"}
                  <ExternalLink aria-hidden="true" className="h-3 w-3" />
                </a>
              )}
            </div>
            {resourceLoading ? (
              <p className="flex items-center gap-2 text-xs text-slate-600" role="status">
                <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
                Searching mapped resources…
              </p>
            ) : resourceError ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                <p className="text-xs text-amber-800" role="alert">{resourceError}</p>
                <button
                  className="mt-2 rounded-md border border-line px-3 py-1.5 text-[10px] text-slate-700"
                  onClick={() => setRefreshVersion((current) => current + 1)}
                  type="button"
                >
                  Retry nearby search
                </button>
              </div>
            ) : resources.length === 0 ? (
              <p className="rounded-lg border border-line bg-slate-50 p-3 text-xs text-slate-500">
                No hospitals, clinics, ambulance stations, or fire stations were
                returned in the searched radius.
              </p>
            ) : (
              <ol aria-label="Nearby emergency resources, ordered by distance" className="max-h-80 space-y-2 overflow-auto">
                {resources.map((resource, index) => (
                  <li
                    className="rounded-lg border border-line bg-slate-50 p-3"
                    key={`${resource.osm_type}-${resource.osm_id}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-slate-900">
                          {index + 1}. {resource.name}
                        </p>
                        <p className="mt-1 text-[10px] capitalize text-slate-500">
                          {resourceLabel(resource)}
                        </p>
                      </div>
                      <span className="shrink-0 font-mono text-[10px] text-emerald-800">
                        {(resource.distance_meters / 1000).toFixed(2)} km
                      </span>
                    </div>
                    {resource.address && (
                      <p className="mt-2 text-[10px] text-slate-500">{resource.address}</p>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-5 rounded-lg border border-dashed border-line bg-slate-50 p-4">
          <p className="text-sm font-medium text-slate-700">
            No active camera location is assigned
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Nearby-resource search requires an administrator-registered camera.
            No incident coordinates can be inferred from this video.
          </p>
        </div>
      )}

      {notice && (
        <p className="mt-4 flex items-center gap-2 text-xs text-emerald-800" role="status">
          <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
          {notice}
        </p>
      )}
      {cameraError && (
        <p className="mt-4 flex items-center gap-2 text-xs text-rose-700" role="alert">
          <AlertCircle aria-hidden="true" className="h-4 w-4" />
          {cameraError}
        </p>
      )}

      {isAdministrator && (
        <div className="mt-5 border-t border-line pt-4">
          <h3 className="text-xs font-semibold text-slate-700">
            Administrator camera assignment
          </h3>
          {cameras.length > 0 && (
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <label className="sr-only" htmlFor="camera-assignment">
                Select a registered camera
              </label>
              <select
                className="field-input sm:max-w-sm"
                id="camera-assignment"
                onChange={(event) => setSelectedCameraId(event.target.value)}
                value={selectedCameraId}
              >
                <option value="">No camera assigned</option>
                {cameras.map((camera) => (
                  <option key={camera.id} value={camera.id}>
                    {camera.name}
                  </option>
                ))}
              </select>
              <button
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-line px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                disabled={saving || selectedCameraId === (location?.camera?.id ?? "")}
                onClick={() => void handleAssignCamera()}
                type="button"
              >
                {saving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save assignment
              </button>
            </div>
          )}
          {cameraError && !cameras.length && (
            <p className="mt-2 text-xs text-amber-800">{cameraError}</p>
          )}
          <details className="mt-4 rounded-lg border border-line bg-slate-50 p-3">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-medium text-slate-600">
              <Plus aria-hidden="true" className="h-4 w-4" />
              Register a camera location
            </summary>
            <form
              className="mt-3 grid gap-3 sm:grid-cols-2"
              onSubmit={(event) => void handleRegisterCamera(event)}
            >
              <label className="text-[10px] text-slate-600">
                Camera name
                <input
                  className="field-input mt-1"
                  maxLength={120}
                  onChange={(event) => setCameraName(event.target.value)}
                  required
                  value={cameraName}
                />
              </label>
              <label className="text-[10px] text-slate-600">
                Address (optional)
                <input
                  className="field-input mt-1"
                  maxLength={500}
                  onChange={(event) => setAddress(event.target.value)}
                  value={address}
                />
              </label>
              <label className="text-[10px] text-slate-600">
                Latitude
                <input
                  className="field-input mt-1"
                  max={90}
                  min={-90}
                  onChange={(event) => setLatitude(event.target.value)}
                  required
                  step="any"
                  type="number"
                  value={latitude}
                />
              </label>
              <label className="text-[10px] text-slate-600">
                Longitude
                <input
                  className="field-input mt-1"
                  max={180}
                  min={-180}
                  onChange={(event) => setLongitude(event.target.value)}
                  required
                  step="any"
                  type="number"
                  value={longitude}
                />
              </label>
              <button
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent-strong px-3 py-2 text-xs font-semibold text-white hover:bg-sky-500 disabled:opacity-50 sm:col-span-2 sm:w-fit"
                disabled={saving}
                type="submit"
              >
                {saving ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Register and assign camera
              </button>
            </form>
          </details>
          {cameraError && (
            <p className="mt-3 text-xs text-rose-700" role="alert">{cameraError}</p>
          )}
        </div>
      )}
      <p className="mt-4 flex items-start gap-2 border-t border-line pt-3 text-[10px] leading-4 text-amber-800">
        <ShieldAlert aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        This is reference information only—not an emergency dispatch or a
        guarantee of service availability.
      </p>
    </section>
  );
}
