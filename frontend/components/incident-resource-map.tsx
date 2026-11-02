"use client";

import { useEffect, useMemo } from "react";
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import type { LatLngExpression, LatLngTuple } from "leaflet";
import type { NearbyResource } from "@/lib/api";

interface IncidentResourceMapProps {
  latitude: number;
  longitude: number;
  cameraName: string;
  resources: NearbyResource[];
  candidateLabel: string;
}

function FitMarkers({
  center,
  positions,
}: {
  center: LatLngExpression;
  positions: LatLngTuple[];
}) {
  const map = useMap();

  useEffect(() => {
    if (positions.length > 1) {
      map.fitBounds(positions, { padding: [28, 28], maxZoom: 14 });
    } else {
      map.setView(center, 13);
    }
  }, [center, map, positions]);

  return null;
}

export function IncidentResourceMap({
  latitude,
  longitude,
  cameraName,
  resources,
  candidateLabel,
}: IncidentResourceMapProps) {
  const center: LatLngExpression = [latitude, longitude];
  const positions = useMemo<LatLngTuple[]>(
    () => [
      [latitude, longitude],
      ...resources.map(
        (resource): LatLngTuple => [resource.latitude, resource.longitude],
      ),
    ],
    [latitude, longitude, resources],
  );

  return (
    <MapContainer
      aria-label="Map of the registered camera and nearby mapped resources"
      center={center}
      className="h-80 w-full rounded-lg"
      scrollWheelZoom={false}
      zoom={13}
    >
      <FitMarkers center={center} positions={positions} />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <CircleMarker
        center={[latitude, longitude]}
        pathOptions={{ color: "#38bdf8", fillColor: "#38bdf8", fillOpacity: 0.9 }}
        radius={9}
      >
        <Popup>
          <strong>{cameraName}</strong>
          <br />
          {candidateLabel}
          <br />
          Approximate camera location, not a verified incident point.
        </Popup>
      </CircleMarker>
      {resources.map((resource) => (
        <CircleMarker
          center={[resource.latitude, resource.longitude]}
          key={`${resource.osm_type}-${resource.osm_id}`}
          pathOptions={{
            color: "#34d399",
            fillColor: "#34d399",
            fillOpacity: 0.8,
          }}
          radius={7}
        >
          <Popup>
            <strong>{resource.name}</strong>
            <br />
            {resource.resource_type.replaceAll("_", " ")}
            <br />
            {(resource.distance_meters / 1000).toFixed(2)} km from camera
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
