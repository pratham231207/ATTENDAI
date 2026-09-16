"""
ai/recognizer.py — identity matching.

Compares a query face embedding against all enrolled student templates
using **chi-square distance** between the LBP histograms, converted to a
bounded "match score" in [0, 1].

Why chi-square and not cosine similarity: histogram vectors are
non-negative, which makes cosine similarity biased high for *any* two
faces (empirically ~0.80 similarity even for two different people in
testing here) — not discriminative enough once more than a couple of
students are enrolled. Chi-square distance is the standard metric for
comparing LBP histograms (it is what OpenCV's own LBPHFaceRecognizer
uses internally) and gave a much cleaner separation in testing: same
person ≈0.13-0.20 distance vs a different real person ≈2.5 distance.

IMPORTANT: match_score is a similarity/match score, not a calibrated
probability of correctness — the rest of the app must never describe it
as one (see config.DEFAULT_RECOGNITION_THRESHOLD and the dashboard/
timeline copy).
"""

from dataclasses import dataclass
from typing import Optional, List

import numpy as np

from ai.embeddings import deserialize_vector
from config import DEFAULT_RECOGNITION_THRESHOLD

# Controls how quickly match_score decays with chi-square distance.
# score = exp(-distance / CHI2_SCALE). Calibrated empirically (see
# tests/test_recognizer.py) so that same-person distances (~0.1-0.4)
# map to high scores and different-person distances (~1.5+) map low.
CHI2_SCALE = 1.0


@dataclass
class MatchResult:
    student_id: Optional[str]
    name: Optional[str]
    match_score: float          # in [0, 1], NOT a probability
    is_unknown: bool             # True if best score fell below threshold


def chi_square_distance(a: np.ndarray, b: np.ndarray, eps: float = 1e-10) -> float:
    """Standard chi-square distance for comparing histograms (lower = more similar)."""
    return float(0.5 * np.sum(((a - b) ** 2) / (a + b + eps)))


def distance_to_match_score(distance: float) -> float:
    """Map an unbounded chi-square distance to a bounded [0, 1] match score."""
    return float(np.exp(-distance / CHI2_SCALE))


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Kept for reference/tests; NOT used for the primary match decision (see module docstring)."""
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    sim = float(np.dot(a, b) / denom)
    return max(0.0, min(1.0, (sim + 1.0) / 2.0 if sim < 0 else sim))


def match_embedding(
    query_vec: np.ndarray,
    enrolled_students: List[dict],
    threshold: float = DEFAULT_RECOGNITION_THRESHOLD,
) -> MatchResult:
    """
    `enrolled_students` is a list of dicts as returned by database.db
    (must have 'student_id', 'name', 'embedding' — a serialized blob).

    Returns the best match if its score >= threshold, otherwise a
    MatchResult with student_id=None, is_unknown=True. Never raises just
    because nothing matched — callers should treat that as UNKNOWN, not
    an error.
    """
    best_id, best_name, best_score = None, None, -1.0

    for s in enrolled_students:
        if not s.get("embedding"):
            continue
        template = deserialize_vector(s["embedding"])
        distance = chi_square_distance(query_vec, template)
        score = distance_to_match_score(distance)
        if score > best_score:
            best_id, best_name, best_score = s["student_id"], s["name"], score

    if best_score < 0:
        # No enrolled students had usable embeddings at all.
        return MatchResult(student_id=None, name=None, match_score=0.0, is_unknown=True)

    if best_score >= threshold:
        return MatchResult(student_id=best_id, name=best_name, match_score=best_score, is_unknown=False)

    return MatchResult(student_id=None, name=None, match_score=best_score, is_unknown=True)
