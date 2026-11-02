"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AdminUsersPanel } from "@/components/admin-users-panel";
import { useAuth } from "@/components/auth-provider";
import { LoadingState } from "@/components/loading-state";

export default function AdminPage() {
  const { session } = useAuth();
  const router = useRouter();
  const isAdministrator = session?.user.role === "administrator";

  useEffect(() => {
    if (session && !isAdministrator) {
      router.replace("/dashboard");
    }
  }, [isAdministrator, router, session]);

  if (!session || !isAdministrator) {
    return <LoadingState label="Checking administrator access" />;
  }

  return (
    <AdminUsersPanel
      accessToken={session.accessToken}
      currentUserId={session.user.id}
    />
  );
}
