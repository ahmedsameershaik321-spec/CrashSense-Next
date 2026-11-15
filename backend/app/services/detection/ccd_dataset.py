import csv
import hashlib
import re
from pathlib import Path
from typing import Any


LABELS = {"ACCIDENT", "NORMAL"}
SPLITS = {"train", "validation", "test"}
REQUIRED_COLUMNS = {
    "video_path",
    "label",
    "source_dataset",
    "source_video_id",
    "frame_labels",
    "sha256",
    "split",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as video_file:
        for chunk in iter(lambda: video_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_permission_record(permission_record: Path) -> None:
    permission_path = permission_record.resolve(strict=True)
    if not permission_path.is_file() or permission_path.stat().st_size == 0:
        raise ValueError("A non-empty written video-use permission record is required.")


def load_authorized_split(
    dataset_root: Path,
    manifest_path: Path,
    splits: set[str],
) -> list[dict[str, Any]]:
    root = dataset_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Dataset root is not a directory: {root}")
    if not splits or not splits <= SPLITS:
        raise ValueError(f"Requested splits must be a non-empty subset of {SPLITS}.")

    source_assignments: dict[tuple[str, str], str] = {}
    source_labels: dict[tuple[str, str], str] = {}
    seen_paths: set[str] = set()
    seen_hashes: set[str] = set()
    selected_rows: list[dict[str, Any]] = []

    with manifest_path.resolve(strict=True).open(
        encoding="utf-8-sig",
        newline="",
    ) as manifest_file:
        reader = csv.DictReader(manifest_file)
        if reader.fieldnames is None or not REQUIRED_COLUMNS <= set(reader.fieldnames):
            raise ValueError(
                "Split manifest must contain: " + ", ".join(sorted(REQUIRED_COLUMNS))
            )

        for line_number, raw_row in enumerate(reader, start=2):
            if None in raw_row:
                raise ValueError(f"Manifest row {line_number} has extra values.")
            row = {
                column: (raw_row[column] or "").strip()
                for column in REQUIRED_COLUMNS
            }
            if any(
                not row[column]
                for column in REQUIRED_COLUMNS - {"frame_labels"}
            ):
                raise ValueError(f"Manifest row {line_number} has an empty field.")

            label = row["label"].upper()
            split = row["split"].lower()
            if label not in LABELS or split not in SPLITS:
                raise ValueError(f"Manifest row {line_number} has an invalid label or split.")
            frame_labels = row["frame_labels"]
            if label == "ACCIDENT":
                if (
                    len(frame_labels) != 50
                    or set(frame_labels) - {"0", "1"}
                    or "1" not in frame_labels
                ):
                    raise ValueError(
                        f"Manifest row {line_number} needs 50 binary crash frame labels."
                    )
            elif frame_labels:
                raise ValueError(
                    f"Manifest row {line_number} must have empty normal frame labels."
                )

            source_key = (
                row["source_dataset"].casefold(),
                row["source_video_id"],
            )
            previous_split = source_assignments.setdefault(source_key, split)
            if previous_split != split:
                raise ValueError(
                    "Original source video appears in multiple data splits."
                )
            previous_label = source_labels.setdefault(source_key, label)
            if previous_label != label:
                raise ValueError(
                    "Original source video has conflicting class labels."
                )

            relative_path = Path(row["video_path"])
            if relative_path.is_absolute():
                raise ValueError(f"Manifest row {line_number} path must be relative.")
            normalized_path = relative_path.as_posix().casefold()
            if normalized_path in seen_paths:
                raise ValueError(f"Manifest row {line_number} repeats a video path.")
            seen_paths.add(normalized_path)

            file_hash = row["sha256"].lower()
            if re.fullmatch(r"[0-9a-f]{64}", file_hash) is None:
                raise ValueError(f"Manifest row {line_number} has an invalid SHA-256.")
            if file_hash in seen_hashes:
                raise ValueError("Manifest contains duplicate video content hashes.")
            seen_hashes.add(file_hash)

            if split not in splits:
                continue
            video_path = (root / relative_path).resolve(strict=True)
            try:
                relative_to_root = video_path.relative_to(root)
            except ValueError as exc:
                raise ValueError(
                    f"Manifest row {line_number} points outside the dataset root."
                ) from exc
            if not video_path.is_file() or video_path.suffix.lower() != ".mp4":
                raise ValueError(f"Manifest row {line_number} is not an MP4 file.")
            if _sha256(video_path) != file_hash:
                raise ValueError(
                    f"Manifest row {line_number} SHA-256 does not match the video."
                )
            selected_rows.append(
                {
                    **row,
                    "label": label,
                    "split": split,
                    "source_key": source_key,
                    "path": root / relative_to_root,
                }
            )

    for split in splits:
        labels_in_split = {
            row["label"] for row in selected_rows if row["split"] == split
        }
        if labels_in_split != LABELS:
            raise ValueError(
                f"The {split} split must contain both ACCIDENT and NORMAL videos."
            )
    return selected_rows
