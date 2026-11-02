"use client";

import { useAuth } from "@/components/auth-provider";
import { AnalysisHistory } from "@/components/analysis-history";
import { LoadingState } from "@/components/loading-state";

export default function AnalysisHistoryPage() {
  const { session } = useAuth();
  if (!session) {
    return <LoadingState label="Checking your analysis access" />;
  }
  return (
    <AnalysisHistory accessToken={session.accessToken} userId={session.user.id} />
  );
}
