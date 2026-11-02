from collections.abc import Iterator
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any


class VideoProcessingError(Exception):
    """Raised when a source video cannot be decoded for analysis."""


@dataclass(frozen=True)
class VideoFrame:
    frame_index: int
    timestamp_seconds: float
    frame_count: int
    frame: Any


def iter_video_frames(
    video_path: Path,
    interval_seconds: float,
    max_dimension: int,
) -> Iterator[VideoFrame]:
    """Decode a video sequentially and yield resized, interval-sampled frames."""
    if interval_seconds <= 0 or max_dimension <= 0:
        raise ValueError("Frame interval and maximum dimension must be positive.")

    try:
        import cv2
    except ImportError as exc:
        raise VideoProcessingError(
            "OpenCV is required to decode videos. Install opencv-python-headless."
        ) from exc

    capture = cv2.VideoCapture(str(video_path))

    try:
        if not capture.isOpened():
            raise VideoProcessingError("The video file could not be opened.")

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not math.isfinite(fps) or fps <= 0:
            fps = 25.0
        reported_frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_count = (
            max(0, int(reported_frame_count))
            if math.isfinite(reported_frame_count)
            else 0
        )
        next_sample_time = 0.0
        frame_index = 0
        decoded_frame = False

        while True:
            ok, frame = capture.read()
            if not ok:
                break

            decoded_frame = True
            reported_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
            timestamp = (
                reported_ms / 1000.0
                if math.isfinite(reported_ms) and reported_ms > 0
                else frame_index / fps
            )

            if timestamp + 1e-9 >= next_sample_time:
                height, width = frame.shape[:2]
                scale = min(1.0, max_dimension / max(height, width))
                if scale < 1:
                    frame = cv2.resize(
                        frame,
                        (
                            max(1, round(width * scale)),
                            max(1, round(height * scale)),
                        ),
                        interpolation=cv2.INTER_AREA,
                    )

                yield VideoFrame(
                    frame_index=frame_index,
                    timestamp_seconds=timestamp,
                    frame_count=frame_count,
                    frame=frame,
                )
                next_sample_time = timestamp + interval_seconds

            frame_index += 1

        if not decoded_frame:
            raise VideoProcessingError(
                "The video contains no decodable frames or uses an unsupported codec."
            )
    finally:
        capture.release()
