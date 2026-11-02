import type { CurrentUser } from "@/lib/api";

export interface AuthSession {
  accessToken: string;
  user: CurrentUser;
  expiresInSeconds?: number;
}

export function canAccessMonitoring(user: CurrentUser | null): boolean {
  return Boolean(
    user?.is_active &&
      (user.role === "monitoring_operator" || user.role === "administrator"),
  );
}

export function authDestination(session: AuthSession | null): string {
  if (!session) {
    return "/login";
  }
  return canAccessMonitoring(session.user) ? "/dashboard" : "/access-pending";
}
