"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowLeft,
  CalendarDays,
  Clock3,
  FileVideo2,
  HardDrive,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  ApiError,
  createVideoStreamSession,
  deleteVideo,
  getVideo,
  type Video,
} from "@/lib/api";
import { LoadingState } from "@/components/loading-state";
import { VideoAnalysisPanel } from "@/components/video-analysis-panel";
import {
  formatDuration,
  formatFileSize,
  formatVideoDate,
} from "@/lib/videos";

interface VideoDetailsProps {
  accessToken: string;
  expiresInSeconds: number;
  userId: string;
  videoId: string;
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function VideoDetails({
  accessToken,
  expiresInSeconds,
  userId,
  videoId,
}: VideoDetailsProps) {
  const router = useRouter();
  const [video, setVideo] = useState<Video | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [streamReady, setStreamReady] = useState(false);
  const [streamError, setStreamError] = useState("");
  const [playerError, setPlayerError] = useState(false);
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        if (!UUID_PATTERN.test(videoId)) {
          throw new ApiError("The requested video could not be found.", 404);
        }
        const result = await getVideo(accessToken, videoId);
        if (!active) {
          return;
        }
        setVideo(result);
        setIsLoading(false);
        try {
          await createVideoStreamSession(accessToken, expiresInSeconds);
          if (active) {
            setStreamReady(true);
          }
        } catch (reason) {
          if (active) {
            setStreamError(
              reason instanceof ApiError
                ? reason.message
                : "Protected video playback could not be initialized.",
            );
          }
        }
      } catch (reason) {
        if (active) {
          setError(
            reason instanceof ApiError
              ? reason.message
              : "Video details could not be loaded.",
          );
          setIsLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [accessToken, expiresInSeconds, videoId]);

  async function confirmDelete() {
    if (isDeleting) {
      return;
    }
    setIsDeleting(true);
    setDeleteError("");
    try {
      await deleteVideo(accessToken, videoId);
      router.replace("/dashboard/videos");
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setDeleteError(
          "This video has an analysis queued or in progress and cannot be deleted yet.",
        );
      } else {
        setDeleteError(
          reason instanceof ApiError
            ? reason.message
            : "The video could not be deleted. Please try again.",
        );
      }
      setIsDeleting(false);
    }
  }

  if (isLoading) {
    return <LoadingState label="Loading video details" />;
  }

  if (error || !video) {
    return (
      <section className="rounded-xl border border-rose-300/15 bg-rose-300/[0.05] p-6" role="alert">
        <h1 className="text-lg font-semibold text-white">Video unavailable</h1>
        <p className="mt-2 text-sm text-rose-200">
          {error || "The requested video could not be found."}
        </p>
        <Link className="mt-5 inline-flex items-center gap-2 text-sm text-sky-200 hover:text-white" href="/dashboard/videos">
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
          Back to video library
        </Link>
      </section>
    );
  }

  const streamUrl = `/api/videos/${encodeURIComponent(video.id)}/stream`;

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <Link
            className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 transition hover:text-white"
            href="/dashboard/videos"
          >
            <ArrowLeft aria-hidden="true" className="h-4 w-4" />
            Video library
          </Link>
          <h1 className="mt-3 max-w-3xl break-words text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            {video.original_filename}
          </h1>
          <p className="mt-2 text-xs text-slate-500">
            Uploaded {formatVideoDate(video.created_at)}
          </p>
        </div>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-rose-300/15 bg-rose-300/[0.04] px-3.5 py-2.5 text-xs font-medium text-rose-200 transition hover:bg-rose-300/[0.09] disabled:opacity-50"
          onClick={() => {
            setDeleteError("");
            setShowDeleteConfirmation(true);
          }}
          type="button"
        >
          <Trash2 aria-hidden="true" className="h-4 w-4" />
          Delete video
        </button>
      </div>

