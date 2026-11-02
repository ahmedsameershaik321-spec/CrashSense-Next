import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { Brand } from "@/components/brand";

interface AuthFrameProps {
  eyebrow: string;
  title: string;
  description: string;
  footer: ReactNode;
  children: ReactNode;
}

export function AuthFrame({
  eyebrow,
  title,
  description,
  footer,
  children,
}: AuthFrameProps) {
  return (
    <main className="min-h-screen bg-canvas bg-auth-glow text-white">
      <div className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col px-5 py-6 sm:px-8 lg:px-12">
        <header className="flex items-center justify-between">
          <Brand />
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 transition hover:bg-white/5 hover:text-white"
          >
            <ArrowLeft aria-hidden="true" className="h-4 w-4" />
            <span className="hidden sm:inline">Back to home</span>
          </Link>
        </header>

        <div className="grid flex-1 items-center gap-12 py-12 lg:grid-cols-[1fr_480px] lg:gap-20">
          <section className="mx-auto hidden max-w-xl lg:mx-0 lg:block">
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-sky-300/15 bg-sky-400/[0.06] px-3 py-1.5 text-xs font-medium text-sky-200">
              <span className="h-1.5 w-1.5 rounded-full bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,.8)]" />
              Intelligent road incident monitoring
            </div>
            <h1 className="text-5xl font-semibold leading-[1.08] tracking-[-0.04em] text-white xl:text-6xl">
              A clearer view
              <br />
              of every moment
              <span className="text-accent">.</span>
            </h1>
            <p className="mt-6 max-w-lg text-base leading-7 text-slate-400">
              Bring video intelligence and human review together in one
              considered workspace for safer, faster incident awareness.
            </p>
            <div className="mt-10 flex items-center gap-3 text-sm text-slate-400">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-white/[0.03] text-accent">
                <ShieldCheck aria-hidden="true" className="h-4 w-4" />
              </span>
              Protected access for approved monitoring teams
            </div>
          </section>

          <section className="mx-auto w-full max-w-md">
            <div className="rounded-2xl border border-white/[0.08] bg-panel/90 p-6 shadow-panel backdrop-blur sm:p-9">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">
                {eyebrow}
              </p>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white sm:text-[28px]">
                {title}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                {description}
              </p>
              <div className="mt-8">{children}</div>
              <div className="mt-7 border-t border-line pt-5 text-center text-sm text-slate-400">
                {footer}
              </div>
            </div>
            <p className="mt-5 text-center text-xs leading-5 text-slate-600">
              Authorized access only. Your activity is governed by your
              organization&apos;s monitoring policy.
            </p>
          </section>
        </div>
        <footer className="flex items-center justify-between border-t border-white/[0.06] py-4 text-xs text-slate-600">
          <span>© {new Date().getFullYear()} CrashSense</span>
          <span>Built for a safer road network</span>
        </footer>
      </div>
    </main>
  );
}
