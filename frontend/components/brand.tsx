import Link from "next/link";
import { Activity } from "lucide-react";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link
      aria-label="CrashSense home"
      className="group inline-flex items-center gap-3"
      href="/"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-200 bg-blue-50 text-accent shadow-sm">
        <Activity aria-hidden="true" className="h-5 w-5" strokeWidth={2.2} />
      </span>
      {!compact && (
        <span className="leading-tight">
          <span className="block text-[15px] font-semibold tracking-[0.12em] text-slate-900">
            CRASHSENSE
          </span>
          <span className="mt-1 block text-[10px] font-medium uppercase tracking-[0.2em] text-slate-500">
            Road intelligence
          </span>
        </span>
      )}
    </Link>
  );
}
