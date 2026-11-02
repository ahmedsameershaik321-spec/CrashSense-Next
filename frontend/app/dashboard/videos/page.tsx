"use client";

import { LoadingState } from "@/components/loading-state";
import { useAuth } from "@/components/auth-provider";
import { VideoLibrary } from "@/components/video-library";

export default function VideoLibraryPage() {
  const { session } = useAuth();
  if (!session) {
    return <LoadingState label="Checking your video access" />;
  }
  return (
    <VideoLibrary
      accessToken={session.accessToken}
      userId={session.user.id}
    />
  );
}
