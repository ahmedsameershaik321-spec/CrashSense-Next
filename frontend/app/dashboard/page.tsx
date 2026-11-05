"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  FileVideo2,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  Video,
  type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { ApiError, getDashboardSummary, type DashboardSummary } from "@/lib/api";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unavailable";
  }
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function errorMessage(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 401) {
      return "Your session has expired. Sign in again to load monitoring data.";
    }
    if (reason.status === 403) {
      return "An active operator account is required to view monitoring data.";
    }
    return reason.message;
  }
  return "The dashboard summary could not be loaded. Check the connection and try again.";
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone,
  href,
  loading,
}: {
  label: string;
  value: number | null;
  detail: string;
  icon: LucideIcon;
  tone: string;
  href?: string;
  loading: boolean;
}) {
  const content = (
    <>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-400">{label}</p>
          {loading ? (
            <div
              aria-hidden="true"
              className="mt-4 h-8 w-20 animate-pulse rounded-md bg-white/[0.07]"
            />
          ) : (
            <p className="mt-3 text-3xl font-semibold tracking-tight text-white tabular-nums">
              {value === null ? "—" : value.toLocaleString()}
            </p>
          )}
        </div>
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${tone}`}>
          <Icon aria-hidden="true" className="h-[18px] w-[18px]" />
        </span>
      </div>
      <p className="mt-4 flex items-center justify-between gap-2 text-[11px] text-slate-500">
        {detail}
        {href && (
          <ArrowUpRight aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-slate-600" />
        )}
      </p>
    </>
  );

  return href ? (
    <Link
      className="group rounded-xl border border-line bg-panel p-5 transition duration-200 hover:-translate-y-0.5 hover:border-slate-600 hover:bg-[#101b2a] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      href={href}
    >
      {content}
    </Link>
  ) : (
    <article className="rounded-xl border border-line bg-panel p-5">{content}</article>
  );
}

function ActivityStatus({ status }: { status: string }) {
  const style =
    status === "completed"
      ? "border-emerald-200/10 bg-emerald-300/[0.06] text-emerald-200"
      : status === "failed"
        ? "border-rose-200/10 bg-rose-300/[0.06] text-rose-200"
        : status === "processing" || status === "queued"
          ? "border-amber-200/10 bg-amber-300/[0.06] text-amber-100"
          : "border-line bg-white/[0.025] text-slate-400";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium capitalize ${style}`}>
      {status === "completed" ? (
        <CheckCircle2 aria-hidden="true" className="h-3 w-3" />
      ) : status === "processing" || status === "queued" ? (
        <LoaderCircle aria-hidden="true" className="h-3 w-3" />
      ) : null}
      {status}
    </span>
  );
}

