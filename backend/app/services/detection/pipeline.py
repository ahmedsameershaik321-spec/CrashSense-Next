import logging
from pathlib import Path
from time import perf_counter
from typing import Callable

from app.config import settings
from app.services.detection.accidents import AccidentCandidateDetector
from app.services.detection.accident_classifier import AccidentClassifier
from app.services.detection.frames import iter_video_frames
from app.services.detection.tracking import TrajectoryTracker
from app.services.detection.yolo import YOLODetector


logger = logging.getLogger(__name__)


class AnalysisCancelled(Exception):
    """Raised when an analysis job has been cancelled by an operator."""


def analyze_video(
    video_path: Path,
    progress_callback: Callable[[int], None],
    cancellation_requested: Callable[[], bool],
) -> dict:
    """Run frame sampling, YOLO/ByteTrack inference, and temporal analysis."""
    started_at = perf_counter()
    detector = YOLODetector()
    detector.reset_tracking()
    classifier = AccidentClassifier(
        settings.accident_classifier_weights,
        detector.device,
        frame_interval_seconds=(
            settings.accident_classifier_frame_interval_seconds
        ),
        normal_threshold=settings.accident_classifier_normal_threshold,
        accident_threshold=settings.accident_classifier_accident_threshold,
    )
    trajectory_tracker = TrajectoryTracker()
    candidate_detector = AccidentCandidateDetector()
    frame_evidence: list[dict] = []
    detection_interval = settings.detection_frame_interval_seconds
    sample_interval = (
        min(
            detection_interval,
            settings.accident_classifier_frame_interval_seconds,
        )
        if classifier.enabled
        else detection_interval
    )
    next_detection_time = 0.0
    last_reported_progress = -1

    for frame in iter_video_frames(
        video_path,
        interval_seconds=sample_interval,
        max_dimension=settings.detection_max_frame_dimension,
    ):
        if cancellation_requested():
            raise AnalysisCancelled

        if classifier.enabled:
            classifier.observe(frame.frame, frame.timestamp_seconds)
        if frame.timestamp_seconds + 1e-9 < next_detection_time:
            continue
        next_detection_time = frame.timestamp_seconds + detection_interval

        height, width = frame.frame.shape[:2]
        detections = detector.detect(frame.frame)
        tracked = trajectory_tracker.update(
            detections,
            frame.timestamp_seconds,
        )
        objects = [item.as_evidence() for item in tracked]
        candidate_detector.observe(
            tracked,
            timestamp_seconds=frame.timestamp_seconds,
            frame_width=width,
            frame_height=height,
            frame_index=frame.frame_index,
        )
        frame_evidence.append(
            {
                "frame_index": frame.frame_index,
                "timestamp_seconds": round(frame.timestamp_seconds, 3),
                "width": width,
                "height": height,
                "objects": objects,
            }
        )

        if frame.frame_count > 0:
            current_progress = min(
                99,
                max(1, round(99 * (frame.frame_index + 1) / frame.frame_count)),
            )
        else:
            current_progress = 0
        if current_progress != last_reported_progress:
            progress_callback(current_progress)
            last_reported_progress = current_progress

    if cancellation_requested():
        raise AnalysisCancelled
    if not frame_evidence:
        raise RuntimeError("The video did not yield any sampled frames.")

    candidates = candidate_detector.candidates()
    object_count = sum(len(frame["objects"]) for frame in frame_evidence)
    accident_classification = classifier.result()
    processing_seconds = perf_counter() - started_at
    logger.info(
        "Video analysis processed %d frames and found %d candidate events.",
        len(frame_evidence),
        len(candidates),
    )
    return {
        "summary": {
            "frames_processed": len(frame_evidence),
            "detections_processed": object_count,
            "candidate_count": len(candidates),
            "model": Path(settings.detection_model_weights).name,
            "device": detector.device,
            "frame_interval_seconds": settings.detection_frame_interval_seconds,
            "processing_seconds": round(processing_seconds, 3),
            "processing_fps": (
                round(len(frame_evidence) / processing_seconds, 2)
                if processing_seconds > 0
                else None
            ),
            "accident_classification": accident_classification,
            "notice": (
                "Candidate scores are heuristic visual evidence, not calibrated "
                "probabilities or confirmation of a collision, injury, or severity. "
                "Classifier scores are unvalidated and require human review."
            ),
        },
        "candidates": candidates,
        "frames": frame_evidence,
    }
