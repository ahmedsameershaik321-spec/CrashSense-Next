"use client";

import dynamic from "next/dynamic";
import type { NearbyResource } from "@/lib/api";

interface ResourceMapProps {
  latitude: number;
  longitude: number;
  cameraName: string;
  resources: NearbyResource[];
  candidateLabel: string;
}

const IncidentResourceMap = dynamic(
  () =>
    import("@/components/incident-resource-map").then(
      (module) => module.IncidentResourceMap,
    ),
  {
    ssr: false,
    loading: () => (
      <div
        aria-label="Loading map"
        className="h-80 animate-pulse rounded-lg border border-line bg-[#09121f]"
        role="status"
      />
    ),
  },
);

export function ResourceMap(props: ResourceMapProps) {
  return <IncidentResourceMap {...props} />;
}
