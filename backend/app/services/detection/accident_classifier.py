import logging
import math
import pickle
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any

from app.services.detection.device import (
    DeviceResolutionError,
    resolve_device,
)


logger = logging.getLogger(__name__)

ARCHITECTURE = "crashsense_mobilenet_v3_small_temporal_v1"
CLASS_TO_INDEX = {"NORMAL": 0, "ACCIDENT": 1}
FRAME_SIZE = 112
WINDOW_SAMPLE_FRAMES = 50
MODEL_INPUT_FRAMES = 16
MAX_EVIDENCE_WINDOWS = 20


class AccidentClassifierError(Exception):
    """Raised when a configured accident classifier cannot run."""


def preprocess_bgr_frame(frame: Any) -> Any:
    try:
        import cv2
    except ImportError as exc:
        raise AccidentClassifierError(
            "OpenCV is required to preprocess classifier frames."
        ) from exc

    if (
        frame is None
        or len(frame.shape) != 3
        or frame.shape[2] != 3
        or frame.shape[0] <= 0
        or frame.shape[1] <= 0
    ):
        raise AccidentClassifierError("Classifier received an invalid video frame.")

    height, width = frame.shape[:2]
    scale = min(FRAME_SIZE / width, FRAME_SIZE / height)
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    resized = cv2.resize(frame, (resized_width, resized_height))
    top = (FRAME_SIZE - resized_height) // 2
    bottom = FRAME_SIZE - resized_height - top
    left = (FRAME_SIZE - resized_width) // 2
    right = FRAME_SIZE - resized_width - left
    padded = cv2.copyMakeBorder(
        resized,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(0, 0, 0),
    )
    return cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)


def prepare_model_input(frames: list[Any]) -> Any:
    try:
        import torch
    except ImportError as exc:
        raise AccidentClassifierError(
            "PyTorch is required for accident classification."
        ) from exc
    if len(frames) != WINDOW_SAMPLE_FRAMES:
        raise ValueError(
            f"Classifier windows require {WINDOW_SAMPLE_FRAMES} sampled frames."
        )

    selected_indices = [
        round(index * (WINDOW_SAMPLE_FRAMES - 1) / (MODEL_INPUT_FRAMES - 1))
        for index in range(MODEL_INPUT_FRAMES)
    ]
    inputs = (
        torch.stack([torch.from_numpy(frames[index]) for index in selected_indices])
        .permute(0, 3, 1, 2)
        .to(dtype=torch.float32)
        .div_(255.0)
    )
    mean = inputs.new_tensor((0.485, 0.456, 0.406)).view(1, 3, 1, 1)
    standard_deviation = inputs.new_tensor((0.229, 0.224, 0.225)).view(1, 3, 1, 1)
    return (inputs - mean) / standard_deviation


