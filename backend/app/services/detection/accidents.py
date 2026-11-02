import math
from dataclasses import dataclass, field

from app.config import settings
from app.services.detection.tracking import TrackedObject


VEHICLE_LABELS = {"bicycle", "car", "motorcycle", "bus", "truck"}
MAX_EVIDENCE_REFERENCES = 20
POST_ANOMALY_RESPONSES = {"stopping", "sustained_deceleration"}
MotionEventKey = tuple[int, float, str]


@dataclass
class _Interaction:
    episode_id: int
    interaction_type: str
    first_timestamp: float
    last_timestamp: float
    last_observation_index: int
    observations: int = 0
    motion_events: int = 0
    labels: set[str] = field(default_factory=set)
    evidence_references: list[str] = field(default_factory=list)
    motion_event_track_ids: set[int] = field(default_factory=set)
    motion_event_keys: set[MotionEventKey] = field(default_factory=set)
    relative_motion_counts: dict[str, int] = field(default_factory=dict)
    previous_separation: float | None = None
    previous_motion: str | None = None
    previous_timestamp: float | None = None
    anomaly_observed_while_approaching: bool = False
    separated_after_anomaly: bool = False
    post_anomaly_behavior_counts: dict[str, int] = field(default_factory=dict)
    resolved_post_anomaly_track_ids: set[int] = field(default_factory=set)
    post_anomaly_response: bool = False


