import { LoaderCircle } from "lucide-react";

export function LoadingState({ label }: { label: string }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-6 text-slate-600">
      <div
        className="flex items-center gap-3 rounded-xl border border-line bg-panel px-5 py-4 shadow-panel"
        role="status"
      >
        <LoaderCircle aria-hidden="true" className="h-5 w-5 animate-spin text-accent" />
        <span className="text-sm">{label}</span>
      </div>
    </main>
  );
}
