import numpy as np
import pytest

from app.services.detection.accident_classifier import (
    ARCHITECTURE,
    CLASS_TO_INDEX,
    AccidentClassifier,
    AccidentClassifierError,
    build_temporal_model,
)


def test_missing_classifier_weights_are_explicitly_unknown():
    classifier = AccidentClassifier(weights_path=None, device="cpu")

    result = classifier.result()

    assert result["label"] == "UNKNOWN"
    assert result["model_status"] == "not_configured"
    assert result["reason_code"] == "weights_not_configured"
    assert result["confidence"] is None
    assert result["human_review_required"] is True


def test_configured_missing_weights_raise_an_error(tmp_path):
    with pytest.raises(AccidentClassifierError, match="do not exist"):
        AccidentClassifier(str(tmp_path / "missing.pth"), "cpu")


def test_unvalidated_checkpoint_runs_temporal_inference_conservatively(tmp_path):
    torch = pytest.importorskip("torch")
    weights_path = tmp_path / "synthetic.pth"
    model = build_temporal_model()
    torch.save(
        {
            "architecture": ARCHITECTURE,
            "class_to_index": CLASS_TO_INDEX,
            "state_dict": model.state_dict(),
            "thresholds": {"normal": 0.0, "accident": 1.0},
        },
        weights_path,
    )
    classifier = AccidentClassifier(str(weights_path), "cpu")
    frame = np.zeros((96, 160, 3), dtype=np.uint8)
    for frame_index in range(50):
        classifier.observe(frame, frame_index / 10)

    result = classifier.result()

    assert result["label"] == "UNKNOWN"
    assert result["model_status"] == "loaded_unvalidated"
    assert result["windows_evaluated"] == 1
    assert result["partial_window_frames"] == 0
    assert result["confidence"] is None
    assert result["max_accident_score"] is not None
    assert len(result["evidence_windows"]) == 1
    assert result["human_review_required"] is True


def test_accident_score_never_becomes_calibrated_confidence(tmp_path):
    torch = pytest.importorskip("torch")
    weights_path = tmp_path / "synthetic.pth"
    model = build_temporal_model()
    torch.save(
        {
            "architecture": ARCHITECTURE,
            "class_to_index": CLASS_TO_INDEX,
            "state_dict": model.state_dict(),
            "thresholds": {"normal": 0.1, "accident": 0.9},
        },
        weights_path,
    )
    classifier = AccidentClassifier(str(weights_path), "cpu")

    class FixedModel:
        def __call__(self, frames):
            return torch.tensor([[0.0, 10.0]], device=frames.device)

    classifier.model = FixedModel()
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    for frame_index in range(50):
        classifier.observe(frame, frame_index / 10)

    result = classifier.result()

    assert result["label"] == "ACCIDENT"
    assert result["confidence"] is None
    assert result["max_accident_score"] > 0.9
    assert result["model_status"] == "loaded_unvalidated"


def test_frame_timestamps_must_increase_for_configured_model(tmp_path):
    torch = pytest.importorskip("torch")
    weights_path = tmp_path / "synthetic.pth"
    model = build_temporal_model()
    torch.save(
        {
            "architecture": ARCHITECTURE,
            "class_to_index": CLASS_TO_INDEX,
            "state_dict": model.state_dict(),
            "thresholds": {"normal": 0.0, "accident": 1.0},
        },
        weights_path,
    )
    classifier = AccidentClassifier(str(weights_path), "cpu")
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    classifier.observe(frame, 1.0)

    with pytest.raises(AccidentClassifierError, match="strictly increasing"):
        classifier.observe(frame, 1.0)


def test_threshold_overrides_do_not_mutate_cached_checkpoint_metadata(tmp_path):
    torch = pytest.importorskip("torch")
    weights_path = tmp_path / "synthetic.pth"
    model = build_temporal_model()
    torch.save(
        {
            "architecture": ARCHITECTURE,
            "class_to_index": CLASS_TO_INDEX,
            "state_dict": model.state_dict(),
            "thresholds": {"normal": 0.2, "accident": 0.8},
        },
        weights_path,
    )

    AccidentClassifier(
        str(weights_path),
        "cpu",
        normal_threshold=0.1,
        accident_threshold=0.9,
    )
    second_classifier = AccidentClassifier(str(weights_path), "cpu")

    assert second_classifier.thresholds == {"normal": 0.2, "accident": 0.8}
