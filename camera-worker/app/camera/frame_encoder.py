from __future__ import annotations

import cv2


class FrameEncoder:
    def __init__(self, jpeg_quality: int) -> None:
        self._jpeg_quality = max(1, min(jpeg_quality, 100))

    def encode_to_jpeg(self, frame: cv2.typing.MatLike) -> bytes:
        success, encoded_frame = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality],
        )
        if not success:
            raise RuntimeError("Could not encode frame to JPEG.")
        return encoded_frame.tobytes()

