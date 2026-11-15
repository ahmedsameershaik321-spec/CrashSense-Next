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
    <main className="min-h-screen bg-canvas bg-auth-glow text-slate-900">
      <div className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col px-5 py-6 sm:px-8 lg:px-12">
        <header className="flex items-center justify-between">
          <Brand />
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
          >
            <ArrowLeft aria-hidden="true" className="h-4 w-4" />
            <span className="hidden sm:inline">Back to home</span>
          </Link>
        </header>

        <div className="grid flex-1 items-center gap-12 py-12 lg:grid-cols-[1fr_480px] lg:gap-20">
          <section className="mx-auto hidden max-w-xl lg:mx-0 lg:block">
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700">
              <span className="h-1.5 w-1.5 rounded-full bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,.8)]" />
              Monitoring workspace
            </div>
            <h1 className="text-5xl font-semibold leading-[1.08] tracking-[-0.04em] text-slate-900 xl:text-6xl">
              Video analysis
              <br />
              and review
              <span className="text-accent">.</span>
            </h1>
            <p className="mt-6 max-w-lg text-base leading-7 text-slate-600">
              Upload video, monitor analysis, and review sampled detection
              evidence.
            </p>
            <div className="mt-10 flex items-center gap-3 text-sm text-slate-600">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-slate-50 text-accent">
                <ShieldCheck aria-hidden="true" className="h-4 w-4" />
              </span>
              Candidate events require human review
            </div>
          </section>

          <section className="mx-auto w-full max-w-md">
            <div className="rounded-xl border border-line bg-panel/90 p-6 shadow-panel backdrop-blur sm:p-9">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">
                {eyebrow}
              </p>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-900 sm:text-[28px]">
                {title}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {description}
              </p>
              <div className="mt-8">{children}</div>
              <div className="mt-7 border-t border-line pt-5 text-center text-sm text-slate-600">
                {footer}
              </div>
            </div>
            <p className="mt-5 text-center text-xs leading-5 text-slate-600">
              Authorized access only. Your activity is governed by your
              organization&apos;s monitoring policy.
            </p>
          </section>
        </div>
        <footer className="flex items-center justify-between border-t border-line py-4 text-xs text-slate-600">
          <span>© {new Date().getFullYear()} CrashSense</span>
        </footer>
      </div>
    </main>
  );
}
