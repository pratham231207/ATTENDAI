"""Tests for attendance/scheduler.py."""

from attendance.scheduler import compute_snapshot_offsets_sec, compute_snapshot_fractions
from config import DEMO_MODE_TOTAL_SECONDS


def test_real_mode_spans_full_lecture_duration():
    offsets = compute_snapshot_offsets_sec(duration_min=50, num_snapshots=5, mode="real")
    assert len(offsets) == 5
    assert offsets == sorted(offsets)
    assert offsets[0] > 0
    assert offsets[-1] < 50 * 60  # last snapshot before the bell, not at t=0 or past the end


def test_demo_mode_is_compressed_regardless_of_duration():
    # Same seed on both calls isolates the thing being tested (duration
    # independence) from the schedule's intentional per-call jitter.
    offsets_short = compute_snapshot_offsets_sec(duration_min=50, num_snapshots=5, mode="demo", seed=1)
    offsets_long = compute_snapshot_offsets_sec(duration_min=180, num_snapshots=5, mode="demo", seed=1)
    # Demo mode timing must not depend on the configured lecture duration.
    assert offsets_short == offsets_long
    assert offsets_short[-1] <= DEMO_MODE_TOTAL_SECONDS


def test_schedule_is_jittered_not_fixed():
    """Anti-gaming: back-to-back schedules (different seeds) should not
    always land on the same instants, unlike the old fixed 10/30/50/70/90 spacing."""
    seen = {tuple(compute_snapshot_fractions(5, seed=s)) for s in range(10)}
    assert len(seen) > 1


def test_same_seed_is_reproducible():
    a = compute_snapshot_fractions(5, seed=42)
    b = compute_snapshot_fractions(5, seed=42)
    assert a == b


def test_same_number_of_snapshots_in_both_modes():
    """Demo mode accelerates timing, but never changes how many observations are taken."""
    real_offsets = compute_snapshot_offsets_sec(50, 5, "real")
    demo_offsets = compute_snapshot_offsets_sec(50, 5, "demo")
    assert len(real_offsets) == len(demo_offsets) == 5


def test_fractions_are_monotonic_and_within_bounds():
    fractions = compute_snapshot_fractions(5)
    assert len(fractions) == 5
    assert fractions == sorted(fractions)
    assert all(0.0 <= f <= 1.0 for f in fractions)


def test_single_snapshot_lands_at_midpoint():
    assert compute_snapshot_fractions(1) == [0.5]
