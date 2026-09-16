"""
attendance/rules.py — the temporal presence rule.

Deliberately has ZERO dependency on OpenCV/AI code so it can be unit
tested in complete isolation (spec section 16: "test the attendance
engine independently of the AI model").
"""

STATUS_PRESENT = "PRESENT"
STATUS_NEEDS_REVIEW = "NEEDS REVIEW"
STATUS_UNKNOWN_NOT_ENROLLED = "UNKNOWN / NOT ENROLLED"


def compute_status(observation_count: int, min_required: int) -> str:
    """
    The core rule:
        observations >= minimum_required -> PRESENT
        observations <  minimum_required -> NEEDS REVIEW

    This function only ever returns PRESENT or NEEDS REVIEW — it is used
    for enrolled students only. UNKNOWN/NOT ENROLLED is a separate
    concept applied to detections that never matched any enrolled
    student at all (see attendance/engine.py), not a result of this rule.
    """
    if observation_count < 0:
        raise ValueError("observation_count cannot be negative")
    if min_required < 0:
        raise ValueError("min_required cannot be negative")
    return STATUS_PRESENT if observation_count >= min_required else STATUS_NEEDS_REVIEW


def compute_coverage_pct(observation_count: int, total_snapshots: int) -> float:
    if total_snapshots <= 0:
        return 0.0
    return round(100.0 * observation_count / total_snapshots, 1)
