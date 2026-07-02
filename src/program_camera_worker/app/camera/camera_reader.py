from __future__ import annotations

import cv2


class CameraReader:
    def __init__(self, camera_index: int, frame_width: int, frame_height: int) -> None:
        self._camera_index = camera_index
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        self._capture = cv2.VideoCapture(self._camera_index)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._frame_width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._frame_height)

        if not self._capture.isOpened():
            raise RuntimeError(f"Could not open camera index {self._camera_index}.")

    def read(self) -> cv2.typing.MatLike:
        if self._capture is None:
            raise RuntimeError("Camera is not open.")

        success, frame = self._capture.read()
        if not success:
            raise RuntimeError("Could not read frame from camera.")
        return frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

