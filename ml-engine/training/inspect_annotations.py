
from pathlib import Path
import random
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

ROOT = Path("ml-engine/datasets/raw/AccidentDetection-9k")
IMAGE_DIR = ROOT / "train/images"
LABEL_DIR = ROOT / "train/labels"

random.seed(42)

label_files = list(LABEL_DIR.glob("*.txt"))
valid_samples = []

for label in label_files:
    if label.stat().st_size > 0:
        valid_samples.append(label)

samples = random.sample(valid_samples, min(6, len(valid_samples)))

fig, axes = plt.subplots(2, 3, figsize=(16, 10))
axes = axes.flatten()

for ax, label_file in zip(axes, samples):
    image_path = next(
        (p for p in IMAGE_DIR.iterdir()
         if p.stem == label_file.stem),
        None
    )

    if image_path is None:
        ax.set_title(f"Missing image: {label_file.stem}")
        ax.axis("off")
        continue

    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    ax.imshow(image)

    for line in label_file.read_text().splitlines():
        class_id, xc, yc, bw, bh = map(float, line.split())

        x = (xc - bw / 2) * width
        y = (yc - bh / 2) * height

        rect = patches.Rectangle(
            (x, y),
            bw * width,
            bh * height,
            linewidth=2,
            edgecolor="red",
            facecolor="none"
        )

        ax.add_patch(rect)
        ax.text(x, y, "Accident", color="white",
                bbox=dict(facecolor="red", alpha=0.8))

    ax.set_title(label_file.stem)
    ax.axis("off")

for ax in axes[len(samples):]:
    ax.axis("off")

plt.tight_layout()
plt.show()
