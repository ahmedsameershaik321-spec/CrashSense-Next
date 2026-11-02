"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowLeftRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileVideo2,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  Video,
} from "lucide-react";
import { AlertAuditPanel } from "@/components/alert-audit-panel";
import {
  ApiError,
  createVideoStreamSession,
  getAnalysisFrames,
  getAnalysisResults,
  getAnalysisStatus,
  getVideo,
  type AccidentCandidate,
  type AnalysisFrame,
  type AnalysisJob,
  type AnalysisResults,
  type Video as VideoRecord,
} from "@/lib/api";
import { LoadingState } from "@/components/loading-state";
import { ResponseResources } from "@/components/response-resources";

const FRAME_PAGE_SIZE = 100;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

interface AnalysisResultsProps {
  accessToken: string;
  expiresInSeconds: number;
  analysisId: string;
  isAdministrator?: boolean;
}

function messageForError(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 401) {
      return "Your session has expired. Sign in again to review this analysis.";
    }
    if (reason.status === 403) {
      return "Your account is not authorized to review analysis results.";
    }
    if (reason.status === 404) {
      return "The analysis job or its video could not be found.";
    }
    return reason.message;
  }
  return "Analysis results could not be loaded. Check the connection and try again.";
}

function formatTimestamp(seconds: number): string {
  const totalMilliseconds = Math.max(0, Math.round(seconds * 1000));
  const minutes = Math.floor(totalMilliseconds / 60_000);
  const remainingSeconds = (totalMilliseconds % 60_000) / 1000;
  return `${minutes}:${remainingSeconds.toFixed(3).padStart(6, "0")}`;
}

function candidateStatus(candidate: AccidentCandidate): string {
  return candidate.verification_status === "verified_detection"
    ? "Verified detection"
    : "Suspected";
}

