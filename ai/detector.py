"""
ai/detector.py — face detection.

Uses OpenCV's built-in Haar Cascade classifier (ships inside every
opencv-python install, no external download). This is a classical,
well-established pretrained detector — appropriate for a 24h hackathon
where a deep detector's weights weren't downloadable on this network
(see README "Known limitations" for the full story).
"""

import cv2
import numpy as np

from config import MIN_FACE_SIZE_PX

_face_cascade = None


def _get_cascade():
    global _face_cascade
    if _face_cascade is None:
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(path)
        if cascade.empty():
            raise RuntimeError(
                f"Could not load Haar cascade from {path}. "
                "Is opencv-contrib-python installed correctly?"
            )
        _face_cascade = cascade
    return _face_cascade


class DetectedFace:
    """A single detected face: bounding box in the original image + crop."""

    __slots__ = ("x", "y", "w", "h", "gray_crop")

    def __init__(self, x, y, w, h, gray_crop):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.gray_crop = gray_crop

    @property
    def box(self):
        return (self.x, self.y, self.w, self.h)


def detect_faces(bgr_image: np.ndarray, min_size_px: int = MIN_FACE_SIZE_PX):
    """
    Detect faces in a BGR image.

    Returns a list of DetectedFace, sorted largest-first (the largest face
    is usually the most reliable / closest to camera, useful as a
    tie-breaker when multiple faces are present).

    Never raises on "no face found" — returns an empty list instead, so
    callers can display a friendly "no face detected" message rather than
    crashing (see error-handling requirements).
    """
    if bgr_image is None or bgr_image.size == 0:
        return []

    gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)  # improves detection under uneven lighting

    cascade = _get_cascade()
    boxes = cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(min_size_px, min_size_px),
    )

    faces = []
    for (x, y, w, h) in boxes:
        crop = gray[y : y + h, x : x + w]
        faces.append(DetectedFace(int(x), int(y), int(w), int(h), crop))

    faces.sort(key=lambda f: f.w * f.h, reverse=True)
    return faces


def draw_detections(bgr_image: np.ndarray, annotations: list):
    """
    Draw bounding boxes + labels on a copy of the image for the live/demo UI.

    `annotations` is a list of dicts: {box: (x,y,w,h), label: str, color: (b,g,r)}
    """
    out = bgr_image.copy()
    for ann in annotations:
        x, y, w, h = ann["box"]
        color = ann.get("color", (0, 200, 0))
        label = ann.get("label", "")
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
        if label:
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(out, (x, y - th - 10), (x + tw + 6, y), color, -1)
            cv2.putText(
                out, label, (x + 3, y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA,
            )
    return out
