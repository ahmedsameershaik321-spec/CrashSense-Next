import argparse
import hashlib
import json
import random
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import URLError

from app.services.detection.accident_classifier import (
    ARCHITECTURE,
    CLASS_TO_INDEX,
    AccidentClassifierError,
    build_temporal_model,
    prepare_model_input,
    preprocess_bgr_frame,
    resolve_classifier_device,
)
from app.services.detection.ccd_dataset import (
    load_authorized_split,
    require_permission_record,
)
from app.services.detection.evaluation import evaluate_predictions, select_thresholds


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the CrashSense temporal classifier from an authorized split."
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--permission-record", type=Path, required=True)
    parser.add_argument("--confirm-authorized-use", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def _read_clip(path: Path) -> list[Any]:
    try:
        import cv2
    except ImportError as exc:
        raise AccidentClassifierError("OpenCV is required to train the classifier.") from exc

    capture = cv2.VideoCapture(str(path))
    frames: list[Any] = []
    try:
        if not capture.isOpened():
            raise AccidentClassifierError(f"Could not open training video: {path.name}.")
        while len(frames) <= 50:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(preprocess_bgr_frame(frame))
    finally:
        capture.release()

    if len(frames) != 50:
        raise AccidentClassifierError(
            f"Training video {path.name} must decode to exactly 50 annotated frames; "
            f"decoded {len(frames)}."
        )
    return frames


def _dataset(rows: list[dict[str, Any]], torch: Any) -> Any:
    class ClipDataset(torch.utils.data.Dataset):
        def __len__(self) -> int:
            return len(rows)

        def __getitem__(self, index: int) -> tuple[Any, Any]:
            row = rows[index]
            frames = _read_clip(row["path"])
            inputs = prepare_model_input(frames)
            label = CLASS_TO_INDEX[row["label"]]
            return inputs, torch.tensor(label, dtype=torch.long)

    return ClipDataset()


def _validation_predictions(
    model: Any,
    loader: Any,
    device: str,
    torch: Any,
) -> tuple[list[float], float]:
    model.eval()
    probabilities: list[float] = []
    loss_total = 0.0
    sample_count = 0
    loss_function = torch.nn.CrossEntropyLoss()
    with torch.inference_mode():
        for inputs, targets in loader:
            inputs = inputs.to(device)
            targets = targets.to(device)
            logits = model(inputs)
            loss_total += float(loss_function(logits, targets).item()) * len(targets)
            probabilities.extend(
                float(value)
                for value in torch.softmax(logits, dim=1)[:, 1].cpu().tolist()
            )
            sample_count += len(targets)
    return probabilities, loss_total / sample_count


def _save_checkpoint(path: Path, checkpoint: dict[str, Any], torch: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        torch.save(checkpoint, temporary_path)
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite checkpoint: {path}")
        temporary_path.rename(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main() -> None:
    args = _arguments()
    if args.epochs <= 0 or args.batch_size <= 0 or args.learning_rate <= 0:
        raise SystemExit("epochs, batch-size, and learning-rate must be positive.")
    if args.output.suffix.lower() not in {".pt", ".pth"}:
        raise SystemExit("Checkpoint output must use a .pt or .pth extension.")
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite checkpoint: {args.output}")

    require_permission_record(args.permission_record)
    train_rows = load_authorized_split(
        args.dataset_root,
        args.manifest,
        {"train"},
    )
    validation_rows = load_authorized_split(
        args.dataset_root,
        args.manifest,
        {"validation"},
    )
    try:
        import torch
    except ImportError as exc:
        raise SystemExit("PyTorch is required to train the classifier.") from exc

    device = resolve_classifier_device(args.device)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    generator = torch.Generator().manual_seed(args.seed)

    training_loader = torch.utils.data.DataLoader(
        _dataset(train_rows, torch),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=device.startswith("cuda"),
        generator=generator,
    )
    validation_loader = torch.utils.data.DataLoader(
        _dataset(validation_rows, torch),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=device.startswith("cuda"),
    )
    try:
        model = build_temporal_model(pretrained_backbone=True).to(device)
    except (OSError, RuntimeError, URLError) as exc:
        raise AccidentClassifierError(
            "Could not load the ImageNet-pretrained MobileNetV3-Small backbone. "
            "Check torchvision weights and network/cache availability."
        ) from exc
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=1e-4,
    )
    loss_function = torch.nn.CrossEntropyLoss()
    labels = [row["label"] for row in validation_rows]
    manifest_hash = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    best_score: tuple[float, float, float] | None = None
    best_epoch = 0
    best_metrics: dict[str, Any] | None = None
    best_checkpoint: dict[str, Any] | None = None

    for epoch in range(1, args.epochs + 1):
        model.train()
        for inputs, targets in training_loader:
            inputs = inputs.to(device)
            targets = targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_function(model(inputs), targets)
            loss.backward()
            optimizer.step()

        probabilities, validation_loss = _validation_predictions(
            model,
            validation_loader,
            device,
            torch,
        )
        thresholds = select_thresholds(labels, probabilities)
        predictions = [
            "ACCIDENT"
            if probability >= thresholds["accident"]
            else "NORMAL"
            if probability <= thresholds["normal"]
            else "UNKNOWN"
            for probability in probabilities
        ]
        metrics = evaluate_predictions(
            [
                {"label": label, "prediction": prediction, "processing_seconds": 0.0}
                for label, prediction in zip(labels, predictions, strict=True)
            ]
        )
        score = (
            metrics["f1"] or 0.0,
            metrics["coverage"],
            -validation_loss,
        )
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "validation_loss": validation_loss,
                    "validation_f1": metrics["f1"],
                    "validation_coverage": metrics["coverage"],
                }
            ),
            flush=True,
        )
        if best_score is not None and score <= best_score:
            continue

        best_score = score
        best_epoch = epoch
        best_metrics = metrics
        checkpoint = {
            "architecture": ARCHITECTURE,
            "class_to_index": CLASS_TO_INDEX,
            "state_dict": {
                name: value.detach().cpu()
                for name, value in model.state_dict().items()
            },
            "thresholds": thresholds,
            "training": {
                "seed": args.seed,
                "device": device,
                "epochs_requested": args.epochs,
                "epochs_completed": args.epochs,
                "selected_epoch": best_epoch,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "optimizer": "AdamW",
                "weight_decay": 1e-4,
                "source_frames_per_video": 50,
                "model_input_frames": 16,
                "frame_size": 112,
                "pretrained_backbone": "MobileNet_V3_Small_Weights.DEFAULT",
                "train_videos": len(train_rows),
                "validation_videos": len(validation_rows),
                "validation_loss": validation_loss,
                "validation_metrics": metrics,
                "dataset_manifest_sha256": manifest_hash,
                "thresholds_selected_from": "validation",
            },
        }
        best_checkpoint = checkpoint

    if best_checkpoint is None:
        raise RuntimeError("Training completed without a validation checkpoint.")
    _save_checkpoint(args.output, best_checkpoint, torch)

    print(
        json.dumps(
            {
                "checkpoint": str(args.output),
                "device": device,
                "selected_epoch": best_epoch,
                "validation_metrics": best_metrics,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
