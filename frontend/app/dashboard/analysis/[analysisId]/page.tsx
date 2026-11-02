"use client";

import { useParams } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import { AnalysisResultsView } from "@/components/analysis-results";
import { LoadingState } from "@/components/loading-state";

export default function AnalysisResultsPage() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const { session } = useAuth();
  if (!session) {
    return <LoadingState label="Checking your analysis access" />;
  }
  return (
    <AnalysisResultsView
      accessToken={session.accessToken}
      analysisId={analysisId}
      expiresInSeconds={session.expiresInSeconds ?? 900}
      isAdministrator={session.user.role === "administrator"}
    />
  );
}
