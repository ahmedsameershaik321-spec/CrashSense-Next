"use client";

import { useParams } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import { LoadingState } from "@/components/loading-state";
import { VideoDetails } from "@/components/video-details";

export default function VideoDetailsPage() {
  const { videoId } = useParams<{ videoId: string }>();
  const { session } = useAuth();
  if (!session) {
    return <LoadingState label="Checking your video access" />;
  }
  return (
    <VideoDetails
      accessToken={session.accessToken}
      expiresInSeconds={session.expiresInSeconds ?? 900}
      userId={session.user.id}
      key={`${session.accessToken}:${videoId}`}
      videoId={videoId}
    />
  );
}
