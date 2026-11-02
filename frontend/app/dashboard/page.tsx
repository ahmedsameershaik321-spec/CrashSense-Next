"use client";

import {
  ArrowUpRight,
  BadgeCheck,
  CalendarDays,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { LoadingState } from "@/components/loading-state";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unavailable";
  }
  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

export default function DashboardPage() {
  const { session } = useAuth();
  if (!session) {
    return <LoadingState label="Loading your dashboard" />;
  }

  const { user } = session;
  const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ");
  const roleLabel = user.role.replaceAll("_", " ");

  const cards = [
    {
      label: "Access role",
      value: roleLabel,
      detail:
        user.role === "administrator"
          ? "Administrator permissions"
          : "Monitoring operator permissions",
      icon: ShieldCheck,
      tone: "text-sky-200 bg-sky-300/[0.08] border-sky-200/10",
    },
    {
      label: "Account status",
      value: user.is_active ? "Active" : "Inactive",
      detail: user.is_email_verified
        ? "Email address verified"
        : "Email verification not recorded",
      icon: BadgeCheck,
      tone: user.is_active
        ? "text-emerald-200 bg-emerald-300/[0.07] border-emerald-200/10"
        : "text-amber-200 bg-amber-300/[0.07] border-amber-200/10",
    },
    {
      label: "Member since",
      value: formatDate(user.created_at),
      detail: "CrashSense account creation",
      icon: CalendarDays,
      tone: "text-violet-200 bg-violet-300/[0.07] border-violet-200/10",
    },
  ];

  return (
    <div className="animate-fade-in">
      <section className="relative overflow-hidden rounded-2xl border border-sky-300/10 bg-gradient-to-br from-[#10233a] via-[#0e1b2b] to-[#0c1624] p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-10 -top-32 h-72 w-72 rounded-full bg-sky-400/[0.07] blur-3xl" />
        <div className="relative flex flex-col justify-between gap-7 md:flex-row md:items-end">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-sky-200/80">
              <span className="h-1.5 w-1.5 rounded-full bg-sky-300" />
              Operations overview
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Good to see you, {user.first_name}.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
              Your CrashSense workspace is ready. Account details below are
              loaded directly from your authenticated profile.
            </p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-lg border border-emerald-200/10 bg-emerald-300/[0.05] px-3.5 py-2.5 text-xs font-medium text-emerald-200">
            <ShieldCheck aria-hidden="true" className="h-4 w-4" />
            Approved access
          </div>
        </div>
      </section>

      <section aria-label="Account summary" className="mt-7 grid gap-4 md:grid-cols-3">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <article
              className="rounded-xl border border-line bg-panel p-5 transition duration-200 hover:-translate-y-0.5 hover:border-slate-600"
              key={card.label}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-medium text-slate-500">
                    {card.label}
                  </p>
                  <p className="mt-3 text-xl font-semibold capitalize tracking-tight text-white">
                    {card.value}
                  </p>
                  <p className="mt-1.5 text-xs text-slate-500">{card.detail}</p>
                </div>
                <span
                  className={`flex h-10 w-10 items-center justify-center rounded-lg border ${card.tone}`}
                >
                  <Icon aria-hidden="true" className="h-[18px] w-[18px]" />
                </span>
              </div>
            </article>
          );
        })}
      </section>

      <section className="mt-8 grid gap-5 xl:grid-cols-[1.4fr_0.8fr]">
        <article className="rounded-xl border border-line bg-panel p-5 sm:p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-semibold text-white">Your workspace</p>
              <p className="mt-1 text-xs text-slate-500">
                Monitoring tools will appear here as they are enabled.
              </p>
            </div>
            <span className="rounded-md border border-line bg-white/[0.02] px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">
              Foundation
            </span>
          </div>
          <div className="mt-6 flex min-h-44 flex-col items-center justify-center rounded-xl border border-dashed border-line bg-[#0a121e]/70 px-6 py-7 text-center">
            <span className="flex h-11 w-11 items-center justify-center rounded-full border border-line bg-white/[0.025] text-slate-500">
              <ArrowUpRight aria-hidden="true" className="h-5 w-5" />
            </span>
            <h2 className="mt-4 text-sm font-medium text-slate-200">
              Analysis overview is not connected yet
            </h2>
            <p className="mt-2 max-w-md text-xs leading-5 text-slate-500">
              The backend currently provides video-specific analysis endpoints,
              not an account-wide dashboard feed. No operational counts are
              shown until a supported summary endpoint is available.
            </p>
          </div>
        </article>

        <article className="rounded-xl border border-line bg-panel p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-sky-200/10 bg-sky-300/[0.07] text-sky-200">
              <UserRound aria-hidden="true" className="h-[18px] w-[18px]" />
            </span>
            <div>
              <h2 className="text-sm font-semibold text-white">Your profile</h2>
              <p className="mt-1 text-xs text-slate-500">
                Authenticated account details
              </p>
            </div>
          </div>
          <dl className="mt-6 space-y-4">
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-600">
                Name
              </dt>
              <dd className="mt-1 text-sm text-slate-200">{fullName}</dd>
            </div>
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-600">
                Email
              </dt>
              <dd className="mt-1 break-all text-sm text-slate-200">
                {user.email}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-600">
                Account ID
              </dt>
              <dd className="mt-1 break-all font-mono text-xs text-slate-400">
                {user.id}
              </dd>
            </div>
            {user.approved_at && (
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-600">
                  Approved
                </dt>
                <dd className="mt-1 text-sm text-slate-200">
                  {formatDate(user.approved_at)}
                </dd>
              </div>
            )}
          </dl>
        </article>
      </section>
    </div>
  );
}
