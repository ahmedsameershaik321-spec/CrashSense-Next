import type { Video } from "@/lib/api";

const MAX_UPLOAD_SIZE_MB = Number(
  process.env.NEXT_PUBLIC_MAX_VIDEO_UPLOAD_SIZE_MB ?? "100",
);

if (!Number.isSafeInteger(MAX_UPLOAD_SIZE_MB) || MAX_UPLOAD_SIZE_MB < 1) {
  throw new Error("NEXT_PUBLIC_MAX_VIDEO_UPLOAD_SIZE_MB must be a positive integer.");
}

export const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;
export const MAX_UPLOAD_SIZE_LABEL = `${MAX_UPLOAD_SIZE_MB} MB`;

const ALLOWED_EXTENSIONS = new Set([".mp4", ".mov", ".avi", ".mkv"]);

export function validateVideoUpload(
  file: Pick<File, "name" | "size">,
): string | null {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_EXTENSIONS.has(extension)) {
    return "Choose an MP4, MOV, AVI, or MKV video.";
  }
  if (file.size <= 0) {
    return "The selected video is empty.";
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return `Video files must be ${MAX_UPLOAD_SIZE_LABEL} or smaller.`;
  }
  return null;
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "Unavailable";
  }
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) {
    return "Not available";
  }
  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const remainingSeconds = totalSeconds % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`
    : `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function formatVideoDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unavailable";
  }
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function filterVideos(
  videos: Video[],
  search: string,
  status: string,
): Video[] {
  const normalizedSearch = search.trim().toLocaleLowerCase();
  return videos.filter((video) => {
    const matchesSearch =
      !normalizedSearch ||
      video.original_filename.toLocaleLowerCase().includes(normalizedSearch);
    const matchesStatus = status === "all" || video.status === status;
    return matchesSearch && matchesStatus;
  });
}
