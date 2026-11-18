import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.config import settings
from app.schemas.analysis import AccidentCandidateResponse
from app.services.detection import yolo
from app.services.detection.accidents import AccidentCandidateDetector
from app.services.detection.frames import VideoProcessingError, iter_video_frames
from app.services.detection.pipeline import AnalysisCancelled, analyze_video
from app.services.detection.tracking import TrackedObject, TrajectoryTracker
from app.services.detection.yolo import (
    DetectedObject,
    DetectionModelError,
    YOLODetector,
)


class FakeFrame:
    def __init__(self, height=100, width=200):
        self.shape = (height, width, 3)


class FakeCapture:
    def __init__(self, frames, fps=2.0):
        self.frames = frames
        self.fps = fps
        self.index = 0
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        if prop == 1:
            return self.fps
        if prop == 2:
            return len(self.frames)
        if prop == 3:
            return max(0, self.index - 1) * 500
        return 0

    def read(self):
        if self.index >= len(self.frames):
            return False, None
        frame = self.frames[self.index]
        self.index += 1
        return True, frame

    def release(self):
        self.released = True


def install_fake_cv2(monkeypatch, frames, fps=2.0):
    capture = FakeCapture(frames, fps)
    fake_cv2 = ModuleType("cv2")
    fake_cv2.VideoCapture = lambda path: capture
    fake_cv2.CAP_PROP_FPS = 1
    fake_cv2.CAP_PROP_FRAME_COUNT = 2
    fake_cv2.CAP_PROP_POS_MSEC = 3
    fake_cv2.INTER_AREA = 4
    fake_cv2.resize = lambda frame, size, interpolation: FakeFrame(
        height=size[1],
        width=size[0],
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    return capture


def make_detection(
    track_id,
    bbox=(10.0, 10.0, 30.0, 30.0),
    label="car",
):
    return DetectedObject(
        class_id=2,
        label=label,
        confidence=0.9,
        bbox=bbox,
        track_id=track_id,
    )


def make_tracked(
    track_id,
    bbox,
    anomaly=None,
    label="car",
    post_behavior=None,
):
    return TrackedObject(
        detection=make_detection(track_id, bbox, label),
        speed_pixels_per_second=10.0,
        motion_anomaly=anomaly,
        post_anomaly_behavior=post_behavior,
    )


def make_episode_candidate(
    candidate_id,
    start,
    end,
    track_ids,
    event_keys,
    interaction_type="vehicle_vehicle",
    status="verified_detection",
):
    return {
        "candidate_id": candidate_id,
        "start_timestamp_seconds": start,
        "end_timestamp_seconds": end,
        "involved_track_ids": track_ids,
        "object_labels": ["car"],
        "confidence_score": 0.8,
        "confidence_type": "heuristic_temporal_evidence_score",
        "verification_status": status,
        "evidence_summary": "Episode evidence.",
        "evidence_references": [f"frame:{candidate_id}"],
        "interaction_observations": 4,
        "motion_events": len(event_keys),
        "interaction_type": interaction_type,
        "_motion_event_keys": set(event_keys),
    }


def test_frame_extraction_samples_and_resizes_without_buffering(
    tmp_path,
    monkeypatch,
):
    capture = install_fake_cv2(
        monkeypatch,
        [FakeFrame() for _ in range(5)],
    )

    frames = list(
        iter_video_frames(
            tmp_path / "source.mp4",
            interval_seconds=1,
            max_dimension=100,
        )
    )

    assert [frame.frame_index for frame in frames] == [0, 2, 4]
    assert [frame.timestamp_seconds for frame in frames] == [0, 1, 2]
    assert all(frame.frame.shape == (50, 100, 3) for frame in frames)
    assert all(frame.frame_count == 5 for frame in frames)
    assert capture.released


def test_frame_extraction_rejects_empty_or_unsupported_video(
    tmp_path,
    monkeypatch,
):
    capture = install_fake_cv2(monkeypatch, [])

    with pytest.raises(VideoProcessingError, match="no decodable frames"):
        list(iter_video_frames(tmp_path / "broken.mp4", 1, 1280))

    assert capture.released


def test_frame_extraction_validates_sampling_configuration(tmp_path):
    with pytest.raises(ValueError):
        list(iter_video_frames(tmp_path / "source.mp4", 0, 1280))


def test_yolo_model_is_loaded_once_and_tracker_receives_configuration(
    monkeypatch,
):
    constructed = []

    class FakeModel:
        predictor = None
        names = {
            0: "person",
            1: "bicycle",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck",
        }

        def track(self, **kwargs):
            self.track_kwargs = kwargs
            return []

    model = FakeModel()
    fake_ultralytics = ModuleType("ultralytics")
    fake_ultralytics.YOLO = lambda weights: constructed.append(weights) or model
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)
    monkeypatch.setattr(yolo, "_resolve_device", lambda configured: "cpu")
    monkeypatch.setattr(settings, "detection_model_weights", "test-yolov8n.pt")
    yolo._load_model.cache_clear()

    try:
        first = YOLODetector()
        second = YOLODetector()
        first.detect(FakeFrame())
    finally:
        yolo._load_model.cache_clear()

    assert first.model is second.model
    assert constructed == ["test-yolov8n.pt"]
    assert model.track_kwargs["tracker"] == "bytetrack.yaml"
    assert model.track_kwargs["persist"] is True
    assert model.track_kwargs["classes"] == [0, 1, 2, 3, 5, 7]
    assert model.track_kwargs["device"] == "cpu"
    assert model.track_kwargs["imgsz"] == settings.detection_image_size


