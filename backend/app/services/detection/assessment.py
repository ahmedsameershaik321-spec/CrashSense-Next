from typing import Any, Literal


def build_review_assessment(
    object_labels: list[str],
    event_state: Literal["suspected", "needs_review"],
) -> dict[str, Any]:
    """Return conservative assessments when evidence does not establish an accident."""
    labels = ", ".join(sorted(set(object_labels))) or "none"
    return {
        "event_state": event_state,
        "accident_category": "UNKNOWN",
        "classification_confidence": None,
        "classification_reasoning": (
            "The available model detects objects, not accident events. "
            "Proximity and motion anomalies alone do not support an accident category."
        ),
        "severity": "UNKNOWN",
        "severity_confidence": None,
        "severity_reasoning_factors": [
            f"Observed object classes: {labels}.",
            "No validated impact, rollover, damage, or injury signal is available.",
        ],
        "severity_missing_information": [
            "Validated collision or impact evidence.",
            "Reliable rollover or visible-damage evidence.",
            "Occupant or injury information, which ordinary CCTV cannot establish.",
        ],
        "human_review_required": True,
    }