def build_temporal_model(pretrained_backbone: bool = False) -> Any:
    """Create a MobileNetV3-small spatial encoder with a temporal head."""
    try:
        from torch import nn
        from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
    except ImportError as exc:
        raise AccidentClassifierError(
            "PyTorch and torchvision are required for accident classification."
        ) from exc

    class TemporalAccidentNetwork(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            weights = (
                MobileNet_V3_Small_Weights.DEFAULT if pretrained_backbone else None
            )
            backbone = mobilenet_v3_small(weights=weights)
            self.spatial_encoder = nn.Sequential(
                backbone.features,
                nn.AdaptiveAvgPool2d(1),
            )
            self.temporal_encoder = nn.Sequential(
                nn.Conv1d(576, 96, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm1d(96),
                nn.SiLU(inplace=True),
                nn.Conv1d(96, 96, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm1d(96),
                nn.SiLU(inplace=True),
                nn.AdaptiveAvgPool1d(1),
            )
            self.classifier = nn.Linear(96, len(CLASS_TO_INDEX))

        def forward(self, frames: Any) -> Any:
            if frames.ndim != 5 or frames.shape[2] != 3:
                raise ValueError(
                    "Classifier input must have shape [batch, time, 3, height, width]."
                )
            batch_size, frame_count, channels, height, width = frames.shape
            spatial = self.spatial_encoder(
                frames.reshape(batch_size * frame_count, channels, height, width)
            )
            spatial = spatial.flatten(1).reshape(batch_size, frame_count, -1)
            temporal = self.temporal_encoder(spatial.transpose(1, 2)).squeeze(-1)
            return self.classifier(temporal)

    return TemporalAccidentNetwork()


@lru_cache(maxsize=1)
def _load_model(weights_path: str, device: str) -> tuple[Any, dict[str, float]]:
    try:
        import torch
    except ImportError as exc:
        raise AccidentClassifierError(
            "PyTorch is required for accident classification."
        ) from exc

    try:
        checkpoint = torch.load(
            weights_path,
            map_location=device,
            weights_only=True,
        )
    except (
        OSError,
        RuntimeError,
        EOFError,
        ValueError,
        TypeError,
        pickle.UnpicklingError,
    ) as exc:
        raise AccidentClassifierError(
            f"Could not load accident-classifier checkpoint: {weights_path}."
        ) from exc

    if not isinstance(checkpoint, dict):
        raise AccidentClassifierError("Classifier checkpoint must be a mapping.")
    if checkpoint.get("architecture") != ARCHITECTURE:
        raise AccidentClassifierError(
            "Classifier checkpoint uses an unsupported architecture."
        )
    if checkpoint.get("class_to_index") != CLASS_TO_INDEX:
        raise AccidentClassifierError(
            "Classifier checkpoint has an incompatible class mapping."
        )
    state_dict = checkpoint.get("state_dict")
    if not isinstance(state_dict, dict):
        raise AccidentClassifierError(
            "Classifier checkpoint does not contain a state_dict."
        )

    model = build_temporal_model()
    try:
        model.load_state_dict(state_dict, strict=True)
    except RuntimeError as exc:
        raise AccidentClassifierError(
            "Classifier checkpoint weights do not match the configured architecture."
        ) from exc
    model.to(device)
    model.eval()

    thresholds = checkpoint.get("thresholds", {})
    if not isinstance(thresholds, dict):
        raise AccidentClassifierError("Classifier thresholds must be a mapping.")
    try:
        parsed_thresholds = {
            "normal": float(thresholds.get("normal", 0.1)),
            "accident": float(thresholds.get("accident", 0.9)),
        }
    except (TypeError, ValueError, OverflowError) as exc:
        raise AccidentClassifierError(
            "Classifier thresholds must be numeric."
        ) from exc
    return model, parsed_thresholds


class AccidentClassifier:
    """Windowed video classifier with conservative three-state output."""

    def __init__(
        self,
        weights_path: str | None,
        device: str,
        frame_interval_seconds: float = 0.1,
        normal_threshold: float | None = None,
        accident_threshold: float | None = None,
    ) -> None:
        if frame_interval_seconds <= 0:
            raise ValueError("Classifier frame interval must be positive.")
        self.device = device
        self.frame_interval_seconds = frame_interval_seconds
        self.weights_path = weights_path
        self.model = None
        self.thresholds = {"normal": 0.1, "accident": 0.9}
        self._window: list[tuple[Any, float]] = []
        self._frames_seen = 0
        self._last_timestamp: float | None = None
        self._window_count = 0
        self._all_windows_normal = True
        self._max_probability = 0.0
        self._accident_probability: float | None = None
        self._evidence_windows: list[dict[str, float]] = []
        self._inference_seconds = 0.0

        if not weights_path:
            return

        path = Path(weights_path).expanduser().resolve()
        if not path.is_file():
            raise AccidentClassifierError(
                f"Configured accident-classifier weights do not exist: {path}."
            )
        try:
            resolve_device(device)
        except DeviceResolutionError as exc:
            raise AccidentClassifierError(str(exc)) from exc

        self.model, checkpoint_thresholds = _load_model(str(path), device)
        self.thresholds = dict(checkpoint_thresholds)
        if normal_threshold is not None:
            self.thresholds["normal"] = normal_threshold
        if accident_threshold is not None:
            self.thresholds["accident"] = accident_threshold
        if (
            not 0 <= self.thresholds["normal"]
            < self.thresholds["accident"]
            <= 1
        ):
            raise ValueError(
                "Classifier thresholds must satisfy 0 <= normal < accident <= 1."
            )

    @property
    def enabled(self) -> bool:
        return self.model is not None

    def observe(self, frame: Any, timestamp_seconds: float) -> None:
        if not self.enabled:
            return
        if not math.isfinite(timestamp_seconds) or timestamp_seconds < 0:
            raise AccidentClassifierError("Classifier frame timestamp is invalid.")
        if (
            self._last_timestamp is not None
            and timestamp_seconds <= self._last_timestamp
        ):
            raise AccidentClassifierError(
                "Classifier frame timestamps must be strictly increasing."
            )

        self._last_timestamp = timestamp_seconds
        self._window.append((preprocess_bgr_frame(frame), timestamp_seconds))
        self._frames_seen += 1
        if len(self._window) < WINDOW_SAMPLE_FRAMES:
            return

        self._infer_window()
        self._window.clear()

    def _infer_window(self) -> None:
        try:
            import torch
        except ImportError as exc:
            raise AccidentClassifierError(
                "PyTorch is required for accident classification."
            ) from exc

        frames = prepare_model_input([frame for frame, _ in self._window])
        frames = frames.unsqueeze(0).to(self.device)

        started = perf_counter()
        try:
            with torch.inference_mode():
                logits = self.model(frames)
                if tuple(logits.shape) != (1, 2):
                    raise AccidentClassifierError(
                        "Classifier returned an invalid output shape."
                    )
                probability = float(torch.softmax(logits, dim=1)[0, 1].item())
        except RuntimeError as exc:
            raise AccidentClassifierError(
                "Accident-classifier inference failed."
            ) from exc
        finally:
            self._inference_seconds += perf_counter() - started

        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise AccidentClassifierError(
                "Classifier returned an invalid accident probability."
            )

        self._window_count += 1
        self._max_probability = max(self._max_probability, probability)
        self._all_windows_normal &= probability <= self.thresholds["normal"]
        if probability >= self.thresholds["accident"]:
            self._accident_probability = max(
                self._accident_probability or 0.0,
                probability,
            )
        evidence = {
            "start_timestamp_seconds": self._window[0][1],
            "end_timestamp_seconds": self._window[-1][1],
            "accident_score": probability,
        }
        self._evidence_windows.append(evidence)
        self._evidence_windows.sort(
            key=lambda item: item["accident_score"],
            reverse=True,
        )
        del self._evidence_windows[MAX_EVIDENCE_WINDOWS:]

    def result(self) -> dict[str, Any]:
        common = {
            "model_status": "loaded_unvalidated" if self.enabled else "not_configured",
            "model": Path(self.weights_path).name if self.weights_path else None,
            "device": self.device,
            "frames_sampled": self._frames_seen,
            "windows_evaluated": self._window_count,
            "partial_window_frames": len(self._window),
            "inference_seconds": round(self._inference_seconds, 6),
            "max_accident_score": (
                self._max_probability if self._window_count else None
            ),
            "thresholds": dict(self.thresholds),
            "evidence_windows": sorted(
                self._evidence_windows,
                key=lambda item: item["start_timestamp_seconds"],
            ),
            "human_review_required": True,
        }
        if not self.enabled:
            return {
                **common,
                "label": "UNKNOWN",
                "confidence": None,
                "reason_code": "weights_not_configured",
                "reason": (
                    "No trained accident-classifier checkpoint is configured."
                ),
            }
        if not self._window_count:
            return {
                **common,
                "label": "UNKNOWN",
                "confidence": None,
                "reason_code": "insufficient_frames",
                "reason": (
                    "The video did not contain a complete classifier window."
                ),
            }
        if self._accident_probability is not None:
            return {
                **common,
                "label": "ACCIDENT",
                "confidence": None,
                "reason_code": "accident_threshold_exceeded",
                "reason": (
                    "At least one temporal window exceeded the configured "
                    "accident threshold; human review is required."
                ),
            }
        if self._all_windows_normal and not self._window:
            return {
                **common,
                "label": "NORMAL",
                "confidence": None,
                "reason_code": "normal_threshold_met",
                "reason": (
                    "All complete temporal windows were below the configured "
                    "normal threshold."
                ),
            }
        return {
            **common,
            "label": "UNKNOWN",
            "confidence": None,
            "reason_code": "uncertain_or_incomplete_video",
            "reason": (
                "Classifier evidence was uncertain or the final temporal "
                "window was incomplete."
            ),
        }


def resolve_classifier_device(configured_device: str) -> str:
    try:
        return resolve_device(configured_device)
    except DeviceResolutionError as exc:
        raise AccidentClassifierError(str(exc)) from exc
