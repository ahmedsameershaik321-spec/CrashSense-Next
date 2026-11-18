
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.detection.yolo import DetectionModelError

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@lru_cache(maxsize=1)
def _load_model(weights: str) -> Any:
    try:
        from ultralytics import YOLO
        return YOLO(weights)
    except ImportError as exc:
        raise DetectionModelError(
            "Ultralytics is required for accident detection."
        ) from exc
    except Exception as exc:
        raise DetectionModelError(
            f"Could not load accident YOLO weights: {weights}"
        ) from exc


class AccidentYOLODetector:
    """Detect accident regions using the trained CrashSense YOLO model."""

    def __init__(self, device: str) -> None:
        path = Path(
            settings.accident_detection_model_weights
        ).expanduser()

        if not path.is_absolute():
            path = PROJECT_ROOT / path

        path = path.resolve()

        if not path.is_file():
            raise DetectionModelError(
                f"Accident model weights not found: {path}"
            )

        self.model = _load_model(str(path))
        self.device = device
        self.model_name = path.name

        names = self.model.names
        entries = names.items() if isinstance(names, dict) else enumerate(names)

        self.accident_class_id = next(
            (
                int(class_id)
                for class_id, label in entries
                if str(label).strip().lower() == "accident"
            ),
            None,
        )

        if self.accident_class_id is None:
            raise DetectionModelError(
                "The configured model does not contain an Accident class."
            )

        logger.info("Loaded accident detector: %s", path)

    def detect(self, frame: Any) -> list[dict]:
        try:
            results = self.model.predict(
                source=frame,
                classes=[self.accident_class_id],
                conf=settings.detection_confidence_threshold,
                iou=settings.detection_iou_threshold,
                imgsz=settings.detection_image_size,
                device=self.device,
                verbose=False,
            )
        except Exception as exc:
            raise DetectionModelError(
                "Accident YOLO inference failed."
            ) from exc

        if not results or results[0].boxes is None:
            return []

        detections = []

        for box in results[0].boxes:
            coordinates = box.xyxy[0].detach().cpu().tolist()
            confidence = float(box.conf[0].item())

            detections.append({
                "label": "accident",
                "confidence": round(confidence, 5),
                "bbox": [round(float(value), 2) for value in coordinates],
            })

        return detections