class AccidentCandidateDetector:
    """Accumulate close interactions with temporal motion anomalies."""

    def __init__(self) -> None:
        self._interactions: dict[tuple[int, int], _Interaction] = {}
        self._completed_interactions: list[
            tuple[tuple[int, int], _Interaction]
        ] = []
        self._pending_interactions: list[_Interaction] = []
        self._observation_index = 0
        self._next_episode_id = 1

    @staticmethod
    def _box_gap(first: tuple[float, ...], second: tuple[float, ...]) -> float:
        horizontal_gap = max(
            first[0] - second[2],
            second[0] - first[2],
            0.0,
        )
        vertical_gap = max(
            first[1] - second[3],
            second[1] - first[3],
            0.0,
        )
        return math.hypot(horizontal_gap, vertical_gap)

    @staticmethod
    def _center_separation(first: TrackedObject, second: TrackedObject) -> float:
        first_box = first.detection.bbox
        second_box = second.detection.bbox
        first_center = (
            (first_box[0] + first_box[2]) / 2,
            (first_box[1] + first_box[3]) / 2,
        )
        second_center = (
            (second_box[0] + second_box[2]) / 2,
            (second_box[1] + second_box[3]) / 2,
        )
        return math.hypot(
            first_center[0] - second_center[0],
            first_center[1] - second_center[1],
        )

    @staticmethod
    def _interaction_type(first: TrackedObject, second: TrackedObject) -> str:
        labels = {first.detection.label, second.detection.label}
        if "person" in labels:
            return "pedestrian_vehicle"
        return "vehicle_vehicle"

    @staticmethod
    def _add_reference(interaction: _Interaction, reference: str) -> None:
        if reference not in interaction.evidence_references:
            interaction.evidence_references.append(reference)
            interaction.evidence_references = interaction.evidence_references[
                -MAX_EVIDENCE_REFERENCES:
            ]

    @staticmethod
    def _record_post_anomaly_behavior(
        interaction: _Interaction,
        tracked_by_id: dict[int, TrackedObject],
        timestamp_seconds: float,
    ) -> None:
        for track_id in interaction.motion_event_track_ids:
            tracked = tracked_by_id.get(track_id)
            behavior = tracked.post_anomaly_behavior if tracked is not None else None
            if behavior is None:
                continue
            interaction.post_anomaly_behavior_counts[behavior] = (
                interaction.post_anomaly_behavior_counts.get(behavior, 0) + 1
            )
            AccidentCandidateDetector._add_reference(
                interaction,
                f"post-anomaly:{track_id}:{behavior}@{timestamp_seconds:.3f}s",
            )
            if behavior in POST_ANOMALY_RESPONSES:
                interaction.post_anomaly_response = True
            if behavior in {
                "speed_recovery",
                "sustained_deceleration",
                "stopping",
                "already_stationary",
            }:
                interaction.resolved_post_anomaly_track_ids.add(track_id)

    def observe(
        self,
        tracked_objects: list[TrackedObject],
        timestamp_seconds: float,
        frame_width: int,
        frame_height: int,
        frame_index: int,
    ) -> None:
        self._observation_index += 1
        tracked_by_id = {
            tracked.detection.track_id: tracked
            for tracked in tracked_objects
            if tracked.detection.track_id is not None
        }

        for interaction in self._interactions.values():
            self._record_post_anomaly_behavior(
                interaction,
                tracked_by_id,
                timestamp_seconds,
            )
        for interaction in self._pending_interactions:
            self._record_post_anomaly_behavior(
                interaction,
                tracked_by_id,
                timestamp_seconds,
            )

        monitoring_seconds = max(
            settings.detection_frame_interval_seconds * 3,
            3.0,
        )
        self._pending_interactions = [
            interaction
            for interaction in self._pending_interactions
            if (
                not interaction.motion_event_track_ids.issubset(
                    interaction.resolved_post_anomaly_track_ids
                )
                and timestamp_seconds - interaction.last_timestamp
                <= monitoring_seconds
            )
        ]

        diagonal = math.hypot(frame_width, frame_height)
        if diagonal <= 0:
            return

        close_pairs: dict[tuple[int, int], tuple[TrackedObject, TrackedObject]] = {}
        for index, first in enumerate(tracked_objects):
            first_id = first.detection.track_id
            if first_id is None:
                continue

            for second in tracked_objects[index + 1:]:
                second_id = second.detection.track_id
                if second_id is None:
                    continue
                if not (
                    first.detection.label in VEHICLE_LABELS
                    or second.detection.label in VEHICLE_LABELS
                ):
                    continue
                if first_id == second_id:
                    continue

                gap_ratio = (
                    self._box_gap(first.detection.bbox, second.detection.bbox)
                    / diagonal
                )
                if gap_ratio <= settings.detection_interaction_distance_ratio:
                    close_pairs[tuple(sorted((first_id, second_id)))] = (
                        first,
                        second,
                    )

        for key, interaction in list(self._interactions.items()):
            if key not in close_pairs:
                self._completed_interactions.append((key, interaction))
                if (
                    interaction.motion_event_track_ids
                    and not interaction.motion_event_track_ids.issubset(
                        interaction.resolved_post_anomaly_track_ids
                    )
                ):
                    self._pending_interactions.append(interaction)
                del self._interactions[key]

        for key, (first, second) in close_pairs.items():
            interaction = self._interactions.get(key)
            if interaction is None:
                interaction = _Interaction(
                    episode_id=self._next_episode_id,
                    interaction_type=self._interaction_type(first, second),
                    first_timestamp=timestamp_seconds,
                    last_timestamp=timestamp_seconds,
                    last_observation_index=self._observation_index,
                )
                self._interactions[key] = interaction
                self._next_episode_id += 1

            interaction.observations += 1
            interaction.last_timestamp = timestamp_seconds
            interaction.last_observation_index = self._observation_index
            interaction.labels.update(
                (first.detection.label, second.detection.label)
            )

            separation = self._center_separation(first, second)
            relative_motion: str | None = None
            if (
                interaction.previous_separation is not None
                and interaction.previous_timestamp is not None
            ):
                elapsed = timestamp_seconds - interaction.previous_timestamp
                if elapsed > 0:
                    separation_rate = (
                        separation - interaction.previous_separation
                    ) / elapsed
                    if separation_rate < -settings.detection_min_speed_pixels_per_second:
                        relative_motion = "approaching"
                    elif separation_rate > settings.detection_min_speed_pixels_per_second:
                        relative_motion = "separating"
                    else:
                        relative_motion = "maintaining"
                    interaction.relative_motion_counts[relative_motion] = (
                        interaction.relative_motion_counts.get(relative_motion, 0) + 1
                    )
                    if relative_motion != interaction.previous_motion:
                        self._add_reference(
                            interaction,
                            f"pair-motion:{relative_motion}:"
                            f"separation={separation:.2f}px:"
                            f"rate={separation_rate:.2f}px/s@"
                            f"{timestamp_seconds:.3f}s",
                        )
                    if (
                        interaction.motion_event_track_ids
                        and relative_motion == "separating"
                    ):
                        interaction.separated_after_anomaly = True

            interaction.previous_separation = separation
            interaction.previous_motion = relative_motion
            interaction.previous_timestamp = timestamp_seconds

            anomalies = [
                obj
                for obj in (first, second)
                if obj.motion_anomaly is not None
            ]
            if anomalies:
                for obj in anomalies:
                    track_id = obj.detection.track_id
                    if track_id is not None:
                        interaction.motion_event_track_ids.add(track_id)
                        event_key = (
                            track_id,
                            float(timestamp_seconds),
                            obj.motion_anomaly,
                        )
                        if event_key not in interaction.motion_event_keys:
                            interaction.motion_event_keys.add(event_key)
                            interaction.motion_events += 1
                            self._add_reference(
                                interaction,
                                f"motion-event:track:{track_id}:"
                                f"{obj.motion_anomaly}@{event_key[1]:.3f}s:"
                                f"pair:{key[0]}-{key[1]}:frame:{frame_index}",
                            )
                if relative_motion == "approaching":
                    interaction.anomaly_observed_while_approaching = True
                self._add_reference(
                    interaction,
                    f"frame:{frame_index}@{timestamp_seconds:.3f}s",
                )

    @staticmethod
    def _has_temporal_response(interaction: _Interaction) -> bool:
        return (
            (
                interaction.separated_after_anomaly
                and interaction.anomaly_observed_while_approaching
            )
            or interaction.post_anomaly_response
        )

    @staticmethod
    def _group_overlapping_candidates(candidates: list[dict]) -> list[dict]:
        parents = list(range(len(candidates)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(first: int, second: int) -> None:
            first_root = find(first)
            second_root = find(second)
            if first_root != second_root:
                parents[second_root] = first_root

        for first_index, first in enumerate(candidates):
            first_tracks = set(first["involved_track_ids"])
            for second_index in range(first_index + 1, len(candidates)):
                second = candidates[second_index]
                overlaps = (
                    first["start_timestamp_seconds"]
                    <= second["end_timestamp_seconds"]
                    and second["start_timestamp_seconds"]
                    <= first["end_timestamp_seconds"]
                )
                if overlaps and first_tracks.intersection(
                    second["involved_track_ids"]
                ):
                    union(first_index, second_index)

        components: dict[int, list[dict]] = {}
        for index, candidate in enumerate(candidates):
            components.setdefault(find(index), []).append(candidate)

        grouped: list[dict] = []
        for component in components.values():
            if len(component) == 1:
                grouped.append(component[0])
                continue

            component.sort(
                key=lambda candidate: (
                    candidate["start_timestamp_seconds"],
                    candidate["candidate_id"],
                )
            )
            track_ids = sorted({
                track_id
                for candidate in component
                for track_id in candidate["involved_track_ids"]
            })
            episode_details = []
            references = []
            labels = set()
            interaction_types = set()
            motion_event_keys: set[MotionEventKey] = set()
            for candidate in component:
                episode_event_keys = sorted(candidate["_motion_event_keys"])
                episode_details.append(
                    f"{candidate['candidate_id']} "
                    f"[{candidate['start_timestamp_seconds']:.3f}-"
                    f"{candidate['end_timestamp_seconds']:.3f}s; "
                    f"type={candidate['interaction_type']}; "
                    f"{candidate['verification_status']}; "
                    f"confidence={candidate['confidence_score']:.3f}; "
                    f"tracks={','.join(map(str, candidate['involved_track_ids']))}; "
                    f"events={episode_event_keys}]"
                )
                references.extend(candidate["evidence_references"])
                labels.update(candidate["object_labels"])
                interaction_types.add(candidate["interaction_type"])
                motion_event_keys.update(episode_event_keys)

            unique_references = list(dict.fromkeys(references))
            incident_id = (
                "incident:tracks:"
                + "-".join(map(str, track_ids))
                + ":episodes:"
                + "-".join(
                    candidate["candidate_id"].rsplit("episode:", 1)[-1]
                    for candidate in component
                )
            )
            grouped.append(
                {
                    "candidate_id": incident_id,
                    "start_timestamp_seconds": min(
                        candidate["start_timestamp_seconds"]
                        for candidate in component
                    ),
                    "end_timestamp_seconds": max(
                        candidate["end_timestamp_seconds"]
                        for candidate in component
                    ),
                    "involved_track_ids": track_ids,
                    "object_labels": sorted(labels),
                    "confidence_score": max(
                        candidate["confidence_score"] for candidate in component
                    ),
                    "confidence_type": "heuristic_temporal_evidence_score",
                    "verification_status": "suspected",
                    "evidence_summary": (
                        f"Grouped {len(component)} overlapping interaction episodes "
                        "sharing tracks. Interaction types: "
                        f"{', '.join(sorted(interaction_types))}. Episode evidence: "
                        + "; ".join(episode_details)
                        + ". Grouping does not confirm a collision or injury; "
                        "operator review is required."
                    ),
                    "evidence_references": unique_references,
                    "interaction_observations": sum(
                        candidate["interaction_observations"]
                        for candidate in component
                    ),
                    "motion_events": len(motion_event_keys),
                }
            )

        for candidate in grouped:
            candidate.pop("_motion_event_keys", None)
            candidate.pop("interaction_type", None)

        return sorted(
            grouped,
            key=lambda candidate: (
                candidate["start_timestamp_seconds"],
                candidate["candidate_id"],
            ),
        )

    def candidates(self) -> list[dict]:
        candidates: list[dict] = []
        episodes = [
            *self._completed_interactions,
            *self._interactions.items(),
        ]
        for (first_id, second_id), interaction in episodes:
            if (
                interaction.observations
                < settings.detection_min_candidate_observations
                or interaction.motion_events == 0
                or not self._has_temporal_response(interaction)
            ):
                continue

            verified = (
                interaction.observations
                >= settings.detection_min_verified_observations
                and interaction.motion_events >= settings.detection_min_motion_events
            )
            persistence_score = min(interaction.observations / 6, 1.0)
            motion_score = min(interaction.motion_events / 4, 1.0)
            confidence_score = round(
                min(0.95, 0.2 + 0.35 * persistence_score + 0.4 * motion_score),
                3,
            )
            status = "verified_detection" if verified else "suspected"
            relative_motion = ", ".join(
                f"{kind}={count}"
                for kind, count in sorted(interaction.relative_motion_counts.items())
            ) or "none"
            post_behavior = ", ".join(
                f"{kind}={count}"
                for kind, count in sorted(
                    interaction.post_anomaly_behavior_counts.items()
                )
            ) or "none"
            candidates.append(
                {
                    "candidate_id": (
                        f"tracks:{first_id}:{second_id}:"
                        f"episode:{interaction.episode_id}"
                    ),
                    "start_timestamp_seconds": interaction.first_timestamp,
                    "end_timestamp_seconds": interaction.last_timestamp,
                    "involved_track_ids": [first_id, second_id],
                    "object_labels": sorted(interaction.labels),
                    "confidence_score": confidence_score,
                    "confidence_type": "heuristic_temporal_evidence_score",
                    "verification_status": status,
                    "evidence_summary": (
                        "A close tracked interaction coincided with abnormal "
                        f"motion evidence ({interaction.motion_events} motion "
                        f"observations across {interaction.observations} frames). "
                        f"Interaction type: {interaction.interaction_type}. "
                        f"Pair motion observations: {relative_motion}. "
                        "Anomaly observed while approaching: "
                        f"{'yes' if interaction.anomaly_observed_while_approaching else 'no'}. "
                        f"Post-anomaly behavior: {post_behavior}. "
                        "This is not confirmation of a collision or injury; "
                        "operator review is required."
                    ),
                    "evidence_references": interaction.evidence_references,
                    "interaction_observations": interaction.observations,
                    "motion_events": interaction.motion_events,
                    "interaction_type": interaction.interaction_type,
                    "_motion_event_keys": set(interaction.motion_event_keys),
                }
            )

        return self._group_overlapping_candidates(candidates)
