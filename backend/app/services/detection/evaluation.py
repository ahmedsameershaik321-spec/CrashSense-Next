import math
from collections.abc import Iterable, Mapping
from typing import Any


GROUND_TRUTH_LABELS = ("NORMAL", "ACCIDENT")
PREDICTION_LABELS = ("NORMAL", "ACCIDENT", "UNKNOWN")


def evaluate_predictions(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    confusion = {
        actual: {predicted: 0 for predicted in PREDICTION_LABELS}
        for actual in GROUND_TRUTH_LABELS
    }
    processing_seconds = 0.0
    total = 0

    for row in rows:
        actual = row.get("label")
        predicted = row.get("prediction")
        elapsed = row.get("processing_seconds")
        if actual not in GROUND_TRUTH_LABELS:
            raise ValueError(f"Unsupported ground-truth label: {actual!r}.")
        if predicted not in PREDICTION_LABELS:
            raise ValueError(f"Unsupported prediction label: {predicted!r}.")
        if (
            isinstance(elapsed, bool)
            or not isinstance(elapsed, (int, float))
            or not math.isfinite(elapsed)
            or elapsed < 0
        ):
            raise ValueError("Each row needs a finite non-negative processing time.")

        confusion[actual][predicted] += 1
        processing_seconds += elapsed
        total += 1

    if not total:
        raise ValueError("No labeled predictions were provided.")

    true_positive = confusion["ACCIDENT"]["ACCIDENT"]
    false_positive = confusion["NORMAL"]["ACCIDENT"]
    false_negative = (
        confusion["ACCIDENT"]["NORMAL"]
        + confusion["ACCIDENT"]["UNKNOWN"]
    )
    positive_total = sum(confusion["ACCIDENT"].values())
    negative_total = sum(confusion["NORMAL"].values())
    predicted_positive = true_positive + false_positive
    precision = (
        true_positive / predicted_positive if predicted_positive else None
    )
    recall = true_positive / positive_total if positive_total else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else 0.0 if positive_total else None
    )

    return {
        "samples": total,
        "confusion_matrix": {
            "rows": list(GROUND_TRUTH_LABELS),
            "columns": list(PREDICTION_LABELS),
            "counts": [
                [confusion[actual][predicted] for predicted in PREDICTION_LABELS]
                for actual in GROUND_TRUTH_LABELS
            ],
        },
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": (
            false_positive / negative_total if negative_total else None
        ),
        "false_negative_rate": (
            false_negative / positive_total if positive_total else None
        ),
        "unknown_predictions": (
            confusion["NORMAL"]["UNKNOWN"] + confusion["ACCIDENT"]["UNKNOWN"]
        ),
        "coverage": (
            (total - confusion["NORMAL"]["UNKNOWN"] - confusion["ACCIDENT"]["UNKNOWN"])
            / total
        ),
        "processing_seconds_total": processing_seconds,
        "videos_per_second": (
            total / processing_seconds if processing_seconds > 0 else None
        ),
        "unknown_handling": (
            "UNKNOWN is counted as a false negative for actual ACCIDENT labels and "
            "as an abstention for NORMAL labels; it is never counted as an "
            "ACCIDENT prediction."
        ),
    }


def select_thresholds(
    labels: list[str],
    probabilities: list[float],
) -> dict[str, float]:
    if not labels or len(labels) != len(probabilities):
        raise ValueError("Validation labels and probabilities must have equal length.")
    if set(labels) != set(GROUND_TRUTH_LABELS):
        raise ValueError("Validation data must contain NORMAL and ACCIDENT labels.")
    if any(
        not math.isfinite(probability) or not 0 <= probability <= 1
        for probability in probabilities
    ):
        raise ValueError("Validation probabilities must be finite values in [0, 1].")

    candidates = sorted({index / 100 for index in range(5, 100, 5)})
    best: tuple[float, float, float, float] | None = None
    selected = {"normal": 0.1, "accident": 0.9}
    for accident_threshold in candidates:
        for normal_threshold in candidates:
            if normal_threshold >= accident_threshold:
                continue
            predictions = [
                "ACCIDENT"
                if probability >= accident_threshold
                else "NORMAL"
                if probability <= normal_threshold
                else "UNKNOWN"
                for probability in probabilities
            ]
            metrics = evaluate_predictions(
                [
                    {
                        "label": label,
                        "prediction": prediction,
                        "processing_seconds": 0.0,
                    }
                    for label, prediction in zip(labels, predictions, strict=True)
                ]
            )
            f1 = metrics["f1"] or 0.0
            score = (
                f1,
                metrics["coverage"],
                -accident_threshold,
                normal_threshold,
            )
            if best is None or score > best:
                best = score
                selected = {
                    "normal": normal_threshold,
                    "accident": accident_threshold,
                }
    return selected
