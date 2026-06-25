"""Pose estimation using MoveNet SinglePose Lightning TFLite (int8).

Keypoints follow the COCO 17-point layout:
  0:nose  1:left_eye  2:right_eye  3:left_ear  4:right_ear
  5:left_shoulder  6:right_shoulder  7:left_elbow  8:right_elbow
  9:left_wrist  10:right_wrist  11:left_hip  12:right_hip
  13:left_knee  14:right_knee  15:left_ankle  16:right_ankle

Each keypoint dict contains:
  name, x, y  – normalised [0, 1] (x=col, y=row)
  score       – model confidence [0, 1]
  visibility  – alias of score, kept for server-side compatibility
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_BACKEND = "movenet"

KEYPOINT_NAMES: list[str] = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]

# (index_a, index_b) pairs for skeleton overlay drawing
_SKELETON_CONNECTIONS: list[tuple[int, int]] = [
    (0, 1), (0, 2), (1, 3), (2, 4),        # head
    (5, 6),                                  # shoulders
    (5, 7), (7, 9),                          # left arm
    (6, 8), (8, 10),                         # right arm
    (5, 11), (6, 12), (11, 12),             # torso
    (11, 13), (13, 15),                      # left leg
    (12, 14), (14, 16),                      # right leg
]

_DRAW_SCORE_THRESHOLD = 0.3
_PERSON_SCORE_THRESHOLD = 0.2


class PoseEstimator:
    def __init__(
        self,
        camera_id: str,
        enabled: bool,
        model_path: str,
        draw_landmarks: bool = True,
        num_threads: int = 4,
    ) -> None:
        self._camera_id = camera_id
        self._enabled = enabled
        self._draw_landmarks = draw_landmarks
        self._interpreter: Any | None = None
        self._input_index: int = 0
        self._output_index: int = 0
        self._input_dtype: Any = np.uint8
        self._input_size: int = 192
        self._input_scale: float = 0.0
        self._input_zero_point: int = 0
        self._output_scale: float = 0.0
        self._output_zero_point: int = 0
        self._output_is_float: bool = True

        if not enabled:
            return

        interpreter = _load_interpreter(model_path, num_threads)
        if interpreter is None:
            self._enabled = False
            return

        interpreter.allocate_tensors()
        input_details = interpreter.get_input_details()[0]
        output_details = interpreter.get_output_details()[0]

        self._interpreter = interpreter
        self._input_index = int(input_details["index"])
        self._output_index = int(output_details["index"])
        self._input_dtype = input_details["dtype"]
        self._input_size = int(input_details["shape"][1])  # [1, H, W, 3]
        self._input_scale, self._input_zero_point = input_details["quantization"]
        self._output_scale, self._output_zero_point = output_details["quantization"]
        self._output_is_float = np.issubdtype(output_details["dtype"], np.floating)

        logger.info(
            "[%s] MoveNet TFLite ready — input: %s %s (size=%d) output_float=%s",
            camera_id,
            input_details["shape"].tolist(),
            self._input_dtype.__name__,
            self._input_size,
            self._output_is_float,
        )

    # ------------------------------------------------------------------
    def estimate(self, frame: cv2.typing.MatLike) -> dict[str, object]:
        frame_height, frame_width = frame.shape[:2]
        empty = self._empty_result(frame_width, frame_height)

        if not self._enabled or self._interpreter is None:
            return empty

        started_at = time.perf_counter()

        input_tensor = self._preprocess(frame)
        self._interpreter.set_tensor(self._input_index, input_tensor)
        self._interpreter.invoke()
        raw_output = self._interpreter.get_tensor(self._output_index)
        inference_ms = (time.perf_counter() - started_at) * 1000

        keypoints_arr = self._dequantize_output(raw_output)  # [17, 3] float32
        keypoints = _raw_to_keypoints(keypoints_arr)

        person_detected = any(kp["score"] >= _PERSON_SCORE_THRESHOLD for kp in keypoints)

        if self._draw_landmarks and person_detected:
            _draw_skeleton(frame, keypoints_arr, frame_width, frame_height)

        return {
            "camera_id": self._camera_id,
            "person_detected": person_detected,
            "keypoints": keypoints,
            "inference_ms": inference_ms,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "backend": _BACKEND,
        }

    def close(self) -> None:
        self._interpreter = None

    # ------------------------------------------------------------------
    def _preprocess(self, frame: cv2.typing.MatLike) -> np.ndarray:
        resized = cv2.resize(
            frame, (self._input_size, self._input_size), interpolation=cv2.INTER_AREA
        )
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        arr = rgb.astype(np.float32)  # [H, W, 3] float32  0–255

        if np.issubdtype(self._input_dtype, np.floating):
            arr /= 255.0
            tensor = np.expand_dims(arr.astype(self._input_dtype), axis=0)
        elif self._input_scale != 0.0:
            quantized = arr / self._input_scale + self._input_zero_point
            info = np.iinfo(self._input_dtype)
            tensor = np.expand_dims(
                np.clip(np.round(quantized), info.min, info.max).astype(self._input_dtype),
                axis=0,
            )
        else:
            tensor = np.expand_dims(rgb.astype(self._input_dtype), axis=0)

        return tensor

    def _dequantize_output(self, raw: np.ndarray) -> np.ndarray:
        """Return a float32 [17, 3] array of [y, x, score]."""
        squeezed = raw.squeeze()  # [17, 3]
        if squeezed.shape != (17, 3):
            squeezed = squeezed.reshape(17, 3)
        if self._output_is_float:
            return squeezed.astype(np.float32)
        if self._output_scale != 0.0:
            return (squeezed.astype(np.float32) - self._output_zero_point) * self._output_scale
        return squeezed.astype(np.float32)

    def _empty_result(self, frame_width: int, frame_height: int) -> dict[str, object]:
        return {
            "camera_id": self._camera_id,
            "person_detected": False,
            "keypoints": [],
            "inference_ms": None,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "backend": _BACKEND,
        }


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _raw_to_keypoints(arr: np.ndarray) -> list[dict[str, object]]:
    """Convert [17, 3] float32 [y, x, score] → list of keypoint dicts.

    ``visibility`` is set to the same value as ``score`` so that the server-side
    ``_is_visible()`` check (which reads ``visibility``) continues to work without
    modification.
    """
    result: list[dict[str, object]] = []
    for i, name in enumerate(KEYPOINT_NAMES):
        y, x, score = float(arr[i, 0]), float(arr[i, 1]), float(arr[i, 2])
        result.append({"name": name, "x": x, "y": y, "score": score, "visibility": score})
    return result


def _draw_skeleton(
    frame: cv2.typing.MatLike,
    arr: np.ndarray,
    frame_width: int,
    frame_height: int,
) -> None:
    pts = [
        (int(arr[i, 1] * frame_width), int(arr[i, 0] * frame_height)) for i in range(17)
    ]
    scores = [float(arr[i, 2]) for i in range(17)]

    for a, b in _SKELETON_CONNECTIONS:
        if scores[a] >= _DRAW_SCORE_THRESHOLD and scores[b] >= _DRAW_SCORE_THRESHOLD:
            cv2.line(frame, pts[a], pts[b], (0, 255, 170), 2, cv2.LINE_AA)

    for i in range(17):
        if scores[i] >= _DRAW_SCORE_THRESHOLD:
            cv2.circle(frame, pts[i], 4, (255, 255, 255), -1, cv2.LINE_AA)


def _load_interpreter(model_path: str, num_threads: int) -> Any | None:
    if not os.path.isfile(model_path):
        logger.error("MoveNet model not found: %s", model_path)
        return None

    try:
        from tflite_runtime.interpreter import Interpreter
        return Interpreter(model_path=model_path, num_threads=num_threads)
    except ImportError:
        pass

    try:
        from tensorflow.lite.python.interpreter import Interpreter  # type: ignore[no-redef]
        return Interpreter(model_path=model_path, num_threads=num_threads)
    except ImportError:
        logger.error(
            "Neither tflite-runtime nor tensorflow is installed. "
            "Run: pip install tflite-runtime"
        )
        return None
