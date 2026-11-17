
from pathlib import Path
import torch
from ultralytics import YOLO
from multiprocessing import freeze_support


def main():
    project_root = Path(__file__).resolve().parents[2]

    data_yaml = (
        project_root
        / "ml-engine"
        / "datasets"
        / "raw"
        / "AccidentDetection-9k"
        / "data.yaml"
    )

    runs_dir = project_root / "ml-engine" / "runs"

    if not data_yaml.exists():
        raise FileNotFoundError(data_yaml)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU not available")

    print("GPU:", torch.cuda.get_device_name(0))
    print("Dataset:", data_yaml)

    model = YOLO("yolov8n.pt")

    model.train(
        data=str(data_yaml),
        epochs=80,
        imgsz=512,
        batch=4,
        patience=20,

        # Avoid Windows multiprocessing issues
        workers=0,

        device=0,
        pretrained=True,
        optimizer="auto",
        amp=True,
        cache=False,
        seed=42,
        project=str(runs_dir),
        name="accident_yolov8n",
        exist_ok=False,
        plots=True,
        save=True,
        val=True
    )

    print("\nTraining completed!")


if __name__ == "__main__":
    freeze_support()
    main()