def test_model_class_mapping_uses_supported_names_and_rejects_unknown_classes():
    assert YOLODetector._road_class_labels(
        {4: "truck", 9: "person", 10: "animal"}
    ) == {4: "truck", 9: "person"}

    with pytest.raises(DetectionModelError, match="no supported COCO"):
        YOLODetector._road_class_labels({0: "vehicle"})


def test_yolo_inference_uses_model_class_ids_and_mapping(monkeypatch):
    class FakeModel:
        names = {4: "truck"}

        def track(self, **kwargs):
            self.track_kwargs = kwargs
            return [
                SimpleNamespace(
                    boxes=SimpleNamespace(
                        xyxy=[[1, 2, 30, 40]],
                        conf=[0.95],
                        cls=[4],
                        id=[31],
                    )
                )
            ]

    model = FakeModel()
    detector = YOLODetector.__new__(YOLODetector)
    detector.device = "cpu"
    detector.model = model
    detector.class_labels = detector._road_class_labels(model.names)
    monkeypatch.setattr(settings, "detection_image_size", 512)

    detections = detector.detect(FakeFrame())

    assert model.track_kwargs["classes"] == [4]
    assert model.track_kwargs["imgsz"] == 512
    assert detections[0].label == "truck"


def test_yolo_detection_output_is_normalized_to_road_classes():
    class FakeTensor:
        def __init__(self, values):
            self.values = values

        def cpu(self):
            return self

        def tolist(self):
            return self.values

    boxes = SimpleNamespace(
        xyxy=FakeTensor([[1, 2, 30, 40], [4, 5, 6, 7]]),
        conf=FakeTensor([0.95, 0.8]),
        cls=FakeTensor([2, 9]),
        id=FakeTensor([31, 32]),
    )
    result = SimpleNamespace(boxes=boxes)

    detections = YOLODetector._parse_result(result)

    assert detections == [
        DetectedObject(
            class_id=2,
            label="car",
            confidence=0.95,
            bbox=(1.0, 2.0, 30.0, 40.0),
            track_id=31,
        )
    ]


def test_yolo_handles_untracked_detection():
    boxes = SimpleNamespace(
        xyxy=[[0, 1, 2, 3]],
        conf=[0.8],
        cls=[0],
        id=None,
    )

    result = YOLODetector._parse_result(SimpleNamespace(boxes=boxes))

    assert result[0].label == "person"
    assert result[0].track_id is None


def test_model_initialization_fails_explicitly_when_pytorch_is_missing(
    monkeypatch,
):
    monkeypatch.setitem(sys.modules, "torch", None)

    with pytest.raises(DetectionModelError, match="PyTorch is required"):
        yolo._resolve_device("auto")


def test_missing_ultralytics_weights_loader_fails_without_fake_results(
    monkeypatch,
):
    monkeypatch.setitem(sys.modules, "ultralytics", None)
    yolo._load_model.cache_clear()

    with pytest.raises(DetectionModelError, match="Ultralytics is required"):
        yolo._load_model("missing-dependency-test.pt", "cpu")


def test_cpu_device_does_not_require_cuda():
    assert yolo._resolve_device("cpu") == "cpu"


def test_auto_device_falls_back_to_cpu_without_cuda(monkeypatch):
    fake_torch = ModuleType("torch")
    fake_torch.cuda = SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    assert yolo._resolve_device("auto") == "cpu"


