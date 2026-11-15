"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Clock3,
  FileVideo2,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import {
  ApiError,
  getAnalysisStatus,
  type AnalysisJob,
} from "@/lib/api";
import { LoadingState } from "@/components/loading-state";
import { formatVideoDate } from "@/lib/videos";

const HISTORY_KEY_PREFIX = "crashsense.analysis-history.v1:";
const MAX_HISTORY_ENTRIES = 50;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

interface AnalysisHistoryProps {
  accessToken: string;
  userId: string;
}

interface HistoryRecord {
  id: string;
  videoId: string;
  job: AnalysisJob | null;
  error: string;
}

function errorMessage(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 401) {
      return "Your session has expired.";
    }
    if (reason.status === 403) {
      return "Your account cannot access this job.";
    }
    if (reason.status === 404) {
      return "This saved analysis job is no longer available.";
    }
    return reason.message;
  }
  return "Could not refresh this analysis job.";
}

function savedIdsForUser(userId: string): Array<{ id: string; videoId: string }> {
  const prefix = `${HISTORY_KEY_PREFIX}${userId}:`;
  const records = new Map<string, { id: string; videoId: string }>();

  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (!key?.startsWith(prefix)) {
      continue;
    }
    const videoId = key.slice(prefix.length);
    if (!UUID_PATTERN.test(videoId)) {
      continue;
    }
    const value = localStorage.getItem(key);
    const parsed: unknown = value ? JSON.parse(value) : [];
    if (
      !Array.isArray(parsed) ||
      !parsed.every((id) => typeof id === "string" && UUID_PATTERN.test(id))
    ) {
      throw new Error("Saved analysis history is invalid.");
    }
    for (const id of parsed) {
      records.set(id, { id, videoId });
    }
  }
  return [...records.values()].slice(0, MAX_HISTORY_ENTRIES);
}

export function AnalysisHistory({
  accessToken,
  userId,
}: AnalysisHistoryProps) {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const saved = savedIdsForUser(userId);
      const current = await Promise.all(
        saved.map(async ({ id, videoId }): Promise<HistoryRecord> => {
          try {
            const job = await getAnalysisStatus(accessToken, id);
            if (job.video_id !== videoId) {
              throw new ApiError(
                "The saved analysis does not match its associated video.",
                502,
              );
            }
            return { id, videoId, job, error: "" };
          } catch (reason) {
            return { id, videoId, job: null, error: errorMessage(reason) };
          }
        }),
      );
      current.sort((first, second) => {
        const firstDate = first.job?.created_at ?? "";
        const secondDate = second.job?.created_at ?? "";
        return secondDate.localeCompare(firstDate);
      });
      setRecords(current);
    } catch {
      setError("Saved analysis history could not be read from this browser.");
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [accessToken, userId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadHistory(), 0);
    return () => window.clearTimeout(timer);
  }, [loadHistory]);

  if (loading) {
    return <LoadingState label="Loading saved analysis history" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-700">
            Monitoring
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
            Analysis history
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Review saved analysis jobs and inspect their backend-reported
            candidates and frame evidence.
          </p>
        </div>
        <button
          className="inline-flex w-fit items-center gap-2 rounded-lg border border-line px-3.5 py-2.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
          onClick={() => void loadHistory()}
          type="button"
        >
          <RefreshCw aria-hidden="true" className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800">
        The API does not expose a history-list endpoint. This list contains up
        to {MAX_HISTORY_ENTRIES} job IDs saved by this browser; each displayed
        status is reloaded from the protected API.
      </div>

      {error && (
        <p
          className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700"
          role="alert"
        >
          {error}
        </p>
      )}

      {!error && records.length === 0 && (
        <section className="rounded-xl border border-dashed border-line bg-panel p-8 text-center">
          <FileVideo2
            aria-hidden="true"
            className="mx-auto h-8 w-8 text-slate-600"
          />
          <h2 className="mt-4 text-sm font-semibold text-slate-700">
            No saved analysis jobs
          </h2>
          <p className="mx-auto mt-2 max-w-md text-xs leading-5 text-slate-500">
            Start analysis from a video. Its job ID will appear here in this
            browser after submission.
          </p>
          <Link
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-accent-strong px-3.5 py-2.5 text-xs font-semibold text-white hover:bg-sky-500"
            href="/dashboard/videos"
          >
            Open video library
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </section>
      )}

      {records.length > 0 && (
        <section
          aria-label="Saved analysis jobs"
          className="space-y-3"
        >
          {records.map((record) => (
            <article
              className="flex flex-col justify-between gap-4 rounded-xl border border-line bg-panel p-4 sm:flex-row sm:items-center sm:p-5"
              key={record.id}
            >
              <div className="flex min-w-0 items-start gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-blue-200 bg-blue-50 text-blue-700">
                  {record.job ? (
                    <Clock3 aria-hidden="true" className="h-4 w-4" />
                  ) : (
                    <AlertCircle aria-hidden="true" className="h-4 w-4" />
                  )}
                </span>
                <div className="min-w-0">
                  <p className="break-all font-mono text-xs text-slate-700">
                    Job {record.id}
                  </p>
                  <p className="mt-1 break-all font-mono text-[10px] text-slate-500">
                    Video {record.videoId}
                  </p>
                  {record.job && (
                    <p className="mt-1 text-[10px] text-slate-600">
                      Created {formatVideoDate(record.job.created_at)}
                    </p>
                  )}
                  {record.error && (
                    <p className="mt-2 text-xs text-rose-700" role="alert">
                      {record.error}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between gap-3 sm:justify-end">
                {record.job ? (
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[10px] font-medium ${
                      record.job.status === "completed"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : record.job.status === "failed"
                          ? "border-rose-200 bg-rose-50 text-rose-700"
                          : record.job.status === "processing"
                            ? "border-amber-200 bg-amber-50 text-amber-800"
                            : "border-line text-slate-600"
                    }`}
                  >
                    {record.job.status}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-[10px] text-slate-500">
                    <LoaderCircle
                      aria-hidden="true"
                      className="h-3.5 w-3.5"
                    />
                    Unavailable
                  </span>
                )}
                <Link
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-700 hover:text-slate-900"
                  href={`/dashboard/analysis/${encodeURIComponent(record.id)}`}
                >
                  Review
                  <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
                </Link>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
