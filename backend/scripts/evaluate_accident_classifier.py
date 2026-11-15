import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from app.services.detection.accident_classifier import (
    AccidentClassifier,
    resolve_classifier_device,
)
from app.services.detection.ccd_dataset import (
    load_authorized_split,
    require_permission_record,
)
from app.services.detection.evaluation import evaluate_predictions
from app.services.detection.frames import iter_video_frames


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a fixed classifier checkpoint on the held-out test split."
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--permission-record", type=Path, required=True)
    parser.add_argument("--confirm-authorized-use", action="store_true", required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--frame-interval", type=float, default=0.1)
    parser.add_argument("--max-dimension", type=int, default=1280)
    return parser.parse_args()


def _prediction(classification: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": classification["label"],
        "reason_code": classification["reason_code"],
        "max_accident_score": classification["max_accident_score"],
        "windows_evaluated": classification["windows_evaluated"],
        "partial_window_frames": classification["partial_window_frames"],
        "evidence_windows": classification["evidence_windows"],
    }


def main() -> None:
    args = _arguments()
    if args.frame_interval <= 0 or args.max_dimension <= 0:
        raise SystemExit("frame-interval and max-dimension must be positive.")
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite evaluation output: {args.output}")
    require_permission_record(args.permission_record)
    test_rows = load_authorized_split(
        args.dataset_root,
        args.manifest,
        {"test"},
    )
    device = resolve_classifier_device(args.device)
    records: list[dict[str, Any]] = []

    for row in test_rows:
        classifier = AccidentClassifier(
            str(args.weights),
            device,
            frame_interval_seconds=args.frame_interval,
        )
        started = perf_counter()
        for frame in iter_video_frames(
            row["path"],
            interval_seconds=args.frame_interval,
            max_dimension=args.max_dimension,
        ):
            classifier.observe(frame.frame, frame.timestamp_seconds)
        classification = classifier.result()
        elapsed = perf_counter() - started
        records.append(
            {
                "video_path": row["video_path"],
                "source_dataset": row["source_dataset"],
                "source_video_id": row["source_video_id"],
                "label": row["label"],
                "prediction": classification["label"],
                "processing_seconds": elapsed,
                "details": _prediction(classification),
            }
        )
        print(
            json.dumps(
                {
                    "split": "test",
                    "video": row["video_path"],
                    "label": row["label"],
                    "prediction": classification["label"],
                    "processing_seconds": round(elapsed, 4),
                }
            ),
            flush=True,
        )

    metrics = evaluate_predictions(records)
    report = {
        "evaluation": "held_out_test",
        "thresholds_source": "checkpoint_validation",
        "device": device,
        "frame_interval_seconds": args.frame_interval,
        "max_dimension": args.max_dimension,
        "metrics": metrics,
        "videos": records,
        "caveat": (
            "Metrics describe this dataset split and checkpoint only. "
            "They do not establish production accuracy or generalization."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, allow_nan=False)
        report_file.write("\n")
    print(
        json.dumps(
            {
                "evaluation": "held_out_test",
                "device": device,
                "metrics": metrics,
                "output": str(args.output),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
