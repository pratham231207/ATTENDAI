"""
Tests for attendance/rules.py — the core temporal-presence rule.

These tests have ZERO dependency on the database or any AI code
(per spec section 16: "test the attendance engine independently of the
AI model"), so they run instantly and can't be broken by anything
face-recognition related.
"""

import pytest

from attendance.rules import (
    compute_status,
    compute_coverage_pct,
    STATUS_PRESENT,
    STATUS_NEEDS_REVIEW,
)


# --- the exact cases called out in the spec -------------------------------

def test_3_of_5_is_present():
    """The minimum-required boundary: exactly 3/5 must be PRESENT, not review."""
    assert compute_status(observation_count=3, min_required=3) == STATUS_PRESENT


def test_4_of_5_is_present():
    assert compute_status(observation_count=4, min_required=3) == STATUS_PRESENT


def test_5_of_5_is_present():
    assert compute_status(observation_count=5, min_required=3) == STATUS_PRESENT


def test_2_of_5_is_needs_review():
    """Below the minimum -> NEEDS REVIEW, and specifically NOT 'ABSENT'."""
    status = compute_status(observation_count=2, min_required=3)
    assert status == STATUS_NEEDS_REVIEW
    assert status != "ABSENT"


# --- additional boundary / edge cases --------------------------------------

def test_0_of_5_is_needs_review_not_absent():
    """A student never observed at all is still NEEDS REVIEW, never auto-marked absent."""
    assert compute_status(observation_count=0, min_required=3) == STATUS_NEEDS_REVIEW


def test_1_below_minimum_is_needs_review():
    assert compute_status(observation_count=2, min_required=3) == STATUS_NEEDS_REVIEW


def test_custom_minimum_required_is_respected():
    # A stricter class policy: require 4/5.
    assert compute_status(3, min_required=4) == STATUS_NEEDS_REVIEW
    assert compute_status(4, min_required=4) == STATUS_PRESENT


def test_negative_observation_count_raises():
    with pytest.raises(ValueError):
        compute_status(-1, min_required=3)


def test_negative_min_required_raises():
    with pytest.raises(ValueError):
        compute_status(3, min_required=-1)


# --- coverage percentage -----------------------------------------------

def test_coverage_pct_basic_cases():
    assert compute_coverage_pct(3, 5) == 60.0
    assert compute_coverage_pct(4, 5) == 80.0
    assert compute_coverage_pct(5, 5) == 100.0
    assert compute_coverage_pct(0, 5) == 0.0


def test_coverage_pct_zero_total_snapshots_is_zero_not_error():
    assert compute_coverage_pct(0, 0) == 0.0
