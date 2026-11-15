import csv
from pathlib import Path

import pytest

from app.services.detection.ccd_dataset import load_authorized_split
from scripts.prepare_ccd_splits import prepare_splits


def _write_fixture_manifest(
    tmp_path: Path,
    entries: list[tuple[str, str, str, str, bytes]],
) -> tuple[Path, Path, Path]:
    root = tmp_path / "ccd"
    root.mkdir(parents=True)
    manifest_path = tmp_path / "manifest.csv"
    permission_record = tmp_path / "permission-record.txt"
    permission_record.write_text("synthetic test authorization", encoding="utf-8")

    with manifest_path.open("w", encoding="utf-8", newline="") as manifest_file:
        writer = csv.writer(manifest_file)
        writer.writerow(
            [
                "video_path",
                "label",
                "source_dataset",
                "source_video_id",
                "frame_labels",
            ]
        )
        for video_path, label, source_dataset, source_id, contents in entries:
            target = root / video_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)
            frame_labels = "0" * 24 + "1" + "0" * 25 if label == "ACCIDENT" else ""
            writer.writerow(
                [video_path, label, source_dataset, source_id, frame_labels]
            )

    return root, manifest_path, permission_record


def _balanced_fixture_entries() -> list[tuple[str, str, str, str, bytes]]:
    entries = []
    for label, source_dataset in (("ACCIDENT", "youtube"), ("NORMAL", "bdd100k")):
        for source_index in range(3):
            source_id = f"{label.lower()}-source-{source_index}"
            for clip_index in range(2):
                video_path = (
                    f"videos/{label.lower()}/{source_index}-{clip_index}.mp4"
                )
                entries.append(
                    (
                        video_path,
                        label,
                        source_dataset,
                        source_id,
                        f"{source_id}-{clip_index}".encode(),
                    )
                )
    return entries


def test_splits_are_deterministic_stratified_and_grouped_by_source(tmp_path):
    root, manifest, permission_record = _write_fixture_manifest(
        tmp_path,
        _balanced_fixture_entries(),
    )
    first_output = tmp_path / "first.csv"
    second_output = tmp_path / "second.csv"

    counts = prepare_splits(
        root,
        manifest,
        first_output,
        permission_record,
        seed=7,
    )
    prepare_splits(root, manifest, second_output, permission_record, seed=7)

    assert first_output.read_bytes() == second_output.read_bytes()
    assert counts == {"train": 4, "validation": 4, "test": 4}

    with first_output.open(encoding="utf-8", newline="") as output_file:
        rows = list(csv.DictReader(output_file))

    splits_by_source = {}
    labels_by_split = {split: set() for split in ("train", "validation", "test")}
    for row in rows:
        source = (row["source_dataset"], row["source_video_id"])
        splits_by_source.setdefault(source, set()).add(row["split"])
        labels_by_split[row["split"]].add(row["label"])

    assert all(len(splits) == 1 for splits in splits_by_source.values())
    assert all(labels == {"ACCIDENT", "NORMAL"} for labels in labels_by_split.values())


def test_rejects_duplicate_video_content(tmp_path):
    entries = _balanced_fixture_entries()
    entries[1] = (*entries[1][:4], entries[0][4])
    root, manifest, permission_record = _write_fixture_manifest(tmp_path, entries)

    with pytest.raises(ValueError, match="Duplicate video content"):
        prepare_splits(root, manifest, tmp_path / "splits.csv", permission_record)


def test_requires_source_ids_and_does_not_overwrite_outputs(tmp_path):
    entries = _balanced_fixture_entries()
    entries[0] = (entries[0][0], entries[0][1], entries[0][2], "", entries[0][4])
    root, manifest, permission_record = _write_fixture_manifest(tmp_path, entries)

    with pytest.raises(ValueError, match="empty required value"):
        prepare_splits(root, manifest, tmp_path / "splits.csv", permission_record)

    entries[0] = _balanced_fixture_entries()[0]
    root, manifest, permission_record = _write_fixture_manifest(
        tmp_path / "valid",
        entries,
    )
    output = tmp_path / "valid" / "splits.csv"
    output.write_text("preserve", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        prepare_splits(root, manifest, output, permission_record)
    assert output.read_text(encoding="utf-8") == "preserve"


def test_requires_permission_record(tmp_path):
    root, manifest, permission_record = _write_fixture_manifest(
        tmp_path,
        _balanced_fixture_entries(),
    )
    permission_record.unlink()

    with pytest.raises(FileNotFoundError):
        prepare_splits(root, manifest, tmp_path / "splits.csv", permission_record)


def test_rejects_malformed_crash_frame_labels(tmp_path):
    root, manifest, permission_record = _write_fixture_manifest(
        tmp_path,
        _balanced_fixture_entries(),
    )
    with manifest.open(encoding="utf-8", newline="") as manifest_file:
        rows = list(csv.reader(manifest_file))
    rows[1][4] = "101"
    with manifest.open("w", encoding="utf-8", newline="") as manifest_file:
        csv.writer(manifest_file).writerows(rows)

    with pytest.raises(ValueError, match="exactly 50 binary frame labels"):
        prepare_splits(root, manifest, tmp_path / "splits.csv", permission_record)


def test_training_manifest_loader_rejects_source_leakage(tmp_path):
    root, manifest, permission_record = _write_fixture_manifest(
        tmp_path,
        _balanced_fixture_entries(),
    )
    split_manifest = tmp_path / "splits.csv"
    prepare_splits(root, manifest, split_manifest, permission_record, seed=7)
    with split_manifest.open(encoding="utf-8", newline="") as manifest_file:
        rows = list(csv.DictReader(manifest_file))

    source = rows[0]["source_video_id"]
    matching_rows = [row for row in rows if row["source_video_id"] == source]
    assert len(matching_rows) == 2
    matching_rows[1]["split"] = "test"
    with split_manifest.open("w", encoding="utf-8", newline="") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="multiple data splits"):
        load_authorized_split(root, split_manifest, {"train"})
