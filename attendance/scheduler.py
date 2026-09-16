"""
attendance/scheduler.py — when each snapshot should be taken.

REAL MODE: snapshots are spread evenly across the actual lecture
duration (in seconds), with a small buffer so the very first snapshot
isn't at t=0 (giving students a moment to be seated) and the last isn't
exactly at the bell.

DEMO MODE: the same *number* of snapshots and the same downstream
attendance logic are used — only the wall-clock timing is compressed
into config.DEMO_MODE_TOTAL_SECONDS, so the whole lecture can be
demoed to judges in ~1-2 minutes. We do NOT fake or shortcut the
attendance result itself; we only shorten the wait between snapshots.

Anti-gaming note: snapshot moments are jittered (see JITTER_FRACTION
below) so they don't always land on the exact same 10/30/50/70/90%
marks. Fixed, predictable timing would let students learn "only be in
frame at these instants" and defeat the whole point of requiring
*repeated* temporal evidence. Pass a `seed` (e.g. the session_id) to
get a schedule that's fixed for that one session (so REAL-mode timing
and any video-fraction mapping agree) but different session-to-session
and unknown in advance.
"""

import random

from config import DEMO_MODE_TOTAL_SECONDS

# Snapshots are placed within evenly-sized cells spanning 10%-90% of the
# lecture, then jittered within their own cell by up to this fraction of
# the cell's half-width. Kept < 1.0 so cells (and therefore snapshots)
# can never cross over each other or escape the overall 10%-90% window.
JITTER_FRACTION = 0.6


def compute_snapshot_fractions(num_snapshots: int, seed=None):
    """
    Returns `num_snapshots` fractions (0-1) of the lecture at which a
    snapshot should be taken.

    Snapshots are stratified across 10%-90% of the lecture (one per
    equal-width cell) and then jittered randomly within their own cell.
    This keeps the same guarantees the old fixed-spacing version had —
    monotonically increasing, no clustering at the very start/end — while
    making the exact moments unpredictable ahead of time.

    `seed`: pass the same seed to get the same schedule back (e.g. reuse
    a session's id so REAL-mode wall-clock timing and video-fraction
    mapping for that session line up). Leave as None for a fresh random
    schedule each call.
    """
    if num_snapshots < 1:
        raise ValueError("num_snapshots must be >= 1")

    if num_snapshots == 1:
        return [0.5]

    start, end = 0.10, 0.90
    cell_width = (end - start) / num_snapshots
    max_jitter = (cell_width / 2) * JITTER_FRACTION

    rng = random.Random(seed)
    fractions = []
    for i in range(num_snapshots):
        cell_center = start + (i + 0.5) * cell_width
        fractions.append(cell_center + rng.uniform(-max_jitter, max_jitter))
    return fractions


def compute_snapshot_offsets_sec(duration_min: int, num_snapshots: int, mode: str, seed=None):
    """
    Returns a list of `num_snapshots` offsets in seconds (from lecture
    start) at which a snapshot should be taken. See
    `compute_snapshot_fractions` for the spacing/jitter logic — this is
    just that same schedule scaled to actual seconds.
    """
    total_seconds = DEMO_MODE_TOTAL_SECONDS if mode == "demo" else duration_min * 60
    fractions = compute_snapshot_fractions(num_snapshots, seed=seed)
    return [round(f * total_seconds, 2) for f in fractions]
