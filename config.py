"""
AttendAI - central configuration.

Keep every tunable constant here so the rest of the app never hard-codes
numbers. This is also where the "temporal presence" defaults live.
"""

import os

# --- Paths -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STUDENTS_DIR = os.path.join(DATA_DIR, "students")
MODELS_DIR = os.path.join(BASE_DIR, "models")
DB_PATH = os.path.join(DATA_DIR, "attendai.db")

os.makedirs(STUDENTS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# --- Attendance defaults (can be overridden per class/session) ---------
DEFAULT_LECTURE_DURATION_MIN = 50
DEFAULT_NUM_SNAPSHOTS = 5
DEFAULT_MIN_OBSERVATIONS = 3

# --- Face recognition ----------------------------------------------------
# We use OpenCV's built-in Haar Cascade for detection and LBPH
# (Local Binary Patterns Histogram) for recognition. Both ship inside
# opencv-contrib-python, so there is zero external model download and
# everything runs fully offline/locally (good for the privacy story too).
#
# LBPH's `predict()` returns a *distance* (lower = more similar), not a
# calibrated probability. We convert it into a bounded "match score" in
# [0, 1] using MATCH_SCORE_DISTANCE_CAP below. This is explicitly a
# similarity/match score, never described as a statistical probability.
FACE_SIZE = (200, 200)  # all faces are resized to this before embedding
# match_score = exp(-chi_square_distance / CHI2_SCALE), see ai/recognizer.py.
# Empirically (tests/test_recognizer.py): same-person distances ~0.1-0.4
# -> score ~0.67-0.90; a genuinely different person's distance ~1.5-2.5
# -> score ~0.08-0.22. 0.5 sits cleanly in the gap between them.
DEFAULT_RECOGNITION_THRESHOLD = 0.5  # minimum match_score to accept an identity

MIN_FACE_SIZE_PX = 60  # ignore detections smaller than this (likely noise)

# --- Demo mode -----------------------------------------------------------
DEMO_MODE_TOTAL_SECONDS = 90  # entire lecture compressed into ~1.5 minutes

# --- Misc ------------------------------------------------------------------
APP_TITLE = "AttendAI — Temporal Presence Attendance"