function RecentStatusChart({
  activities,
  loading,
  available,
}: {
  activities: DashboardSummary["recent_activity"];
  loading: boolean;
  available: boolean;
}) {
  const statuses = [
    { name: "Completed", status: "completed", tone: "bg-emerald-300" },
    { name: "Processing", status: "processing", tone: "bg-sky-300" },
    { name: "Queued", status: "queued", tone: "bg-amber-300" },
    { name: "Failed", status: "failed", tone: "bg-rose-300" },
    { name: "Cancelled", status: "cancelled", tone: "bg-slate-500" },
  ];
  const counts = statuses.map((item) => ({
    ...item,
    count: activities.filter((activity) => activity.status === item.status).length,
  }));
  const total = activities.length;

  return (
    <section
      aria-labelledby="recent-status-title"
      className="rounded-xl border border-line bg-panel p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Activity snapshot
          </p>
          <h2 className="mt-2 text-sm font-semibold text-white" id="recent-status-title">
            Recent job mix
          </h2>
        </div>
        <span className="rounded-md border border-line bg-white/[0.025] px-2 py-1 text-[10px] text-slate-400">
          Latest {loading ? "—" : total}
        </span>
      </div>
      {loading ? (
        <div aria-hidden="true" className="mt-6 h-3 animate-pulse rounded-full bg-white/[0.06]" />
      ) : !available ? (
        <p className="mt-6 rounded-lg border border-dashed border-line px-3 py-4 text-center text-xs text-slate-500">
          Status mix unavailable
        </p>
      ) : total ? (
        <div
          aria-label={`Analysis job statuses among the latest ${total} jobs`}
          className="mt-6 flex h-3 overflow-hidden rounded-full bg-white/[0.04]"
          role="img"
        >
          {counts.filter((item) => item.count > 0).map((item) => (
            <span
              className={`${item.tone} first:rounded-l-full last:rounded-r-full`}
              key={item.status}
              style={{ width: `${(item.count / total) * 100}%` }}
            />
          ))}
        </div>
      ) : (
        <p className="mt-6 rounded-lg border border-dashed border-line px-3 py-4 text-center text-xs text-slate-500">
          No activity to chart yet
        </p>
      )}
      <ul className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3">
        {counts.map((item) => (
          <li className="flex min-w-0 items-center justify-between gap-2" key={item.status}>
            <span className="flex min-w-0 items-center gap-2 text-[11px] text-slate-400">
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${item.tone}`} />
              <span className="truncate">{item.name}</span>
            </span>
            <span className="text-[11px] tabular-nums text-slate-300">
              {loading || !available ? "—" : item.count}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-5 border-t border-line pt-3 text-[10px] leading-4 text-slate-600">
        Distribution reflects only the latest{" "}
        {loading || !available ? "available" : total} analysis jobs.
      </p>
    </section>
  );
}

export default function DashboardPage() {
  const { session } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const accessToken = session?.accessToken;

  const loadSummary = useCallback(async () => {
    if (!accessToken) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      setSummary(await getDashboardSummary(accessToken));
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadSummary(), 0);
    return () => window.clearTimeout(timer);
  }, [loadSummary]);

  if (!session) {
    return (
      <div aria-label="Loading monitoring overview" className="space-y-6" role="status">
        <div className="h-40 animate-pulse rounded-2xl border border-line bg-panel" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <div className="h-36 animate-pulse rounded-xl border border-line bg-panel" key={index} />
          ))}
        </div>
      </div>
    );
  }

  const metrics = [
    {
      label: "Uploaded videos",
      value: summary?.total_videos ?? null,
      detail: "Protected footage in your library",
      icon: Video,
      tone: "border-sky-200/10 bg-sky-300/[0.07] text-sky-200",
      href: "/dashboard/videos",
    },
    {
      label: "Completed analyses",
      value: summary?.completed_analyses ?? null,
      detail: "Analysis jobs completed",
      icon: CheckCircle2,
      tone: "border-emerald-200/10 bg-emerald-300/[0.07] text-emerald-200",
      href: "/dashboard/analysis",
    },
    {
      label: "In progress",
      value: summary?.processing_analyses ?? null,
      detail: "Queued or processing now",
      icon: Clock3,
      tone: "border-amber-200/10 bg-amber-300/[0.07] text-amber-100",
      href: "/dashboard/analysis",
    },
    {
      label: "Accident candidates",
      value: summary?.detected_candidates ?? null,
      detail: "Heuristic detections across completed analyses",
      icon: ShieldAlert,
      tone: "border-violet-200/10 bg-violet-300/[0.07] text-violet-200",
      href: "/dashboard/analysis",
    },
  ];

  return (
    <div className="animate-fade-in space-y-7">
      <section className="relative overflow-hidden rounded-2xl border border-sky-300/10 bg-gradient-to-br from-[#11243a] via-[#0d1a2a] to-[#0b1522] p-6 shadow-panel sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-32 h-80 w-80 rounded-full bg-sky-400/[0.08] blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-1/3 h-px w-1/3 bg-gradient-to-r from-transparent via-sky-300/30 to-transparent" />
        <div className="relative flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
          <div>
            <p className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200/80">
              <span className="h-1.5 w-1.5 rounded-full bg-sky-300 shadow-[0_0_10px_rgba(125,211,252,0.8)]" />
              Monitoring overview
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Good to see you, {session.user.first_name}.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
              A live view of your protected footage and analysis activity. Candidate
              detections are visual evidence for operator review, not confirmed incidents.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div
              className={`inline-flex items-center gap-2 rounded-lg border px-3.5 py-2.5 text-xs font-medium ${
                summary?.analysis_worker_running
                  ? "border-emerald-200/10 bg-emerald-300/[0.05] text-emerald-200"
                  : loading
                    ? "border-line bg-white/[0.025] text-slate-400"
                    : "border-amber-200/10 bg-amber-300/[0.05] text-amber-100"
              }`}
              role="status"
            >
              {loading ? (
                <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : summary?.analysis_worker_running ? (
                <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
              ) : (
                <ArrowDownRight aria-hidden="true" className="h-4 w-4" />
              )}
              {loading
                ? "Checking system"
                : !summary
                  ? "System status unavailable"
                  : summary.analysis_worker_running
                    ? "Analysis worker online"
                    : "Analysis worker unavailable"}
            </div>
            <button
              className="inline-flex items-center gap-2 rounded-lg border border-line bg-white/[0.025] px-3.5 py-2.5 text-xs font-medium text-slate-200 transition hover:border-slate-600 hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50"
              disabled={loading}
              onClick={() => void loadSummary()}
              type="button"
            >
              <RefreshCw aria-hidden="true" className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>
      </section>

      {error && (
        <section
          className="flex flex-col justify-between gap-3 rounded-xl border border-rose-300/15 bg-rose-300/[0.05] p-4 sm:flex-row sm:items-center"
          role="alert"
        >
          <p className="text-sm text-rose-200">{error}</p>
          <button
            className="inline-flex w-fit items-center gap-2 rounded-lg border border-rose-200/15 px-3 py-2 text-xs font-medium text-rose-100 hover:bg-rose-200/[0.05]"
            onClick={() => void loadSummary()}
            type="button"
          >
            <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />
            Try again
          </button>
        </section>
      )}

      <section aria-label="Monitoring metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCard {...metric} loading={loading} key={metric.label} />
        ))}
      </section>

      <div className="grid items-start gap-5 2xl:grid-cols-[minmax(0,1.8fr)_minmax(270px,0.7fr)]">
        <section className="overflow-hidden rounded-xl border border-line bg-panel">
          <div className="flex flex-col justify-between gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-center sm:px-6">
            <div>
              <h2 className="text-sm font-semibold text-white">Recent analysis activity</h2>
              <p className="mt-1 text-xs text-slate-500">
                Latest jobs reported by the monitoring service
              </p>
            </div>
            <Link
              className="inline-flex w-fit items-center gap-1.5 text-xs font-medium text-sky-200 transition hover:text-white"
              href="/dashboard/analysis"
            >
              View review history
              <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
            </Link>
          </div>

          {loading ? (
            <div aria-label="Loading recent analysis activity" className="space-y-3 p-5" role="status">
              {Array.from({ length: 4 }, (_, index) => (
                <div className="h-12 animate-pulse rounded-lg bg-white/[0.035]" key={index} />
              ))}
            </div>
          ) : summary?.recent_activity.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left">
                <thead>
                  <tr className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-600">
                    <th className="px-6 py-3">Analysis / video</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Candidates</th>
                    <th className="px-6 py-3 text-right">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/70">
                  {summary.recent_activity.map((activity) => (
                    <tr className="transition hover:bg-white/[0.02]" key={activity.analysis_id}>
                      <td className="px-6 py-3.5">
                        <Link
                          className="group flex min-w-0 items-center gap-3"
                          href={`/dashboard/analysis/${encodeURIComponent(activity.analysis_id)}`}
                        >
                          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-sky-200/10 bg-sky-300/[0.05] text-sky-200">
                            <FileVideo2 aria-hidden="true" className="h-4 w-4" />
                          </span>
                          <span className="min-w-0">
                            <span className="block max-w-[330px] truncate text-xs font-medium text-slate-200 group-hover:text-white">
                              {activity.video_name}
                            </span>
                            <span className="mt-1 block font-mono text-[10px] text-slate-600">
                              {activity.analysis_id.slice(0, 8)}
                            </span>
                          </span>
                        </Link>
                      </td>
                      <td className="px-4 py-3.5">
                        <ActivityStatus status={activity.status} />
                      </td>
                      <td className="px-4 py-3.5 text-right text-xs tabular-nums text-slate-300">
                        {activity.candidate_count.toLocaleString()}
                      </td>
                      <td className="px-6 py-3.5 text-right text-[11px] text-slate-500">
                        {formatDate(activity.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : error ? (
            <div className="px-6 py-12 text-center">
              <p className="text-sm font-medium text-slate-200">Activity is unavailable</p>
              <p className="mt-2 text-xs text-slate-500">Retry the summary request to load recent analysis jobs.</p>
            </div>
          ) : (
            <div className="px-6 py-12 text-center">
              <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-white/[0.025] text-slate-500">
                <FileVideo2 aria-hidden="true" className="h-5 w-5" />
              </span>
              <h3 className="mt-4 text-sm font-medium text-slate-200">No analysis activity yet</h3>
              <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-slate-500">
                Upload road footage and start an analysis to see processing activity here.
              </p>
              <Link
                className="mt-5 inline-flex items-center gap-2 rounded-lg bg-accent-strong px-3.5 py-2.5 text-xs font-semibold text-white transition hover:bg-sky-500"
                href="/dashboard/videos"
              >
                Browse protected videos
                <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
              </Link>
            </div>
          )}
        </section>
        <RecentStatusChart
          activities={summary?.recent_activity ?? []}
          available={summary !== null}
          loading={loading}
        />
      </div>
    </div>
  );
}
