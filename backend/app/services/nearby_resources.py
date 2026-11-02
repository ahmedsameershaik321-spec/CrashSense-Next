import math
from typing import Any

import httpx

from app.config import settings
from app.schemas.response import NearbyResource

OSM_ATTRIBUTION = "© OpenStreetMap contributors"
RESOURCE_TYPES = {
    "hospital",
    "clinic",
    "ambulance_station",
    "fire_station",
}


class ResourceLookupError(Exception):
    """Raised when the configured OpenStreetMap resource service is unavailable."""


def _distance_meters(
    latitude: float,
    longitude: float,
    other_latitude: float,
    other_longitude: float,
) -> float:
    earth_radius_meters = 6_371_000
    first_latitude = math.radians(latitude)
    second_latitude = math.radians(other_latitude)
    latitude_delta = math.radians(other_latitude - latitude)
    longitude_delta = math.radians(other_longitude - longitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(first_latitude)
        * math.cos(second_latitude)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * earth_radius_meters * math.asin(min(1, math.sqrt(haversine)))


def _resource_type(tags: dict[str, Any]) -> str | None:
    amenity = tags.get("amenity")
    if amenity in {"hospital", "clinic"}:
        return amenity
    emergency = tags.get("emergency")
    if emergency in {"ambulance_station", "fire_station"}:
        return emergency
    return None


def _address(tags: dict[str, Any]) -> str | None:
    components = [
        " ".join(
            str(value)
            for value in (tags.get("addr:housenumber"), tags.get("addr:street"))
            if value
        ),
        tags.get("addr:city"),
        tags.get("addr:postcode"),
    ]
    rendered = [str(component) for component in components if component]
    return ", ".join(rendered) or None


def _overpass_query(latitude: float, longitude: float, radius_meters: int) -> str:
    filters = [
        '["amenity"~"^(hospital|clinic)$"]',
        '["emergency"~"^(ambulance_station|fire_station)$"]',
    ]
    clauses = [
        f"{element}{filter_expression}(around:{radius_meters},{latitude:.7f},{longitude:.7f});"
        for filter_expression in filters
        for element in ("node", "way", "relation")
    ]
    return "[out:json];(" + "".join(clauses) + ");out center tags;"


def find_nearby_resources(
    latitude: float,
    longitude: float,
    radius_meters: int,
) -> list[NearbyResource]:
    try:
        with httpx.Client(
            timeout=settings.osm_overpass_timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = client.post(
                settings.osm_overpass_url,
                data={"data": _overpass_query(latitude, longitude, radius_meters)},
                headers={"User-Agent": "CrashSense/0.1 resource lookup"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ResourceLookupError(
            "Nearby OpenStreetMap resources could not be retrieved."
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise ResourceLookupError("OpenStreetMap returned an invalid resource response.")

    resources: dict[tuple[str, int], NearbyResource] = {}
    for element in payload["elements"]:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags")
        if not isinstance(tags, dict):
            continue
        category = _resource_type(tags)
        osm_type = element.get("type")
        osm_id = element.get("id")
        point = element if "lat" in element and "lon" in element else element.get("center")
        if (
            category not in RESOURCE_TYPES
            or osm_type not in {"node", "way", "relation"}
            or not isinstance(osm_id, int)
            or not isinstance(point, dict)
        ):
            continue
        resource_latitude = point.get("lat")
        resource_longitude = point.get("lon")
        if (
            not isinstance(resource_latitude, (int, float))
            or not isinstance(resource_longitude, (int, float))
            or not math.isfinite(resource_latitude)
            or not math.isfinite(resource_longitude)
        ):
            continue
        distance = _distance_meters(
            latitude,
            longitude,
            float(resource_latitude),
            float(resource_longitude),
        )
        if distance > radius_meters:
            continue
        resources[(osm_type, osm_id)] = NearbyResource(
            osm_type=osm_type,
            osm_id=osm_id,
            resource_type=category,
            name=str(tags.get("name") or f"Unnamed {category.replace('_', ' ')}"),
            latitude=float(resource_latitude),
            longitude=float(resource_longitude),
            distance_meters=round(distance, 1),
            address=_address(tags),
        )
    return sorted(resources.values(), key=lambda resource: resource.distance_meters)