export function AnalysisResultsView({
  accessToken,
  expiresInSeconds,
  analysisId,
  isAdministrator = false,
}: AnalysisResultsProps) {
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [results, setResults] = useState<AnalysisResults | null>(null);
  const [video, setVideo] = useState<VideoRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [playbackError, setPlaybackError] = useState("");
  const [streamReady, setStreamReady] = useState(false);
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [frames, setFrames] = useState<AnalysisFrame[]>([]);
  const [frameOffset, setFrameOffset] = useState(0);
  const [selectedFrameIndex, setSelectedFrameIndex] = useState(0);
  const [framesLoading, setFramesLoading] = useState(false);
  const [frameError, setFrameError] = useState("");
  const playerRef = useRef<HTMLVideoElement>(null);
  const loadVersion = useRef(0);
  const frameVersion = useRef(0);

  const loadResults = useCallback(async () => {
    const version = ++loadVersion.current;
    setLoading(true);
    setError("");
    setPlaybackError("");
    setStreamReady(false);
    setVideo(null);
    setResults(null);

    try {
      if (!UUID_PATTERN.test(analysisId)) {
        throw new ApiError("The requested analysis job could not be found.", 404);
      }
      const currentJob = await getAnalysisStatus(accessToken, analysisId);
      if (version !== loadVersion.current) {
        return;
      }
      setJob(currentJob);
      if (currentJob.status !== "completed") {
        setLoading(false);
        return;
      }

      const response = await getAnalysisResults(accessToken, analysisId);
      if (version !== loadVersion.current) {
        return;
      }
      if (
        response.job_id !== currentJob.id ||
        response.video_id !== currentJob.video_id
      ) {
        throw new ApiError("The server returned results for a different job.", 502);
      }
      const orderedCandidates = [...response.candidates].sort(
        (first, second) =>
          first.start_timestamp_seconds - second.start_timestamp_seconds,
      );
      setResults(response);
      setSelectedCandidateId(orderedCandidates[0]?.candidate_id ?? "");

      try {
        const videoRecord = await getVideo(accessToken, response.video_id);
        if (version !== loadVersion.current) {
          return;
        }
        setVideo(videoRecord);
        await createVideoStreamSession(accessToken, expiresInSeconds);
        if (version === loadVersion.current) {
          setStreamReady(true);
        }
      } catch (reason) {
        if (version === loadVersion.current) {
          setPlaybackError(messageForError(reason));
        }
      }
    } catch (reason) {
      if (version === loadVersion.current) {
        setError(messageForError(reason));
        setJob(null);
      }
    } finally {
      if (version === loadVersion.current) {
        setLoading(false);
      }
    }
  }, [accessToken, analysisId, expiresInSeconds]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadResults(), 0);
    return () => {
      window.clearTimeout(timer);
      loadVersion.current += 1;
      frameVersion.current += 1;
    };
  }, [loadResults]);

  const orderedCandidates = useMemo(
    () =>
      [...(results?.candidates ?? [])].sort(
        (first, second) =>
          first.start_timestamp_seconds - second.start_timestamp_seconds,
      ),
    [results],
  );
  const selectedCandidate =
    orderedCandidates.find(
      (candidate) => candidate.candidate_id === selectedCandidateId,
    ) ?? null;
  const selectedFrame = frames[selectedFrameIndex] ?? null;

  const loadFramePage = useCallback(
    async (offset: number, candidate: AccidentCandidate) => {
      const version = ++frameVersion.current;
      setFramesLoading(true);
      setFrameError("");
      try {
        const response = await getAnalysisFrames(
          accessToken,
          analysisId,
          offset,
          FRAME_PAGE_SIZE,
        );
        if (version !== frameVersion.current) {
          return;
        }
        setFrames(response);
        setFrameOffset(offset);
        if (response.length) {
          const target =
            (candidate.start_timestamp_seconds +
              candidate.end_timestamp_seconds) /
            2;
          const nearestIndex = response.reduce(
            (closest, frame, index, list) =>
              Math.abs(frame.timestamp_seconds - target) <
              Math.abs(list[closest].timestamp_seconds - target)
                ? index
                : closest,
            0,
          );
          setSelectedFrameIndex(nearestIndex);
        } else {
          setSelectedFrameIndex(0);
        }
      } catch (reason) {
        if (version === frameVersion.current) {
          setFrameError(messageForError(reason));
          setFrames([]);
        }
      } finally {
        if (version === frameVersion.current) {
          setFramesLoading(false);
        }
      }
    },
    [accessToken, analysisId],
  );

  useEffect(() => {
    if (!selectedCandidate || !results) {
      return;
    }
    const estimatedOffset = Math.max(
      0,
      Math.floor(
        selectedCandidate.start_timestamp_seconds /
          results.summary.frame_interval_seconds,
      ) - Math.floor(FRAME_PAGE_SIZE / 4),
    );
    const pageOffset = Math.min(
      estimatedOffset,
      Math.max(0, results.total_frames - FRAME_PAGE_SIZE),
    );
    const timer = window.setTimeout(
      () => void loadFramePage(pageOffset, selectedCandidate),
      0,
    );
    return () => {
      window.clearTimeout(timer);
      frameVersion.current += 1;
    };
  }, [loadFramePage, results, selectedCandidate]);

  useEffect(() => {
    if (selectedFrame && playerRef.current && streamReady) {
      playerRef.current.currentTime = selectedFrame.timestamp_seconds;
    }
  }, [selectedFrame, streamReady]);

  async function changeFramePage(direction: -1 | 1) {
    if (!selectedCandidate || !results) {
      return;
    }
    const nextOffset = frameOffset + direction * FRAME_PAGE_SIZE;
    if (nextOffset < 0 || nextOffset >= results.total_frames) {
      return;
    }
    await loadFramePage(nextOffset, selectedCandidate);
  }

  if (loading) {
    return <LoadingState label="Loading analysis results" />;
  }

  if (error) {
    return (
      <section
        className="rounded-xl border border-rose-300/15 bg-rose-300/[0.05] p-6"
        role="alert"
      >
        <h1 className="text-lg font-semibold text-white">Results unavailable</h1>
        <p className="mt-2 text-sm text-rose-200">{error}</p>
        <button
          className="mt-5 inline-flex items-center gap-2 rounded-lg border border-line px-3.5 py-2.5 text-xs font-medium text-slate-200 hover:bg-white/[0.04]"
          onClick={() => void loadResults()}
          type="button"
        >
          <RefreshCw aria-hidden="true" className="h-4 w-4" />
          Retry
        </button>
      </section>
    );
  }

  if (!job) {
    return null;
  }

  if (job.status !== "completed" || !results) {
    return (
      <div className="space-y-5">
        <PageBackLink />
        <section className="rounded-xl border border-line bg-panel p-6">
          <div className="flex items-center gap-3">
            {job.status === "failed" ? (
              <AlertCircle aria-hidden="true" className="h-5 w-5 text-rose-200" />
            ) : (
              <Clock3 aria-hidden="true" className="h-5 w-5 text-amber-200" />
            )}
            <div>
              <h1 className="text-lg font-semibold text-white">
                {job.status === "failed"
                  ? "Analysis failed"
                  : job.status === "cancelled"
                    ? "Analysis cancelled"
                    : "Analysis is not complete"}
              </h1>
              <p className="mt-1 text-sm text-slate-400">
                Current status: <span className="capitalize">{job.status}</span>
                {(job.status === "queued" || job.status === "processing") &&
                  ` · ${job.progress}% reported by the backend`}
              </p>
              {job.error_message && (
                <p className="mt-2 text-sm text-rose-200">{job.error_message}</p>
              )}
            </div>
          </div>
          <button
            className="mt-5 inline-flex items-center gap-2 rounded-lg border border-line px-3.5 py-2.5 text-xs font-medium text-slate-200 hover:bg-white/[0.04]"
            onClick={() => void loadResults()}
            type="button"
          >
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
            Refresh status
          </button>
        </section>
      </div>
    );
  }

  const summary = results.summary;
  const framePageCount = Math.ceil(results.total_frames / FRAME_PAGE_SIZE);
  const currentFramePage =
    results.total_frames === 0
      ? 0
      : Math.floor(frameOffset / FRAME_PAGE_SIZE) + 1;
  const streamUrl = video
    ? `/api/videos/${encodeURIComponent(video.id)}/stream`
    : "";

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <PageBackLink />
          <p className="mt-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200">
            Incident review
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            Analysis results
          </h1>
          <p className="mt-2 break-all font-mono text-xs text-slate-500">
            Job {job.id}
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-2 rounded-full border border-emerald-200/10 bg-emerald-300/[0.06] px-3 py-1.5 text-xs font-medium text-emerald-200">
          <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
          Completed
        </span>
      </div>

      <section
        aria-label="Video information"
        className="flex flex-col gap-3 rounded-xl border border-line bg-panel p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5"
      >
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-sky-200/10 bg-sky-300/[0.06] text-sky-200">
            <FileVideo2 aria-hidden="true" className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-white">
              {video?.original_filename ?? "Video record unavailable"}
            </h2>
            <p className="mt-1 break-all font-mono text-[10px] text-slate-500">
              Video {results.video_id}
            </p>
          </div>
        </div>
        {video && (
          <Link
            className="inline-flex w-fit items-center gap-2 text-xs font-medium text-sky-200 hover:text-white"
            href={`/dashboard/videos/${encodeURIComponent(video.id)}`}
          >
            <Video aria-hidden="true" className="h-4 w-4" />
            Open video details
          </Link>
        )}
      </section>

      <section
        aria-label="Analysis summary"
        className="grid gap-3 sm:grid-cols-3"
      >
        <SummaryCard
          label="Frames processed"
          value={summary.frames_processed.toLocaleString()}
        />
        <SummaryCard
          label="Detections processed"
          value={summary.detections_processed.toLocaleString()}
        />
        <SummaryCard
          label="Accident candidates"
          value={summary.candidate_count.toLocaleString()}
        />
      </section>

      <ResponseResources
        accessToken={accessToken}
        candidate={selectedCandidate}
        isAdministrator={isAdministrator}
        videoId={results.video_id}
      />

      {selectedCandidate && (
        <AlertAuditPanel
          accessToken={accessToken}
          analysisId={analysisId}
          candidateId={selectedCandidate.candidate_id}
        />
      )}

      <section className="rounded-xl border border-line bg-panel p-4 sm:p-5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Processing details
        </h2>
        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
          <Metadata label="Model" value={summary.model} />
          <Metadata label="Device" value={summary.device} />
          <Metadata
            label="Sampling interval"
            value={`${summary.frame_interval_seconds}s`}
          />
        </dl>
        <p className="mt-4 flex gap-2 border-t border-line pt-3 text-[11px] leading-5 text-amber-100/80">
          <ShieldAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
          {summary.notice}
        </p>
      </section>

      <section
        aria-labelledby="candidate-list-title"
        className="grid gap-5 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.6fr)]"
      >
        <div className="rounded-xl border border-line bg-panel p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2
                className="text-sm font-semibold text-white"
                id="candidate-list-title"
              >
                Candidate review
              </h2>
              <p className="mt-1 text-[11px] text-slate-500">
                Ordered by first observed timestamp
              </p>
            </div>
            <span className="rounded-full border border-line px-2.5 py-1 text-[10px] text-slate-400">
              {orderedCandidates.length}
            </span>
          </div>

          {orderedCandidates.length === 0 ? (
            <div className="mt-5 rounded-lg border border-line bg-[#09121f]/70 p-4">
              <p className="text-sm font-medium text-slate-200">
                No candidates were returned
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                This completed analysis contains no candidate records. No incident
                has been inferred.
              </p>
            </div>
          ) : (
            <ol className="mt-4 space-y-2">
              {orderedCandidates.map((candidate, index) => {
                const selected =
                  candidate.candidate_id === selectedCandidateId;
                return (
                  <li key={candidate.candidate_id}>
                    <button
                      aria-current={selected ? "true" : undefined}
                      className={`w-full rounded-lg border p-3 text-left transition ${
                        selected
                          ? "border-sky-300/20 bg-sky-300/[0.06]"
                          : "border-line bg-[#09121f]/60 hover:border-slate-600"
                      }`}
                      onClick={() =>
                        setSelectedCandidateId(candidate.candidate_id)
                      }
                      type="button"
                    >
                      <span className="flex items-start justify-between gap-3">
                        <span className="min-w-0">
                          <span className="block text-xs font-semibold text-white">
                            Candidate {index + 1}
                          </span>
                          <span className="mt-1 block font-mono text-[10px] text-slate-500">
                            {formatTimestamp(candidate.start_timestamp_seconds)}
                            {" – "}
                            {formatTimestamp(candidate.end_timestamp_seconds)}
                          </span>
                        </span>
                        <CandidateStatus candidate={candidate} />
                      </span>
                      <span className="mt-2 block truncate text-[10px] text-slate-400">
                        Tracks {candidate.involved_track_ids.join(", ") || "not supplied"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          )}
        </div>

        {selectedCandidate ? (
          <CandidateEvidence
            candidate={selectedCandidate}
            frame={selectedFrame}
            frames={frames}
            frameOffset={frameOffset}
            frameError={frameError}
            framesLoading={framesLoading}
            framePageCount={framePageCount}
            currentFramePage={currentFramePage}
            totalFrames={results.total_frames}
            playbackError={playbackError}
            streamReady={streamReady}
            streamUrl={streamUrl}
            playerRef={playerRef}
            onPreviousFrame={() =>
              setSelectedFrameIndex((current) => Math.max(0, current - 1))
            }
            onNextFrame={() =>
              setSelectedFrameIndex((current) =>
                Math.min(frames.length - 1, current + 1),
              )
            }
            onPreviousPage={() => void changeFramePage(-1)}
            onNextPage={() => void changeFramePage(1)}
            onRetryEvidence={() =>
              void loadFramePage(frameOffset, selectedCandidate)
            }
            onPlaybackError={setPlaybackError}
          />
        ) : (
          <div className="flex min-h-64 items-center justify-center rounded-xl border border-dashed border-line bg-panel p-6 text-center">
            <div>
              <ArrowLeftRight
                aria-hidden="true"
                className="mx-auto h-6 w-6 text-slate-600"
              />
              <p className="mt-3 text-sm text-slate-300">
                Select a candidate to inspect evidence
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function PageBackLink() {
  return (
    <Link
      className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 transition hover:text-white"
      href="/dashboard/analysis"
    >
      <ArrowLeft aria-hidden="true" className="h-4 w-4" />
      Analysis history
    </Link>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-xl border border-line bg-panel p-4">
      <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-white">
        {value}
      </p>
    </article>
  );
}

function Metadata({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-slate-600">
        {label}
      </dt>
      <dd className="mt-1 break-words text-slate-300">{value}</dd>
    </div>
  );
}

function CandidateStatus({ candidate }: { candidate: AccidentCandidate }) {
  const verified = candidate.verification_status === "verified_detection";
  return (
    <span
      className={`shrink-0 rounded-full border px-2 py-1 text-[9px] font-medium ${
        verified
          ? "border-amber-200/10 bg-amber-300/[0.06] text-amber-200"
          : "border-sky-200/10 bg-sky-300/[0.06] text-sky-200"
      }`}
    >
      {candidateStatus(candidate)}
    </span>
  );
}

function CandidateEvidence({
  candidate,
  frame,
  frames,
  frameOffset,
  frameError,
  framesLoading,
  framePageCount,
  currentFramePage,
  totalFrames,
  playbackError,
  streamReady,
  streamUrl,
  playerRef,
  onPreviousFrame,
  onNextFrame,
  onPreviousPage,
  onNextPage,
  onRetryEvidence,
  onPlaybackError,
}: {
  candidate: AccidentCandidate;
  frame: AnalysisFrame | null;
  frames: AnalysisFrame[];
  frameOffset: number;
  frameError: string;
  framesLoading: boolean;
  framePageCount: number;
  currentFramePage: number;
  totalFrames: number;
  playbackError: string;
  streamReady: boolean;
  streamUrl: string;
  playerRef: RefObject<HTMLVideoElement | null>;
  onPreviousFrame: () => void;
  onNextFrame: () => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
  onRetryEvidence: () => void;
  onPlaybackError: (message: string) => void;
}) {
  const selectedIndex = frame ? frames.indexOf(frame) : -1;
  const verified = candidate.verification_status === "verified_detection";

  return (
    <article
      aria-label={`Evidence for ${candidate.candidate_id}`}
      className="min-w-0 rounded-xl border border-line bg-panel p-4 sm:p-5"
    >
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-white">Candidate evidence</h2>
            <CandidateStatus candidate={candidate} />
          </div>
          <p className="mt-1 break-all font-mono text-[10px] text-slate-500">
            {candidate.candidate_id}
          </p>
        </div>
        <span className="shrink-0 text-xs font-medium text-slate-300">
          {formatTimestamp(candidate.start_timestamp_seconds)}
          {" – "}
          {formatTimestamp(candidate.end_timestamp_seconds)}
        </span>
      </div>

      <p className="mt-4 rounded-lg border border-line bg-[#09121f]/70 p-3 text-xs leading-5 text-slate-300">
        {candidate.evidence_summary}
      </p>
      <p className="mt-2 text-[10px] leading-4 text-slate-500">
        {verified
          ? "This is the backend pipeline's verified_detection classification, not a human confirmation or a medical assessment."
          : "Suspected candidates require operator review and are not confirmed accidents."}
      </p>

      <dl className="mt-4 grid gap-3 rounded-lg border border-line bg-[#09121f]/50 p-3 text-xs sm:grid-cols-2">
        <Metadata
          label="Heuristic confidence score"
          value={`${candidate.confidence_score.toFixed(3)} · ${candidate.confidence_type}`}
        />
        <Metadata
          label="Involved tracks"
          value={candidate.involved_track_ids.join(", ") || "Not supplied"}
        />
        <Metadata
          label="Object labels"
          value={candidate.object_labels.join(", ") || "Not supplied"}
        />
        <Metadata
          label="Interaction observations / motion events"
          value={`${candidate.interaction_observations} / ${candidate.motion_events}`}
        />
      </dl>

      {candidate.evidence_references.length > 0 && (
        <details className="mt-3 rounded-lg border border-line bg-[#09121f]/50 px-3 py-2">
          <summary className="cursor-pointer text-[11px] font-medium text-slate-300">
            Backend evidence references ({candidate.evidence_references.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {candidate.evidence_references.map((reference, index) => (
              <li
                className="break-all font-mono text-[10px] text-slate-500"
                key={`${reference}-${index}`}
              >
                {reference}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="mt-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-semibold text-white">Evidence frames</h3>
            <p className="mt-1 text-[10px] text-slate-500">
              The API provides sampled detections, not still-image files. The
              protected video player seeks to the selected frame timestamp.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              aria-label="Previous evidence frame"
              className="rounded-md border border-line p-2 text-slate-300 hover:bg-white/[0.04] disabled:opacity-40"
              disabled={framesLoading || selectedIndex <= 0}
              onClick={onPreviousFrame}
              type="button"
            >
              <ChevronLeft aria-hidden="true" className="h-4 w-4" />
            </button>
            <button
              aria-label="Next evidence frame"
              className="rounded-md border border-line p-2 text-slate-300 hover:bg-white/[0.04] disabled:opacity-40"
              disabled={
                framesLoading ||
                selectedIndex < 0 ||
                selectedIndex >= frames.length - 1
              }
              onClick={onNextFrame}
              type="button"
            >
              <ChevronRight aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        </div>

        {framesLoading && (
          <p className="mt-3 flex items-center gap-2 text-xs text-slate-400" role="status">
            <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
            Loading sampled frame evidence
          </p>
        )}
        {frameError && (
          <div
            className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-300/15 bg-rose-300/[0.05] p-3"
            role="alert"
          >
            <span className="text-xs text-rose-200">{frameError}</span>
            <button
              className="text-xs font-medium text-white underline underline-offset-2"
              onClick={onRetryEvidence}
              type="button"
            >
              Retry evidence
            </button>
          </div>
        )}
        {!framesLoading && !frameError && !frame && (
          <p className="mt-3 rounded-lg border border-line bg-[#09121f]/60 p-3 text-xs text-slate-400">
            No sampled frame evidence was returned for this candidate.
          </p>
        )}

        {frame && !framesLoading && (
          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-[#09121f]/60 p-3">
              <p className="text-xs font-medium text-slate-200">
                Frame {frame.frame_index} · {formatTimestamp(frame.timestamp_seconds)}
              </p>
              <p className="text-[10px] text-slate-500">
                {frame.width} × {frame.height} · {frame.objects.length} detected objects
              </p>
            </div>

            {streamReady && streamUrl ? (
              <video
                className="aspect-video max-h-[60vh] w-full rounded-lg bg-black"
                controls
                onError={() =>
                  onPlaybackError(
                    "Protected video playback failed. The stream session may have expired or the file may be unavailable.",
                  )
                }
                onLoadedMetadata={() => {
                  if (playerRef.current && frame) {
                    playerRef.current.currentTime = frame.timestamp_seconds;
                  }
                }}
                playsInline
                preload="metadata"
                ref={playerRef}
                src={streamUrl}
              >
                Video playback is not supported by this browser.
              </video>
            ) : (
              <div
                className="rounded-lg border border-amber-200/10 bg-amber-300/[0.04] p-3 text-xs text-amber-100"
                role="status"
              >
                {playbackError || "Preparing protected video playback."}
              </div>
            )}
            {playbackError && streamReady && (
              <p
                className="rounded-lg border border-rose-300/15 bg-rose-300/[0.05] p-3 text-xs text-rose-200"
                role="alert"
              >
                {playbackError}
              </p>
            )}

            {frame.objects.length === 0 ? (
              <p className="rounded-lg border border-line bg-[#09121f]/60 p-3 text-xs text-slate-500">
                No tracked objects were returned for this sampled frame.
              </p>
            ) : (
              <ul aria-label="Objects detected in selected frame" className="space-y-2">
                {frame.objects.map((object, index) => (
                  <li
                    className="flex flex-col gap-2 rounded-lg border border-line bg-[#09121f]/60 p-3 sm:flex-row sm:items-center sm:justify-between"
                    key={`${object.track_id ?? "untracked"}-${index}`}
                  >
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                      <span className="font-semibold capitalize text-slate-100">
                        {object.label}
                      </span>
                      <span className="font-mono text-[10px] text-slate-500">
                        Track {object.track_id ?? "untracked"}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        Detector score {object.confidence.toFixed(3)}
                      </span>
                      <span className="font-mono text-[10px] text-slate-600">
                        Box [{object.bbox.map((coordinate) => coordinate.toFixed(0)).join(", ")}]
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {object.motion_anomaly
                        ? `Motion: ${object.motion_anomaly}`
                        : `State: ${object.motion_state}`}
                      {object.post_anomaly_behavior
                        ? ` · After anomaly: ${object.post_anomaly_behavior}`
                        : ""}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
              <p className="text-[10px] text-slate-500">
                Page {currentFramePage || 0} of {framePageCount} · frame offset{" "}
                {frameOffset}
              </p>
              <div className="flex gap-2">
                <button
                  className="rounded-md border border-line px-2.5 py-1.5 text-[10px] text-slate-300 hover:bg-white/[0.04] disabled:opacity-40"
                  disabled={framesLoading || frameOffset <= 0}
                  onClick={onPreviousPage}
                  type="button"
                >
                  Previous frames
                </button>
                <button
                  className="rounded-md border border-line px-2.5 py-1.5 text-[10px] text-slate-300 hover:bg-white/[0.04] disabled:opacity-40"
                  disabled={
                    framesLoading ||
                    frameOffset + FRAME_PAGE_SIZE >= totalFrames
                  }
                  onClick={onNextPage}
                  type="button"
                >
                  Next frames
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}
