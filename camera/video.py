"""
camera/video.py — pre-recorded classroom video as a frame source.

Useful both as a genuine input mode (spec section 4: "Pre-recorded
classroom video if practical") and as the practical way to test/demo
the snapshot pipeline on a machine without a webcam.
"""

import cv2

from camera.webcam import CameraError  # reuse the same error type for uniform handling


class VideoFileSource:
    def __init__(self, path: str):
        self.path = path
        self._cap = None
        self.fps = None
        self.frame_count = None
        self.duration_sec = None

    def open(self):
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened():
            cap.release()
            raise CameraError(
                f"Could not open video file: {self.path}. "
                "Make sure it's a valid, readable video file (mp4/avi/mov)."
            )
        self._cap = cap
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.duration_sec = (self.frame_count / self.fps) if self.fps else 0.0
        return self

    def read_frame_at_fraction(self, fraction: float):
        """
        Seek to `fraction` (0.0-1.0) of the way through the video and
        return that frame. Used so a 5-snapshot schedule maps sensibly
        onto a video of any length, regardless of the configured lecture
        duration.
        """
        if self._cap is None:
            raise CameraError("Video source was not opened before reading a frame.")
        fraction = max(0.0, min(1.0, fraction))
        target_frame = int(fraction * max(self.frame_count - 1, 0))
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CameraError(
                f"Failed to read frame at {fraction:.0%} of the video. "
                "The file may be corrupted or use an unsupported codec."
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
