"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileVideo2,
  HardDrive,
  Play,
  RefreshCw,
  Search,
} from "lucide-react";
import { ApiError, listVideos, type Video } from "@/lib/api";
import { LoadingState } from "@/components/loading-state";
import { VideoUpload } from "@/components/video-upload";
import { VideoAnalysisPanel } from "@/components/video-analysis-panel";
import {
  filterVideos,
  formatDuration,
  formatFileSize,
  formatVideoDate,
} from "@/lib/videos";

const PAGE_SIZE = 20;

const statusStyles: Record<string, string> = {
  uploaded: "border-sky-200/10 bg-sky-300/[0.06] text-sky-200",
  processing: "border-amber-200/10 bg-amber-300/[0.06] text-amber-200",
  processed: "border-emerald-200/10 bg-emerald-300/[0.06] text-emerald-200",
  failed: "border-rose-200/10 bg-rose-300/[0.06] text-rose-200",
};

interface VideoLibraryProps {
  accessToken: string;
  userId: string;
}

export function VideoLibrary({ accessToken, userId }: VideoLibraryProps) {
  const [videos, setVideos] = useState<Video[]>([]);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const requestId = useRef(0);

  const loadPage = useCallback(
    async (nextOffset: number) => {
      const currentRequest = ++requestId.current;
      setIsLoading(true);
      setError("");
      try {
        const page = await listVideos(accessToken, PAGE_SIZE, nextOffset);
        if (requestId.current === currentRequest) {
          setVideos(page);
          setOffset(nextOffset);
        }
      } catch (reason) {
        if (requestId.current === currentRequest) {
          setError(
            reason instanceof ApiError
              ? reason.message
              : "The video library could not be loaded.",
          );
        }
      } finally {
        if (requestId.current === currentRequest) {
          setIsLoading(false);
        }
      }
    },
    [accessToken],
  );

  useEffect(() => {
    const currentRequest = ++requestId.current;
    listVideos(accessToken, PAGE_SIZE, 0)
      .then((page) => {
        if (requestId.current === currentRequest) {
          setVideos(page);
          setOffset(0);
        }
      })
      .catch((reason: unknown) => {
        if (requestId.current === currentRequest) {
          setError(
            reason instanceof ApiError
              ? reason.message
              : "The video library could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (requestId.current === currentRequest) {
          setIsLoading(false);
        }
      });
    return () => {
      requestId.current += 1;
    };
  }, [accessToken]);

  const filteredVideos = filterVideos(videos, search, statusFilter);
  const hasPreviousPage = offset > 0;
  const hasNextPage = videos.length === PAGE_SIZE;

  async function refreshAfterUpload() {
    setSearch("");
    setStatusFilter("all");
    await loadPage(0);
  }

  return (
    <div className="animate-fade-in space-y-7">
      <section className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-sky-200/80">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-300" />
            Protected media
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">
            Video library
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Browse and manage uploaded road footage. Access is enforced by the
            CrashSense API for every request.
          </p>
        </div>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-line bg-white/[0.025] px-3.5 py-2.5 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:bg-white/[0.05]"
          disabled={isLoading}
          onClick={() => void loadPage(offset)}
          type="button"
        >
          <RefreshCw
            aria-hidden="true"
            className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`}
          />
          Refresh
        </button>
      </section>

      <VideoUpload accessToken={accessToken} onUploaded={refreshAfterUpload} />

      <section aria-labelledby="library-results-title">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 id="library-results-title" className="text-base font-semibold text-white">
              Uploaded videos
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Search and filters apply to the currently loaded page.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-[minmax(190px,280px)_160px]">
            <label className="relative">
              <span className="sr-only">Search this page</span>
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
              />
              <input
                className="field-input pl-9"
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search filenames"
                type="search"
                value={search}
              />
            </label>
            <label>
              <span className="sr-only">Filter by video status</span>
              <select
                className="field-input"
                onChange={(event) => setStatusFilter(event.target.value)}
                value={statusFilter}
              >
                <option value="all">All statuses</option>
                <option value="uploaded">Uploaded</option>
                <option value="processing">Processing</option>
                <option value="processed">Processed</option>
                <option value="failed">Failed</option>
              </select>
            </label>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-300/15 bg-rose-300/[0.05] p-5" role="alert">
            <p className="text-sm text-rose-200">{error}</p>
            <button
              className="mt-3 text-xs font-medium text-rose-100 underline underline-offset-4"
              onClick={() => void loadPage(offset)}
              type="button"
            >
              Try again
            </button>
          </div>
        )}

        {isLoading ? (
          <LoadingState label="Loading uploaded videos" />
        ) : !error && filteredVideos.length === 0 ? (
          <div className="flex min-h-56 flex-col items-center justify-center rounded-xl border border-dashed border-line bg-panel/60 px-6 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full border border-line bg-white/[0.025] text-slate-500">
              <FileVideo2 aria-hidden="true" className="h-5 w-5" />
            </span>
            <h3 className="mt-4 text-sm font-semibold text-slate-200">
              {videos.length === 0 ? "No videos in this library page" : "No matching videos"}
            </h3>
            <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
              {videos.length === 0
                ? "Upload a road video above to add it to the protected library."
                : "Try another filename or status filter, or browse a different page."}
            </p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
            {filteredVideos.map((video) => (
              <article
                className="group overflow-hidden rounded-xl border border-line bg-panel transition hover:-translate-y-0.5 hover:border-slate-600"
                key={video.id}
              >
                <Link
                  aria-label={`View ${video.original_filename}`}
                  className="block"
                  href={`/dashboard/videos/${encodeURIComponent(video.id)}`}
                >
                  <div className="relative flex h-36 items-center justify-center overflow-hidden bg-gradient-to-br from-[#14243a] via-[#0d1a2a] to-[#0a121e]">
                    <div className="absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(120,170,210,.08)_1px,transparent_1px),linear-gradient(90deg,rgba(120,170,210,.08)_1px,transparent_1px)] [background-size:28px_28px]" />
                    <span className="relative flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-black/20 text-sky-100 transition group-hover:scale-105 group-hover:bg-sky-400/20">
                      <Play aria-hidden="true" className="ml-0.5 h-5 w-5 fill-current" />
                    </span>
                    <span className="absolute bottom-3 left-4 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-500">
                      Protected video
                    </span>
                    <span
                      className={`absolute right-3 top-3 rounded-full border px-2.5 py-1 text-[10px] font-medium capitalize ${
                        statusStyles[video.status] ??
                        "border-slate-200/10 bg-slate-300/[0.05] text-slate-300"
                      }`}
                    >
                      {video.status}
                    </span>
                  </div>
                  <div className="p-4">
                    <h3 className="truncate text-sm font-semibold text-slate-100">
                      {video.original_filename}
                    </h3>
                    <dl className="mt-4 grid grid-cols-2 gap-x-3 gap-y-3">
                      <div className="flex min-w-0 items-center gap-2 text-xs text-slate-400">
                        <HardDrive aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-slate-600" />
                        <dd className="truncate">{formatFileSize(video.file_size_bytes)}</dd>
                      </div>
                      <div className="flex min-w-0 items-center gap-2 text-xs text-slate-400">
                        <Clock3 aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-slate-600" />
                        <dd className="truncate">{formatDuration(video.duration_seconds)}</dd>
                      </div>
                      <div className="col-span-2 flex min-w-0 items-center gap-2 text-xs text-slate-500">
                        <CalendarDays aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-slate-600" />
                        <dd className="truncate">Uploaded {formatVideoDate(video.created_at)}</dd>
                      </div>
                    </dl>
                  </div>
                </Link>
                <div className="border-t border-line p-3">
                  <VideoAnalysisPanel
                    accessToken={accessToken}
                    compact
                    key={`${userId}:${video.id}`}
                    userId={userId}
                    videoId={video.id}
                  />
                </div>
              </article>
            ))}
          </div>
        )}

        <div className="mt-5 flex items-center justify-between border-t border-line pt-4">
          <p className="text-xs text-slate-500">
            {videos.length
              ? `Page ${Math.floor(offset / PAGE_SIZE) + 1} · ${videos.length} records`
              : "No records on this page"}
          </p>
          <div className="flex gap-2">
            <button
              aria-label="Previous videos page"
              className="rounded-lg border border-line p-2 text-slate-300 transition hover:bg-white/[0.04] disabled:cursor-not-allowed disabled:opacity-40"
              disabled={!hasPreviousPage || isLoading}
              onClick={() => void loadPage(Math.max(0, offset - PAGE_SIZE))}
              type="button"
            >
              <ChevronLeft aria-hidden="true" className="h-4 w-4" />
            </button>
            <button
              aria-label="Next videos page"
              className="rounded-lg border border-line p-2 text-slate-300 transition hover:bg-white/[0.04] disabled:cursor-not-allowed disabled:opacity-40"
              disabled={!hasNextPage || isLoading}
              onClick={() => void loadPage(offset + PAGE_SIZE)}
              type="button"
            >
              <ChevronRight aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
