import pytest

from app.services.detection.evaluation import evaluate_predictions, select_thresholds


def test_evaluation_counts_unknown_accidents_as_misses_not_positive_predictions():
    metrics = evaluate_predictions(
        [
            {"label": "ACCIDENT", "prediction": "ACCIDENT", "processing_seconds": 0.1},
            {"label": "ACCIDENT", "prediction": "UNKNOWN", "processing_seconds": 0.1},
            {"label": "NORMAL", "prediction": "NORMAL", "processing_seconds": 0.1},
            {"label": "NORMAL", "prediction": "ACCIDENT", "processing_seconds": 0.1},
        ]
    )

    assert metrics["confusion_matrix"]["counts"] == [[1, 1, 0], [0, 1, 1]]
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["false_positive_rate"] == 0.5
    assert metrics["false_negative_rate"] == 0.5
    assert metrics["unknown_predictions"] == 1
    assert metrics["coverage"] == 0.75
    assert metrics["videos_per_second"] == 10


def test_validation_threshold_selection_requires_both_classes():
    thresholds = select_thresholds(["NORMAL", "ACCIDENT"], [0.05, 0.95])
    predictions = [
        "ACCIDENT"
        if score >= thresholds["accident"]
        else "NORMAL"
        if score <= thresholds["normal"]
        else "UNKNOWN"
        for score in [0.05, 0.95]
    ]

    assert thresholds["normal"] < thresholds["accident"]
    assert predictions == ["NORMAL", "ACCIDENT"]
    with pytest.raises(ValueError, match="contain NORMAL and ACCIDENT"):
        select_thresholds(["ACCIDENT"], [0.95])


def test_metrics_reject_invalid_scores_and_empty_evaluation():
    with pytest.raises(ValueError, match="No labeled predictions"):
        evaluate_predictions([])
    with pytest.raises(ValueError, match="finite non-negative processing time"):
        evaluate_predictions(
            [{"label": "NORMAL", "prediction": "UNKNOWN", "processing_seconds": -1}]
        )
