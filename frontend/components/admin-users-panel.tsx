"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  UserCheck,
  UserMinus,
  UserRoundCog,
} from "lucide-react";
import {
  ApiError,
  approveAdminUser,
  listAdminUsers,
  updateAdminUserRole,
  updateAdminUserStatus,
  type AdminUser,
} from "@/lib/api";

const PAGE_SIZE = 20;
type OperationalRole = "monitoring_operator" | "administrator";

interface AdminUsersPanelProps {
  accessToken: string;
  currentUserId: string;
}

function messageForError(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 401) {
      return "Your session has expired. Sign in again to manage accounts.";
    }
    if (reason.status === 403) {
      return "Administrator access is required to manage users.";
    }
    return reason.message;
  }
  return "The user list could not be loaded. Check the connection and retry.";
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Unavailable"
    : new Intl.DateTimeFormat("en", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(parsed);
}

function statusLabel(user: AdminUser): string {
  if (user.role === "pending") {
    return "Pending approval";
  }
  return user.is_active ? "Active" : "Suspended";
}

export function AdminUsersPanel({
  accessToken,
  currentUserId,
}: AdminUsersPanelProps) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<Record<string, OperationalRole>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [offset, setOffset] = useState(0);
  const [busyUserId, setBusyUserId] = useState("");
  const [reloadVersion, setReloadVersion] = useState(0);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const page = await listAdminUsers(accessToken, PAGE_SIZE, offset);
      setUsers(page);
      setRoles((current) => {
        const next = { ...current };
        for (const user of page) {
          if (!next[user.id]) {
            next[user.id] =
              user.role === "administrator"
                ? "administrator"
                : "monitoring_operator";
          }
        }
        return next;
      });
    } catch (reason) {
      setUsers([]);
      setError(messageForError(reason));
    } finally {
      setLoading(false);
    }
  }, [accessToken, offset]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadUsers(), 0);
    return () => window.clearTimeout(timer);
  }, [loadUsers, reloadVersion]);

  const replaceUser = (updated: AdminUser) => {
    setUsers((current) =>
      current.map((user) => (user.id === updated.id ? updated : user)),
    );
    setNotice(`${updated.email} account was updated.`);
  };

  const approve = async (user: AdminUser) => {
    const role = roles[user.id] ?? "monitoring_operator";
    if (
      !window.confirm(
        `Approve ${user.email} and assign the ${role.replaceAll("_", " ")} role?`,
      )
    ) {
      return;
    }
    setBusyUserId(user.id);
    setError("");
    setNotice("");
    try {
      replaceUser(await approveAdminUser(accessToken, user.id, role));
    } catch (reason) {
      setError(messageForError(reason));
    } finally {
      setBusyUserId("");
    }
  };

  const changeRole = async (user: AdminUser) => {
    const role = roles[user.id] ?? "monitoring_operator";
    if (role === user.role) {
      return;
    }
    if (
      !window.confirm(
        `Change ${user.email}'s role to ${role.replaceAll("_", " ")}?`,
      )
    ) {
      return;
    }
    setBusyUserId(user.id);
    setError("");
    setNotice("");
    try {
      replaceUser(await updateAdminUserRole(accessToken, user.id, role));
    } catch (reason) {
      setError(messageForError(reason));
    } finally {
      setBusyUserId("");
    }
  };

  const changeStatus = async (user: AdminUser) => {
    const nextActive = !user.is_active;
    const action = nextActive ? "reactivate" : "suspend";
    if (!window.confirm(`${action[0].toUpperCase()}${action.slice(1)} ${user.email}?`)) {
      return;
    }
    setBusyUserId(user.id);
    setError("");
    setNotice("");
    try {
      replaceUser(
        await updateAdminUserStatus(accessToken, user.id, nextActive),
      );
    } catch (reason) {
      setError(messageForError(reason));
    } finally {
      setBusyUserId("");
    }
  };

  const hasNextPage = users.length === PAGE_SIZE;

  return (
    <div className="animate-fade-in">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200">
            <ShieldCheck aria-hidden="true" className="h-4 w-4" />
            Administrator
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            User management
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Review registrations, grant approved operational roles, and suspend
            or reactivate existing accounts. Changes are enforced by the API.
          </p>
        </div>
        <button
          className="inline-flex w-fit items-center gap-2 rounded-lg border border-line px-3 py-2 text-xs text-slate-200 hover:bg-white/[0.04] disabled:opacity-50"
          disabled={loading}
          onClick={() => setReloadVersion((current) => current + 1)}
          type="button"
        >
          <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />
          Refresh
        </button>
      </header>

      {notice && (
        <p
          className="mt-5 rounded-lg border border-emerald-200/10 bg-emerald-300/[0.05] px-3 py-2.5 text-xs text-emerald-200"
          role="status"
        >
          {notice}
        </p>
      )}
      {error && (
        <div
          className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-300/15 bg-rose-300/[0.04] px-3 py-2.5"
          role="alert"
        >
          <p className="flex items-center gap-2 text-xs text-rose-200">
            <AlertCircle aria-hidden="true" className="h-4 w-4 shrink-0" />
            {error}
          </p>
          <button
            className="rounded-md border border-line px-3 py-1.5 text-xs text-slate-200"
            onClick={() => setReloadVersion((current) => current + 1)}
            type="button"
          >
            Retry
          </button>
        </div>
      )}

      <section
        aria-label="Registered users"
        className="mt-6 overflow-hidden rounded-xl border border-line bg-panel"
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-4 sm:px-5">
          <div>
            <h2 className="text-sm font-semibold text-white">Registered accounts</h2>
            <p className="mt-1 text-[11px] text-slate-500">
              Showing records {users.length ? offset + 1 : 0}–
              {offset + users.length}
            </p>
          </div>
          <span className="rounded-full border border-line px-2.5 py-1 text-[10px] text-slate-400">
            {users.length} on this page
          </span>
        </div>

        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-2 text-xs text-slate-400" role="status">
            <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
            Loading registered accounts…
          </div>
        ) : !error && users.length === 0 ? (
          <div className="p-8 text-center">
            <UserRoundCog aria-hidden="true" className="mx-auto h-7 w-7 text-slate-600" />
            <p className="mt-3 text-sm font-medium text-slate-200">
              No accounts on this page
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {offset > 0
                ? "There are no more account records."
                : "No registered accounts were returned by the API."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] text-left text-xs">
              <thead className="bg-[#09121f]/70 text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-medium">Account</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Registered</th>
                  <th className="px-5 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {users.map((user) => {
                  const isPending = user.role === "pending";
                  const isBusy = busyUserId === user.id;
                  return (
                    <tr key={user.id}>
                      <td className="px-5 py-4">
                        <p className="font-medium text-slate-100">
                          {[user.first_name, user.last_name].filter(Boolean).join(" ")}
                          {user.id === currentUserId && (
                            <span className="ml-2 text-[10px] text-sky-300">(you)</span>
                          )}
                        </p>
                        <p className="mt-1 text-[11px] text-slate-500">{user.email}</p>
                        <p className="mt-1 text-[10px] text-slate-600">
                          Email {user.is_email_verified ? "verified" : "not verified"}
                        </p>
                      </td>
                      <td className="px-4 py-4">
                        <span
                          className={`rounded-full border px-2.5 py-1 text-[10px] ${
                            isPending
                              ? "border-amber-200/10 bg-amber-200/[0.04] text-amber-100"
                              : user.is_active
                                ? "border-emerald-200/10 bg-emerald-300/[0.04] text-emerald-200"
                                : "border-rose-200/10 bg-rose-300/[0.04] text-rose-200"
                          }`}
                        >
                          {statusLabel(user)}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        {isPending ? (
                          <label className="sr-only" htmlFor={`role-${user.id}`}>
                            Role to assign to {user.email}
                          </label>
                        ) : null}
                        <select
                          aria-label={`Role for ${user.email}`}
                          className="rounded-md border border-line bg-[#09121f] px-2 py-1.5 text-[11px] capitalize text-slate-200 disabled:opacity-60"
                          disabled={isBusy || (!isPending && user.id === currentUserId)}
                          id={`role-${user.id}`}
                          onChange={(event) =>
                            setRoles((current) => ({
                              ...current,
                              [user.id]:
                                event.target.value === "administrator"
                                  ? "administrator"
                                  : "monitoring_operator",
                            }))
                          }
                          value={
                            isPending
                              ? roles[user.id] ?? "monitoring_operator"
                              : roles[user.id] ?? user.role
                          }
                        >
                          {isPending && <option value="pending">pending</option>}
                          <option value="monitoring_operator">Monitoring operator</option>
                          <option value="administrator">Administrator</option>
                        </select>
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-slate-400">
                        {formatDate(user.created_at)}
                      </td>
                      <td className="px-5 py-4">
                        {isBusy ? (
                          <span className="inline-flex items-center gap-2 text-[10px] text-slate-400" role="status">
                            <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
                            Saving
                          </span>
                        ) : isPending ? (
                          <button
                            className="inline-flex items-center gap-1.5 rounded-md border border-sky-200/15 bg-sky-300/[0.05] px-2.5 py-1.5 text-[10px] font-medium text-sky-100 hover:bg-sky-300/[0.1]"
                            onClick={() => void approve(user)}
                            type="button"
                          >
                            <UserCheck aria-hidden="true" className="h-3.5 w-3.5" />
                            Approve
                          </button>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {user.role !== (roles[user.id] ?? user.role) &&
                              user.id !== currentUserId && (
                                <button
                                  className="rounded-md border border-line px-2.5 py-1.5 text-[10px] text-slate-200 hover:bg-white/[0.04]"
                                  onClick={() => void changeRole(user)}
                                  type="button"
                                >
                                  Save role
                                </button>
                              )}
                            {user.id !== currentUserId && (
                              <button
                                className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[10px] ${
                                  user.is_active
                                    ? "border-rose-200/10 text-rose-200 hover:bg-rose-300/[0.05]"
                                    : "border-emerald-200/10 text-emerald-200 hover:bg-emerald-300/[0.05]"
                                }`}
                                onClick={() => void changeStatus(user)}
                                type="button"
                              >
                                {user.is_active ? (
                                  <UserMinus aria-hidden="true" className="h-3.5 w-3.5" />
                                ) : (
                                  <UserCheck aria-hidden="true" className="h-3.5 w-3.5" />
                                )}
                                {user.is_active ? "Suspend" : "Reactivate"}
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-line px-4 py-3 sm:px-5">
          <p className="text-[10px] text-slate-500">Page {Math.floor(offset / PAGE_SIZE) + 1}</p>
          <div className="flex gap-2">
            <button
              aria-label="Previous user page"
              className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1.5 text-[10px] text-slate-300 disabled:opacity-40"
              disabled={loading || offset === 0}
              onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
              type="button"
            >
              <ChevronLeft aria-hidden="true" className="h-3.5 w-3.5" />
              Previous
            </button>
            <button
              aria-label="Next user page"
              className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1.5 text-[10px] text-slate-300 disabled:opacity-40"
              disabled={loading || !hasNextPage}
              onClick={() => setOffset((current) => current + PAGE_SIZE)}
              type="button"
            >
              Next
              <ChevronRight aria-hidden="true" className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