      <section aria-label="Video player" className="overflow-hidden rounded-2xl border border-line bg-black">
        {streamReady ? (
          <video
            className="aspect-video max-h-[72vh] w-full bg-black"
            controls
            onError={() => setPlayerError(true)}
            playsInline
            preload="metadata"
            src={streamUrl}
          >
            Your browser does not support HTML video playback.
          </video>
        ) : (
          <div className="flex aspect-video max-h-[72vh] flex-col items-center justify-center bg-[#05080d] px-6 text-center">
            <FileVideo2 aria-hidden="true" className="h-9 w-9 text-slate-600" />
            <p className="mt-3 text-sm text-slate-300">
              {streamError ? "Protected playback unavailable" : "Preparing protected playback"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {streamError || "The video will load using authenticated byte-range requests."}
            </p>
          </div>
        )}
        {playerError && (
          <div className="border-t border-rose-300/10 bg-rose-300/[0.05] px-4 py-3" role="alert">
            <p className="text-sm text-rose-200">
              Playback failed. The file may be unavailable, unsupported by this browser, or your access token may have expired. Return to the library and sign in again if needed.
            </p>
          </div>
        )}
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Video metadata">
        <MetadataCard
          icon={<HardDrive aria-hidden="true" className="h-4 w-4" />}
          label="File size"
          value={formatFileSize(video.file_size_bytes)}
        />
        <MetadataCard
          icon={<Clock3 aria-hidden="true" className="h-4 w-4" />}
          label="Duration"
          value={formatDuration(video.duration_seconds)}
        />
        <MetadataCard
          icon={<FileVideo2 aria-hidden="true" className="h-4 w-4" />}
          label="Format"
          value={video.content_type}
        />
        <MetadataCard
          icon={<ShieldCheck aria-hidden="true" className="h-4 w-4" />}
          label="Processing status"
          value={video.status}
        />
      </section>

      <VideoAnalysisPanel
        accessToken={accessToken}
        key={`${userId}:${video.id}`}
        userId={userId}
        videoId={video.id}
      />

      <section className="rounded-xl border border-line bg-panel p-5 sm:p-6">
        <div className="flex items-center gap-2">
          <CalendarDays aria-hidden="true" className="h-4 w-4 text-sky-200" />
          <h2 className="text-sm font-semibold text-white">Video information</h2>
        </div>
        <dl className="mt-5 grid gap-5 sm:grid-cols-2">
          <div>
            <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-600">Video ID</dt>
            <dd className="mt-1 break-all font-mono text-xs text-slate-300">{video.id}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-600">Last updated</dt>
            <dd className="mt-1 text-sm text-slate-300">{formatVideoDate(video.updated_at)}</dd>
          </div>
        </dl>
      </section>

      {showDeleteConfirmation && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !isDeleting) {
              setShowDeleteConfirmation(false);
            }
          }}
        >
          <section
            aria-labelledby="delete-video-title"
            aria-modal="true"
            className="w-full max-w-md rounded-2xl border border-line bg-[#0c1624] p-6 shadow-2xl"
            role="dialog"
          >
            <h2 id="delete-video-title" className="text-lg font-semibold text-white">
              Delete this video?
            </h2>
            <p className="mt-2 break-words text-sm leading-6 text-slate-400">
              “{video.original_filename}” and its stored file will be permanently removed. This cannot be undone.
            </p>
            {deleteError && (
              <p className="mt-4 rounded-lg border border-rose-300/15 bg-rose-300/[0.06] px-3 py-2.5 text-sm text-rose-200" role="alert">
                {deleteError}
              </p>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-lg border border-line px-3.5 py-2.5 text-xs font-medium text-slate-300 hover:bg-white/[0.04] disabled:opacity-50"
                disabled={isDeleting}
                onClick={() => setShowDeleteConfirmation(false)}
                type="button"
              >
                Keep video
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-rose-500/90 px-3.5 py-2.5 text-xs font-semibold text-white hover:bg-rose-500 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={isDeleting}
                onClick={() => void confirmDelete()}
                type="button"
              >
                <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
                {isDeleting ? "Deleting…" : "Delete video"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function MetadataCard({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <article className="rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center gap-2 text-slate-500">
        {icon}
        <h2 className="text-xs font-medium">{label}</h2>
      </div>
      <p className="mt-3 break-words text-sm font-semibold capitalize text-slate-100">{value}</p>
    </article>
  );
}
