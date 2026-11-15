"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  CircleDot,
  Clock3,
  LoaderCircle,
  Play,
  RotateCcw,
  XCircle,
} from "lucide-react";
import {
  ApiError,
  getAnalysisStatus,
  startVideoAnalysis,
  type AnalysisJob,
  type AnalysisStatus,
} from "@/lib/api";
import { formatVideoDate } from "@/lib/videos";

const POLL_INTERVAL_MS = 2500;
const MAX_SAVED_JOB_IDS = 10;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const statusLabels: Record<AnalysisStatus, string> = {
  queued: "Queued",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

const statusStyles: Record<AnalysisStatus, string> = {
  queued: "border-blue-200 bg-blue-50 text-blue-700",
  processing: "border-amber-200 bg-amber-50 text-amber-800",
  completed: "border-emerald-200 bg-emerald-50 text-emerald-800",
  failed: "border-rose-200 bg-rose-50 text-rose-700",
  cancelled: "border-slate-200/10 bg-slate-300/[0.05] text-slate-600",
};

const terminalStatuses = new Set<AnalysisStatus>([
  "completed",
  "failed",
  "cancelled",
]);

interface VideoAnalysisPanelProps {
  accessToken: string;
  userId: string;
  videoId: string;
  compact?: boolean;
}

function historyKey(userId: string, videoId: string): string {
  return `crashsense.analysis-history.v1:${userId}:${videoId}`;
}

function isActive(job: AnalysisJob): boolean {
  return job.status === "queued" || job.status === "processing";
}

function errorMessage(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 401) {
      return "Your session has expired. Sign in again to continue.";
    }
    if (reason.status === 403) {
      return "Your account is not authorized to run video analysis.";
    }
    if (reason.status === 404) {
      return "The video or analysis job could not be found.";
    }
    return reason.message;
  }
  return "Could not reach the analysis service. Check the connection and try again.";
}

