import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.config import settings
from app.services.detection.device import (
    DeviceResolutionError,
    resolve_device,
)


logger = logging.getLogger(__name__)

ROAD_CLASS_IDS = (0, 1, 2, 3, 5, 7)
CLASS_LABELS = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


class DetectionModelError(Exception):
    """Raised when the configured detection model cannot be used."""


@dataclass(frozen=True)
class DetectedObject:
    class_id: int
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]
    track_id: int | None


def _resolve_device(configured_device: str) -> str:
    try:
        return resolve_device(configured_device)
    except DeviceResolutionError as exc:
        raise DetectionModelError(str(exc)) from exc


@lru_cache(maxsize=2)
def _load_model(weights: str, device: str) -> Any:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise DetectionModelError(
            "Ultralytics is required for YOLO inference. Install the backend ML dependencies."
        ) from exc

    logger.info("Loading YOLO weights %s on %s.", weights, device)
    try:
        return YOLO(weights)
    except Exception as exc:
        raise DetectionModelError(
            f"Could not load configured YOLO weights: {weights}."
        ) from exc


class YOLODetector:
    """Cached Ultralytics road-user detector with ByteTrack integration."""

    def __init__(self) -> None:
        device = _resolve_device(settings.detection_device)
        self.device = device
        self.model = _load_model(settings.detection_model_weights, device)
        self.class_labels = self._road_class_labels(
            getattr(self.model, "names", None)
        )

    def reset_tracking(self) -> None:
        predictor = getattr(self.model, "predictor", None)
        trackers = getattr(predictor, "trackers", ())
        for tracker in trackers:
            reset = getattr(tracker, "reset", None)
            if reset is not None:
                reset()

    def detect(self, frame: Any) -> list[DetectedObject]:
        try:
            results = self.model.track(
                source=frame,
                persist=True,
                tracker="bytetrack.yaml",
                classes=list(self.class_labels),
                conf=settings.detection_confidence_threshold,
                iou=settings.detection_iou_threshold,
                imgsz=settings.detection_image_size,
                device=self.device,
                verbose=False,
            )
        except Exception as exc:
            raise DetectionModelError("YOLO inference failed.") from exc

        if not results:
            return []

        return self._parse_result(results[0], self.class_labels)

    @staticmethod
    def _road_class_labels(names: Any) -> dict[int, str]:
        if isinstance(names, dict):
            entries = names.items()
        elif isinstance(names, (list, tuple)):
            entries = enumerate(names)
        else:
            raise DetectionModelError(
                "The configured model does not expose a supported class mapping."
            )

        supported_labels = set(CLASS_LABELS.values())
        labels: dict[int, str] = {}
        for raw_class_id, raw_label in entries:
            label = str(raw_label).strip().lower()
            if label not in supported_labels:
                continue
            try:
                class_id = int(raw_class_id)
            except (TypeError, ValueError) as exc:
                raise DetectionModelError(
                    "The configured model has an invalid class mapping."
                ) from exc
            labels[class_id] = label

        if not labels:
            raise DetectionModelError(
                "The configured model has no supported COCO road-user classes."
            )
        return labels

    @staticmethod
    def _values(value: Any) -> list[Any]:
        if value is None:
            return []
        if hasattr(value, "cpu"):
            value = value.cpu()
        if hasattr(value, "tolist"):
            value = value.tolist()
        return value

    @classmethod
    def _parse_result(
        cls,
        result: Any,
        class_labels: dict[int, str] | None = None,
    ) -> list[DetectedObject]:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        labels = class_labels if class_labels is not None else CLASS_LABELS
        coordinates = cls._values(getattr(boxes, "xyxy", None))
        confidences = cls._values(getattr(boxes, "conf", None))
        class_ids = cls._values(getattr(boxes, "cls", None))
        track_ids = cls._values(getattr(boxes, "id", None))

        detections: list[DetectedObject] = []
        for index, (bbox, confidence, raw_class_id) in enumerate(
            zip(coordinates, confidences, class_ids, strict=False)
        ):
            class_id = int(raw_class_id)
            label = labels.get(class_id)
            if label is None or len(bbox) != 4:
                continue
            track_id = (
                int(track_ids[index])
                if index < len(track_ids) and track_ids[index] is not None
                else None
            )
            detections.append(
                DetectedObject(
                    class_id=class_id,
                    label=label,
                    confidence=float(confidence),
                    bbox=tuple(float(coordinate) for coordinate in bbox),
                    track_id=track_id,
                )
            )

        return detections
