"""
ai/embeddings.py — face "embedding" (feature vector) computation.

Method: grid-based uniform Local Binary Pattern (LBP) histograms.
This is the same classical family of features behind OpenCV's own
LBPHFaceRecognizer, but implemented here as a *per-face fixed-length
vector* (via scikit-image's well-tested LBP implementation) rather than
a single jointly-trained classifier. That matters for a hackathon:

  - Enrolling a new student only needs computing (and averaging) that
    student's own vector(s) — no retraining a global model every time
    someone enrolls.
  - It plugs cleanly into the `students.embedding` BLOB column and a
    simple cosine-similarity comparison at recognition time.

This is a hand-engineered classical CV feature, not a deep-learned
embedding — good enough to demo temporal-presence attendance logic on a
small enrolled class in a hackathon setting, but it is NOT presented as
a highly accurate biometric system (see README limitations).
"""

import io
import json

import numpy as np
import cv2
from skimage.feature import local_binary_pattern

from config import FACE_SIZE

# LBP parameters: 8 neighbors, radius 1, "uniform" method -> 10 possible
# uniform-pattern bins (0..8 transitions + 1 "non-uniform" bucket).
_LBP_P = 8
_LBP_R = 1
_LBP_N_BINS = _LBP_P + 2  # uniform LBP bin count
_GRID = (8, 8)  # split the face into an 8x8 grid of cells for spatial info


def preprocess_face(gray_crop: np.ndarray) -> np.ndarray:
    """Resize + light normalization so every face is compared on equal footing."""
    face = cv2.resize(gray_crop, FACE_SIZE, interpolation=cv2.INTER_AREA)
    face = cv2.equalizeHist(face)
    return face


def compute_embedding(gray_crop: np.ndarray) -> np.ndarray:
    """
    Compute a single fixed-length L2-normalized feature vector for one
    face crop, using grid-based uniform LBP histograms.
    """
    face = preprocess_face(gray_crop)
    lbp = local_binary_pattern(face, P=_LBP_P, R=_LBP_R, method="uniform")

    h, w = face.shape
    gh, gw = _GRID
    cell_h, cell_w = h // gh, w // gw

    hists = []
    for i in range(gh):
        for j in range(gw):
            cell = lbp[i * cell_h : (i + 1) * cell_h, j * cell_w : (j + 1) * cell_w]
            hist, _ = np.histogram(
                cell, bins=_LBP_N_BINS, range=(0, _LBP_N_BINS), density=False
            )
            hists.append(hist.astype(np.float32))

    vec = np.concatenate(hists)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.astype(np.float32)


def build_student_template(gray_crops: list) -> tuple:
    """
    Given multiple enrollment face crops for one student, compute each
    crop's embedding and average them into a single template vector
    (then re-normalize). Averaging several samples makes the template
    more robust to lighting/pose variation in any single photo.

    Returns (template_vector: np.ndarray, meta: dict)
    """
    if not gray_crops:
        raise ValueError("At least one face image is required to enroll a student.")

    vectors = [compute_embedding(c) for c in gray_crops]
    stacked = np.stack(vectors, axis=0)
    template = stacked.mean(axis=0)
    norm = np.linalg.norm(template)
    if norm > 0:
        template = template / norm

    meta = {
        "method": "lbp_grid_uniform",
        "lbp_P": _LBP_P,
        "lbp_R": _LBP_R,
        "grid": list(_GRID),
        "num_samples": len(gray_crops),
        "dim": int(template.shape[0]),
    }
    return template.astype(np.float32), meta


def serialize_vector(vec: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, vec.astype(np.float32))
    return buf.getvalue()


def deserialize_vector(blob: bytes) -> np.ndarray:
    buf = io.BytesIO(blob)
    return np.load(buf)
