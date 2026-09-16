"""
camera/webcam.py — laptop webcam capture.

Wraps cv2.VideoCapture with the graceful failure modes the spec calls
for: no camera present, camera busy/permission denied, or a mid-stream
read failure should never crash the app — they should surface as a
clear, human-readable message so the teacher can fall back to a video
file or retry.
"""

import cv2


class CameraError(Exception):
    """Raised for any camera problem the UI should show as a friendly message."""


class WebcamSource:
    def __init__(self, index: int = 0):
        self.index = index
        self._cap = None

    def open(self):
        cap = cv2.VideoCapture(self.index)
        if not cap.isOpened():
            cap.release()
            raise CameraError(
                f"Could not access webcam (device index {self.index}). "
                "Check that a camera is connected, not in use by another app, "
                "and that this app has camera permission. You can also switch "
                "to 'Pre-recorded video' as the input source."
            )
        self._cap = cap
        return self

    def read_frame(self):
        """Returns a BGR frame. Raises CameraError on failure (never returns None silently)."""
        if self._cap is None:
            raise CameraError("Webcam was not opened before reading a frame.")
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CameraError(
                "Failed to read a frame from the webcam. It may have been "
                "disconnected or is being used by another application."
            )
        return frame

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def is_webcam_available(index: int = 0) -> bool:
    """Best-effort check used by the UI to decide whether to offer webcam as an option."""
    cap = cv2.VideoCapture(index)
    ok = cap.isOpened()
    cap.release()
    return ok
