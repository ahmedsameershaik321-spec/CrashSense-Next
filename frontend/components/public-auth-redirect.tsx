"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { authDestination } from "@/lib/auth";
import { useAuth } from "@/components/auth-provider";
import { LoadingState } from "@/components/loading-state";

export function PublicAuthRedirect({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (session) {
      router.replace(authDestination(session));
    }
  }, [router, session]);

  if (session) {
    return <LoadingState label="Preparing secure sign-in" />;
  }
  return children;
}
