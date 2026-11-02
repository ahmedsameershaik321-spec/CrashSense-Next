"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { authDestination, canAccessMonitoring } from "@/lib/auth";
import { useAuth } from "@/components/auth-provider";
import { LoadingState } from "@/components/loading-state";

export function AuthGate({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const destination = authDestination(session);
    if (destination !== "/dashboard") {
      router.replace(destination);
    }
  }, [router, session]);

  if (!session || !canAccessMonitoring(session.user)) {
    return <LoadingState label="Checking your access" />;
  }

  if (!pathname.startsWith("/dashboard")) {
    return <LoadingState label="Opening your workspace" />;
  }

  return children;
}
