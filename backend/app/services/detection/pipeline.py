import logging
from pathlib import Path
from typing import Callable

from app.config import settings
from app.services.detection.accidents import AccidentCandidateDetector
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
    detector = YOLODetector()
    detector.reset_tracking()
    trajectory_tracker = TrajectoryTracker()
    candidate_detector = AccidentCandidateDetector()
    frame_evidence: list[dict] = []

    for frame in iter_video_frames(
        video_path,
        interval_seconds=settings.detection_frame_interval_seconds,
        max_dimension=settings.detection_max_frame_dimension,
    ):
        if cancellation_requested():
            raise AnalysisCancelled

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
            progress_callback(
                min(99, max(1, round(99 * (frame.frame_index + 1) / frame.frame_count)))
            )
        else:
            progress_callback(0)

    if cancellation_requested():
        raise AnalysisCancelled
    if not frame_evidence:
        raise RuntimeError("The video did not yield any sampled frames.")

    candidates = candidate_detector.candidates()
    object_count = sum(len(frame["objects"]) for frame in frame_evidence)
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
            "notice": (
                "Candidate scores are heuristic visual evidence, not calibrated "
                "probabilities or confirmation of a collision, injury, or severity."
            ),
        },
        "candidates": candidates,
        "frames": frame_evidence,
    }
