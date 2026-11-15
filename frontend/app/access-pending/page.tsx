"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Clock3, LogOut, ShieldAlert } from "lucide-react";
import { Brand } from "@/components/brand";
import { LoadingState } from "@/components/loading-state";
import { useAuth } from "@/components/auth-provider";
import { canAccessMonitoring } from "@/lib/auth";

export default function AccessPendingPage() {
  const { session, signOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!session) {
      router.replace("/login");
    } else if (canAccessMonitoring(session.user)) {
      router.replace("/dashboard");
    }
  }, [router, session]);

  if (!session || canAccessMonitoring(session.user)) {
    return <LoadingState label="Checking account status" />;
  }

  const isPending = session.user.role === "pending";
  const fullName = [session.user.first_name, session.user.last_name]
    .filter(Boolean)
    .join(" ");

  return (
    <main className="min-h-screen bg-canvas bg-auth-glow px-5 py-7 text-slate-900 sm:px-8">
      <div className="mx-auto max-w-3xl">
        <Brand />
        <section className="mt-16 rounded-xl border border-line bg-panel p-7 shadow-panel sm:mt-24 sm:p-10">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-amber-200 bg-amber-50 text-amber-800">
            {isPending ? (
              <Clock3 aria-hidden="true" className="h-5 w-5" />
            ) : (
              <ShieldAlert aria-hidden="true" className="h-5 w-5" />
            )}
          </span>
          <p className="mt-7 text-xs font-semibold uppercase tracking-[0.18em] text-amber-800">
            {isPending ? "Approval required" : "Access unavailable"}
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            {isPending ? "Your request is under review." : "Your account is inactive."}
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
            {isPending
              ? "Your account is pending administrator approval. Monitoring and protected operational features remain unavailable until an authorized administrator approves access."
              : "This account cannot access monitoring features. Contact your CrashSense administrator for assistance."}
          </p>
          <div className="mt-8 grid gap-3 rounded-xl border border-line bg-white p-4 text-sm sm:grid-cols-2">
            <div>
              <p className="text-xs text-slate-500">Signed in as</p>
              <p className="mt-1 font-medium text-slate-700">{fullName}</p>
              <p className="mt-0.5 text-slate-600">{session.user.email}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Current role</p>
              <p className="mt-1 font-medium capitalize text-slate-700">
                {session.user.role.replaceAll("_", " ")}
              </p>
              <p className="mt-0.5 text-slate-500">
                Account status: {session.user.is_active ? "active" : "inactive"}
              </p>
            </div>
          </div>
          <button
            className="mt-7 inline-flex items-center gap-2 rounded-lg border border-line px-4 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
            onClick={() => {
              signOut();
              router.replace("/login");
            }}
            type="button"
          >
            <LogOut aria-hidden="true" className="h-4 w-4" />
            Sign out
          </button>
        </section>
        <p className="mt-6 text-center text-xs text-slate-600">
          CrashSense enforces permissions on the API. This page is an additional
          interface restriction, not a substitute for server-side authorization.
        </p>
      </div>
    </main>
  );
}
