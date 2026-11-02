"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Bell,
  ChevronLeft,
  CircleHelp,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  Video,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Brand } from "@/components/brand";
import { useAuth } from "@/components/auth-provider";

const navigation = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard, active: true },
  { label: "Video library", href: "/dashboard/videos", icon: Video, active: false },
];

const monitoringNavigation = [
  { label: "Incident review", href: "/dashboard/analysis", icon: Activity },
];

export function DashboardShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, signOut } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  if (!session) {
    return null;
  }

  const fullName = [session.user.first_name, session.user.last_name]
    .filter(Boolean)
    .join(" ");
  const initials = [session.user.first_name, session.user.last_name]
    .filter(Boolean)
    .map((part) => part?.[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 2);

  function handleSignOut() {
    signOut();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen bg-canvas text-white">
      {mobileOpen && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
          type="button"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-line bg-[#0a121e] transition-all duration-200 ${
          mobileOpen
            ? "w-[270px] translate-x-0"
            : "w-[270px] -translate-x-full lg:translate-x-0"
        } ${collapsed ? "lg:w-[82px]" : "lg:w-[250px]"}`}
      >
        <div className="flex h-[76px] items-center justify-between border-b border-line px-5">
          <Brand compact={collapsed} />
          <button
            aria-label="Close navigation"
            className="rounded-lg p-2 text-slate-500 hover:bg-white/5 hover:text-white lg:hidden"
            onClick={() => setMobileOpen(false)}
            type="button"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
          {!collapsed && (
            <button
              aria-label="Collapse sidebar"
              className="hidden rounded-md p-1.5 text-slate-600 transition hover:bg-white/5 hover:text-slate-300 lg:block"
              onClick={() => setCollapsed(true)}
              type="button"
            >
              <ChevronLeft aria-hidden="true" className="h-4 w-4" />
            </button>
          )}
          {collapsed && (
            <button
              aria-label="Expand sidebar"
              className="hidden rounded-md p-1.5 text-slate-600 transition hover:bg-white/5 hover:text-slate-300 lg:block"
              onClick={() => setCollapsed(false)}
              type="button"
            >
              <Menu aria-hidden="true" className="h-4 w-4" />
            </button>
          )}
        </div>

        <nav aria-label="Main navigation" className="flex-1 space-y-7 px-3 py-6">
          <div>
            <p
              className={`mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600 ${
                collapsed ? "lg:hidden" : ""
              }`}
            >
              Workspace
            </p>
            {navigation.map((item) => {
              const Icon = item.icon;
              const active =
                item.href === "/dashboard"
                  ? pathname === item.href
                  : pathname.startsWith(item.href);
              return (
                <Link
                  aria-current={active ? "page" : undefined}
                  className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                    active
                      ? "bg-sky-400/[0.11] font-medium text-sky-200"
                      : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-100"
                  }`}
                  href={item.href}
                  key={item.href}
                  onClick={() => setMobileOpen(false)}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon aria-hidden="true" className="h-[18px] w-[18px] shrink-0" />
                  <span className={collapsed ? "lg:hidden" : ""}>{item.label}</span>
                  {active && !collapsed && (
                    <span className="ml-auto h-1.5 w-1.5 rounded-full bg-accent" />
                  )}
                </Link>
              );
            })}
          </div>

          <div>
            <p
              className={`mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600 ${
                collapsed ? "lg:hidden" : ""
              }`}
            >
              Monitoring
            </p>
            <div className="space-y-1">
              {monitoringNavigation.map((item) => {
                const Icon = item.icon;
                const active = pathname.startsWith(item.href);
                return (
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                      active
                        ? "bg-sky-400/[0.11] font-medium text-sky-200"
                        : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-100"
                    }`}
                    href={item.href}
                    key={item.href}
                    onClick={() => setMobileOpen(false)}
                    title={collapsed ? item.label : undefined}
                  >
                    <Icon
                      aria-hidden="true"
                      className="h-[18px] w-[18px] shrink-0"
                    />
                    <span className={collapsed ? "lg:hidden" : ""}>{item.label}</span>
                    {active && !collapsed && (
                      <span className="ml-auto h-1.5 w-1.5 rounded-full bg-accent" />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>

          {session.user.role === "administrator" && (
            <div>
              <p
                className={`mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600 ${
                  collapsed ? "lg:hidden" : ""
                }`}
              >
                Administration
              </p>
              <Link
                aria-current={
                  pathname.startsWith("/dashboard/admin") ? "page" : undefined
                }
                className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                  pathname.startsWith("/dashboard/admin")
                    ? "bg-sky-400/[0.11] font-medium text-sky-200"
                    : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-100"
                }`}
                href="/dashboard/admin"
                onClick={() => setMobileOpen(false)}
                title={collapsed ? "User management" : undefined}
              >
                <Settings aria-hidden="true" className="h-[18px] w-[18px] shrink-0" />
                <span className={collapsed ? "lg:hidden" : ""}>User management</span>
              </Link>
            </div>
          )}
        </nav>

        <div className="border-t border-line p-3">
          <div
            className={`mb-3 flex items-center gap-3 rounded-lg bg-white/[0.025] p-2.5 ${
              collapsed ? "lg:justify-center" : ""
            }`}
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-sky-300/15 bg-sky-300/[0.08] text-xs font-semibold text-sky-200">
              {initials || "CS"}
            </span>
            <div className={`min-w-0 ${collapsed ? "lg:hidden" : ""}`}>
              <p className="truncate text-xs font-medium text-slate-200">
                {fullName}
              </p>
              <p className="mt-0.5 truncate text-[10px] text-slate-500">
                {session.user.email}
              </p>
            </div>
          </div>
          <button
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400 transition hover:bg-rose-400/[0.07] hover:text-rose-200 ${
              collapsed ? "lg:justify-center" : ""
            }`}
            onClick={handleSignOut}
            title={collapsed ? "Sign out" : undefined}
            type="button"
          >
            <LogOut aria-hidden="true" className="h-[18px] w-[18px] shrink-0" />
            <span className={collapsed ? "lg:hidden" : ""}>Sign out</span>
          </button>
        </div>
      </aside>

      <div className={`min-h-screen transition-[padding] duration-200 ${collapsed ? "lg:pl-[82px]" : "lg:pl-[250px]"}`}>
        <header className="sticky top-0 z-20 flex h-[76px] items-center justify-between border-b border-line bg-canvas/90 px-5 backdrop-blur-xl sm:px-8">
          <div className="flex items-center gap-3">
            <button
              aria-label="Open navigation"
              className="rounded-lg border border-line p-2 text-slate-300 hover:bg-white/[0.04] lg:hidden"
              onClick={() => setMobileOpen(true)}
              type="button"
            >
              <Menu aria-hidden="true" className="h-4 w-4" />
            </button>
            <div>
              <p className="text-sm font-medium text-white">Monitoring workspace</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {pathname.startsWith("/dashboard/videos")
                  ? "Workspace / Video library"
                  : pathname.startsWith("/dashboard/analysis")
                    ? "Monitoring / Incident review"
                    : pathname.startsWith("/dashboard/admin")
                      ? "Administration / User management"
                      : "Workspace / Overview"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-2 rounded-full border border-emerald-300/10 bg-emerald-300/[0.05] px-3 py-1.5 text-[11px] font-medium text-emerald-200 sm:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
              Authorized session
            </span>
            <button
              aria-label="Notifications are not configured"
              className="rounded-lg border border-line p-2 text-slate-500"
              disabled
              title="Notifications are not configured"
              type="button"
            >
              <Bell aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1500px] p-5 sm:p-8 lg:p-10">
          {children}
          <footer className="mt-12 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5 text-[11px] text-slate-600">
            <span>CrashSense monitoring workspace</span>
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck aria-hidden="true" className="h-3.5 w-3.5" />
              API-enforced access controls
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CircleHelp aria-hidden="true" className="h-3.5 w-3.5" />
              Help &amp; guidance
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