export function VideoAnalysisPanel({
  accessToken,
  userId,
  videoId,
  compact = false,
}: VideoAnalysisPanelProps) {
  const [jobs, setJobs] = useState<AnalysisJob[]>([]);
  const [jobErrors, setJobErrors] = useState<Record<string, string>>({});
  const [historyError, setHistoryError] = useState("");
  const [submissionError, setSubmissionError] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const requestVersion = useRef(0);

  useEffect(() => {
    let active = true;
    const version = ++requestVersion.current;
    void (async () => {
      try {
        const saved = localStorage.getItem(historyKey(userId, videoId));
        const parsed: unknown = saved ? JSON.parse(saved) : [];
        if (
          !Array.isArray(parsed) ||
          !parsed.every(
            (id) => typeof id === "string" && UUID_PATTERN.test(id),
          )
        ) {
          throw new Error("Stored job history is invalid.");
        }
        const savedIds = parsed.slice(0, MAX_SAVED_JOB_IDS);
        if (savedIds.length === 0) {
          return;
        }
        const results = await Promise.all(
          savedIds.map(async (analysisId) => {
            try {
              const job = await getAnalysisStatus(accessToken, analysisId);
              if (job.video_id !== videoId) {
                throw new ApiError(
                  "The saved analysis belongs to a different video.",
                  502,
                );
              }
              return { job, error: null };
            } catch (reason) {
              return { job: null, id: analysisId, error: errorMessage(reason) };
            }
          }),
        );
        if (!active || requestVersion.current !== version) {
          return;
        }
        setJobs(results.flatMap((result) => (result.job ? [result.job] : [])));
        setJobErrors(
          Object.fromEntries(
            results.flatMap((result) =>
              result.error && "id" in result
                ? [[result.id, result.error]]
                : [],
            ),
          ),
        );
      } catch {
        if (active && requestVersion.current === version) {
          setHistoryError(
            "Saved analysis history could not be read from this browser.",
          );
        }
      }
    })();

    return () => {
      active = false;
      requestVersion.current += 1;
    };
  }, [accessToken, userId, videoId]);

  useEffect(() => {
    let active = true;
    const cleanups: (() => void)[] = [];

    for (const job of jobs) {
      if (!isActive(job)) {
        continue;
      }

      let stopped = false;
      let timer: ReturnType<typeof setTimeout> | undefined;
      const schedule = (delay: number) => {
        timer = setTimeout(() => void poll(), delay);
      };
      const poll = async () => {
        try {
          const updated = await getAnalysisStatus(accessToken, job.id);
          if (!active || stopped) {
            return;
          }
          if (updated.video_id !== videoId) {
            throw new ApiError("The analysis job belongs to a different video.", 502);
          }
          setJobs((current) =>
            current.map((item) => (item.id === updated.id ? updated : item)),
          );
          setJobErrors((current) => {
            const next = { ...current };
            delete next[job.id];
            return next;
          });
          if (isActive(updated)) {
            schedule(POLL_INTERVAL_MS);
          }
        } catch (reason) {
          if (!active || stopped) {
            return;
          }
          const message = errorMessage(reason);
          setJobErrors((current) => ({ ...current, [job.id]: message }));
          if (
            reason instanceof ApiError &&
            (reason.status === 401 || reason.status === 403 || reason.status === 404)
          ) {
            return;
          }
          schedule(POLL_INTERVAL_MS * 2);
        }
      };
      schedule(POLL_INTERVAL_MS);
      cleanups.push(() => {
        stopped = true;
        if (timer !== undefined) {
          clearTimeout(timer);
        }
      });
    }

    return () => {
      active = false;
      cleanups.forEach((cleanup) => cleanup());
    };
  }, [accessToken, jobs, videoId]);

  async function submitAnalysis() {
    if (isStarting || jobs.some(isActive)) {
      return;
    }
    setIsStarting(true);
    setSubmissionError("");
    try {
      const job = await startVideoAnalysis(accessToken, videoId);
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setExpandedJobId(job.id);
      try {
        const saved = localStorage.getItem(historyKey(userId, videoId));
        const parsed: unknown = saved ? JSON.parse(saved) : [];
        const ids =
          Array.isArray(parsed) &&
          parsed.every(
            (id) => typeof id === "string" && UUID_PATTERN.test(id),
          )
            ? parsed
            : [];
        localStorage.setItem(
          historyKey(userId, videoId),
          JSON.stringify(
            [job.id, ...ids.filter((id) => id !== job.id)].slice(
              0,
              MAX_SAVED_JOB_IDS,
            ),
          ),
        );
        setHistoryError("");
      } catch {
        setHistoryError(
          "Analysis was queued, but its job ID could not be saved in this browser.",
        );
      }
    } catch (reason) {
      setSubmissionError(errorMessage(reason));
    } finally {
      setIsStarting(false);
    }
  }

  const activeJob = jobs.find(isActive);
  const canStart = !activeJob && !isStarting;

  return (
    <section
      aria-labelledby={`analysis-title-${videoId}`}
      className={`rounded-xl border border-line bg-panel ${
        compact ? "p-3" : "p-5 sm:p-6"
      }`}
    >
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <div className="flex items-center gap-2">
            <CircleDot aria-hidden="true" className="h-4 w-4 text-blue-700" />
            <h2
              className="text-sm font-semibold text-slate-900"
              id={`analysis-title-${videoId}`}
            >
              {compact ? "Video analysis" : "Accident analysis"}
            </h2>
          </div>
          {!compact && (
            <p className="mt-1.5 text-xs leading-5 text-slate-500">
              Start the database-backed YOLO analysis job and follow its reported
              worker status.
            </p>
          )}
        </div>
        <button
          className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2.5 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
            canStart
              ? "bg-accent-strong text-white hover:bg-sky-500"
              : "border border-line bg-slate-50 text-slate-600"
          }`}
          disabled={!canStart}
          onClick={() => void submitAnalysis()}
          type="button"
        >
          {isStarting ? (
            <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : activeJob ? (
            <Clock3 aria-hidden="true" className="h-4 w-4" />
          ) : jobs.some((job) => job.status === "failed") ? (
            <RotateCcw aria-hidden="true" className="h-4 w-4" />
          ) : (
            <Play aria-hidden="true" className="h-4 w-4" />
          )}
          {isStarting
            ? "Starting analysis"
            : activeJob
              ? "Analysis in progress"
              : jobs.some((job) => job.status === "failed")
                ? "Analyze again"
                : "Analyze video"}
        </button>
      </div>

      {submissionError && (
        <p
          className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700"
          role="alert"
        >
          {submissionError}
        </p>
      )}
      {historyError && (
        <p
          className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800"
          role="status"
        >
          {historyError}
        </p>
      )}

      {jobs.length > 0 && (
        <div className={`${compact ? "mt-3 space-y-2" : "mt-5 space-y-3"}`}>
          <h3 className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Recent analysis jobs
          </h3>
          {jobs.map((job) => (
            <AnalysisJobItem
              expanded={expandedJobId === job.id}
              key={job.id}
              job={job}
              pollError={jobErrors[job.id]}
              onToggle={() =>
                setExpandedJobId((current) =>
                  current === job.id ? null : job.id,
                )
              }
              compact={compact}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function AnalysisJobItem({
  job,
  pollError,
  expanded,
  onToggle,
  compact,
}: {
  job: AnalysisJob;
  pollError?: string;
  expanded: boolean;
  onToggle: () => void;
  compact: boolean;
}) {
  const StatusIcon =
    job.status === "completed"
      ? CheckCircle2
      : job.status === "failed"
        ? XCircle
        : job.status === "cancelled"
          ? AlertCircle
          : job.status === "processing"
            ? LoaderCircle
            : Clock3;

  return (
    <article className="rounded-lg border border-line bg-slate-50">
      <button
        aria-expanded={expanded}
        className={`flex w-full items-center justify-between gap-3 text-left hover:bg-slate-50 ${
          compact ? "p-2.5" : "p-3.5"
        }`}
        onClick={onToggle}
        type="button"
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <StatusIcon
            aria-hidden="true"
            className={`h-4 w-4 shrink-0 ${
              job.status === "processing" ? "animate-spin" : ""
            } ${
              job.status === "completed"
                ? "text-emerald-800"
                : job.status === "failed"
                  ? "text-rose-700"
                  : job.status === "processing"
                    ? "text-amber-800"
                    : "text-blue-700"
            }`}
          />
          <span className="min-w-0">
            <span className="block truncate font-mono text-[11px] text-slate-600">
              Job {job.id.slice(0, 8)}
            </span>
            <span className="mt-0.5 block text-[10px] text-slate-600">
              {formatVideoDate(job.created_at)}
            </span>
          </span>
        </span>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-medium ${
            statusStyles[job.status]
          }`}
        >
          {statusLabels[job.status]}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-line px-3.5 py-3.5">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="text-slate-500">Job ID</span>
            <span className="break-all font-mono text-[10px] text-slate-600">
              {job.id}
            </span>
          </div>
          {(job.status === "queued" || job.status === "processing") && (
            <div className="mt-3">
              <div className="mb-1.5 flex justify-between text-[10px] text-slate-500">
                <span>{job.status === "queued" ? "Waiting for worker" : "Processing"}</span>
                <span>{job.progress}%</span>
              </div>
              <div
                aria-label={`Analysis progress ${job.progress}%`}
                aria-valuemax={100}
                aria-valuemin={0}
                aria-valuenow={job.progress}
                className="h-1.5 overflow-hidden rounded-full bg-slate-800"
                role="progressbar"
              >
                <div
                  className="h-full rounded-full bg-sky-400 transition-[width]"
                  style={{ width: `${job.progress}%` }}
                />
              </div>
            </div>
          )}
          {job.status === "completed" && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-emerald-800">
                Processing completed with backend-reported progress of {job.progress}%.
              </p>
              <Link
                className="text-xs font-medium text-blue-700 hover:text-slate-900"
                href={`/dashboard/analysis/${encodeURIComponent(job.id)}`}
              >
                Review results
              </Link>
            </div>
          )}
          {job.status === "failed" && (
            <p className="mt-3 text-xs text-rose-700">
              {job.error_message || "Analysis failed without a server-provided error message."}
            </p>
          )}
          {job.status === "cancelled" && (
            <p className="mt-3 text-xs text-slate-600">
              This analysis job was cancelled.
            </p>
          )}
          {job.cancel_requested && isActive(job) && (
            <p className="mt-2 text-[10px] text-amber-800">
              Cancellation was requested by an authorized user.
            </p>
          )}
          {pollError && (
            <p className="mt-3 text-xs text-rose-700" role="alert">
              Status refresh failed: {pollError}
            </p>
          )}
          {!terminalStatuses.has(job.status) && (
            <p className="mt-2 text-[10px] text-slate-600">
              Status refreshes automatically while this job is active.
            </p>
          )}
        </div>
      )}
    </article>
  );
}
