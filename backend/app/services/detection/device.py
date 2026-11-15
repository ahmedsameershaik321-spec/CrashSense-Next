import re


class DeviceResolutionError(Exception):
    """Raised when the requested PyTorch device is unavailable or invalid."""


def resolve_device(configured_device: str) -> str:
    requested = configured_device.lower()
    if requested == "cpu":
        return "cpu"
    if requested != "auto":
        match = re.fullmatch(r"cuda(?::(\d+))?", requested)
        if match is None:
            raise DeviceResolutionError(
                "DETECTION_DEVICE must be 'auto', 'cpu', 'cuda', or 'cuda:N'."
            )
        try:
            import torch
        except ImportError as exc:
            raise DeviceResolutionError(
                "CUDA was requested but PyTorch is not installed."
            ) from exc
        device_index = int(match.group(1) or "0")
        if (
            not torch.cuda.is_available()
            or device_index >= torch.cuda.device_count()
        ):
            raise DeviceResolutionError(
                f"CUDA device {device_index} is unavailable."
            )
        return f"cuda:{device_index}"

    try:
        import torch
    except ImportError as exc:
        raise DeviceResolutionError(
            "PyTorch is required for model inference. Install PyTorch for your platform."
        ) from exc

    return "cuda:0" if torch.cuda.is_available() else "cpu"
