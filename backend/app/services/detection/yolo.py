import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.config import settings


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
    requested = configured_device.lower()
    if requested == "cpu":
        return "cpu"
    if requested != "auto":
        match = re.fullmatch(r"cuda(?::(\d+))?", requested)
        if match is None:
            raise DetectionModelError(
                "DETECTION_DEVICE must be 'auto', 'cpu', 'cuda', or 'cuda:N'."
            )
        try:
            import torch
        except ImportError as exc:
            raise DetectionModelError(
                "CUDA was requested but PyTorch is not installed."
            ) from exc
        device_index = int(match.group(1) or "0")
        if (
            not torch.cuda.is_available()
            or device_index >= torch.cuda.device_count()
        ):
            raise DetectionModelError(
                f"CUDA device {device_index} is unavailable."
            )
        return f"cuda:{device_index}"

    try:
        import torch
    except ImportError as exc:
        raise DetectionModelError(
            "PyTorch is required for YOLO inference. Install PyTorch for your platform."
        ) from exc

    return "cuda:0" if torch.cuda.is_available() else "cpu"


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
    """Cached YOLOv8 detector with Ultralytics ByteTrack integration."""

    def __init__(self) -> None:
        device = _resolve_device(settings.detection_device)
        self.device = device
        self.model = _load_model(settings.detection_model_weights, device)

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
                classes=list(ROAD_CLASS_IDS),
                conf=settings.detection_confidence_threshold,
                iou=settings.detection_iou_threshold,
                device=self.device,
                verbose=False,
            )
        except Exception as exc:
            raise DetectionModelError("YOLO inference failed.") from exc

        if not results:
            return []

        return self._parse_result(results[0])

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
    def _parse_result(cls, result: Any) -> list[DetectedObject]:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        coordinates = cls._values(getattr(boxes, "xyxy", None))
        confidences = cls._values(getattr(boxes, "conf", None))
        class_ids = cls._values(getattr(boxes, "cls", None))
        track_ids = cls._values(getattr(boxes, "id", None))

        detections: list[DetectedObject] = []
        for index, (bbox, confidence, raw_class_id) in enumerate(
            zip(coordinates, confidences, class_ids, strict=False)
        ):
            class_id = int(raw_class_id)
            label = CLASS_LABELS.get(class_id)
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
