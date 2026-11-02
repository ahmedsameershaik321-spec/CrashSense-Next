import math
from dataclasses import dataclass

from app.config import settings
from app.services.detection.yolo import DetectedObject


@dataclass(frozen=True)
class TrackedObject:
    detection: DetectedObject
    speed_pixels_per_second: float | None
    motion_anomaly: str | None
    velocity_x_pixels_per_second: float | None = None
    velocity_y_pixels_per_second: float | None = None
    motion_state: str = "unknown"
    post_anomaly_behavior: str | None = None

    def as_evidence(self) -> dict:
        return {
            "track_id": self.detection.track_id,
            "class_id": self.detection.class_id,
            "label": self.detection.label,
            "confidence": self.detection.confidence,
            "bbox": list(self.detection.bbox),
            "speed_pixels_per_second": self.speed_pixels_per_second,
            "velocity_x_pixels_per_second": self.velocity_x_pixels_per_second,
            "velocity_y_pixels_per_second": self.velocity_y_pixels_per_second,
            "motion_anomaly": self.motion_anomaly,
            "motion_state": self.motion_state,
            "post_anomaly_behavior": self.post_anomaly_behavior,
        }


@dataclass
class _TrackState:
    center_x: float
    center_y: float
    timestamp: float
    velocity_x: float | None = None
    velocity_y: float | None = None
    speed: float | None = None
    ever_moved: bool = False
    post_anomaly_speed: float | None = None
    post_anomaly_deceleration_observations: int = 0


class TrajectoryTracker:
    """Derive approximate motion from IDs maintained by ByteTrack."""

    def __init__(self) -> None:
        self._states: dict[int, _TrackState] = {}

    def update(
        self,
        detections: list[DetectedObject],
        timestamp_seconds: float,
    ) -> list[TrackedObject]:
        tracked: list[TrackedObject] = []

        for detection in detections:
            track_id = detection.track_id
            if track_id is None:
                tracked.append(TrackedObject(detection, None, None))
                continue

            x1, y1, x2, y2 = detection.bbox
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            previous = self._states.get(track_id)
            speed: float | None = None
            anomaly: str | None = None
            velocity_x: float | None = None
            velocity_y: float | None = None
            ever_moved = previous.ever_moved if previous is not None else False
            post_anomaly_speed = (
                previous.post_anomaly_speed if previous is not None else None
            )
            post_anomaly_deceleration_observations = (
                previous.post_anomaly_deceleration_observations
                if previous is not None
                else 0
            )
            post_anomaly_behavior: str | None = None

            if previous is not None:
                elapsed = timestamp_seconds - previous.timestamp
                if elapsed > 0:
                    velocity_x = (center_x - previous.center_x) / elapsed
                    velocity_y = (center_y - previous.center_y) / elapsed
                    speed = math.hypot(velocity_x, velocity_y)

                    if (
                        previous.speed is not None
                        and previous.speed
                        >= settings.detection_min_speed_pixels_per_second
                        and speed
                        <= previous.speed * settings.detection_stop_speed_ratio
                    ):
                        anomaly = "sudden_deceleration"
                    elif (
                        previous.velocity_x is not None
                        and previous.velocity_y is not None
                        and speed
                        >= settings.detection_min_speed_pixels_per_second
                    ):
                        prior_speed = math.hypot(
                            previous.velocity_x,
                            previous.velocity_y,
                        )
                        if prior_speed >= settings.detection_min_speed_pixels_per_second:
                            dot = (
                                previous.velocity_x * velocity_x
                                + previous.velocity_y * velocity_y
                            ) / (prior_speed * speed)
                            if dot < -0.5:
                                anomaly = "abrupt_direction_change"

            minimum_speed = settings.detection_min_speed_pixels_per_second
            if speed is not None and speed >= minimum_speed:
                ever_moved = True

            if anomaly is not None:
                post_anomaly_speed = speed
                post_anomaly_deceleration_observations = 0
            elif (
                previous is not None
                and previous.post_anomaly_speed is not None
                and speed is not None
            ):
                if speed < minimum_speed:
                    post_anomaly_behavior = (
                        "stopping" if ever_moved else "already_stationary"
                    )
                elif previous.speed is not None and speed > previous.speed:
                    post_anomaly_behavior = "speed_recovery"
                    post_anomaly_speed = None
                    post_anomaly_deceleration_observations = 0
                elif previous.speed is not None and speed < previous.speed:
                    post_anomaly_deceleration_observations += 1
                    post_anomaly_behavior = (
                        "sustained_deceleration"
                        if post_anomaly_deceleration_observations >= 2
                        else "continued_movement"
                    )
                else:
                    post_anomaly_deceleration_observations = 0
                    post_anomaly_behavior = "continued_movement"

            if speed is None:
                motion_state = "unknown"
            elif speed >= minimum_speed:
                motion_state = "moving"
            else:
                motion_state = "stopping" if ever_moved else "already_stationary"

            self._states[track_id] = _TrackState(
                center_x=center_x,
                center_y=center_y,
                timestamp=timestamp_seconds,
                velocity_x=velocity_x,
                velocity_y=velocity_y,
                speed=speed,
                ever_moved=ever_moved,
                post_anomaly_speed=post_anomaly_speed,
                post_anomaly_deceleration_observations=(
                    post_anomaly_deceleration_observations
                ),
            )
            tracked.append(
                TrackedObject(
                    detection=detection,
                    speed_pixels_per_second=speed,
                    motion_anomaly=anomaly,
                    velocity_x_pixels_per_second=velocity_x,
                    velocity_y_pixels_per_second=velocity_y,
                    motion_state=motion_state,
                    post_anomaly_behavior=post_anomaly_behavior,
                )
            )

        retention_seconds = max(
            settings.detection_frame_interval_seconds * 3,
            3.0,
        )
        self._states = {
            track_id: state
            for track_id, state in self._states.items()
            if timestamp_seconds - state.timestamp <= retention_seconds
        }
        return tracked
