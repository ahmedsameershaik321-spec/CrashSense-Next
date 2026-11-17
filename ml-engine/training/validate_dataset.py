
from pathlib import Path
from collections import Counter

ROOT = Path("ml-engine/datasets/raw/AccidentDetection-9k")
SPLITS = ["train", "valid", "test"]

total_images = 0
total_labels = 0
total_boxes = 0
empty_labels = 0
invalid_labels = []

for split in SPLITS:
    image_dir = ROOT / split / "images"
    label_dir = ROOT / split / "labels"

    images = {
        p.stem for p in image_dir.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    }

    labels = {p.stem for p in label_dir.glob("*.txt")}

    missing_labels = images - labels
    orphan_labels = labels - images

    split_boxes = 0
    split_empty = 0
    split_invalid = []

    for label_file in label_dir.glob("*.txt"):
        try:
            lines = label_file.read_text().splitlines()

            if not lines:
                split_empty += 1
                continue

            for line_number, line in enumerate(lines, start=1):
                values = line.split()

                if len(values) != 5:
                    raise ValueError("Expected 5 values")

                class_id = int(values[0])
                x, y, w, h = map(float, values[1:])

                if class_id != 0:
                    raise ValueError(f"Unexpected class ID: {class_id}")

                if not all(0 <= v <= 1 for v in (x, y, w, h)):
                    raise ValueError("Coordinates outside 0-1")

                if w <= 0 or h <= 0:
                    raise ValueError("Invalid box width or height")

                split_boxes += 1

        except Exception as error:
            split_invalid.append(
                f"{label_file.name}: {error}"
            )

    print(f"\n--- {split.upper()} ---")
    print("Images:", len(images))
    print("Labels:", len(labels))
    print("Missing labels:", len(missing_labels))
    print("Orphan labels:", len(orphan_labels))
    print("Bounding boxes:", split_boxes)
    print("Empty labels:", split_empty)
    print("Invalid annotations:", len(split_invalid))

    for error in split_invalid[:5]:
        print("  ", error)

    total_images += len(images)
    total_labels += len(labels)
    total_boxes += split_boxes
    empty_labels += split_empty
    invalid_labels.extend(split_invalid)

print("\n===== DATASET SUMMARY =====")
print("Total images:", total_images)
print("Total labels:", total_labels)
print("Total bounding boxes:", total_boxes)
print("Total empty labels:", empty_labels)
print("Total invalid annotations:", len(invalid_labels))