def test_explicit_cuda_device_is_validated(monkeypatch):
    fake_torch = ModuleType("torch")
    fake_torch.cuda = SimpleNamespace(
        is_available=lambda: True,
        device_count=lambda: 2,
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    assert yolo._resolve_device("cuda:1") == "cuda:1"
    with pytest.raises(DetectionModelError, match="unavailable"):
        yolo._resolve_device("cuda:2")
    with pytest.raises(DetectionModelError, match="DETECTION_DEVICE"):
        yolo._resolve_device("gpu")


def test_trajectory_tracker_calculates_motion_and_deceleration(monkeypatch):
    monkeypatch.setattr(settings, "detection_min_speed_pixels_per_second", 10)
    monkeypatch.setattr(settings, "detection_stop_speed_ratio", 0.2)
    tracker = TrajectoryTracker()

    assert tracker.update([make_detection(1, (0, 0, 10, 10))], 0)[0].speed_pixels_per_second is None
    moving = tracker.update([make_detection(1, (20, 0, 30, 10))], 1)[0]
    stopped = tracker.update([make_detection(1, (21, 0, 31, 10))], 2)[0]

    assert moving.speed_pixels_per_second == 20
    assert moving.motion_anomaly is None
    assert stopped.speed_pixels_per_second == 1
    assert stopped.motion_anomaly == "sudden_deceleration"
    assert stopped.motion_state == "stopping"


def test_tracker_distinguishes_stopping_from_already_stationary(monkeypatch):
    monkeypatch.setattr(settings, "detection_min_speed_pixels_per_second", 10)
    tracker = TrajectoryTracker()

    stationary = tracker.update([make_detection(1, (0, 0, 10, 10))], 0)[0]
    still_stationary = tracker.update(
        [make_detection(1, (0, 0, 10, 10))],
        1,
    )[0]
    tracker.update([make_detection(2, (0, 0, 10, 10))], 0)
    tracker.update([make_detection(2, (20, 0, 30, 10))], 1)
    stopped_after_motion = tracker.update(
        [make_detection(2, (21, 0, 31, 10))],
        2,
    )[0]

    assert stationary.motion_state == "unknown"
    assert still_stationary.motion_state == "already_stationary"
    assert stopped_after_motion.motion_state == "stopping"


def test_tracker_records_recovery_after_anomaly(monkeypatch):
    monkeypatch.setattr(settings, "detection_min_speed_pixels_per_second", 10)
    monkeypatch.setattr(settings, "detection_stop_speed_ratio", 0.2)
    tracker = TrajectoryTracker()
    tracker.update([make_detection(1, (0, 0, 10, 10))], 0)
    tracker.update([make_detection(1, (20, 0, 30, 10))], 1)

    anomaly = tracker.update([make_detection(1, (21, 0, 31, 10))], 2)[0]
    recovered = tracker.update([make_detection(1, (40, 0, 50, 10))], 3)[0]

    assert anomaly.motion_anomaly == "sudden_deceleration"
    assert recovered.post_anomaly_behavior == "speed_recovery"


def test_trajectory_state_survives_short_occlusion():
    tracker = TrajectoryTracker()
    tracker.update([make_detection(5, (0, 0, 10, 10))], 0)
    tracker.update([], 1)

    resumed = tracker.update(
        [make_detection(5, (10, 0, 20, 10))],
        2,
    )[0]

    assert resumed.speed_pixels_per_second == 5


def test_overlapping_boxes_alone_do_not_create_accident_candidate():
    detector = AccidentCandidateDetector()
    objects = [
        make_tracked(1, (0, 0, 20, 20)),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]

    for frame_index in range(5):
        detector.observe(objects, frame_index, 100, 100, frame_index)

    assert detector.candidates() == []


def test_temporal_interaction_and_motion_produce_reviewable_candidate(
    monkeypatch,
):
    monkeypatch.setattr(settings, "detection_min_candidate_observations", 2)
    monkeypatch.setattr(settings, "detection_min_verified_observations", 4)
    monkeypatch.setattr(settings, "detection_min_motion_events", 2)
    detector = AccidentCandidateDetector()

    for frame_index in range(4):
        objects = [
            make_tracked(
                1,
                (0, 0, 20, 20),
                "sudden_deceleration" if frame_index in (1, 2) else None,
                post_behavior="stopping" if frame_index == 3 else None,
            ),
            make_tracked(2, (10, 10, 30, 30), label="motorcycle"),
        ]
        detector.observe(objects, frame_index, 100, 100, frame_index)

    candidates = detector.candidates()

    assert len(candidates) == 1
    assert candidates[0]["verification_status"] == "verified_detection"
    assert candidates[0]["event_state"] == "needs_review"
    assert candidates[0]["accident_category"] == "UNKNOWN"
    assert candidates[0]["classification_confidence"] is None
    assert candidates[0]["severity"] == "UNKNOWN"
    assert candidates[0]["severity_confidence"] is None
    assert candidates[0]["human_review_required"] is True
    response = AccidentCandidateResponse.model_validate(candidates[0])
    assert response.event_state == "needs_review"
    assert response.accident_category == "UNKNOWN"
    assert response.severity == "UNKNOWN"
    assert candidates[0]["confidence_type"] == "heuristic_temporal_evidence_score"
    assert "not confirmation" in candidates[0]["evidence_summary"]
    assert candidates[0]["evidence_references"]


def test_short_temporal_window_cannot_be_marked_needs_review(monkeypatch):
    monkeypatch.setattr(settings, "detection_min_candidate_observations", 2)
    monkeypatch.setattr(settings, "detection_min_verified_observations", 4)
    monkeypatch.setattr(settings, "detection_min_motion_events", 2)
    monkeypatch.setattr(settings, "detection_min_verified_duration_seconds", 2.0)
    detector = AccidentCandidateDetector()

    for frame_index, timestamp in enumerate((0.0, 0.2, 0.4, 0.6)):
        objects = [
            make_tracked(
                1,
                (0, 0, 20, 20),
                "sudden_deceleration" if frame_index in (1, 2) else None,
                post_behavior="stopping" if frame_index == 3 else None,
            ),
            make_tracked(2, (10, 10, 30, 30), label="motorcycle"),
        ]
        detector.observe(
            objects,
            timestamp,
            100,
            100,
            frame_index,
        )

    candidate = detector.candidates()[0]

    assert candidate["verification_status"] == "suspected"
    assert candidate["event_state"] == "suspected"


def test_single_anomaly_remains_a_suspected_candidate(monkeypatch):
    monkeypatch.setattr(settings, "detection_min_candidate_observations", 2)
    monkeypatch.setattr(settings, "detection_min_verified_observations", 4)
    detector = AccidentCandidateDetector()

    for frame_index in range(2):
        objects = [
            make_tracked(
                1,
                (0, 0, 20, 20),
                "abrupt_direction_change" if frame_index == 1 else None,
            ),
            make_tracked(2, (10, 10, 30, 30), label="person"),
        ]
        detector.observe(objects, frame_index, 100, 100, frame_index)
    detector.observe(
        [
            make_tracked(1, (0, 0, 20, 20), post_behavior="stopping"),
            make_tracked(2, (10, 10, 30, 30), label="person"),
        ],
        2,
        100,
        100,
        2,
    )

    assert detector.candidates()[0]["verification_status"] == "suspected"


def test_interaction_evidence_must_be_consecutive(monkeypatch):
    monkeypatch.setattr(settings, "detection_min_candidate_observations", 2)
    detector = AccidentCandidateDetector()
    objects = [
        make_tracked(1, (0, 0, 20, 20), "sudden_deceleration"),
        make_tracked(2, (10, 10, 30, 30), label="person"),
    ]

    detector.observe(objects, 0, 100, 100, 0)
    detector.observe([], 1, 100, 100, 1)
    detector.observe(objects, 2, 100, 100, 2)

    assert detector.candidates() == []


def test_completed_interaction_is_candidate_before_video_ends():
    detector = AccidentCandidateDetector()
    objects = [
        make_tracked(1, (0, 0, 20, 20)),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]
    anomalous_objects = [
        make_tracked(1, (0, 0, 20, 20), "sudden_deceleration"),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]
    post_anomaly_objects = [
        make_tracked(1, (0, 0, 20, 20), post_behavior="stopping"),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]

    detector.observe(objects, 0, 100, 100, 0)
    detector.observe(anomalous_objects, 1, 100, 100, 1)
    detector.observe(post_anomaly_objects, 2, 100, 100, 2)
    detector.observe([], 3, 100, 100, 3)
    detector.observe([], 4, 100, 100, 4)

    candidates = detector.candidates()

    assert len(candidates) == 1
    assert candidates[0]["start_timestamp_seconds"] == 0
    assert candidates[0]["end_timestamp_seconds"] == 2
    assert candidates[0]["verification_status"] == "suspected"


def test_post_anomaly_stopping_is_retained_after_interaction_ends():
    detector = AccidentCandidateDetector()
    close_objects = [
        make_tracked(1, (0, 0, 20, 20)),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]
    anomalous_objects = [
        make_tracked(1, (0, 0, 20, 20), "sudden_deceleration"),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]

    detector.observe(close_objects, 0, 100, 100, 0)
    detector.observe(anomalous_objects, 1, 100, 100, 1)
    detector.observe(
        [
            make_tracked(
                1,
                (0, 0, 20, 20),
                post_behavior="continued_movement",
            ),
            make_tracked(2, (200, 200, 220, 220), label="truck"),
        ],
        2,
        100,
        100,
        2,
    )
    detector.observe(
        [
            make_tracked(
                1,
                (0, 0, 20, 20),
                post_behavior="continued_movement",
            ),
        ],
        3,
        100,
        100,
        3,
    )
    detector.observe(
        [make_tracked(1, (0, 0, 20, 20), post_behavior="stopping")],
        4,
        100,
        100,
        4,
    )

    candidates = detector.candidates()

    assert len(candidates) == 1
    assert candidates[0]["end_timestamp_seconds"] == 1
    assert "stopping" in candidates[0]["evidence_summary"]
    assert any(
        reference.startswith("post-anomaly:1:stopping@4.000s")
        for reference in candidates[0]["evidence_references"]
    )


def test_multiple_separate_interaction_episodes_are_distinct_candidates():
    detector = AccidentCandidateDetector()
    objects = [
        make_tracked(1, (0, 0, 20, 20)),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]
    anomalous_objects = [
        make_tracked(1, (0, 0, 20, 20), "sudden_deceleration"),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]
    post_anomaly_objects = [
        make_tracked(1, (0, 0, 20, 20), post_behavior="stopping"),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]

    detector.observe(objects, 0, 100, 100, 0)
    detector.observe(anomalous_objects, 1, 100, 100, 1)
    detector.observe(post_anomaly_objects, 2, 100, 100, 2)
    detector.observe([], 3, 100, 100, 3)
    detector.observe(objects, 4, 100, 100, 4)
    detector.observe(anomalous_objects, 5, 100, 100, 5)
    detector.observe(post_anomaly_objects, 6, 100, 100, 6)
    detector.observe([], 7, 100, 100, 7)
    detector.observe([], 8, 100, 100, 8)

    candidates = detector.candidates()

    assert len(candidates) == 2
    assert [candidate["start_timestamp_seconds"] for candidate in candidates] == [
        0,
        4,
    ]
    assert len({candidate["candidate_id"] for candidate in candidates}) == 2


def test_candidate_retrieval_does_not_duplicate_an_interaction_episode():
    detector = AccidentCandidateDetector()
    objects = [
        make_tracked(1, (0, 0, 20, 20), "sudden_deceleration"),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]

    detector.observe(objects, 0, 100, 100, 0)
    detector.observe(objects, 1, 100, 100, 1)
    detector.observe(
        [
            make_tracked(1, (0, 0, 20, 20), post_behavior="stopping"),
            make_tracked(2, (10, 10, 30, 30), label="truck"),
        ],
        2,
        100,
        100,
        2,
    )
    detector.observe([], 3, 100, 100, 3)

    candidates = detector.candidates()

    assert len(candidates) == 1
    assert len({candidate["candidate_id"] for candidate in candidates}) == 1
    assert detector.candidates() == candidates


def test_collision_like_deceleration_and_close_interaction_create_candidate(
    monkeypatch,
):
    monkeypatch.setattr(settings, "detection_min_candidate_observations", 2)
    tracker = TrajectoryTracker()
    detector = AccidentCandidateDetector()
    vehicle_positions = (
        (0, 0, 20, 20),
        (100, 0, 120, 20),
        (200, 0, 220, 20),
        (201, 0, 221, 20),
        (201, 0, 221, 20),
    )

    for frame_index, bbox in enumerate(vehicle_positions):
        tracked = tracker.update(
            [
                make_detection(1, bbox, "car"),
                make_detection(2, (205, 0, 225, 20), "truck"),
            ],
            float(frame_index),
        )
        detector.observe(
            tracked,
            float(frame_index),
            frame_width=1000,
            frame_height=1000,
            frame_index=frame_index,
        )

    candidates = detector.candidates()

    assert len(candidates) == 1
    assert candidates[0]["verification_status"] == "suspected"
    assert candidates[0]["involved_track_ids"] == [1, 2]
    assert candidates[0]["motion_events"] == 1


def test_transient_deceleration_with_speed_recovery_is_not_candidate():
    tracker = TrajectoryTracker()
    detector = AccidentCandidateDetector()
    positions = (
        (0, 0, 20, 20),
        (20, 0, 40, 20),
        (21, 0, 41, 20),
        (40, 0, 60, 20),
    )

    for frame_index, bbox in enumerate(positions):
        tracked = tracker.update(
            [
                make_detection(1, bbox),
                make_detection(2, (30, 0, 50, 20), "truck"),
            ],
            float(frame_index),
        )
        detector.observe(tracked, float(frame_index), 1000, 1000, frame_index)

    candidates = detector.candidates()

    assert candidates == []


def test_approaching_then_separating_pair_retains_relative_motion_evidence(
    monkeypatch,
):
    monkeypatch.setattr(settings, "detection_min_candidate_observations", 2)
    detector = AccidentCandidateDetector()
    first_centers = (20, 20, 20, 20)
    second_centers = (100, 70, 40, 70)

    for frame_index, (first_center, second_center) in enumerate(
        zip(first_centers, second_centers)
    ):
        objects = [
            make_tracked(
                1,
                (first_center - 10, 0, first_center + 10, 20),
                "sudden_deceleration" if frame_index == 1 else None,
            ),
            make_tracked(
                2,
                (second_center - 10, 0, second_center + 10, 20),
                label="truck",
            ),
        ]
        detector.observe(objects, float(frame_index), 1000, 1000, frame_index)

    candidates = detector.candidates()

    assert len(candidates) == 1
    assert "approaching" in candidates[0]["evidence_summary"]
    assert "separating" in candidates[0]["evidence_summary"]
    assert any(
        reference.startswith(
            "pair-motion:approaching:separation=50.00px:rate=-30.00px/s"
        )
        for reference in candidates[0]["evidence_references"]
    )
    assert any(
        reference.startswith("pair-motion:separating")
        for reference in candidates[0]["evidence_references"]
    )


def test_sustained_deceleration_after_close_interaction_is_candidate(monkeypatch):
    monkeypatch.setattr(settings, "detection_min_candidate_observations", 2)
    tracker = TrajectoryTracker()
    detector = AccidentCandidateDetector()
    positions = (0, 100, 120, 136, 148)

    for frame_index, left in enumerate(positions):
        tracked = tracker.update(
            [
                make_detection(1, (left, 0, left + 20, 20)),
                make_detection(2, (140, 0, 160, 20), "truck"),
            ],
            float(frame_index),
        )
        detector.observe(tracked, float(frame_index), 1000, 1000, frame_index)

    candidates = detector.candidates()

    assert len(candidates) == 1
    assert "sustained_deceleration" in candidates[0]["evidence_summary"]
    assert any(
        reference.startswith("post-anomaly:1:sustained_deceleration")
        for reference in candidates[0]["evidence_references"]
    )


def test_ordinary_turn_with_continued_movement_is_not_candidate():
    tracker = TrajectoryTracker()
    detector = AccidentCandidateDetector()
    centers = (100, 120, 140, 120, 100, 80)

    for frame_index, center in enumerate(centers):
        tracked = tracker.update(
            [
                make_detection(1, (center - 10, 0, center + 10, 20)),
                make_detection(2, (140, 0, 160, 20), "truck"),
            ],
            float(frame_index),
        )
        detector.observe(tracked, float(frame_index), 1000, 1000, frame_index)

    assert detector.candidates() == []


def test_overlapping_episodes_sharing_a_track_group_and_keep_episode_evidence():
    detector = AccidentCandidateDetector()
    objects = [
        make_tracked(1, (0, 0, 20, 20)),
        make_tracked(2, (10, 0, 30, 20), label="truck"),
        make_tracked(3, (20, 0, 40, 20)),
    ]
    anomalous_objects = [
        make_tracked(1, (0, 0, 20, 20)),
        make_tracked(2, (10, 0, 30, 20), "sudden_deceleration", label="truck"),
        make_tracked(3, (20, 0, 40, 20)),
    ]
    stopped_objects = [
        make_tracked(1, (0, 0, 20, 20)),
        make_tracked(
            2,
            (10, 0, 30, 20),
            label="truck",
            post_behavior="stopping",
        ),
        make_tracked(3, (20, 0, 40, 20)),
    ]

    detector.observe(objects, 0, 1000, 1000, 0)
    detector.observe(anomalous_objects, 1, 1000, 1000, 1)
    detector.observe(stopped_objects, 2, 1000, 1000, 2)

    candidates = detector.candidates()

    assert len(candidates) == 1
    assert candidates[0]["involved_track_ids"] == [1, 2, 3]
    assert candidates[0]["motion_events"] == 1
    assert candidates[0]["verification_status"] == "suspected"
    assert "Grouped 2 overlapping interaction episodes" in candidates[0]["evidence_summary"]
    assert "tracks:1:2:episode:1" in candidates[0]["evidence_summary"]
    assert "tracks:2:3:episode:" in candidates[0]["evidence_summary"]
    assert "events=[(2, 1.0, 'sudden_deceleration')]" in candidates[0]["evidence_summary"]
    assert "type=vehicle_vehicle" in candidates[0]["evidence_summary"]
    assert any(
        reference.startswith("frame:1@")
        for reference in candidates[0]["evidence_references"]
    )


def test_grouped_episode_deduplicates_same_track_anomaly_and_keeps_episode_evidence():
    detector = AccidentCandidateDetector()
    shared_event = (2, 1.0, "sudden_deceleration")
    candidates = detector._group_overlapping_candidates(
        [
            make_episode_candidate(
                "tracks:1:2:episode:4",
                1.0,
                2.0,
                [1, 2],
                [shared_event],
            ),
            make_episode_candidate(
                "tracks:2:3:episode:7",
                1.5,
                2.5,
                [2, 3],
                [shared_event],
            ),
        ]
    )

    assert len(candidates) == 1
    incident = candidates[0]
    assert incident["motion_events"] == 1
    assert incident["verification_status"] == "suspected"
    assert "tracks:1:2:episode:4 [1.000-2.000s" in incident["evidence_summary"]
    assert "tracks:2:3:episode:7 [1.500-2.500s" in incident["evidence_summary"]
    assert "tracks=1,2" in incident["evidence_summary"]
    assert "tracks=2,3" in incident["evidence_summary"]
    assert set(incident["evidence_references"]) == {
        "frame:tracks:1:2:episode:4",
        "frame:tracks:2:3:episode:7",
    }


def test_grouped_episodes_count_different_tracks_anomalies_independently():
    detector = AccidentCandidateDetector()
    candidates = detector._group_overlapping_candidates(
        [
            make_episode_candidate(
                "tracks:1:2:episode:1",
                1.0,
                2.0,
                [1, 2],
                [(1, 1.5, "sudden_deceleration")],
            ),
            make_episode_candidate(
                "tracks:2:3:episode:2",
                1.0,
                2.0,
                [2, 3],
                [(3, 1.5, "sudden_deceleration")],
            ),
        ]
    )

    assert candidates[0]["motion_events"] == 2


def test_grouped_episodes_count_different_anomaly_types_independently():
    detector = AccidentCandidateDetector()
    candidates = detector._group_overlapping_candidates(
        [
            make_episode_candidate(
                "tracks:1:2:episode:1",
                1.0,
                2.0,
                [1, 2],
                [(2, 1.5, "sudden_deceleration")],
            ),
            make_episode_candidate(
                "tracks:2:3:episode:2",
                1.0,
                2.0,
                [2, 3],
                [(2, 1.5, "abrupt_direction_change")],
            ),
        ]
    )

    assert candidates[0]["motion_events"] == 2


def test_pedestrian_vehicle_interaction_remains_a_candidate(monkeypatch):
    monkeypatch.setattr(settings, "detection_min_candidate_observations", 2)
    detector = AccidentCandidateDetector()
    person = make_tracked(1, (0, 0, 20, 20), label="person")
    car = make_tracked(2, (10, 0, 30, 20))
    anomalous_car = make_tracked(
        2,
        (10, 0, 30, 20),
        anomaly="sudden_deceleration",
    )
    stopped_car = make_tracked(
        2,
        (10, 0, 30, 20),
        post_behavior="stopping",
    )

    detector.observe([person, car], 0.0, 100, 100, 0)
    detector.observe([person, anomalous_car], 1.0, 100, 100, 1)
    detector.observe([person, stopped_car], 2.0, 100, 100, 2)

    candidates = detector.candidates()

    assert len(candidates) == 1
    assert candidates[0]["involved_track_ids"] == [1, 2]
    assert "Interaction type: pedestrian_vehicle" in candidates[0]["evidence_summary"]
    assert candidates[0]["verification_status"] == "suspected"


def test_close_normal_traffic_without_motion_anomaly_is_not_a_candidate():
    detector = AccidentCandidateDetector()
    objects = [
        make_tracked(1, (0, 0, 20, 20)),
        make_tracked(2, (10, 10, 30, 30), label="truck"),
    ]

    for frame_index in range(6):
        detector.observe(objects, frame_index, 100, 100, frame_index)

    assert detector.candidates() == []


def test_brief_event_between_sampled_frames_is_not_observed(tmp_path, monkeypatch):
    frames = [FakeFrame() for _ in range(5)]
    brief_event_frame = frames[1]
    install_fake_cv2(monkeypatch, frames, fps=2.0)

    sampled = list(
        iter_video_frames(
            tmp_path / "source.mp4",
            interval_seconds=1,
            max_dimension=1280,
        )
    )

    assert [frame.frame_index for frame in sampled] == [0, 2, 4]
    assert brief_event_frame not in [frame.frame for frame in sampled]


def test_pipeline_persists_sampled_detections_and_progress(monkeypatch, tmp_path):
    class FakeDetector:
        device = "cpu"

        def reset_tracking(self):
            pass

        def detect(self, frame):
            return [make_detection(1)]

    frames = [
        SimpleNamespace(
            frame_index=index * 2,
            timestamp_seconds=float(index),
            frame_count=6,
            frame=FakeFrame(),
        )
        for index in range(3)
    ]
    monkeypatch.setattr(
        "app.services.detection.pipeline.YOLODetector",
        FakeDetector,
    )
    monkeypatch.setattr(
    "app.services.detection.pipeline.AccidentYOLODetector",
    lambda device: SimpleNamespace(
        model_name="test-accident-model",
        detect=lambda frame: [],
    ),
    )
    monkeypatch.setattr(
        "app.services.detection.pipeline.iter_video_frames",
        lambda *args, **kwargs: iter(frames),
    )
    progress = []

    result = analyze_video(
        tmp_path / "source.mp4",
        progress_callback=progress.append,
        cancellation_requested=lambda: False,
    )

    assert result["summary"]["frames_processed"] == 3
    assert result["summary"]["detections_processed"] == 3
    assert result["summary"]["device"] == "cpu"
    assert result["summary"]["processing_seconds"] >= 0
    assert result["summary"]["processing_fps"] is None or (
        result["summary"]["processing_fps"] > 0
    )
    assert result["summary"]["accident_classification"]["label"] == "UNKNOWN"
    assert (
        result["summary"]["accident_classification"]["reason_code"]
        == "weights_not_configured"
    )
    assert result["frames"][0]["objects"][0]["track_id"] == 1
    assert progress == [16, 50, 82]


def test_classifier_uses_finer_sampling_without_changing_yolo_cadence(
    monkeypatch,
    tmp_path,
):
    class FakeDetector:
        device = "cpu"

        def __init__(self):
            self.timestamps = []

        def reset_tracking(self):
            pass

        def detect(self, frame):
            self.timestamps.append(frame.timestamp)
            return []

    class FakeClassifier:
        enabled = True
        observations = []

        def __init__(self, weights_path, device, **kwargs):
            self.__class__.observations = []

        def observe(self, frame, timestamp_seconds):
            self.observations.append(timestamp_seconds)

        def result(self):
            return {"label": "UNKNOWN", "model_status": "loaded_unvalidated"}

    detector = FakeDetector()
    frames = [
        SimpleNamespace(
            frame_index=index,
            timestamp_seconds=index / 10,
            frame_count=21,
            frame=SimpleNamespace(shape=(100, 200, 3), timestamp=index / 10),
        )
        for index in range(21)
    ]
    monkeypatch.setattr(settings, "accident_classifier_weights", "synthetic.pth")
    monkeypatch.setattr(settings, "accident_classifier_frame_interval_seconds", 0.1)
    monkeypatch.setattr(
        "app.services.detection.pipeline.YOLODetector",
        lambda: detector,
    )
    monkeypatch.setattr(
        "app.services.detection.pipeline.AccidentClassifier",
        FakeClassifier,
    )
    monkeypatch.setattr(
    "app.services.detection.pipeline.AccidentYOLODetector",
    lambda device: SimpleNamespace(
        model_name="test-accident-model",
        detect=lambda frame: [],
    ),
)
    intervals = []

    def frames_at_interval(*args, **kwargs):
        intervals.append(kwargs["interval_seconds"])
        return iter(frames)

    monkeypatch.setattr(
        "app.services.detection.pipeline.iter_video_frames",
        frames_at_interval,
    )

    result = analyze_video(
        tmp_path / "source.mp4",
        progress_callback=lambda value: None,
        cancellation_requested=lambda: False,
    )

    assert intervals == [0.1]
    assert len(FakeClassifier.observations) == 21
    assert detector.timestamps == [0.0, 1.0, 2.0]
    assert result["summary"]["accident_classification"]["model_status"] == (
        "loaded_unvalidated"
    )


def test_pipeline_honors_cancellation_between_frames(monkeypatch, tmp_path):
    class FakeDetector:
        device = "cpu"

        def reset_tracking(self):
            pass

        def detect(self, frame):
            raise AssertionError("Inference should not run after cancellation.")

    monkeypatch.setattr(
        "app.services.detection.pipeline.YOLODetector",
        FakeDetector,
    )
    monkeypatch.setattr(
        "app.services.detection.pipeline.iter_video_frames",
        lambda *args, **kwargs: iter(
            [SimpleNamespace(frame=FakeFrame(), frame_index=0)]
        ),
    )

    with pytest.raises(AnalysisCancelled):
        analyze_video(
            tmp_path / "source.mp4",
            progress_callback=lambda value: None,
            cancellation_requested=lambda: True,
        )
