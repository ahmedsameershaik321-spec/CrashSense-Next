import argparse
import csv
import hashlib
import random
from pathlib import Path


LABELS = ("ACCIDENT", "NORMAL")
SPLITS = ("train", "validation", "test")
SPLIT_RATIOS = (0.7, 0.15, 0.15)
ANNOTATION_FRAME_COUNT = 50
REQUIRED_COLUMNS = {
    "video_path",
    "label",
    "source_dataset",
    "source_video_id",
    "frame_labels",
}
OUTPUT_COLUMNS = (
    "video_path",
    "label",
    "source_dataset",
    "source_video_id",
    "frame_labels",
    "sha256",
    "split",
)


def _allocate_split_sizes(group_count: int) -> list[int]:
    if group_count < len(SPLITS):
        raise ValueError(
            "Each class needs at least three distinct original source videos "
            "for train, validation, and test."
        )

    exact_sizes = [group_count * ratio for ratio in SPLIT_RATIOS]
    sizes = [int(size) for size in exact_sizes]
    remainder = group_count - sum(sizes)
    remainder_order = sorted(
        range(len(SPLITS)),
        key=lambda index: (-(exact_sizes[index] - sizes[index]), index),
    )
    for index in remainder_order[:remainder]:
        sizes[index] += 1

    for index, size in enumerate(sizes):
        if size:
            continue
        donor = max(
            (candidate for candidate, count in enumerate(sizes) if count > 1),
            key=lambda candidate: sizes[candidate] - exact_sizes[candidate],
            default=None,
        )
        if donor is None:
            raise ValueError("Could not allocate all source videos to each split.")
        sizes[donor] -= 1
        sizes[index] += 1

    return sizes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as video_file:
        for chunk in iter(lambda: video_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_splits(
    dataset_root: Path,
    source_manifest: Path,
    output_manifest: Path,
    permission_record: Path,
    seed: int = 2026,
) -> dict[str, int]:
    root = dataset_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Dataset root is not a directory: {root}")

    permission_path = permission_record.resolve(strict=True)
    if not permission_path.is_file() or permission_path.stat().st_size == 0:
        raise ValueError(
            "A non-empty written permission record is required before preparing CCD."
        )

    source_path = source_manifest.resolve(strict=True)
    output_path = output_manifest.resolve()
    if source_path == output_path:
        raise ValueError("Output manifest must not overwrite the source manifest.")
    if output_path.exists():
        raise FileExistsError(f"Output manifest already exists: {output_path}")

    rows: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    seen_hashes: dict[str, str] = {}
    source_labels: dict[tuple[str, str], str] = {}

    with source_path.open(encoding="utf-8-sig", newline="") as manifest_file:
        reader = csv.DictReader(manifest_file)
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(
            reader.fieldnames
        ):
            required = ", ".join(sorted(REQUIRED_COLUMNS))
            raise ValueError(f"Manifest must contain columns: {required}.")

        for line_number, raw_row in enumerate(reader, start=2):
            if None in raw_row:
                raise ValueError(f"Manifest row {line_number} has extra values.")

            values = {
                column: (raw_row[column] or "").strip()
                for column in REQUIRED_COLUMNS
            }
            if any(
                not values[column]
                for column in REQUIRED_COLUMNS - {"frame_labels"}
            ):
                raise ValueError(
                    f"Manifest row {line_number} has an empty required value."
                )

            label = values["label"].upper()
            if label not in LABELS:
                raise ValueError(
                    f"Manifest row {line_number} has unsupported label "
                    f"{values['label']!r}."
                )
            frame_labels = values["frame_labels"]
            if label == "ACCIDENT":
                if (
                    len(frame_labels) != ANNOTATION_FRAME_COUNT
                    or set(frame_labels) - {"0", "1"}
                    or "1" not in frame_labels
                ):
                    raise ValueError(
                        f"Manifest row {line_number} must contain exactly "
                        f"{ANNOTATION_FRAME_COUNT} binary frame labels with an "
                        "accident frame for ACCIDENT."
                    )
            elif frame_labels:
                raise ValueError(
                    f"Manifest row {line_number} must leave frame_labels empty "
                    "for NORMAL videos."
                )

            relative_path = Path(values["video_path"])
            if relative_path.is_absolute():
                raise ValueError(
                    f"Manifest row {line_number} must use a relative video path."
                )
            video_path = (root / relative_path).resolve(strict=True)
            try:
                relative_video_path = video_path.relative_to(root).as_posix()
            except ValueError as exc:
                raise ValueError(
                    f"Manifest row {line_number} points outside the dataset root."
                ) from exc
            if not video_path.is_file() or video_path.suffix.lower() != ".mp4":
                raise ValueError(
                    f"Manifest row {line_number} is not an existing MP4 video."
                )
            if relative_video_path in seen_paths:
                raise ValueError(
                    f"Manifest row {line_number} repeats video "
                    f"{relative_video_path!r}."
                )
            seen_paths.add(relative_video_path)

            digest = _sha256(video_path)
            if digest in seen_hashes:
                raise ValueError(
                    "Duplicate video content found at "
                    f"{seen_hashes[digest]!r} and {relative_video_path!r}."
                )
            seen_hashes[digest] = relative_video_path

            source_dataset = values["source_dataset"].casefold()
            source_video_id = values["source_video_id"]
            source_key = (source_dataset, source_video_id)
            previous_label = source_labels.setdefault(source_key, label)
            if previous_label != label:
                raise ValueError(
                    f"Original source {source_dataset}:{source_video_id} has "
                    "conflicting class labels."
                )

            rows.append(
                {
                    "video_path": relative_video_path,
                    "label": label,
                    "source_dataset": source_dataset,
                    "source_video_id": source_video_id,
                    "frame_labels": frame_labels,
                    "sha256": digest,
                }
            )

    if not rows:
        raise ValueError("Manifest contains no videos.")

    groups_by_label: dict[str, list[tuple[str, str]]] = {
        label: [] for label in LABELS
    }
    for source_key, label in source_labels.items():
        groups_by_label[label].append(source_key)

    assignments: dict[tuple[str, str], str] = {}
    rng = random.Random(seed)
    for label in LABELS:
        groups = sorted(groups_by_label[label])
        sizes = _allocate_split_sizes(len(groups))
        rng.shuffle(groups)
        offset = 0
        for split, size in zip(SPLITS, sizes, strict=True):
            for source_key in groups[offset : offset + size]:
                assignments[source_key] = split
            offset += size

    for row in rows:
        row["split"] = assignments[
            (row["source_dataset"], row["source_video_id"])
        ]

    split_order = {split: index for index, split in enumerate(SPLITS)}
    rows.sort(
        key=lambda row: (
            split_order[row["split"]],
            row["label"],
            row["source_dataset"],
            row["source_video_id"],
            row["video_path"],
        )
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts = {split: 0 for split in SPLITS}
    with output_path.open("x", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        for row in rows:
            counts[row["split"]] += 1

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create deterministic CCD splits grouped by original video."
    )
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--permission-record",
        type=Path,
        required=True,
        help="Path to the written CCD video-use authorization record.",
    )
    parser.add_argument(
        "--confirm-authorized-use",
        action="store_true",
        required=True,
        help="Confirm authorization covers these source videos and split processing.",
    )
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    counts = prepare_splits(
        args.dataset_root,
        args.manifest,
        args.output,
        args.permission_record,
        seed=args.seed,
    )
    print(
        "Wrote source-grouped splits: "
        + ", ".join(f"{split}={counts[split]}" for split in SPLITS)
    )


if __name__ == "__main__":
    main()
